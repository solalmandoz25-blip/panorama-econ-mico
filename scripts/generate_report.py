import os
import re
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from jinja2 import Template
from deep_translator import GoogleTranslator

TODAY = datetime.today()
FRED_KEY = os.environ.get("FRED_API_KEY", "")

DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES_ABR_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

def translate_es(text):
    if not text:
        return text
    try:
        return GoogleTranslator(source="auto", target="es").translate(text)
    except Exception as e:
        print(f"Error traducción: {e}")
        return text

def _clean_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    text = " ".join(text.split())
    return text

def _fetch_feed_items(url, limit=8):
    items_out = []
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:limit]
        for item in items:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            desc_raw = item.findtext("description", "") or item.findtext("summary", "")
            description = _clean_html(desc_raw)
            if len(description) > 180:
                description = description[:177].rsplit(" ", 1)[0] + "..."
            items_out.append({"title": title, "link": link, "description": description})
    except Exception as e:
        print(f"Error feed {url}: {e}")
    return items_out

def get_rss_news():
    feeds = [
        ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
        ("Bloomberg Economics", "https://feeds.bloomberg.com/economics/news.rss"),
        ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
    ]
    all_news = []

    keywords_high = [
        "fed", "rate cut", "rate hike", "interest rate", "monetary policy", "central bank",
        "inflation", "bcrp", "bce", "ecb", "powell", "lagarde", "treasury yield",
