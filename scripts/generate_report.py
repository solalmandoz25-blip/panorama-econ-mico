import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from jinja2 import Template

TODAY = datetime.today()

def get_rss_news():
    feeds = [
        ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
        ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
        ("Financial Times", "https://www.ft.com/rss/home"),
        ("El País", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada"),
    ]
    all_news = []
    keywords_high = ["fed", "bank", "rate", "inflation", "gdp", "bcrp", "bce", "ecb", "treasury", "monetary", "recession", "tasa", "inflación", "reserva federal", "banco central", "peru", "perú"]
    keywords_med = ["market", "economy", "trade", "oil", "dollar", "euro", "mercado", "economía", "petróleo", "dólar"]

    for source, url in feeds:
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            items = root.findall(".//item")[:5]
            for item in items:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub = item.findtext("pubDate", "")[:16] if item.findtext("pubDate") else ""
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
                    "pub": pub,
                    "relevance": relevance
                })
        except Exception as e:
            print(f"Error {source}: {e}")

    high = [n for n in all_news if n["relevance"] == "Alta relevancia"][:4]
    med = [n for n in all_news if n["relevance"] == "Media relevancia"][:2]
    return high + med

def get_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    countries = {"USD": "🇺🇸 EE.UU.", "EUR": "🇪🇺 Europa", "PEN": "🇵🇪 Perú"}
    result = {"🇺🇸 EE.UU.": [], "🇪🇺 Europa": [], "🇵🇪 Perú": []}
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
