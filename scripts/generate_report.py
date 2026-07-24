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
        "recession", "tasa de interés", "inflación", "política monetaria",
        "war", "conflict", "sanctions", "geopolit", "military", "invasion",
        "drone", "ukraine", "russia", "middle east", "ceasefire", "tariff", "trade war",
    ]
    keywords_med = [
        "gdp", "economy", "trade", "growth", "economía", "crecimiento", "pbi",
    ]
    exclude_keywords = [
        "stock", "stocks", "shares", "equity", "equities", "earnings", "nasdaq",
        "s&p", "dow jones", "ipo", "buyback", "dividend", "wall street", "markets wrap",
    ]

    for source, url in feeds:
        for item in _fetch_feed_items(url, limit=8):
            title_lower = item["title"].lower()
            if any(k in title_lower for k in exclude_keywords):
                continue
            if any(k in title_lower for k in keywords_high):
                relevance = "Alta relevancia"
            elif any(k in title_lower for k in keywords_med):
                relevance = "Media relevancia"
            else:
                continue
            all_news.append({"source": source, "title": item["title"], "link": item["link"], "relevance": relevance, "description": item["description"]})

    high = [n for n in all_news if n["relevance"] == "Alta relevancia"][:4]
    med = [n for n in all_news if n["relevance"] == "Media relevancia"][:3]
    result = high + med
    seen_titles = set()
    deduped = []
    for n in result:
        if n["title"] not in seen_titles:
            seen_titles.add(n["title"])
            deduped.append(n)
    deduped = deduped[:6]

    for n in deduped:
        n["title_en"] = n["title"]
        original_title = n["title"]
        n["title"] = translate_es(n["title"])
        n["description"] = translate_es(n["description"])
        print(f"Traducido: {original_title[:40]}... -> {n['title'][:40]}...")

    return deduped

def _fmt_event_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str)
        dia = DIAS_ES[dt.weekday()]
        mes = MESES_ABR_ES[dt.month - 1]
        return f"{dia} {dt.day} {mes}, {dt.strftime('%H:%M')}"
    except Exception:
        return ""

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
                date_str = event.get("date", "")
                if currency in countries and impact == level:
                    country_label = countries[currency]
                    if len(result[country_label]) < 4:
                        title_es = translate_es(title)
                        fecha = _fmt_event_date(date_str)
                        prefijo = f"{fecha} — " if fecha else ""
                        result[country_label].append(f"{prefijo}{title_es} {impact_stars[level]}")
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
