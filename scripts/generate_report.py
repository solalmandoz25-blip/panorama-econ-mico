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
        result = GoogleTranslator(source="auto", target="es").translate(text)
        if not result:
            return text
        bad_markers = ["server error", "that's an error", "please try again later", "error 500", "error 502", "error 503"]
        result_lower = result.lower()
        if any(marker in result_lower for marker in bad_markers):
            print(f"Traduccion sospechosa descartada, usando original: {text[:60]}")
            return text
        return result
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

TICKER_PATTERN = re.compile(r"\([A-Z]{1,5}(\.[A-Z]{1,3})?\)")

def get_rss_news():
    feeds = [
        ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
        ("Bloomberg Economics", "https://feeds.bloomberg.com/economics/news.rss"),
        ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
    ]
    all_news = []

    # Solo 3 temas: politica monetaria/tasas, inflacion, y guerra/geopolitica relevante.
    keywords_high = [
        "fed", "rate cut", "rate hike", "interest rate", "policy rate", "monetary policy",
        "central bank", "bcrp", "bce", "ecb", "powell", "lagarde",
        "quantitative easing", "quantitative tightening", "fomc",
        "tasa de interés", "tasa de referencia", "política monetaria",
        "inflation", "inflación", "consumer prices", "cpi",
        "war", "conflict", "sanctions", "invasion", "military strike", "drone strike",
        "ceasefire", "ukraine", "russia", "middle east", "geopolit",
    ]
    keywords_med = [
        "treasury yield", "bond yield", "rate decision", "ecb decision", "bcrp decision",
        "tariff", "trade war", "ppi", "producer prices",
    ]
    exclude_keywords = [
        "stock", "stocks", "shares", "equity", "equities", "earnings", "nasdaq",
        "s&p", "dow jones", "ipo", "buyback", "dividend", "wall street", "markets wrap",
        "profit", "quarterly", "revenue", "guidance", "unit", "ceo", "cfo",
        "acquisition", "merger", "lowers its", "raises its", "lifts outlook",
    ]

    for source, url in feeds:
        for item in _fetch_feed_items(url, limit=40):
            title = item["title"]
            title_lower = title.lower()
            if any(k in title_lower for k in exclude_keywords):
                continue
            if TICKER_PATTERN.search(title):
                continue
            if any(k in title_lower for k in keywords_high):
                relevance = "Alta relevancia"
            elif any(k in title_lower for k in keywords_med):
                relevance = "Media relevancia"
            else:
                continue
            all_news.append({"source": source, "title": item["title"], "link": item["link"], "relevance": relevance, "description": item["description"]})

    high = [n for n in all_news if n["relevance"] == "Alta relevancia"][:5]
    result = high
    seen_titles = set()
    deduped = []
    for n in result:
        if n["title"] not in seen_titles:
            seen_titles.add(n["title"])
            deduped.append(n)
    deduped = deduped[:5]

    def _region_priority(title_en):
        t = title_en.lower()
        if any(re.search(p, t) for p in REGION_KEYWORDS["usa"]):
            return 0
        if any(re.search(p, t) for p in REGION_KEYWORDS["peru"]):
            return 1
        if any(re.search(p, t) for p in REGION_KEYWORDS["europa"]):
            return 2
        return 3

    deduped.sort(key=lambda n: _region_priority(n["title"]))

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
    urls = [
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
    ]
    countries = {"USD": "🇺🇸 Estados Unidos", "EUR": "🇪🇺 Europa"}
    result = {"🇺🇸 Estados Unidos": [], "🇪🇺 Europa": []}
    all_events = []
    for url in urls:
        try:
            r = requests.get(url, timeout=8)
            all_events.extend(r.json())
        except Exception as e:
            print(f"Error calendar {url}: {e}")

    def _parse_dt(event):
        try:
            return datetime.fromisoformat(event.get("date", ""))
        except Exception:
            return datetime.max

    CALENDAR_KEYWORDS = [
        "inflation", "cpi", "consumer price", "pce", "core pce",
        "unemployment", "jobless", "payroll", "employment change", "jobs report", "non-farm", "nonfarm",
        "gdp",
        "rate decision", "interest rate", "policy rate", "fed funds", "refinancing rate", "deposit rate",
        "monetary policy",
    ]

    def _es_relevante(title):
        t = title.lower()
        return any(k in t for k in CALENDAR_KEYWORDS)

    impact_stars = {"High": "★★★", "Medium": "★★", "Low": "★"}
    for currency, country_label in countries.items():
        matched = [e for e in all_events if e.get("country", "") == currency and _es_relevante(e.get("title", "")) and e.get("impact", "") in ("High", "Medium")]
        if not matched:
            matched = [e for e in all_events if e.get("country", "") == currency and _es_relevante(e.get("title", "")) and e.get("impact", "") == "Low"]
        matched.sort(key=_parse_dt)
        eventos = []
        for e in matched[:5]:
            title_es = translate_es(e.get("title", ""))
            fecha = _fmt_event_date(e.get("date", ""))
            prefijo = f"{fecha} — " if fecha else ""
            impact = e.get("impact", "")
            eventos.append(f"{prefijo}{title_es} {impact_stars.get(impact, '')}")
        result[country_label] = eventos

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
                val = float(last["values"][0])
                fecha = last["name"]
                peru_events.append(f"{fecha} — {nombre}: {val:.2f}% {estrellas}")
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
    for fecha_dt, nombre, estrellas in proximos_futuros:
        dia = DIAS_ES[fecha_dt.weekday()]
        mes = MESES_ABR_ES[fecha_dt.month - 1]
        peru_events.append(f"Próximo — {dia} {fecha_dt.day} {mes} {fecha_dt.year} — {nombre} {estrellas}")

    result["🇵🇪 Perú"] = peru_events[:5]
    ordenado = {
        "🇺🇸 Estados Unidos": result["🇺🇸 Estados Unidos"],
        "🇵🇪 Perú": result["🇵🇪 Perú"],
        "🇪🇺 Europa": result["🇪🇺 Europa"],
    }
    return ordenado

def fred_get(series_id, limit=13):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit
    }
    for intento in range(3):
        try:
            r = requests.get(url, params=params, timeout=20)
            obs = r.json().get("observations", [])
            obs = [o for o in obs if o["value"] != "."]
            return obs[::-1]
        except Exception as e:
            print(f"Error FRED {series_id} (intento {intento+1}): {e}")
        time.sleep(2)
    return []

def fred_latest(series_id, limit=4):
    """Devuelve el valor mas reciente de una serie de FRED."""
    obs = fred_get(series_id, limit)
    if not obs:
        return None
    try:
        return float(obs[-1]["value"])
    except (ValueError, TypeError, KeyError, IndexError):
        return None

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

def imf_weo_series(indicator, country_code):
    """Consulta la API pública del FMI (World Economic Outlook / DataMapper)
    que trae series historicas y proyecciones oficiales por pais.
    Reintenta porque el servidor del FMI a veces responde lento."""
    url = f"https://www.imf.org/external/datamapper/api/v1/{indicator}/{country_code}"
    for intento in range(3):
        try:
            r = requests.get(url, timeout=25)
            data = r.json()
            return data.get("values", {}).get(indicator, {}).get(country_code, {})
        except Exception as e:
            print(f"Error IMF WEO {indicator} {country_code} (intento {intento+1}): {e}")
        time.sleep(2)
    return {}

def get_imf_trend(indicator, country_code):
    """Arma anterior/actual/proyectada usando datos REALES del FMI (WEO):
    año anterior, año actual y año siguiente publicados oficialmente."""
    series = imf_weo_series(indicator, country_code)
    if not series:
        return None
    anterior_year = str(TODAY.year - 1)
    actual_year = str(TODAY.year)
    proyectada_year = str(TODAY.year + 1)
    anterior = series.get(anterior_year)
    actual = series.get(actual_year)
    proyectada = series.get(proyectada_year)
    if anterior is None or actual is None or proyectada is None:
        print(f"IMF WEO {indicator} {country_code}: faltan años {anterior_year}/{actual_year}/{proyectada_year} en {list(series.keys())[-6:]}")
        return None
    return {"anterior": round(float(anterior), 2), "actual": round(float(actual), 2), "proyectada": round(float(proyectada), 2)}

def compute_trend(data_list):
    """Toma la serie de datos reales y arma anterior/actual/proyectada.
    'Proyectada' es una extrapolación lineal simple: continúa la misma
    pendiente entre 'anterior' y 'actual' un paso más hacia adelante."""
    if not data_list or len(data_list) < 2:
        return None
    try:
        anterior = float(data_list[-2]["value"])
        actual = float(data_list[-1]["value"])
    except (ValueError, TypeError, IndexError):
        return None
    proyectada = round(actual + (actual - anterior), 2)
    return {"anterior": round(anterior, 2), "actual": round(actual, 2), "proyectada": proyectada}

def build_macro_trend(macro):
    """Tasa: no existe una proyeccion oficial gratuita y consistente para
    los 3 (solo la Fed publica dot-plot), asi que se mantiene la
    extrapolacion de tendencia sobre datos reales historicos para Peru
    y Europa. Para EE.UU. se usa la proyeccion REAL de la Fed (FEDTARMD,
    mediana del dot-plot del FOMC).
    Inflacion y PBI: se reemplaza por proyecciones OFICIALES del FMI
    (World Economic Outlook), que ya publican año anterior/actual/siguiente."""
    trend = {
        "tasa": {
            "peru": compute_trend(macro.get("peru", {}).get("tasa", [])),
            "usa": compute_trend(macro.get("usa", {}).get("tasa", [])),
            "europa": compute_trend(macro.get("europa", {}).get("tasa", [])),
        },
        "inflacion": {},
        "pbi": {},
    }

    fed_dot_plot = fred_latest("FEDTARMD")
    if trend["tasa"]["usa"] and fed_dot_plot is not None:
        trend["tasa"]["usa"]["proyectada"] = round(fed_dot_plot, 2)
        print(f"Tasa OK — USA proyectada real (Fed dot-plot): {fed_dot_plot}")
    else:
        print(f"Tasa USA: no se pudo obtener dot-plot real de la Fed, se mantiene extrapolacion (fed_dot_plot={fed_dot_plot})")

    imf_countries = {"peru": "PER", "usa": "USA", "europa": "EURO"}
    for region_key, imf_code in imf_countries.items():
        trend["inflacion"][region_key] = get_imf_trend("PCPIPCH", imf_code)
        trend["pbi"][region_key] = get_imf_trend("NGDP_RPCH"
