import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from jinja2 import Template

TODAY = datetime.today()
FRED_KEY = os.environ.get("FRED_API_KEY", "")

def get_rss_news():
    feeds = [
        ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
        ("Bloomberg Economics", "https://feeds.bloomberg.com/economics/news.rss"),
        ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
    ]
    all_news = []
    keywords_high = ["fed", "rate", "inflation", "gdp", "bcrp", "bce", "ecb", "treasury", "monetary", "recession", "tasa", "inflación", "central bank", "powell", "interest rate", "yield", "bond", "dollar", "currency"]
    keywords_med = ["market", "economy", "trade", "oil", "stock", "earnings", "growth", "mercado", "economía", "petróleo"]
    for source, url in feeds:
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            items = root.findall(".//item")[:8]
            for item in items:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                title_lower = title.lower()
                if any(k in title_lower for k in keywords_high):
                    relevance = "Alta relevancia"
                elif any(k in title_lower for k in keywords_med):
                    relevance = "Media relevancia"
                else:
                    continue
                all_news.append({"source": source, "title": title, "link": link, "relevance": relevance})
        except Exception as e:
            print(f"Error {source}: {e}")
    high = [n for n in all_news if n["relevance"] == "Alta relevancia"][:4]
    med = [n for n in all_news if n["relevance"] == "Media relevancia"][:3]
    result = high + med
    seen_titles = set()
    deduped = []
    for n in result:
        if n["title"] not in seen_titles:
            seen_titles.add(n["title"])
            deduped.append(n)
    return deduped[:6]

def get_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    countries = {"USD": "🇺🇸 EE.UU.", "EUR": "🇪🇺 Europa"}
    result = {"🇺🇸 EE.UU.": [], "🇪🇺 Europa": []}
    try:
        r = requests.get(url, timeout=8)
        data = r.json()
        impact_stars = {"High": "★★★", "Medium": "★★", "Low": "★"}
        for level in ["High", "Medium", "Low"]:
            for event in data:
                currency = event.get("country", "")
                impact = event.get("impact", "")
                title = event.get("title", "")
                if currency in countries and impact == level:
                    country_label = countries[currency]
                    if len(result[country_label]) < 4:
                        result[country_label].append(f"{title} {impact_stars[level]}")
            if all(len(result[c]) >= 1 for c in countries.values()):
                break
    except Exception as e:
        print(f"Error calendar: {e}")
    try:
        url_bcrp = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04722MM/json"
        r2 = requests.get(url_bcrp, timeout=8)
        data2 = r2.json()
        periods = data2.get("periods", [])
        if periods:
            last = periods[-1]
            tasa_val = last["values"][0]
            tasa_date = last["name"]
            result["🇵🇪 Perú"] = [f"Tasa de referencia BCRP: {tasa_val}% ({tasa_date})"]
        else:
            result["🇵🇪 Perú"] = []
    except Exception as e:
        print(f"Error BCRP: {e}")
        result["🇵🇪 Perú"] = []
    return result

def fred_get(series_id, limit=13):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        obs = r.json().get("observations", [])
        obs = [o for o in obs if o["value"] != "."]
        return obs[::-1]
    except Exception as e:
        print(f"Error FRED {series_id}: {e}")
        return []

def bcrp_get(series_id, limit=3):
    url = f"https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{series_id}/json"
    try:
        r = requests.get(url, timeout=8)
        periods = r.json().get("periods", [])
        return periods[-limit:] if periods else []
    except Exception as e:
        print(f"Error BCRP {series_id}: {e}")
        return []

def get_macro_data():
    macro = {}

    # PERÚ
    tasa_pe = bcrp_get("PD04722MM", 3)
    infl_pe = bcrp_get("PN01273PM", 3)
    pbi_pe = bcrp_get("PN01728AM", 3)
    macro["peru"] = {
        "tasa": [{"date": p["name"], "value": p["values"][0]} for p in tasa_pe],
        "inflacion": [{"date": p["name"], "value": p["values"][0]} for p in infl_pe],
        "pbi": [{"date": p["name"], "value": p["values"][0]} for p in pbi_pe],
    }

    # EE.UU. (FRED)
    fedfunds = fred_get("FEDFUNDS", 3)
    cpi_raw = fred_get("CPIAUCSL", 16)
    gdp = fred_get("A191RL1Q225SBEA", 3)

    # CPI interanual = (CPI_actual / CPI_hace_12_meses - 1) * 100
    infl_us = []
    if len(cpi_raw) >= 13:
        for i in range(12, len(cpi_raw)):
            val = round((float(cpi_raw[i]["value"]) / float(cpi_raw[i-12]["value"]) - 1) * 100, 2)
            infl_us.append({"date": cpi_raw[i]["date"][:7], "value": str(val)})
    infl_us = infl_us[-3:]

    macro["usa"] = {
        "tasa": [{"date": o["date"][:7], "value": o["value"]} for o in fedfunds],
        "inflacion": infl_us,
        "pbi": [{"date": o["date"][:7], "value": o["value"]} for o in gdp],
    }

    print(f"Macro OK — PE tasa:{len(macro['peru']['tasa'])} infl:{len(macro['peru']['inflacion'])} pbi:{len(macro['peru']['pbi'])}")
    print(f"Macro OK — US tasa:{len(macro['usa']['tasa'])} infl:{len(macro['usa']['inflacion'])} pbi:{len(macro['usa']['pbi'])}")
    return macro

news = get_rss_news()
calendar = get_calendar()
macro = get_macro_data()
week_str = TODAY.strftime("%d de %B, %Y")

with open("templates/dashboard.html") as f:
    template = Template(f.read())

html = template.render(week=week_str, news=news, calendar=calendar, macro=macro)

os.makedirs("output", exist_ok=True)
with open("output/index.html", "w") as f:
    f.write(html)

print(f"✅ Dashboard generado — {len(news)} noticias, calendario OK")
