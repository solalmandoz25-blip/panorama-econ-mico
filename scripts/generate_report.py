import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from jinja2 import Template

TODAY = datetime.today()

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
                all_news.append({
                    "source": source,
                    "title": title,
                    "link": link,
                    "relevance": relevance
                })
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
        for event in data:
            currency = event.get("currency", "")
            impact = event.get("impact", "")
            title = event.get("title", "")
            if currency in countries and impact == "High":
                country_label = countries[currency]
                if len(result[country_label]) < 4:
                    result[country_label].append(title)
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


news = get_rss_news()
calendar = get_calendar()
week_str = TODAY.strftime("%d de %B, %Y")

with open("templates/dashboard.html") as f:
    template = Template(f.read())

html = template.render(
    week=week_str,
    news=news,
    calendar=calendar
)

os.makedirs("output", exist_ok=True)
with open("output/index.html", "w") as f:
    f.write(html)

print(f"✅ Dashboard generado — {len(news)} noticias, calendario OK")
