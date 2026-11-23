# AI compute tape - a one-file market dashboard (open source)

A clean, single-file HTML dashboard: six tickers vs a reference close, price count-up,
intraday sparklines, a ranked change bar chart and a day-high callout. Research-note style
(white, one blue accent, Inter + IBM Plex Mono). No framework, no build step.

Files
- `index.html` - standalone dashboard with the Nov 23, 2026 snapshot embedded (open it in a browser).
- `template.html` - the same page with a `/*DATA*/null` placeholder.
- `dashboard_clip.py` - fetches real 5-min bars from Yahoo Finance's public chart endpoint,
  fills the template, renders it frame by frame with Playwright, and encodes an H.264 MP4 + PNG still.
- `compute_tape.json` - the ticker config (labels only; all numbers are fetched).

Run
```
pip install playwright && playwright install chromium
python dashboard_clip.py --config compute_tape.json --out out/
```
(the script looks for the template in `dashboard_clip/template.html` next to it; adjust `HERE` or move the file.)

Data: Yahoo Finance chart API, 5-min bars. Snapshot in index.html: Mon Nov 23, 2026, as of 1:09 PM PT,
changes vs the Fri Nov 20 close. Not investment advice. MIT license. Made by @Contrasignal_ai.
