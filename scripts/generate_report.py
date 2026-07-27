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
        "gdp", "economy", "economic", "trade", "growth", "economía", "crecimiento", "pbi",
        "jobs report", "unemployment", "employment", "consumer prices", "cpi", "ppi",
        "budget", "deficit", "debt ceiling", "stimulus", "exports", "imports",
        "supply chain", "manufacturing", "housing market", "oil prices", "energy prices",
        "currency", "exchange rate", "bond market", "sovereign debt", "credit rating",
    ]
    exclude_keywords = [
        "stock", "stocks", "shares", "equity", "equities", "earnings", "nasdaq",
        "s&p", "dow jones", "ipo", "buyback", "dividend", "wall street", "markets wrap",
    ]

    for source, url in feeds:
        for item in _fetch_feed_items(url, limit=15):
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
    countries = {"USD": "🇺🇸 Estados Unidos", "EUR": "🇪🇺 Europa"}
    result = {"🇺🇸 Estados Unidos": [], "🇪🇺 Europa": []}
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

    peru_events = []
    series_pe = [
        ("PD04722MM", "Tasa de referencia BCRP", "★★★"),
        ("PN01273PM", "Inflación interanual (IPC)", "★★★"),
        ("PN01728AM", "Crecimiento del PBI", "★★"),
    ]
    for series_id, nombre, estrellas in series_pe:
        try:
            r2 = requests.get(f"https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{series_id}/json", timeout=8)
            periods = r2.json().get("periods", [])
            if periods:
                last = periods[-1]
                val = round(float(last["values"][0]), 2)
                fecha = last["name"]
                peru_events.append(f"{fecha} — {nombre}: {val}% {estrellas}")
        except Exception as e:
            print(f"Error BCRP {series_id}: {e}")

    def next_weekday(base_date, weekday, n=1):
        d = base_date.replace(day=1)
        count = 0
        while True:
            if d.weekday() == weekday:
                count += 1
                if count == n:
                    return d
            d += timedelta(days=1)

    hoy = TODAY
    mes_actual = hoy.replace(day=1)
    mes_siguiente = (mes_actual + timedelta(days=32)).replace(day=1)

    decision_tasa = next_weekday(mes_actual, 3, 1)
    if decision_tasa < hoy:
        decision_tasa = next_weekday(mes_siguiente, 3, 1)

    ipc_release = mes_siguiente + timedelta(days=2)
    pbi_release = mes_siguiente.replace(day=15)

    proximos = [
        (decision_tasa, "Decisión de tasa de referencia BCRP", "★★★"),
        (ipc_release, "Publicación IPC (inflación) INEI", "★★★"),
        (pbi_release, "Publicación PBI mensual INEI", "★★"),
    ]
    proximos_futuros = sorted([p for p in proximos if p[0] >= hoy])
    if proximos_futuros:
        fecha_dt, nombre, estrellas = proximos_futuros[0]
        dia = DIAS_ES[fecha_dt.weekday()]
        mes = MESES_ABR_ES[fecha_dt.month - 1]
        peru_events.append(f"Próximo — {dia} {fecha_dt.day} {mes} — {nombre} {estrellas}")

    result["🇵🇪 Perú"] = peru_events
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

def fred_monthly(series_id, months=3, raw_limit=100):
    obs = fred_get(series_id, raw_limit)
    monthly = {}
    for o in obs:
        monthly[o["date"][:7]] = o["value"]
    keys = sorted(monthly.keys())[-months:]
    return [{"date": k, "value": monthly[k]} for k in keys]

def bcrp_get(series_id, limit=3):
    url = f"https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{series_id}/json"
    for intento in range(3):
        try:
            r = requests.get(url, timeout=8)
            periods = r.json().get("periods", [])
            if periods:
                return periods[-limit:]
        except Exception as e:
            print(f"Error BCRP {series_id} (intento {intento+1}): {e}")
        time.sleep(2)
    return []

def get_macro_data():
    macro = {}

    tasa_pe = bcrp_get("PD04722MM", 3)
    infl_pe = bcrp_get("PN01273PM", 3)
    pbi_pe = bcrp_get("PN01728AM", 3)
    macro["peru"] = {
        "tasa": [{"date": p["name"], "value": p["values"][0]} for p in tasa_pe],
        "inflacion": [{"date": p["name"], "value": p["values"][0]} for p in infl_pe],
        "pbi": [{"date": p["name"], "value": p["values"][0]} for p in pbi_pe],
    }

    fedfunds = fred_get("FEDFUNDS", 3)
    cpi_raw = fred_get("CPIAUCSL", 16)
    gdp = fred_get("A191RL1Q225SBEA", 3)

    infl_us = []
    if len(cpi_raw) >= 13:
        for i in
