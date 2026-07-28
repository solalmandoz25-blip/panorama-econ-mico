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
    keys = ["tasa", "inflacion", "pbi"]
    trend = {}
    for k in keys:
        trend[k] = {
            "peru": compute_trend(macro.get("peru", {}).get(k, [])),
            "usa": compute_trend(macro.get("usa", {}).get(k, [])),
            "europa": compute_trend(macro.get("europa", {}).get(k, [])),
        }
    return trend

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

FALLBACK_KEYWORDS_EN = [
    r"\brate\b", "inflation", "monetary", "central bank", "recession", "war", "conflict", "tariff",
]

def find_relevant_news(region_key, news_list):
    patterns = REGION_KEYWORDS.get(region_key, [])
    for n in news_list:
        title_lower = n.get("title_en", n["title"]).lower()
        if any(re.search(p, title_lower) for p in patterns):
            return n
    return None

def get_peru_fallback_news():
    feed_url = "https://gestion.pe/arc/outboundfeeds/rss/category/economia/?outputType=xml"
    items = _fetch_feed_items(feed_url, limit=5)
    if items:
        return items[0]
    return None

def get_europa_fallback_news():
    feed_url = "https://feeds.feedburner.com/euronews/en/business/"
    items = _fetch_feed_items(feed_url, limit=8)
    patterns = REGION_KEYWORDS["europa"] + FALLBACK_KEYWORDS_EN
    for item in items:
        title_lower = item["title"].lower()
        if any(re.search(p, title_lower) for p in patterns):
            item["title"] = translate_es(item["title"])
            item["description"] = translate_es(item["description"])
            return item
    return None

def get_usa_fallback_news():
    feed_url = "https://feeds.reuters.com/reuters/businessNews"
    items = _fetch_feed_items(feed_url, limit=8)
    patterns = REGION_KEYWORDS["usa"] + FALLBACK_KEYWORDS_EN
    for item in items:
        title_lower = item["title"].lower()
        if any(re.search(p, title_lower) for p in patterns):
            item["title"] = translate_es(item["title"])
            item["description"] = translate_es(item["description"])
            return item
    if items:
        item = items[0]
        item["title"] = translate_es(item["title"])
        item["description"] = translate_es(item["description"])
        return item
    return None

def generate_conclusiones(macro, news_list):
    labels = [("peru", "🇵🇪 Perú"), ("usa", "🇺🇸 Estados Unidos"), ("europa", "🇪🇺 Europa")]
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

        noticia = find_relevant_news(key, news_list)
        if not noticia and key == "peru":
            noticia = get_peru_fallback_news()
        if not noticia and key == "europa":
            noticia = get_europa_fallback_news()
        if not noticia and key == "usa":
            noticia = get_usa_fallback_news()

        lineas.append({
            "label": label,
            "resumen": f"{label}: {resumen}",
            "noticia_titulo": noticia["title"] if noticia else None,
            "noticia_desc": noticia["description"] if noticia else None,
            "noticia_link": noticia["link"] if noticia else None,
        })
    return lineas

def get_impacto_empresarial(macro_trend):
    """Traduce las tendencias macro en implicancias practicas para
    decisiones de negocio: costo de financiamiento, precios, crecimiento."""
    interpretaciones = {
        "tasa": {
            "al alza": "financiamiento más costoso; se recomienda evaluar la fijación de tasas en el corto plazo",
            "a la baja": "costo de fondeo a la baja; representa una oportunidad para nuevas líneas de crédito",
            "estable": "costo de financiamiento estable, sin cambios significativos previstos",
        },
        "inflacion": {
            "al alza": "presión al alza sobre costos operativos y márgenes; se sugiere revisar la estrategia de precios",
            "a la baja": "entorno de precios más predecible, favorable para la planificación a mediano plazo",
            "estable": "inflación bajo control, sin impacto significativo previsto en el corto plazo",
        },
        "pbi": {
            "al alza": "el crecimiento económico favorece la expansión y una mayor demanda",
            "a la baja": "la desaceleración sugiere cautela en las proyecciones de crecimiento",
            "estable": "actividad económica estable, sin señales de cambio abrupto",
        },
    }
    labels = [("peru", "🇵🇪 Perú"), ("usa", "🇺🇸 Estados Unidos"), ("europa", "🇪🇺 Europa")]
    resultado = []
    for key, label in labels:
        partes = []
        for metric in ["tasa", "inflacion", "pbi"]:
            d = macro_trend.get(metric, {}).get(key)
            if not d:
                continue
            direccion = _trend([d["anterior"], d["actual"]])
            partes.append(interpretaciones[metric][direccion])
        if partes:
            resumen = "; ".join(partes) + "."
            resumen = resumen[0].upper() + resumen[1:]
        else:
            resumen = "sin datos suficientes para un análisis esta semana."
        resultado.append({"label": label, "resumen": f"{label}: {resumen}"})
    return resultado

def _decap(texto):
    """Pone en minúscula solo la primera letra, preservando siglas
    como PBI que ya vienen en mayúscula dentro de la frase."""
    if not texto:
        return texto
    return texto[0].lower() + texto[1:]

def get_frase_final(macro_trend, dato_semana):
    """Genera una frase de cierre de maximo dos lineas que resume el tono
    general de la semana, combinando la tendencia dominante con el dato
    mas destacado."""
    conteo = {"al alza": 0, "a la baja": 0, "estable": 0}
    for metric, regiones in macro_trend.items():
        for region_key, d in regiones.items():
            if not d:
                continue
            direccion = _trend([d["anterior"], d["actual"]])
            conteo[direccion] += 1
    dominante = max(conteo, key=conteo.get)
    tono = {
        "al alza": "una semana marcada por presiones al alza en varios frentes",
        "a la baja": "una semana con señales de alivio en varios frentes",
        "estable": "una semana de relativa estabilidad en los principales indicadores",
    }[dominante]
    if dato_semana:
        return f"En general, {tono}; lo más destacado fue el movimiento en {_decap(dato_semana['metric_label'])} de {dato_semana['region_label']}."
    return f"En general, {tono} esta semana."

def get_dato_semana(macro_trend):
    """Selecciona el dato macro con el cambio mas significativo de la
    semana (mayor variacion absoluta entre 'anterior' y 'actual')."""
    labels = {"peru": "🇵🇪 Perú", "usa": "🇺🇸 Estados Unidos", "europa": "🇪🇺 Europa"}
    metric_labels = {"tasa": "Tasa de referencia", "inflacion": "Inflación interanual", "pbi": "Crecimiento del PBI"}
    candidatos = []
    for metric, regiones in macro_trend.items():
        for region_key, d in regiones.items():
            if not d:
                continue
            cambio = round(d["actual"] - d["anterior"], 2)
            candidatos.append({
                "region_label": labels.get(region_key, region_key),
                "metric_label": metric_labels.get(metric, metric),
                "valor": d["actual"],
                "anterior": d["anterior"],
                "cambio": cambio,
            })
    if not candidatos:
        return None
    destacado = max(candidatos, key=lambda c: abs(c["cambio"]))
    valor_fmt = f"{destacado['valor']:.2f}"
    anterior_fmt = f"{destacado['anterior']:.2f}"
    destacado["valor"] = valor_fmt
    if destacado["cambio"] == 0:
        destacado["texto"] = f"{destacado['metric_label']} de {destacado['region_label']} se mantuvo estable en {valor_fmt}%."
    else:
        direccion = "subió" if destacado["cambio"] > 0 else "bajó"
        signo = "+" if destacado["cambio"] > 0 else ""
        destacado["texto"] = f"{destacado['metric_label']} de {destacado['region_label']} {direccion} de {anterior_fmt}% a {valor_fmt}% ({signo}{destacado['cambio']:.2f} p.p.)."
    return destacado

def get_top3_para_clientes(news_list):
    """Selecciona los 3 puntos mas importantes de la semana para compartir
    con clientes: prioriza noticias de alta relevancia; si no hay 3,
    completa con las siguientes disponibles."""
    altas = [n for n in news_list if n["relevance"] == "Alta relevancia"]
    top3 = altas[:3]
    if len(top3) < 3:
        restantes = [n for n in news_list if n not in top3]
        top3 += restantes[: 3 - len(top3)]
    return top3

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

news = get_rss_news()
calendar = get_calendar()
macro = get_macro_data()
macro_trend = build_macro_trend(macro)
conclusiones = generate_conclusiones(macro, news)
dato_semana = get_dato_semana(macro_trend)
frase_final = get_frase_final(macro_trend, dato_semana)
week_str = f"{TODAY.day} de {MESES_ES[TODAY.month - 1]}, {TODAY.year}"

with open("templates/dashboard.html") as f:
    template = Template(f.read())

html = template.render(week=week_str, news=news, calendar=calendar, macro=macro, macro_trend=macro_trend, conclusiones=conclusiones, dato_semana=dato_semana, frase_final=frase_final)

os.makedirs("output", exist_ok=True)
with open("output/index.html", "w") as f:
    f.write(html)

print(f"✅ Dashboard generado — {len(news)} noticias, calendario OK")
