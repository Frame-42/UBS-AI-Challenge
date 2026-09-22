# Vendor risk intelligence

A responsive, dependency-free frontend prototype for a global bank. Built with HTML, CSS, and JavaScript on the `website` branch.

## Run locally

```sh
python3 serve.py
```

Open **http://localhost:8000**. No installation or build step is required. You can also open `index.html` directly.

## Explore

- Search, filter, sort, and paginate vendors directly in the dashboard.
- Click a vendor to open its assessment, cyber, reputation, and fraud subscores, trends, signals, and concrete fictional source records.
- Export the filtered dashboard as a CSV snapshot using the header button.
- Adjust the custom red-and-white sliders to weight cyber, reputation, and fraud scores.
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

Each vendor has three source records (cyber, reputation, fraud), with a report title, fictional publisher, publication date, document ID, and expandable excerpt. Source buttons on the subscores open the corresponding record. These records are invented fixtures, not external links or retrieved evidence. The displayed weighted score is the rounded weighted mean of the three subscores. Each slider sets a relative weight (0–100); weights are normalized by their sum, and at least one must remain nonzero. Default weights are equal. Weight changes update ranking, risk badges and filters, summary metrics, vendor assessments, and exports. Click any score heading to sort by that dimension; click a subscore to open its source directly. CSV exports include the three subscores and normalized weights. These controls are a prototype calculation, not a validated risk model.

On small screens, the vendor table scrolls horizontally to keep all three subscore columns available. The simulated historical weighted trend applies each fixture’s daily change to all three subscores, then recomputes using the current weights; it is not historical market data. Weights apply throughout the dashboard and reset to equal weights on page reload. The interface is a single dashboard without separate portfolio or watchlist views.
