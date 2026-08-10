import os
import re
import time
import requests
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta
from jinja2 import Template
from deep_translator import GoogleTranslator


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

TODAY = datetime.today()
FRED_KEY = os.environ.get("FRED_API_KEY", "")

DIAS_ES = [
    "Lun", "Mar", "Mié", "Jue",
    "Vie", "Sáb", "Dom"
]

MESES_ABR_ES = [
    "ene", "feb", "mar", "abr",
    "may", "jun", "jul", "ago",
    "sep", "oct", "nov", "dic"
]

MESES_ES = [
    "enero", "febrero", "marzo", "abril",
    "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre",
    "diciembre"
]


# ============================================================
# TRADUCCIÓN
# ============================================================

def translate_es(text):

    if not text:
        return text

    try:

        result = GoogleTranslator(
            source="auto",
            target="es"
        ).translate(text)

        if not result:
            return text

        bad_markers = [
            "server error",
            "that's an error",
            "please try again later",
            "error 500",
            "error 502",
            "error 503",
        ]

        result_lower = result.lower()

        if any(
            marker in result_lower
            for marker in bad_markers
        ):

            print(
                "Traducción sospechosa descartada, "
                f"usando original: {text[:60]}"
            )

            return text

        return result

    except Exception as e:

        print(
            f"Error traducción: {e}"
        )

        return text


# ============================================================
# RSS HELPERS
# ============================================================

def _clean_html(text):

    text = re.sub(
        r"<[^>]+>",
        "",
        text or ""
    )

    text = (
        text
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )

    text = " ".join(
        text.split()
    )

    return text


def _fetch_feed_items(
    url,
    limit=8
):

    items_out = []

    try:

        r = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        r.raise_for_status()

        root = ET.fromstring(
            r.content
        )

        items = root.findall(
            ".//item"
        )[:limit]

        for item in items:

            title = (
                item.findtext(
                    "title",
                    ""
                )
                .strip()
            )

            link = (
                item.findtext(
                    "link",
                    ""
                )
                .strip()
            )

            desc_raw = (
                item.findtext(
                    "description",
                    ""
                )
                or
                item.findtext(
                    "summary",
                    ""
                )
            )

            description = (
                _clean_html(
                    desc_raw
                )
            )

            if len(description) > 180:

                description = (
                    description[:177]
                    .rsplit(" ", 1)[0]
                    + "..."
                )

            items_out.append({
                "title": title,
                "link": link,
                "description": description,
            })

    except Exception as e:

        print(
            f"Error feed {url}: {e}"
        )

    return items_out


# ============================================================
# PALABRAS CLAVE REGIONALES
# ============================================================

REGION_KEYWORDS = {

    "peru": [
        r"\bperu\b",
        r"\bperú\b",
        r"\bbcrp\b",
        r"\blima\b",
        "sol peruano",
        "sunat",
        "andean",
        "latam",
        "latin america",
    ],

    "usa": [
        r"\bfed\b",
        "powell",
        "treasury",
        "washington",
        r"\bus\b",
        r"\bu\.s\.",
        "dollar",
        "united states",
        r"\bamerica",
        "yield",
        "rate cut",
        "rate hike",
        "recession",
        "jobs report",
        "unemployment",
        "nonfarm",
        "non-farm",
        "payroll",
        "payrolls",
    ],

    "europa": [
        r"\becb\b",
        r"\bbce\b",
        "euro",
        "europe",
        "european",
        "eurozone",
        "germany",
        "france",
        r"\beu\b",
        "lagarde",
    ],
}


FALLBACK_KEYWORDS_EN = [
    r"\brate\b",
    "inflation",
    "monetary",
    "central bank",
    "recession",
    "war",
    "conflict",
    "tariff",
]


# ============================================================
# NOTICIAS
# ============================================================

TICKER_PATTERN = re.compile(
    r"\([A-Z]{1,5}(\.[A-Z]{1,3})?\)"
)


def get_rss_news():

    feeds = [

        (
            "Bloomberg",
            "https://feeds.bloomberg.com/markets/news.rss"
        ),

        (
            "Bloomberg Economics",
            "https://feeds.bloomberg.com/economics/news.rss"
        ),

        (
            "CNBC",
            "https://www.cnbc.com/id/100003114/device/rss/rss.html"
        ),

        (
            "MarketWatch",
            "https://feeds.content.dowjones.io/public/rss/mw_topstories"
        ),

        (
            "Investing.com",
            "https://www.investing.com/rss/news_25.rss"
        ),
    ]

    all_news = []

    keywords_high = [

        # TASAS / POLÍTICA MONETARIA
        "fed",
        "rate cut",
        "rate hike",
        "interest rate",
        "policy rate",
        "monetary policy",
        "central bank",
        "bcrp",
        "bce",
        "ecb",
        "powell",
        "lagarde",
        "quantitative easing",
        "quantitative tightening",
        "fomc",

        "tasa de interés",
        "tasa de referencia",
        "política monetaria",

        # INFLACIÓN
        "inflation",
        "inflación",
        "consumer prices",
        "cpi",

        # EMPLEO / NFP
        "nonfarm payroll",
        "non-farm payroll",
        "nonfarm payrolls",
        "non-farm payrolls",
        "payrolls",
        "jobs report",
        "employment report",
        "unemployment",

        # GEOPOLÍTICA
        "war",
        "conflict",
        "sanctions",
        "invasion",
        "military strike",
        "drone strike",
        "ceasefire",
        "ukraine",
        "russia",
        "middle east",
        "geopolit",
    ]

    keywords_med = [
        "treasury yield",
        "bond yield",
        "rate decision",
        "ecb decision",
        "bcrp decision",
        "tariff",
        "trade war",
        "ppi",
        "producer prices",
    ]

    exclude_keywords = [
        "stock",
        "stocks",
        "shares",
        "equity",
        "equities",
        "earnings",
        "nasdaq",
        "s&p",
        "dow jones",
        "ipo",
        "buyback",
        "dividend",
        "wall street",
        "markets wrap",
        "profit",
        "quarterly",
        "revenue",
        "guidance",
        "unit",
        "ceo",
        "cfo",
        "acquisition",
        "merger",
        "lowers its",
        "raises its",
        "lifts outlook",
    ]

    for source, url in feeds:

        for item in _fetch_feed_items(
            url,
            limit=40
        ):

            title = item["title"]
            title_lower = title.lower()

            if any(
                k in title_lower
                for k in exclude_keywords
            ):
                continue

            if TICKER_PATTERN.search(
                title
            ):
                continue

            if any(
                k in title_lower
                for k in keywords_high
            ):

                relevance = (
                    "Alta relevancia"
                )

            elif any(
                k in title_lower
                for k in keywords_med
            ):

                relevance = (
                    "Media relevancia"
                )

            else:
                continue

            all_news.append({
                "source": source,
                "title": item["title"],
                "link": item["link"],
                "relevance": relevance,
                "description": item["description"],
            })

    high = [
        n
        for n in all_news
        if n["relevance"]
        == "Alta relevancia"
    ]

    seen_titles = set()
    deduped = []

    for n in high:

        if n["title"] not in seen_titles:

            seen_titles.add(
                n["title"]
            )

            deduped.append(n)

    def _region_priority(
        title_en
    ):

        t = title_en.lower()

        if any(
            re.search(p, t)
            for p
            in REGION_KEYWORDS["usa"]
        ):
            return 0

        if any(
            re.search(p, t)
            for p
            in REGION_KEYWORDS["peru"]
        ):
            return 1

        if any(
            re.search(p, t)
            for p
            in REGION_KEYWORDS["europa"]
        ):
            return 2

        return 3

    deduped.sort(
        key=lambda n:
        _region_priority(
            n["title"]
        )
    )

    deduped = deduped[:5]

    for n in deduped:

        n["title_en"] = (
            n["title"]
        )

        original_title = (
            n["title"]
        )

        n["title"] = translate_es(
            n["title"]
        )

        n["description"] = (
            translate_es(
                n["description"]
            )
        )

        print(
            f"Traducido: "
            f"{original_title[:40]}... "
            f"-> {n['title'][:40]}..."
        )

    return deduped


# ============================================================
# CALENDARIO ECONÓMICO
# ============================================================

CALENDAR_URLS = [

    "https://nfs.faireconomy.media/"
    "ff_calendar_thisweek.json",

    "https://nfs.faireconomy.media/"
    "ff_calendar_nextweek.json",
]


def fetch_calendar_events():

    all_events = []

    for url in CALENDAR_URLS:

        try:

            r = requests.get(
                url,
                timeout=8,
                headers={
                    "User-Agent":
                    "Mozilla/5.0"
                }
            )

            r.raise_for_status()

            data = r.json()

            if isinstance(
                data,
                list
            ):

                all_events.extend(
                    data
                )

        except Exception as e:

            print(
                f"Error calendar "
                f"{url}: {e}"
            )

    seen = set()
    deduped = []

    for e in all_events:

        key = (

            e.get(
                "title",
                ""
            )
            .strip()
            .lower(),

            e.get(
                "date",
                ""
            ),

            e.get(
                "country",
                ""
            ),
        )

        if key not in seen:

            seen.add(key)

            deduped.append(e)

    return deduped


def _parse_event_dt(
    event
):

    try:

        dt = datetime.fromisoformat(
            event.get(
                "date",
                ""
            )
        )

        if dt.tzinfo is not None:

            dt = dt.replace(
                tzinfo=None
            )

        return dt

    except Exception:

        return datetime.max


def _fmt_event_date(
    date_str
):

    if not date_str:
        return ""

    try:

        dt = datetime.fromisoformat(
            date_str
        )

        dia = DIAS_ES[
            dt.weekday()
        ]

        mes = MESES_ABR_ES[
            dt.month - 1
        ]

        return (
            f"{dia} "
            f"{dt.day} "
            f"{mes}, "
            f"{dt.strftime('%H:%M')}"
        )

    except Exception:

        return ""


def get_calendar():

    all_events = (
        fetch_calendar_events()
    )

    countries = {

        "USD":
            "🇺🇸 Estados Unidos",

        "EUR":
            "🇪🇺 Europa",
    }

    result = {

        "🇺🇸 Estados Unidos": [],
        "🇪🇺 Europa": [],
    }

    CALENDAR_KEYWORDS = [

        "inflation",
        "cpi",
        "consumer price",
        "pce",
        "core pce",

        "unemployment",
        "jobless",
        "payroll",
        "employment change",
        "jobs report",
        "non-farm",
        "nonfarm",

        "gdp",

        "rate decision",
        "interest rate",
        "policy rate",
        "fed funds",
        "refinancing rate",
        "deposit rate",
        "monetary policy",
    ]

    def _es_relevante(
        title
    ):

        t = title.lower()

        return any(
            k in t
            for k
            in CALENDAR_KEYWORDS
        )

    TEMA_GRUPOS = {

        "inflation":
            "inflacion",

        "cpi":
            "inflacion",

        "consumer price":
            "inflacion",

        "pce":
            "inflacion",

        "core pce":
            "inflacion",

        "unemployment":
            "empleo",

        "jobless":
            "empleo",

        "payroll":
            "empleo",

        "employment change":
            "empleo",

        "jobs report":
            "empleo",

        "non-farm":
            "empleo",

        "nonfarm":
            "empleo",

        "gdp":
            "pbi",

        "rate decision":
            "tasa",

        "interest rate":
            "tasa",

        "policy rate":
            "tasa",

        "fed funds":
            "tasa",

        "refinancing rate":
            "tasa",

        "deposit rate":
            "tasa",

        "monetary policy":
            "tasa",
    }

    def _grupo_tema(
        title
    ):

        t = title.lower()

        for (
            kw,
            grupo
        ) in TEMA_GRUPOS.items():

            if kw in t:

                return grupo

        return None

    impact_stars = {

        "High":
            "★★★",

        "Medium":
            "★★",

        "Low":
            "★",
    }

    for (
        currency,
        country_label
    ) in countries.items():

        matched = [

            e
            for e in all_events

            if (

                e.get(
                    "country",
                    ""
                )
                == currency

                and

                _es_relevante(
                    e.get(
                        "title",
                        ""
                    )
                )

                and

                e.get(
                    "impact",
                    ""
                )
                in (
                    "High",
                    "Medium"
                )

                and

                _parse_event_dt(
                    e
                )
                >= TODAY
            )
        ]

        if not matched:

            matched = [

                e
                for e in all_events

                if (

                    e.get(
                        "country",
                        ""
                    )
                    == currency

                    and

                    _es_relevante(
                        e.get(
                            "title",
                            ""
                        )
                    )

                    and

                    e.get(
                        "impact",
                        ""
                    )
                    == "Low"

                    and

                    _parse_event_dt(
                        e
                    )
                    >= TODAY
                )
            ]

        matched.sort(
            key=_parse_event_dt
        )

        eventos = []

        grupos_por_fecha = set()

        for e in matched:

            if len(eventos) >= 5:

                break

            titulo = e.get(
                "title",
                ""
            )

            fecha_dt = (
                _parse_event_dt(
                    e
                )
            )

            grupo = (
                _grupo_tema(
                    titulo
                )
            )

            clave_grupo = (

                grupo,

                (
                    fecha_dt.date()
                    if fecha_dt
                    != datetime.max
                    else None
                )
            )

            if (
                grupo
                and
                clave_grupo
                in grupos_por_fecha
            ):
                continue

            if grupo:

                grupos_por_fecha.add(
                    clave_grupo
                )

            title_es = translate_es(
                titulo
            )

            fecha = _fmt_event_date(
                e.get(
                    "date",
                    ""
                )
            )

            prefijo = (

                f"{fecha} — "

                if fecha

                else ""
            )

            impact = e.get(
                "impact",
                ""
            )

            eventos.append(

                f"{prefijo}"
                f"{title_es} "
                f"{impact_stars.get(impact, '')}"
            )

        result[
            country_label
        ] = eventos

    # ========================================================
    # PERÚ
    # ========================================================

    peru_events = []

    def next_weekday(
        base_date,
        weekday,
        n=1
    ):

        d = base_date.replace(
            day=1
        )

        count = 0

        while True:

            if d.weekday() == weekday:

                count += 1

                if count == n:

                    return d

            d += timedelta(
                days=1
            )

    hoy = TODAY

    mes_actual = hoy.replace(
        day=1
    )

    mes_siguiente = (

        mes_actual
        + timedelta(
            days=32
        )

    ).replace(
        day=1
    )

    decision_tasa = (
        next_weekday(
            mes_actual,
            3,
            1
        )
    )

    if decision_tasa < hoy:

        decision_tasa = (
            next_weekday(
                mes_siguiente,
                3,
                1
            )
        )

    ipc_release = (

        mes_siguiente
        + timedelta(
            days=2
        )
    )

    if (
        ipc_release.date()
        ==
        decision_tasa.date()
    ):

        ipc_release += timedelta(
            days=2
        )

    pbi_release = (
        mes_siguiente.replace(
            day=15
        )
    )

    proximos = [

        (
            decision_tasa,
            "Decisión de tasa de referencia BCRP",
            "★★★"
        ),

        (
            ipc_release,
            "Publicación IPC (inflación) INEI",
            "★★★"
        ),

        (
            pbi_release,
            "Publicación PBI mensual INEI",
            "★★"
        ),
    ]

    proximos_futuros = sorted(
        [
            p
            for p in proximos
            if p[0] >= hoy
        ]
    )

    for (
        fecha_dt,
        nombre,
        estrellas
    ) in proximos_futuros:

        dia = DIAS_ES[
            fecha_dt.weekday()
        ]

        mes = MESES_ABR_ES[
            fecha_dt.month - 1
        ]

        peru_events.append(

            f"Próximo — "
            f"{dia} "
            f"{fecha_dt.day} "
            f"{mes} "
            f"{fecha_dt.year} — "
            f"{nombre} "
            f"{estrellas}"
        )

    result[
        "🇵🇪 Perú"
    ] = peru_events[:5]

    return {

        "🇺🇸 Estados Unidos":
            result[
                "🇺🇸 Estados Unidos"
            ],

        "🇵🇪 Perú":
            result[
                "🇵🇪 Perú"
            ],

        "🇪🇺 Europa":
            result[
                "🇪🇺 Europa"
            ],
    }


# ============================================================
# FRED
# ============================================================

def fred_get(
    series_id,
    limit=13
):

    url = (
        "https://api.stlouisfed.org/"
        "fred/series/observations"
    )

    params = {

        "series_id":
            series_id,

        "api_key":
            FRED_KEY,

        "file_type":
            "json",

        "sort_order":
            "desc",

        "limit":
            limit,
    }

    for intento in range(3):

        try:

            r = requests.get(
                url,
                params=params,
                timeout=20
            )

            r.raise_for_status()

            data = r.json()

            obs = data.get(
                "observations",
                []
            )

            obs = [

                o
                for o in obs

                if o.get(
                    "value"
                ) != "."
            ]

            return obs[::-1]

        except Exception as e:

            print(

                f"Error FRED "
                f"{series_id} "
                f"(intento "
                f"{intento + 1}): "
                f"{e}"
            )

        time.sleep(2)

    return []


def fred_latest(
    series_id,
    limit=4
):

    obs = fred_get(
        series_id,
        limit
    )

    if not obs:

        return None

    try:

        return float(
            obs[-1][
                "value"
            ]
        )

    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError
    ):

        return None


def fred_monthly(
    series_id,
    months=3,
    raw_limit=100
):

    obs = fred_get(
        series_id,
        raw_limit
    )

    monthly = {}

    for o in obs:

        monthly[
            o["date"][:7]
        ] = o["value"]

    keys = sorted(
        monthly.keys()
    )[-months:]

    return [

        {
            "date": k,
            "value": monthly[k]
        }

        for k in keys
    ]


# ============================================================
# BCRP
# ============================================================

def bcrp_get(
    series_id,
    limit=3
):

    url = (

        "https://estadisticas.bcrp.gob.pe/"
        "estadisticas/series/api/"
        f"{series_id}/json"
    )

    for intento in range(3):

        try:

            r = requests.get(
                url,
                timeout=8
            )

            r.raise_for_status()

            periods = (
                r.json()
                .get(
                    "periods",
                    []
                )
            )

            if periods:

                return periods[
                    -limit:
                ]

        except Exception as e:

            print(

                f"Error BCRP "
                f"{series_id} "
                f"(intento "
                f"{intento + 1}): "
                f"{e}"
            )

        time.sleep(2)

    return []


# ============================================================
# NFP
# ============================================================

def get_nfp_data():
    """
    PAYEMS = Total Nonfarm Payrolls.

    La serie está expresada en miles de personas.

    El cambio mensual del NFP se calcula:

        PAYEMS actual
        -
        PAYEMS anterior
    """

    obs = fred_get(
        "PAYEMS",
        4
    )

    if len(obs) < 2:

        print(
            "NFP: PAYEMS no devolvió "
            "suficientes observaciones."
        )

        return None

    try:

        previous_level = float(
            obs[-2][
                "value"
            ]
        )

        current_level = float(
            obs[-1][
                "value"
            ]
        )

        change = (
            current_level
            -
            previous_level
        )

        result = {

            "date":
                obs[-1][
                    "date"
                ][:7],

            "previous_date":
                obs[-2][
                    "date"
                ][:7],

            "current_level":
                current_level,

            "previous_level":
                previous_level,

            "change":
                round(
                    change,
                    0
                ),
        }

        print(
            "PAYEMS OK — "
            f"Periodo: "
            f"{result['date']} — "
            f"Cambio: "
            f"{result['change']} mil"
        )

        return result

    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError
    ) as e:

        print(
            f"Error calculando NFP: "
            f"{e}"
        )

        return None


# ============================================================
# FECHA DE PUBLICACIÓN DEL EMPLOYMENT SITUATION
# ============================================================

def find_current_month_nfp_release():
    """
    Busca en el calendario oficial del BLS
    una publicación de Employment Situation
    que haya ocurrido durante el mes actual.

    Así no dependemos del feed de Fair Economy,
    que solo conserva esta semana y la próxima.
    """

    url = (
        "https://www.bls.gov/"
        "schedule/news_release/"
        "empsit.htm"
    )

    try:

        r = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent":
                    (
                        "Mozilla/5.0 "
                        "(compatible; "
                        "EconomicDashboard/1.0)"
                    )
            }
        )

        r.raise_for_status()

        html = r.text

    except Exception as e:

        print(
            "Error calendario BLS "
            f"Employment Situation: {e}"
        )

        return None

    # Quitar tags HTML para hacer
    # el parser más resistente.
    clean_text = re.sub(
        r"<[^>]+>",
        " ",
        html
    )

    clean_text = (
        clean_text
        .replace("&nbsp;", " ")
        .replace("&#160;", " ")
    )

    clean_text = re.sub(
        r"\s+",
        " ",
        clean_text
    )

    meses_en = {

        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    # Ejemplo que queremos capturar:
    #
    # Aug. 7, 2026 08:30 AM
    #
    # También acepta:
    # August 7, 2026 08:30 AM

    pattern = re.compile(

        r"(Jan(?:uary)?|"
        r"Feb(?:ruary)?|"
        r"Mar(?:ch)?|"
        r"Apr(?:il)?|"
        r"May|"
        r"Jun(?:e)?|"
        r"Jul(?:y)?|"
        r"Aug(?:ust)?|"
        r"Sep(?:tember)?|"
        r"Oct(?:ober)?|"
        r"Nov(?:ember)?|"
        r"Dec(?:ember)?)"

        r"\.?\s+"

        r"(\d{1,2})"

        r",?\s+"

        r"(\d{4})"

        r".{0,100}?"

        r"08:30\s*AM",

        re.IGNORECASE
    )

    releases = []

    for match in pattern.finditer(
        clean_text
    ):

        month_text = (
            match.group(1)
            .lower()[:3]
        )

        month_num = (
            meses_en.get(
                month_text
            )
        )

        if not month_num:
            continue

        day = int(
            match.group(2)
        )

        year = int(
            match.group(3)
        )

        try:

            release_dt = datetime(
                year,
                month_num,
                day,
                8,
                30
            )

        except ValueError:

            continue

        # Solamente queremos releases:
        #
        # 1. del mes actual
        # 2. del año actual
        # 3. que ya ocurrieron

        if (
            release_dt.year
            == TODAY.year

            and

            release_dt.month
            == TODAY.month

            and

            release_dt
            <= TODAY
        ):

            releases.append(
                release_dt
            )

    if not releases:

        print(
            "BLS: no se encontró "
            "Employment Situation "
            "publicado durante "
            "el mes actual."
        )

        return None

    release_dt = max(
        releases
    )

    print(
        "✅ BLS Employment Situation "
        "encontrado: "
        f"{release_dt.strftime('%Y-%m-%d %H:%M')}"
    )

    return {

        "datetime":
            release_dt,

        "source":
            "BLS",
    }


# ============================================================
# DATO DEL MES NFP
# ============================================================

def get_nfp_dato_mes():

    release = (
        find_current_month_nfp_release()
    )

    if not release:

        print(
            "NFP: todavía no se encontró "
            "un Employment Situation "
            "publicado este mes."
        )

        return None

    nfp = get_nfp_data()

    if not nfp:

        print(
            "NFP: BLS encontró el release, "
            "pero PAYEMS no devolvió "
            "datos suficientes."
        )

        return None

    release_dt = (
        release["datetime"]
    )

    change = int(
        round(
            nfp["change"]
        )
    )

    abs_change = abs(
        change
    )

    # ========================================================
    # HEADLINE
    # ========================================================

    if change > 0:

        headline = (

            "🇺🇸 Estados Unidos suma "
            f"{abs_change:,} mil "
            "empleos no agrícolas"
        )

        descripcion = (

            "Las nóminas no agrícolas "
            f"aumentaron en "
            f"{abs_change:,} mil empleos "
            "respecto al mes anterior."
        )

    elif change < 0:

        headline = (

            "🇺🇸 Estados Unidos pierde "
            f"{abs_change:,} mil "
            "empleos no agrícolas"
        )

        descripcion = (

            "Las nóminas no agrícolas "
            f"disminuyeron en "
            f"{abs_change:,} mil empleos "
            "respecto al mes anterior."
        )

    else:

        headline = (

            "🇺🇸 El empleo no agrícola "
            "se mantiene sin cambios"
        )

        descripcion = (

            "Las nóminas no agrícolas "
            "no registraron variación "
            "respecto al mes anterior."
        )

    fecha = (

        f"{MESES_ABR_ES[
            release_dt.month - 1
        ].capitalize()}. "
        f"{release_dt.year}"
    )

    dato = {

        "metric_key":
            "nfp",

        "metric_label":
            "Nóminas no agrícolas",

        "region_key":
            "usa",

        "region_label":
            "🇺🇸 Estados Unidos",

        "fecha":
            fecha,

        "headline":
            headline,

        "descripcion":
            descripcion,

        "valor":
            f"{change:,}",

        "unidad":
            "mil empleos",

        "release_date":
            release_dt.strftime(
                "%Y-%m-%d"
            ),

        "observation_period":
            nfp["date"],
    }

    print("")
    print(
        "======================================"
    )
    print(
        "⭐ DATO DEL MES SELECCIONADO: NFP"
    )
    print(
        f"Release BLS: "
        f"{dato['release_date']}"
    )
    print(
        f"Periodo PAYEMS: "
        f"{dato['observation_period']}"
    )
    print(
        f"Cambio NFP: "
        f"{dato['valor']} mil"
    )
    print(
        f"Headline: "
        f"{dato['headline']}"
    )
    print(
        "======================================"
    )
    print("")

    return dato


# ============================================================
# DATOS MACRO
# ============================================================

def get_macro_data():

    macro = {}

    # ========================================================
    # PERÚ
    # ========================================================

    tasa_pe = bcrp_get(
        "PD04722MM",
        3
    )

    infl_pe = bcrp_get(
        "PN01273PM",
        3
    )

    pbi_pe = bcrp_get(
        "PN01728AM",
        3
    )

    macro["peru"] = {

        "tasa": [

            {
                "date":
                    p["name"],

                "value":
                    p["values"][0]
            }

            for p in tasa_pe
        ],

        "inflacion": [

            {
                "date":
                    p["name"],

                "value":
                    p["values"][0]
            }

            for p in infl_pe
        ],

        "pbi": [

            {
                "date":
                    p["name"],

                "value":
                    p["values"][0]
            }

            for p in pbi_pe
        ],

        "empleo": [],
    }

    # ========================================================
    # ESTADOS UNIDOS
    # ========================================================

    fedfunds = fred_get(
        "FEDFUNDS",
        3
    )

    cpi_raw = fred_get(
        "CPIAUCSL",
        16
    )

    gdp = fred_get(
        "A191RL1Q225SBEA",
        3
    )

    unrate_us = fred_get(
        "UNRATE",
        3
    )

    infl_us = []

    if len(cpi_raw) >= 13:

        for i in range(
            12,
            len(cpi_raw)
        ):

            val = round(

                (
                    float(
                        cpi_raw[i][
                            "value"
                        ]
                    )

                    /

                    float(
                        cpi_raw[
                            i - 12
                        ][
                            "value"
                        ]
                    )

                    - 1
                )

                * 100,

                2
            )

            infl_us.append({

                "date":
                    cpi_raw[i][
                        "date"
                    ][:7],

                "value":
                    str(val),
            })

    infl_us = infl_us[-3:]

    macro["usa"] = {

        "tasa": [

            {
                "date":
                    o["date"][:7],

                "value":
                    o["value"]
            }

            for o in fedfunds
        ],

        "inflacion":
            infl_us,

        "pbi": [

            {
                "date":
                    o["date"][:7],

                "value":
                    o["value"]
            }

            for o in gdp
        ],

        # Esto sigue siendo unemployment rate.
        # NO es NFP.
        "empleo": [

            {
                "date":
                    o["date"][:7],

                "value":
                    o["value"]
            }

            for o in unrate_us
        ],
    }

    # ========================================================
    # EUROPA
    # ========================================================

    macro["europa"] = {

        "tasa":
            fred_monthly(
                "ECBDFR",
                3
            ),

        "inflacion":
            fred_monthly(
                "CPHPTT01EZM659N",
                3
            ),

        "pbi":
            fred_monthly(
                "NAEXKP01EZQ659S",
                3
            ),

        "empleo":
            fred_monthly(
                "LRHUTTTTEZM156S",
                3
            ),
    }

    print(
        "Macro OK — "
        f"PE tasa:"
        f"{len(macro['peru']['tasa'])} "
        f"infl:"
        f"{len(macro['peru']['inflacion'])} "
        f"pbi:"
        f"{len(macro['peru']['pbi'])}"
    )

    print(
        "Macro OK — "
        f"US tasa:"
        f"{len(macro['usa']['tasa'])} "
        f"infl:"
        f"{len(macro['usa']['inflacion'])} "
        f"pbi:"
        f"{len(macro['usa']['pbi'])} "
        f"desempleo:"
        f"{len(macro['usa']['empleo'])}"
    )

    print(
        "Macro OK — "
        f"EUROPA tasa:"
        f"{len(macro['europa']['tasa'])} "
        f"infl:"
        f"{len(macro['europa']['inflacion'])} "
        f"pbi:"
        f"{len(macro['europa']['pbi'])} "
        f"desempleo:"
        f"{len(macro['europa']['empleo'])}"
    )

    return macro


# ============================================================
# FMI
# ============================================================

def imf_weo_series(
    indicator,
    country_code
):

    url = (

        "https://www.imf.org/"
        "external/datamapper/api/v1/"
        f"{indicator}/"
        f"{country_code}"
    )

    for intento in range(3):

        try:

            r = requests.get(
                url,
                timeout=25
            )

            r.raise_for_status()

            data = r.json()

            return (

                data
                .get(
                    "values",
                    {}
                )
                .get(
                    indicator,
                    {}
                )
                .get(
                    country_code,
                    {}
                )
            )

        except Exception as e:

            print(

                f"Error IMF WEO "
                f"{indicator} "
                f"{country_code} "
                f"(intento "
                f"{intento + 1}): "
                f"{e}"
            )

        time.sleep(2)

    return {}


def get_imf_trend(
    indicator,
    country_code
):

    series = imf_weo_series(
        indicator,
        country_code
    )

    if not series:

        return None

    anterior_year = str(
        TODAY.year - 1
    )

    actual_year = str(
        TODAY.year
    )

    proyectada_year = str(
        TODAY.year + 1
    )

    anterior = series.get(
        anterior_year
    )

    actual = series.get(
        actual_year
    )

    proyectada = series.get(
        proyectada_year
    )

    if (
        anterior is None
        or
        actual is None
        or
        proyectada is None
    ):

        print(

            f"IMF WEO "
            f"{indicator} "
            f"{country_code}: "
            "faltan años "
            f"{anterior_year}/"
            f"{actual_year}/"
            f"{proyectada_year}"
        )

        return None

    return {

        "anterior":
            round(
                float(
                    anterior
                ),
                2
            ),

        "actual":
            round(
                float(
                    actual
                ),
                2
            ),

        "proyectada":
            round(
                float(
                    proyectada
                ),
                2
            ),
    }


# ============================================================
# TENDENCIA
# ============================================================

def compute_trend(
    data_list
):

    if (
        not data_list
        or
        len(data_list) < 2
    ):

        return None

    try:

        anterior = float(
            data_list[-2][
                "value"
            ]
        )

        actual = float(
            data_list[-1][
                "value"
            ]
        )

    except (
        ValueError,
        TypeError,
        IndexError,
        KeyError
    ):

        return None

    proyectada = round(

        actual
        +
        (
            actual
            -
            anterior
        ),

        2
    )

    return {

        "anterior":
            round(
                anterior,
                2
            ),

        "actual":
            round(
                actual,
                2
            ),

        "proyectada":
            proyectada,
    }


def build_macro_trend(
    macro
):

    trend = {

        "tasa": {

            "peru":
                compute_trend(
                    macro
                    .get(
                        "peru",
                        {}
                    )
                    .get(
                        "tasa",
                        []
                    )
                ),

            "usa":
                compute_trend(
                    macro
                    .get(
                        "usa",
                        {}
                    )
                    .get(
                        "tasa",
                        []
                    )
                ),

            "europa":
                compute_trend(
                    macro
                    .get(
                        "europa",
                        {}
                    )
                    .get(
                        "tasa",
                        []
                    )
                ),
        },

        "inflacion": {},

        "pbi": {},
    }

    # ========================================================
    # FED DOT PLOT
    # ========================================================

    fed_dot_plot = fred_latest(
        "FEDTARMD"
    )

    if (
        trend["tasa"]["usa"]
        and
        fed_dot_plot is not None
    ):

        trend[
            "tasa"
        ][
            "usa"
        ][
            "proyectada"
        ] = round(
            fed_dot_plot,
            2
        )

        print(
            "Tasa OK — "
            "USA proyectada real "
            "(Fed dot-plot): "
            f"{fed_dot_plot}"
        )

    else:

        print(
            "Tasa USA: no se pudo "
            "obtener dot-plot real "
            "de la Fed."
        )

    # ========================================================
    # FMI
    # ========================================================

    imf_countries = {

        "peru":
            "PER",

        "usa":
            "USA",

        "europa":
            "EURO",
    }

    for (
        region_key,
        imf_code
    ) in imf_countries.items():

        trend[
            "inflacion"
        ][
            region_key
        ] = get_imf_trend(
            "PCPIPCH",
            imf_code
        )

        trend[
            "pbi"
        ][
            region_key
        ] = get_imf_trend(
            "NGDP_RPCH",
            imf_code
        )

    return trend


# ============================================================
# HELPERS
# ============================================================

def _fmt(val):

    try:

        return (
            f"{float(val):.2f}"
        )

    except (
        TypeError,
        ValueError
    ):

        return str(val)


def _trend(vals):

    nums = [

        float(v)

        for v in vals

        if v is not None
    ]

    if len(nums) < 2:

        return "estable"

    diff = (
        nums[-1]
        -
        nums[0]
    )

    if abs(diff) < 0.05:

        return "estable"

    return (

        "al alza"

        if diff > 0

        else "a la baja"
    )


# ============================================================
# NOTICIAS POR REGIÓN
# ============================================================

def find_relevant_news(
    region_key,
    news_list
):

    patterns = (
        REGION_KEYWORDS.get(
            region_key,
            []
        )
    )

    for n in news_list:

        title_lower = (

            n.get(
                "title_en",
                n["title"]
            )
            .lower()
        )

        if any(

            re.search(
                p,
                title_lower
            )

            for p in patterns
        ):

            return n

    return None


def get_peru_fallback_news():

    feed_url = (

        "https://gestion.pe/"
        "arc/outboundfeeds/rss/"
        "category/economia/"
        "?outputType=xml"
    )

    items = _fetch_feed_items(
        feed_url,
        limit=5
    )

    if items:

        return items[0]

    return None


def get_europa_fallback_news():

    feed_url = (

        "https://feeds.feedburner.com/"
        "euronews/en/business/"
    )

    items = _fetch_feed_items(
        feed_url,
        limit=8
    )

    patterns = (

        REGION_KEYWORDS[
            "europa"
        ]

        +

        FALLBACK_KEYWORDS_EN
    )

    for item in items:

        title_lower = (
            item["title"]
            .lower()
        )

        if any(

            re.search(
                p,
                title_lower
            )

            for p in patterns
        ):

            item["title"] = (
                translate_es(
                    item["title"]
                )
            )

            item["description"] = (
                translate_es(
                    item[
                        "description"
                    ]
                )
            )

            return item

    return None


def get_usa_fallback_news():

    feed_url = (

        "https://feeds.reuters.com/"
        "reuters/businessNews"
    )

    items = _fetch_feed_items(
        feed_url,
        limit=8
    )

    patterns = (

        REGION_KEYWORDS[
            "usa"
        ]

        +

        FALLBACK_KEYWORDS_EN
    )

    for item in items:

        title_lower = (
            item["title"]
            .lower()
        )

        if any(

            re.search(
                p,
                title_lower
            )

            for p in patterns
        ):

            item["title"] = (
                translate_es(
                    item["title"]
                )
            )

            item["description"] = (
                translate_es(
                    item[
                        "description"
                    ]
                )
            )

            return item

    if items:

        item = items[0]

        item["title"] = (
            translate_es(
                item["title"]
            )
        )

        item["description"] = (
            translate_es(
                item[
                    "description"
                ]
            )
        )

        return item

    return None


# ============================================================
# CONCLUSIONES
# ============================================================

def generate_conclusiones(
    macro,
    news_list
):

    labels = [

        (
            "peru",
            "🇵🇪 Perú"
        ),

        (
            "usa",
            "🇺🇸 Estados Unidos"
        ),

        (
            "europa",
            "🇪🇺 Europa"
        ),
    ]

    lineas = []

    for (
        key,
        label
    ) in labels:

        data = macro.get(
            key,
            {}
        )

        tasa = [

            o["value"]

            for o
            in data.get(
                "tasa",
                []
            )
        ]

        infl = [

            o["value"]

            for o
            in data.get(
                "inflacion",
                []
            )
        ]

        pbi = [

            o["value"]

            for o
            in data.get(
                "pbi",
                []
            )
        ]

        partes = []

        if tasa:

            partes.append(

                "tasa de referencia en "
                f"{_fmt(tasa[-1])}% "
                f"({_trend(tasa)})"
            )

        if infl:

            partes.append(

                "inflación interanual en "
                f"{_fmt(infl[-1])}% "
                f"({_trend(infl)})"
            )

        if pbi:

            partes.append(

                "crecimiento del PBI en "
                f"{_fmt(pbi[-1])}% "
                f"({_trend(pbi)})"
            )

        resumen = (

            ", ".join(
                partes
            )
            + "."

            if partes

            else

            "sin datos disponibles "
            "este mes."
        )

        noticia = (
            find_relevant_news(
                key,
                news_list
            )
        )

        if (
            not noticia
            and key == "peru"
        ):

            noticia = (
                get_peru_fallback_news()
            )

        if (
            not noticia
            and key == "europa"
        ):

            noticia = (
                get_europa_fallback_news()
            )

        if (
            not noticia
            and key == "usa"
        ):

            noticia = (
                get_usa_fallback_news()
            )

        lineas.append({

            "label":
                label,

            "resumen":
                f"{label}: {resumen}",

            "noticia_titulo":
                (
                    noticia["title"]
                    if noticia
                    else None
                ),

            "noticia_desc":
                (
                    noticia[
                        "description"
                    ]
                    if noticia
                    else None
                ),

            "noticia_link":
                (
                    noticia["link"]
                    if noticia
                    else None
                ),
        })

    return lineas


# ============================================================
# IMPACTO EMPRESARIAL
# ============================================================

def get_impacto_empresarial(
    macro_trend
):

    interpretaciones = {

        "tasa": {

            "al alza":

                (
                    "financiamiento más costoso; "
                    "se recomienda evaluar la "
                    "fijación de tasas en el "
                    "corto plazo"
                ),

            "a la baja":

                (
                    "costo de fondeo a la baja; "
                    "representa una oportunidad "
                    "para nuevas líneas de crédito"
                ),

            "estable":

                (
                    "costo de financiamiento "
                    "estable, sin cambios "
                    "significativos previstos"
                ),
        },

        "inflacion": {

            "al alza":

                (
                    "presión al alza sobre "
                    "costos operativos y márgenes; "
                    "se sugiere revisar la "
                    "estrategia de precios"
                ),

            "a la baja":

                (
                    "entorno de precios más "
                    "predecible, favorable para "
                    "la planificación a mediano "
                    "plazo"
                ),

            "estable":

                (
                    "inflación bajo control, "
                    "sin impacto significativo "
                    "previsto en el corto plazo"
                ),
        },

        "pbi": {

            "al alza":

                (
                    "el crecimiento económico "
                    "favorece la expansión y "
                    "una mayor demanda"
                ),

            "a la baja":

                (
                    "la desaceleración sugiere "
                    "cautela en las proyecciones "
                    "de crecimiento"
                ),

            "estable":

                (
                    "actividad económica estable, "
                    "sin señales de cambio abrupto"
                ),
        },
    }

    labels = [

        (
            "peru",
            "🇵🇪 Perú"
        ),

        (
            "usa",
            "🇺🇸 Estados Unidos"
        ),

        (
            "europa",
            "🇪🇺 Europa"
        ),
    ]

    resultado = []

    for (
        key,
        label
    ) in labels:

        partes = []

        for metric in [

            "tasa",
            "inflacion",
            "pbi"

        ]:

            d = (

                macro_trend
                .get(
                    metric,
                    {}
                )
                .get(
                    key
                )
            )

            if not d:

                continue

            direccion = (
                _trend(
                    [
                        d["anterior"],
                        d["actual"]
                    ]
                )
            )

            partes.append(

                interpretaciones[
                    metric
                ][
                    direccion
                ]
            )

        if partes:

            resumen = (
                "; ".join(
                    partes
                )
                + "."
            )

            resumen = (

                resumen[0].upper()
                +
                resumen[1:]
            )

        else:

            resumen = (

                "sin datos suficientes "
                "para un análisis este mes."
            )

        resultado.append({

            "label":
                label,

            "resumen":
                f"{label}: {resumen}",
        })

    return resultado


# ============================================================
# FRASE FINAL
# ============================================================

def _decap(texto):

    if not texto:

        return texto

    return (

        texto[0].lower()
        +
        texto[1:]
    )


def get_frase_final(
    macro_trend,
    dato_semana
):

    conteo = {

        "al alza":
            0,

        "a la baja":
            0,

        "estable":
            0,
    }

    for (
        metric,
        regiones
    ) in macro_trend.items():

        for (
            region_key,
            d
        ) in regiones.items():

            if not d:

                continue

            direccion = (
                _trend(
                    [
                        d["anterior"],
                        d["actual"]
                    ]
                )
            )

            conteo[
                direccion
            ] += 1

    dominante = max(
        conteo,
        key=conteo.get
    )

    tono = {

        "al alza":

            (
                "un mes marcado por "
                "presiones al alza en "
                "varios frentes"
            ),

        "a la baja":

            (
                "un mes con señales "
                "de alivio en varios "
                "frentes"
            ),

        "estable":

            (
                "un mes de relativa "
                "estabilidad en los "
                "principales indicadores"
            ),

    }[dominante]

    if dato_semana:

        return (

            f"En general, {tono}; "
            "lo más destacado fue "
            f"{_decap(dato_semana['metric_label'])} "
            f"de "
            f"{dato_semana['region_label']}."
        )

    return (
        f"En general, {tono}."
    )


# ============================================================
# FECHAS
# ============================================================

def _fecha_legible(
    date_str
):

    if not date_str:

        return ""

    m = re.match(

        r"^(\d{4})-(\d{2})$",

        date_str
    )

    if m:

        anio = m.group(1)

        mes = int(
            m.group(2)
        )

        return (

            f"{MESES_ABR_ES[
                mes - 1
            ].capitalize()}. "
            f"{anio}"
        )

    return date_str


def _fecha_orden(
    date_str
):

    if not date_str:

        return (
            0,
            0
        )

    # FRED YYYY-MM
    m = re.match(

        r"^(\d{4})-(\d{2})$",

        date_str
    )

    if m:

        return (

            int(
                m.group(1)
            ),

            int(
                m.group(2)
            )
        )

    # BCRP Jul.2026
    m2 = re.match(

        r"^([A-Za-zÀ-ÿ]{3})\.?(\d{4})$",

        date_str
    )

    if m2:

        mes_str = (
            m2.group(1)
            .lower()
        )

        anio = int(
            m2.group(2)
        )

        try:

            mes_idx = (

                MESES_ABR_ES
                .index(
                    mes_str
                )

                + 1
            )

        except ValueError:

            mes_idx = 0

        return (

            anio,
            mes_idx
        )

    return (
        0,
        0
    )


# ============================================================
# DATO DEL MES
# ============================================================

def get_dato_semana(
    macro_trend,
    macro
):
    """
    Selección del Dato del Mes.

    PRIORIDAD:
    Si el Employment Situation ya fue
    publicado durante el mes actual,
    el NFP se utiliza como dato destacado.

    Si todavía no salió el NFP,
    se utiliza la lógica macro anterior
    como fallback.
    """

    # ========================================================
    # PRIORIDAD 1 — NFP
    # ========================================================

    nfp_dato = (
        get_nfp_dato_mes()
    )

    if nfp_dato:

        print(
            "⭐ PRIORIDAD NFP ACTIVADA"
        )

        return nfp_dato

    # ========================================================
    # FALLBACK
    # ========================================================

    print(
        "Dato del Mes: "
        "NFP no disponible. "
        "Usando fallback macro."
    )

    labels = {

        "peru":
            "🇵🇪 Perú",

        "usa":
            "🇺🇸 Estados Unidos",

        "europa":
            "🇪🇺 Europa",
    }

    metric_labels = {

        "tasa":
            "Tasa de referencia",

        "inflacion":
            "Inflación interanual",

        "pbi":
            "Crecimiento del PBI",

        "empleo":
            "Tasa de desempleo",
    }

    candidatos = []

    for region_key in [

        "peru",
        "usa",
        "europa"

    ]:

        for metric in [

            "tasa",
            "inflacion",
            "pbi",
            "empleo"

        ]:

            raw_list = (

                macro
                .get(
                    region_key,
                    {}
                )
                .get(
                    metric,
                    []
                )
            )

            d = compute_trend(
                raw_list
            )

            if not d:

                continue

            cambio = round(

                d["actual"]
                -
                d["anterior"],

                2
            )

            fecha_orden = (

                _fecha_orden(
                    raw_list[-1][
                        "date"
                    ]
                )

                if raw_list

                else (
                    0,
                    0
                )
            )

            candidatos.append({

                "metric_key":
                    metric,

                "region_key":
                    region_key,

                "region_label":
                    labels.get(
                        region_key,
                        region_key
                    ),

                "metric_label":
                    metric_labels.get(
                        metric,
                        metric
                    ),

                "valor":
                    d["actual"],

                "anterior":
                    d["anterior"],

                "cambio":
                    cambio,

                "fecha_orden":
                    fecha_orden,
            })

    if not candidatos:

        return None

    destacado = max(

        candidatos,

        key=lambda c: (

            c[
                "fecha_orden"
            ],

            abs(
                c["cambio"]
            )
        )
    )

    raw_list = (

        macro
        .get(
            destacado[
                "region_key"
            ],
            {}
        )
        .get(
            destacado[
                "metric_key"
            ],
            []
        )
    )

    if raw_list:

        fecha = (
            _fecha_legible(
                raw_list[-1][
                    "date"
                ]
            )
        )

    else:

        fecha = (

            f"{MESES_ES[
                TODAY.month - 1
            ].capitalize()} "
            f"{TODAY.year}"
        )

    valor_fmt = (
        f"{destacado['valor']:.2f}"
    )

    anterior_fmt = (
        f"{destacado['anterior']:.2f}"
    )

    if destacado[
        "cambio"
    ] == 0:

        headline = (

            f"{destacado['metric_label']} "
            f"de "
            f"{destacado['region_label']} "
            "se mantiene estable en "
            f"{valor_fmt}%"
        )

        descripcion = (

            "Sin cambios respecto "
            "al periodo anterior "
            f"({anterior_fmt}%)."
        )

    else:

        direccion = (

            "sube"

            if destacado[
                "cambio"
            ] > 0

            else "baja"
        )

        signo = (

            "+"

            if destacado[
                "cambio"
            ] > 0

            else ""
        )

        headline = (

            f"{destacado['metric_label']} "
            f"de "
            f"{destacado['region_label']} "
            f"{direccion} a "
            f"{valor_fmt}%"
        )

        descripcion = (

            f"Desde "
            f"{anterior_fmt}% "
            "en el periodo anterior "
            f"({signo}"
            f"{destacado['cambio']:.2f} "
            "p.p.)."
        )

    destacado[
        "fecha"
    ] = fecha

    destacado[
        "headline"
    ] = headline

    destacado[
        "descripcion"
    ] = descripcion

    destacado[
        "valor"
    ] = valor_fmt

    return destacado


# ============================================================
# CONCLUSIÓN DÓLAR
# ============================================================

def get_conclusion_dolar(
    macro_trend
):

    tasa = macro_trend.get(
        "tasa",
        {}
    )

    usa = tasa.get(
        "usa"
    )

    europa = tasa.get(
        "europa"
    )

    if (
        not usa
        or
        not europa
    ):

        return None

    cambio_usa = round(

        usa["proyectada"]
        -
        usa["actual"],

        2
    )

    cambio_europa = round(

        europa["proyectada"]
        -
        europa["actual"],

        2
    )

    diferencial = round(

        cambio_usa
        -
        cambio_europa,

        2
    )

    if diferencial > 0.05:

        direccion = (
            "fortalecerse"
        )

        razon = (

            "la Fed proyecta mantener "
            "tasas relativamente más "
            "altas frente al BCE "
            f"(diferencial de "
            f"{diferencial:+.2f} p.p.), "
            "lo que favorece el atractivo "
            "del dólar frente al euro"
        )

    elif diferencial < -0.05:

        direccion = (
            "debilitarse"
        )

        razon = (

            "el diferencial de tasas "
            "se mueve a favor del euro "
            "frente al dólar "
            f"({diferencial:+.2f} p.p.), "
            "lo que le resta atractivo "
            "relativo al dólar"
        )

    else:

        direccion = (

            "mantenerse relativamente "
            "estable"
        )

        razon = (

            "el diferencial de tasas "
            "entre la Fed y el BCE "
            "no muestra cambios "
            "significativos en el "
            "corto plazo"
        )

    return (

        "Con base en las proyecciones "
        "de tasas, se espera que el "
        f"dólar tienda a {direccion} "
        "frente al euro en el corto "
        f"plazo, ya que {razon}."
    )


# ============================================================
# LABELS DE PERIODOS
# ============================================================

def get_periodo_labels():

    def add_months(
        date,
        delta
    ):

        total = (

            date.month
            - 1
            + delta
        )

        y = (

            date.year
            +
            total // 12
        )

        m = (

            total % 12
            + 1
        )

        return date.replace(

            year=y,
            month=m,
            day=1
        )

    anterior_dt = add_months(
        TODAY,
        -1
    )

    actual_dt = TODAY

    proyectada_dt = add_months(
        TODAY,
        1
    )

    tasa_labels = [

        [
            "Anterior",

            (
                f"("
                f"{MESES_ABR_ES[
                    anterior_dt.month - 1
                ]}. "
                f"{anterior_dt.year}"
                f")"
            )
        ],

        [
            "Actual",

            (
                f"("
                f"{MESES_ABR_ES[
                    actual_dt.month - 1
                ]}. "
                f"{actual_dt.year}"
                f")"
            )
        ],

        [
            "Proyectada",

            (
                f"("
                f"{MESES_ABR_ES[
                    proyectada_dt.month - 1
                ]}. "
                f"{proyectada_dt.year}"
                f")"
            )
        ],
    ]

    infl_pbi_labels = [

        [
            "Anterior",

            (
                f"("
                f"{MESES_ABR_ES[
                    TODAY.month - 1
                ]}. "
                f"{TODAY.year - 1}"
                f")"
            )
        ],

        [
            "Actual",

            (
                f"("
                f"{MESES_ABR_ES[
                    TODAY.month - 1
                ]}. "
                f"{TODAY.year}"
                f")"
            )
        ],

        [
            "Proyectada",

            (
                f"("
                f"{MESES_ABR_ES[
                    TODAY.month - 1
                ]}. "
                f"{TODAY.year + 1}"
                f")"
            )
        ],
    ]

    return {

        "tasa":
            tasa_labels,

        "inflacion":
            infl_pbi_labels,

        "pbi":
            infl_pbi_labels,
    }


# ============================================================
# EJECUCIÓN
# ============================================================

print("")
print(
    "======================================"
)
print(
    "GENERANDO PANORAMA ECONÓMICO"
)
print(
    f"Fecha: "
    f"{TODAY.strftime('%Y-%m-%d %H:%M')}"
)
print(
    "======================================"
)
print("")


news = get_rss_news()

calendar = get_calendar()

macro = get_macro_data()

macro_trend = build_macro_trend(
    macro
)

dato_semana = get_dato_semana(
    macro_trend,
    macro
)

conclusion_dolar = (
    get_conclusion_dolar(
        macro_trend
    )
)

periodo_labels = (
    get_periodo_labels()
)

month_str = (

    f"{MESES_ES[
        TODAY.month - 1
    ].capitalize()} "
    f"{TODAY.year}"
)


# ============================================================
# TEMPLATE HTML
# ============================================================

with open(
    "templates/dashboard.html",
    encoding="utf-8"
) as f:

    template = Template(
        f.read()
    )


html = template.render(

    month=
        month_str,

    news=
        news,

    calendar=
        calendar,

    macro=
        macro,

    macro_trend=
        macro_trend,

    dato_semana=
        dato_semana,

    conclusion_dolar=
        conclusion_dolar,

    periodo_labels=
        periodo_labels,
)


# ============================================================
# OUTPUT
# ============================================================

os.makedirs(
    "output",
    exist_ok=True
)


with open(
    "output/index.html",
    "w",
    encoding="utf-8"
) as f:

    f.write(
        html
    )


print("")
print(
    "======================================"
)
print(
    "✅ DASHBOARD GENERADO"
)
print(
    f"Noticias: {len(news)}"
)
print(
    "Calendario: OK"
)

if dato_semana:

    print(
        "Dato del Mes:"
    )

    print(
        dato_semana[
            "headline"
        ]
    )

else:

    print(
        "Dato del Mes: "
        "NO DISPONIBLE"
    )

print(
    "======================================"
)
print("")
