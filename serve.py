"""Serve the dashboard and the collected risk framework snapshot locally."""
import argparse
import json
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from risk_framework import WebsiteDataset, load_collection, load_config, load_json
from risk_framework.validation import ValidationError

ROOT = Path(__file__).resolve().parent


class DashboardData:
    def __init__(self, root=ROOT):
        self.root = root
        self.lock = threading.Lock()
        self.fingerprint = None
        self.dataset = None

    def score(self, weights=None):
        with self.lock:
            config = self.root / 'examples/collection_config.json'
            defaults = self.root / 'examples/collection_weights.json'
            paths = sorted((self.root / 'companies').rglob('*.json')) + [config, defaults]
            fingerprint = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
            if fingerprint != self.fingerprint:
                dataset = WebsiteDataset(load_collection(self.root / 'companies'), load_config(config))
                default_weights = load_json(defaults)
                # Validate both inputs before replacing the retained snapshot.
                dataset.score(default_weights)
                self.dataset, self.defaults = dataset, default_weights
                self.fingerprint = fingerprint
            result = self.dataset.score(self.defaults if weights is None else weights)
            result['dashboard'] = {'default_weights': self.defaults}
            return result


class DashboardHandler(SimpleHTTPRequestHandler):
    data = DashboardData()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/api/dashboard':
            try:
                params = parse_qs(url.query)
                weights = json.loads(params['weights'][0]) if 'weights' in params else None
                if weights is not None and not isinstance(weights, dict):
                    raise ValueError('Weights must be an object')
                result = self.data.score(weights)
            except (ValueError, TypeError, ValidationError) as exc:
                self.send_json(400, {'error': str(exc)})
            except (OSError, RuntimeError):
                self.send_json(503, {'error': 'Collection snapshot unavailable. Check the saved reports.'})
            else:
                self.send_json(200, result)
            return
        if url.path not in ('/', '/index.html', '/styles.css', '/app.js'):
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        if urlsplit(self.path).path not in ('/', '/index.html', '/styles.css', '/app.js'):
            self.send_error(404)
            return
        super().do_HEAD()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), DashboardHandler)
    print(f'Dashboard is running at http://localhost:{args.port} · Ctrl+C to stop', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')
    finally:
        server.server_close()
