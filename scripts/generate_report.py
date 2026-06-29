import os
import requests
import json
from datetime import datetime, timedelta
from jinja2 import Template

API_KEY = os.environ["FMP_API_KEY"]
PAIRS = ["USDPEN", "EURUSD", "EURPEN"]
TODAY = datetime.today()
WEEK_AGO = TODAY - timedelta(days=7)

def get_historical(pair):
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/forex/{pair}"
    params = {
        "from": WEEK_AGO.strftime("%Y-%m-%d"),
        "to": TODAY.strftime("%Y-%m-%d"),
        "apikey": API_KEY
    }
    r = requests.get(url, params=params)
    data = r.json()
    return data.get("historical", [])[::-1]

def get_forex_news():
    url = "https://financialmodelingprep.com/api/v4/forex_news"
    params = {"page": 0, "apikey": API_KEY}
    r = requests.get(url, params=params)
    data = r.json()
    return data[:6] if isinstance(data, list) else []

def build_sparkline(prices):
    if not prices:
        return ""
    vals = [p["close"] for p in prices]
    min_v, max_v = min(vals), max(vals)
    rng = max_v - min_v or 1
    w, h = 200, 60
    points = []
    for i, v in enumerate(vals):
        x = int(i / (len(vals) - 1) * w) if len(vals) > 1 else w // 2
        y = int(h - ((v - min_v) / rng) * h)
        points.append(f"{x},{y}")
    color = "#22c55e" if vals[-1] >= vals[0] else "#ef4444"
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}"><polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/></svg>'

report_data = {}
for pair in PAIRS:
    hist = get_historical(pair)
    report_data[pair] = {
        "history": hist,
        "sparkline": build_sparkline(hist),
        "latest": hist[-1]["close"] if hist else "N/A",
        "change": round(hist[-1]["close"] - hist[0]["close"], 4) if len(hist) > 1 else 0,
        "pct": round((hist[-1]["close"] - hist[0]["close"]) / hist[0]["close"] * 100, 2) if len(hist) > 1 else 0
    }

news = get_forex_news()
week_str = TODAY.strftime("%d de %B, %Y")

with open("templates/dashboard.html") as f:
    template = Template(f.read())

html = template.render(
    week=week_str,
    pairs=report_data,
    news=news
)

os.makedirs("output", exist_ok=True)
with open("output/index.html", "w") as f:
    f.write(html)

print("Dashboard generado correctamente")
