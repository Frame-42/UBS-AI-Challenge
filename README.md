# Vendor risk intelligence

A responsive, dependency-free frontend prototype for a global bank. Built with HTML, CSS, and JavaScript on the `website` branch.

## Run locally

```sh
python3 serve.py
```

Open **http://localhost:8000**. No installation or build step is required. You can also open `index.html` directly.

## Explore

- Search, filter, sort, and paginate the vendor portfolio.
- Click a vendor to open its assessment, cyber, reputation, and fraud subscores, trends, signals, and concrete fictional source records.
- Add vendors to your watchlist, which is saved in your browser.
- Explore the activity feed and export a CSV snapshot from Reports or the header.
- Pause/resume simulated updates using the Live control.
- Use `/` to search and Escape to dismiss the detail panel.

All assessments, scores, sources, publishers, incidents, locations, and news are **fictional demo data**, including entries associated with real vendor names. Scores measure risk on a 0–100 scale (higher means greater risk): low below 30, moderate 30–59, high 60+. Updates are simulated every 12 seconds; no external data or risk model is connected.

## Implementation

- `index.html`: application shell and accessible dialogs.
- `styles.css`: responsive red-and-white design system.
- `app.js`: demo data, application state, views, and simulation.
- `sources.js`: three fictional reports per vendor, with subscores and specific findings.
- `serve.py`: development-only local HTTP server (binds to localhost).

To integrate a risk algorithm later, replace the `vendors` fixture and the update timer in `app.js` with an API response/subscription. Keep the score scale and timestamps explicit. The server is for local previews only; this is not a production banking application.

Each vendor has three source records (cyber, reputation, fraud), with a report title, fictional publisher, publication date, document ID, and expandable excerpt. Source buttons on the subscores open the corresponding record. These records are invented fixtures, not external links or retrieved evidence. Overall risk and subscores are independent demo values; no aggregation formula is connected. CSV exports include all three subscores.
