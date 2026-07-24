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

    macro["europa"] = {
        "tasa": fred_monthly("ECBDFR", 3),
        "inflacion": fred_monthly("CPHPTT01EZM659N", 3),
        "pbi": fred_monthly("NAEXKP01EZQ659S", 3),
    }
    print(f"Macro OK — EUROPA tasa:{len(macro['europa']['tasa'])} infl:{len(macro['europa']['inflacion'])} pbi:{len(macro['europa']['pbi'])}")

    return macro

def _fmt(val):
    try:
        return f"{float(val):.2f}"
    except (TypeError, ValueError):
        return str(val)

def _trend(vals):
    nums = [float(v) for v in vals if v is not None]
    if len(nums) < 2:
        return "estable"
    diff = nums[-1] - nums[0]
    if abs(diff) < 0.05:
        return "estable"
    return "al alza" if diff > 0 else "a la baja"

REGION_KEYWORDS = {
    "peru": [r"\bperu\b", r"\bperú\b", r"\bbcrp\b", r"\blima\b", "sol peruano", "sunat", "andean", "latam", "latin america"],
    "usa": [r"\bfed\b", "powell", "treasury", "washington", r"\bus\b", r"\bu\.s\.", "dollar", "united states", r"\bamerica", "yield", "rate cut", "rate hike", "recession", "jobs report", "unemployment"],
    "europa": [r"\becb\b", r"\bbce\b", "euro", "europe", "european", "eurozone", "germany", "france", r"\beu\b", "lagarde"],
}

def find_relevant_news(region_key, news_list):
    patterns = REGION_KEYWORDS.get(region_key, [])
    for n in news_list:
        title_lower = n["title"].lower()
        if any(re.search(p, title_lower) for p in patterns):
            return n
    return None

def get_peru_fallback_news():
    feed_url = "https://gestion.pe/arc/outboundfeeds/rss/category/economia/?outputType=xml"
    items = _fetch_feed_items(feed_url, limit=5)
    if items:
        return items[0]
    return None

def generate_conclusiones(macro, news_list):
    labels = [("peru", "🇵🇪 Perú"), ("usa", "🇺🇸 EE.UU."), ("europa", "🇪🇺 Europa")]
    lineas = []
    for key, label in labels:
        data = macro.get(key, {})
        tasa = [o["value"] for o in data.get("tasa", [])]
        infl = [o["value"] for o in data.get("inflacion", [])]
        pbi = [o["value"] for o in data.get("pbi", [])]
        partes = []
        if tasa:
            partes.append(f"tasa de referencia en {_fmt(tasa[-1])}% ({_trend(tasa)})")
        if infl:
            partes.append(f"inflación interanual en {_fmt(infl[-1])}% ({_trend(infl)})")
        if pbi:
            partes.append(f"crecimiento del PBI en {_fmt(pbi[-1])}% ({_trend(pbi)})")
        resumen = ", ".join(partes) + "." if partes else "sin datos disponibles esta semana."

        # Solo asigna noticia si hay coincidencia GENUINA con la región.
        # Perú tiene fuente propia como respaldo (Gestión). EE.UU./Europa: solo si calza,
        # nunca se le da a una región la noticia "sobrante" de otra.
        noticia = find_relevant_news(key, news_list)
        if not noticia and key == "peru":
            noticia = get_peru_fallback_news()

        lineas.append({
            "label": label,
            "resumen": f"{label}: {resumen}",
            "noticia_titulo": noticia["title"] if noticia else None,
            "noticia_desc": noticia["description"] if noticia else None,
            "noticia_link": noticia["link"] if noticia else None,
        })
    return lineas

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

news = get_rss_news()
calendar = get_calendar()
macro = get_macro_data()
conclusiones = generate_conclusiones(macro, news)
week_str = f"{TODAY.day} de {MESES_ES[TODAY.month - 1]}, {TODAY.year}"

with open("templates/dashboard.html") as f:
    template = Template(f.read())

html = template.render(week=week_str, news=news, calendar=calendar, macro=macro, conclusiones=conclusiones)

os.makedirs("output", exist_ok=True)
with open("output/index.html", "w") as f:
    f.write(html)

print(f"✅ Dashboard generado — {len(news)} noticias, calendario OK")
