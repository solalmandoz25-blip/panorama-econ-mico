import os
import requests
from datetime import datetime
from jinja2 import Template

TODAY = datetime.today()

def get_rates():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        r = requests.get(url, timeout=10)
        data = r.json()
        rates = data.get("rates", {})
        usd_pen = round(rates.get("PEN", 0), 4)
        eur_usd = round(1 / rates.get("EUR", 1), 4)
        eur_pen = round(rates.get("PEN", 0) / rates.get("EUR", 1), 4)
        return usd_pen, eur_usd, eur_pen
    except:
        return None, None, None

def get_prev_rates():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        r = requests.get(url, timeout=10)
        data = r.json()
        rates = data.get("rates", {})
        usd_pen = round(rates.get("PEN", 0), 4)
        eur_usd = round(1 / rates.get("EUR", 1), 4)
        eur_pen = round(rates.get("PEN", 0) / rates.get("EUR", 1), 4)
        return usd_pen, eur_usd, eur_pen
    except:
        return None, None, None

def get_forex_news():
    try:
        url = "https://financialmodelingprep.com/api/v3/stock_news"
        params = {"limit": 8, "apikey": os.environ.get("FMP_API_KEY", "")}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

usd_pen, eur_usd, eur_pen = get_rates()

pairs_data = {
    "USDPEN": {
        "label": "USD/PEN",
        "latest": usd_pen or "N/A",
        "change": 0,
        "pct": 0
    },
    "EURUSD": {
        "label": "EUR/USD",
        "latest": eur_usd or "N/A",
        "change": 0,
        "pct": 0
    },
    "EURPEN": {
        "label": "EUR/PEN",
        "latest": eur_pen or "N/A",
        "change": 0,
        "pct": 0
    }
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
print(f"USD/PEN: {usd_pen} | EUR/USD: {eur_usd} | EUR/PEN: {eur_pen}")
