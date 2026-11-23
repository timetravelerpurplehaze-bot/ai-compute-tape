#!/usr/bin/env python3
"""Dashboard clip builder for @Contrasignal_ai (Research-note style).

Builds a standalone HTML dashboard from REAL market data (Yahoo Finance chart API),
renders it frame-by-frame with Playwright (deterministic window.renderAt(t)),
and encodes an X/Buffer-compatible H.264 MP4 plus a PNG still.

Usage:
  .venv/bin/python tools/dashboard_clip.py --config tools/dashboard_clip/configs/compute_tape.json \
      --out media/2026-11-23/dash [--seconds 10] [--fps 30] [--code "github link"]

Config JSON: {title, kicker, headline, dek, big_label, bars_title, source,
  tickers: [{symbol, label, name, lead?}]}. Prices/%/highs/sparklines are always fetched live;
  nothing numeric comes from the config. Template: tools/dashboard_clip/template.html
  (reads a DATA object; any new dashboard = new template or config).
"""
import argparse, json, os, subprocess, time, datetime, urllib.request, urllib.parse, shutil
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
PT = ZoneInfo("America/Los_Angeles")

def fetch(symbol, raw_dir):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=5m&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    body = urllib.request.urlopen(req, timeout=20).read()
    open(os.path.join(raw_dir, symbol.replace("^", "_") + ".json"), "wb").write(body)
    r = json.loads(body)["chart"]["result"][0]
    m = r["meta"]; q = r["indicators"]["quote"][0]
    series = [[ts, c] for ts, c in zip(r["timestamp"], q["close"]) if c is not None]
    hs = [(h, ts) for ts, h in zip(r["timestamp"], q["high"]) if h is not None]
    high_time = max(hs)[1] if hs else None  # start of the 5-min bar holding the session high
    price = m["regularMarketPrice"]; prev = m["chartPreviousClose"]
    reg = m["currentTradingPeriod"]["regular"]
    return dict(price=price, prev=prev, high=m["regularMarketDayHigh"], chg=(price / prev - 1) * 100,
                time=m["regularMarketTime"], high_time=high_time, currency=m.get("currency", "USD"), series=series,
                session=[reg["start"], reg["end"]])

def build(cfg, out, code):
    raw = os.path.join(out, "raw"); os.makedirs(raw, exist_ok=True)
    tickers, session, latest = [], None, 0
    for t in cfg["tickers"]:
        d = fetch(t["symbol"], raw)
        session = session or d.pop("session"); d.pop("session", None)
        latest = max(latest, d["time"])
        tickers.append({**t, **d})
    asof_dt = datetime.datetime.fromtimestamp(latest, PT)
    data = {k: cfg[k] for k in ("title", "kicker", "headline", "dek", "big_label", "bars_title", "source")}
    data.update(tickers=tickers, session=session, code=code or "",
                asof="As of " + asof_dt.strftime("%-I:%M %p PT, %a %b %-d, %Y"))
    data["asof_iso"] = asof_dt.isoformat()
    tpl = open(os.path.join(HERE, "dashboard_clip", cfg.get("template", "template.html"))).read()
    html = tpl.replace("/*DATA*/null", json.dumps(data))
    path = os.path.join(out, "index.html"); open(path, "w").write(html)
    json.dump(data, open(os.path.join(out, "data.json"), "w"), indent=1)
    return path, data

def record(html_path, out, seconds, fps, w=1920, h=1080):
    from playwright.sync_api import sync_playwright
    frames = os.path.join(out, "frames"); shutil.rmtree(frames, ignore_errors=True); os.makedirs(frames)
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:  # bundled build missing: fall back to system Chrome
            b = p.chromium.launch(executable_path=shutil.which("google-chrome") or "/usr/bin/google-chrome")
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.add_init_script("window.__CAPTURE__=true")
        pg.goto("file://" + os.path.abspath(html_path)); pg.wait_for_load_state("networkidle")
        pg.evaluate("document.fonts.ready")
        n = int(seconds * fps)
        for i in range(n):
            pg.evaluate(f"renderAt({i / fps})")
            pg.screenshot(path=os.path.join(frames, f"f{i:04d}.png"))
        pg.evaluate(f"renderAt({seconds})")
        still = os.path.join(out, "still.png"); pg.screenshot(path=still)
        b.close()
    mp4 = os.path.join(out, "clip.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(frames, "f%04d.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high",
                    "-movflags", "+faststart", "-r", str(fps), mp4], check=True)
    return mp4, still

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=10); ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--code", default=""); ap.add_argument("--no-record", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    html, data = build(cfg, a.out, a.code)
    for t in data["tickers"]:
        print(f'{t["symbol"]:6} {t["price"]:>10.2f} prev {t["prev"]:>10.2f} {t["chg"]:+6.2f}% high {t["high"]:.2f} @ {datetime.datetime.fromtimestamp(t["time"], PT):%H:%M:%S} PT')
    print(data["asof"])
    if not a.no_record:
        mp4, still = record(html, a.out, a.seconds, a.fps)
        print(mp4, os.path.getsize(mp4), still)
