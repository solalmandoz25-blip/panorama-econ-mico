import os
import requests
from datetime import datetime, timedelta
from jinja2 import Template

API_KEY = os.environ["FMP_API_KEY"]
TODAY = datetime.today()
WEEK_AGO = TODAY - timedelta(days=7)

PAIRS = {
    "USD/PEN": "USDPEN",
    "EUR/USD": "EURUSD",
    "EUR/PEN": "EURPEN"
}

def get_historical(symbol):
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/forex/{symbol}"
    params = {
        "from": WEEK_AGO.strftime("%Y-%m-%d"),
        "to": TODAY.strftime("%Y-%m-%d"),
        "apikey": API_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        hist = data.get("historical", [])
        return hist[::-1]
    except:
        return []

def get_forex_news():
    url = "https://financialmodelingprep.com/api/v4/forex_news"
    params = {"page": 0, "apikey": API_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data[:8] if isinstance(data, list) else []
    except:
        return []

def build_sparkline(prices):
    if len(prices) < 2:
        return "<p style='color:#999;font-size:0.8rem'>Sin datos suficientes</p>"
    vals = [p["close"] for p in prices]
    min_v, max_v = min(vals), max(vals)
    rng = max_v - min_v or 0.0001
    w, h = 260, 70
    points = []
    for i, v in enumerate(vals):
        x = int(i / (len(vals) - 1) * w)
        y = int(h - ((v - min_v) / rng) * (h - 10) - 5)
        points.append(f"{x},{y}")
    color = "#22c55e" if vals[-1] >= vals[0] else "#ef4444"
    pts = " ".join(points)
    return f'''<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="display:block">
  <polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>
  <circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" r="4" fill="{color}"/>
</svg>'''

def get_eur_pen(eurusd_hist, usdpen_hist):
    result = []
    for i in range(min(len(eurusd_hist), len(usdpen_hist))):
        close = round(eurusd_hist[i]["close"] * usdpen_hist[i]["close"], 4)
        result.append({"close": close, "date": eurusd_hist[i].get("date", "")})
    return result

# Obtener datos
eurusd = get_historical("EURUSD")
usdpen = get_historical("USDPEN")
eurpen = get_eur_pen(eurusd, usdpen)

def build_pair_data(hist, label):
    if not hist:
        return {"label": label, "latest": "N/A", "open": "N/A", "change": 0, "pct": 0, "sparkline": "", "dates": [], "closes": []}
    latest = hist[-1]["close"]
    open_val = hist[0]["close"]
    change = round(latest - open_val, 4)
    pct = round((latest - open_val) / open_val * 100, 2) if open_val else 0
    return {
        "label": label,
        "latest": latest,
        "open": open_val,
        "change": change,
        "pct": pct,
        "sparkline": build_sparkline(hist),
        "dates": [p.get("date", "") for p in hist],
        "closes": [p["close"] for p in hist]
    }

pairs_data = {
    "EURUSD": build_pair_data(eurusd, "EUR/USD"),
    "USDPEN": build_pair_data(usdpen, "USD/PEN"),
    "EURPEN": build_pair_data(eurpen, "EUR/PEN")
}

news = get_forex_news()
week_str = TODAY.strftime("%d de %B, %Y")

with open("templates/dashboard.html") as f:
    template = Template(f.read())

html = template.render(
    week=week_str,
    pairs=pairs_data,
    news=news
)

os.makedirs("output", exist_ok=True)
with open("output/index.html", "w") as f:
    f.write(html)

print("✅ Dashboard generado correctamente")
