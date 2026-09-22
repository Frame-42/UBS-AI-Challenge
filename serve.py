"""Local dashboard assets and read-only scoring API; no external data collection."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from risk_framework import WebsiteDataset, load_collection, load_config, load_json
from risk_framework.validation import ValidationError, parse_json

ROOT = Path(__file__).resolve().parent
POLICY_DEFAULTS = ROOT / "risk_framework/defaults.json"
ASSET_PATHS = frozenset(("/", "/index.html", "/styles.css", "/app.js"))


class SnapshotError(RuntimeError):
    """Saved reports or scoring policy could not produce a valid snapshot."""


class DashboardData:
    """Cache a validated collector snapshot; weights never trigger collection.

    Replace the cache only after new inputs validate. A failed reload raises an
    error, allowing the browser to keep its last successful view visibly stale.
    """

    def __init__(self, root: Path = ROOT) -> None:
        self.root = Path(root)
        self.lock = threading.Lock()
        self.fingerprint: tuple | None = None
        self.dataset: WebsiteDataset | None = None
        self.defaults: dict[str, float] = {}

    def score(self, weights: Mapping[str, float] | None = None) -> dict[str, Any]:
        with self.lock:
            try:
                config = self.root / "examples/collection_config.json"
                defaults = self.root / "examples/collection_weights.json"
                paths = sorted((self.root / "companies").rglob("*.json"))
                paths += [config, defaults, POLICY_DEFAULTS]
                fingerprint = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
                if fingerprint != self.fingerprint:
                    dataset = WebsiteDataset(load_collection(self.root / "companies"), load_config(config))
                    default_weights = load_json(defaults)
                    dataset.score(default_weights)
                    self.dataset, self.defaults = dataset, default_weights
                    self.fingerprint = fingerprint
            except (OSError, ValueError, TypeError) as exc:
                raise SnapshotError(f"Cannot load collection snapshot: {exc}") from exc

            assert self.dataset is not None
            result = self.dataset.score(self.defaults if weights is None else weights)
            result["dashboard"] = {"default_weights": deepcopy(self.defaults)}
            return result


def query_weights(query: str) -> dict[str, float] | None:
    """Reject malformed, repeated, or unknown parameters instead of guessing."""
    params = parse_qs(query, keep_blank_values=True, strict_parsing=True)
    if set(params) - {"weights"}:
        raise ValidationError("The only supported query parameter is weights")
    if "weights" not in params:
        return None
    if len(params["weights"]) != 1:
        raise ValidationError("Supply weights once")
    weights = parse_json(params["weights"][0])
    if not isinstance(weights, dict):
        raise ValidationError("Weights must be a JSON object")
    return weights


class DashboardHandler(SimpleHTTPRequestHandler):
    data = DashboardData()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/api/dashboard":
            try:
                result = self.data.score(query_weights(url.query))
            except SnapshotError as exc:
                self.log_error("%s", exc)
                self.send_json(503, {"error": "Collection snapshot unavailable. Check the saved reports and scoring configuration."})
            except (ValueError, TypeError) as exc:
                self.send_json(400, {"error": str(exc)})
            else:
                self.send_json(200, result)
            return
        if url.path not in ASSET_PATHS:
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if urlsplit(self.path).path not in ASSET_PATHS:
            self.send_error(404)
            return
        super().do_HEAD()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000, help="Local port (default: 8000)")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Dashboard is running at http://127.0.0.1:{server.server_port} · Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
