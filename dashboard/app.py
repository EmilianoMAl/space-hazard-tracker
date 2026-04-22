"""
app.py — Space Hazard Tracker v2.1
Editorial dark design — 5 NASA APIs
"""

import os, logging, re
from datetime import datetime, timedelta

import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
NASA_BASE    = "https://api.nasa.gov"
EONET_BASE   = "https://eonet.gsfc.nasa.gov/api/v3"

st.set_page_config(
    page_title="Space Hazard Tracker",
    page_icon="☄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@300;400;500&family=Inter:wght@300;400;500&display=swap');

html, body, [data-testid="stApp"] {
    background-color: #090a10 !important;
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] {
    background-color: #060710 !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
}
h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important;
}
p, div, span { font-family: 'Inter', sans-serif !important; }

[data-testid="stTabs"] button {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important; font-weight: 500 !important;
    letter-spacing: 0.1em !important; color: #334155 !important;
    text-transform: uppercase !important;
    border-bottom: 2px solid transparent !important;
    padding: 12px 20px !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #f97316 !important;
    border-bottom: 2px solid #f97316 !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important; color: #334155 !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stDataFrame"] {
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: 8px !important;
}
hr { border-color: rgba(255,255,255,0.05) !important; }

.kpi {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px; padding: 20px 16px; position: relative;
}
.kpi-accent {
    position: absolute; top: 0; left: 0; right: 0;
    height: 2px; border-radius: 8px 8px 0 0;
}
.kpi-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px; letter-spacing: 0.18em;
    text-transform: uppercase; color: #334155; margin-bottom: 10px;
}
.kpi-num {
    font-family: 'Syne', sans-serif;
    font-size: 36px; font-weight: 800; line-height: 1;
    margin-bottom: 6px;
}
.kpi-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: #1e293b;
}

.sec {
    display: flex; align-items: center; gap: 10px;
    margin: 2rem 0 1rem; padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.sec-line { width: 24px; height: 2px; flex-shrink: 0; border-radius: 1px; }
.sec-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; font-weight: 500; letter-spacing: 0.18em;
    color: #64748b; text-transform: uppercase;
}

.tag {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; padding: 3px 10px; border-radius: 4px;
    letter-spacing: 0.06em; font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# ── Theme helpers ─────────────────────────────────────────────────────────────
BG   = "rgba(0,0,0,0)"
CARD = "rgba(9,10,16,0.95)"
BASE = dict(
    paper_bgcolor=BG, plot_bgcolor=CARD,
    font=dict(family="JetBrains Mono", color="#334155", size=11),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(bgcolor=BG, font=dict(color="#475569", size=10)),
)
AX = dict(gridcolor="rgba(255,255,255,0.04)",
          linecolor="rgba(255,255,255,0.06)", zeroline=False)

RISK = {"HIGH": "#ef4444", "MEDIUM": "#eab308", "LOW": "#22c55e"}
FLARE = {"X": "#ef4444", "M": "#f97316", "C": "#eab308", "B": "#38bdf8", "A": "#475569"}

CATEGORY_META = {
    "Wildfires":            ("#ef4444",  "🔥"),
    "Severe Storms":        ("#38bdf8",  "🌀"),
    "Volcanoes":            ("#f97316",  "🌋"),
    "Floods":               ("#3b82f6",  "🌊"),
    "Earthquakes":          ("#eab308",  "⚡"),
    "Landslides":           ("#a16207",  "⛰"),
    "Sea and Lake Ice":     ("#bae6fd",  "❄️"),
    "Drought":              ("#d97706",  "🌵"),
    "Dust and Haze":        ("#92400e",  "💨"),
    "Temperature Extremes": ("#fb923c",  "🌡"),
    "Manmade":              ("#a78bfa",  "🏭"),
    "Snow":                 ("#e0f2fe",  "🌨"),
    "Water Color":          ("#22d3ee",  "💧"),
}

def ccolor(c): return CATEGORY_META.get(c, ("#64748b", "🌐"))[0]
def cicon(c):  return CATEGORY_META.get(c, ("#64748b", "🌐"))[1]

def kp_meta(kp):
    if kp >= 8: return "EXTREME",  "#ef4444"
    if kp >= 7: return "SEVERE",   "#f97316"
    if kp >= 6: return "STRONG",   "#eab308"
    if kp >= 5: return "MODERATE", "#84cc16"
    if kp >= 4: return "MINOR",    "#22c55e"
    return "QUIET", "#22c55e"

def chart(fig, h=380, title="", extra=None):
    kw = {**BASE, "height": h}
    if title:
        kw["title"] = dict(text=title, font=dict(family="Syne", size=13, color="#94a3b8"))
    if extra:
        kw.update(extra)
    fig.update_layout(**kw)
    fig.update_xaxes(**AX)
    fig.update_yaxes(**AX)
    return fig

def section(label, color="#f97316"):
    st.markdown(f"""<div class='sec'>
        <div class='sec-line' style='background:{color};'></div>
        <div class='sec-title'>{label}</div>
    </div>""", unsafe_allow_html=True)


# ── API calls ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def get_apod():
    try:
        r = requests.get(f"{NASA_BASE}/planetary/apod",
                         params={"api_key": NASA_API_KEY}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"APOD: {e}")
        return None


@st.cache_data(ttl=3600)
def get_neo(days=7) -> pd.DataFrame:
    start = datetime.utcnow().strftime("%Y-%m-%d")
    end   = (datetime.utcnow() + timedelta(days=days-1)).strftime("%Y-%m-%d")
    try:
        r = requests.get(f"{NASA_BASE}/neo/rest/v1/feed",
                         params={"start_date": start, "end_date": end,
                                 "api_key": NASA_API_KEY}, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"NEO: {e}")
        return pd.DataFrame()

    rows = []
    for date_str, objs in data.get("near_earth_objects", {}).items():
        for o in objs:
            ap   = o["close_approach_data"][0] if o.get("close_approach_data") else {}
            km   = o.get("estimated_diameter", {}).get("kilometers", {})
            miss = float(ap.get("miss_distance", {}).get("kilometers", 0))
            dmin = float(km.get("estimated_diameter_min", 0))
            dmax = float(km.get("estimated_diameter_max", 0))
            rows.append({
                "name":        o["name"].strip("()"),
                "date":        date_str,
                "diam_min_km": round(dmin, 4),
                "diam_max_km": round(dmax, 4),
                "diam_avg_m":  round((dmin + dmax) / 2 * 1000, 1),
                "miss_mkm":    round(miss / 1_000_000, 4),
                "miss_ld":     round(float(ap.get("miss_distance", {}).get("lunar", 0)), 2),
                "vel_kmh":     round(float(ap.get("relative_velocity", {}).get("kilometers_per_hour", 0))),
                "vel_kms":     round(float(ap.get("relative_velocity", {}).get("kilometers_per_second", 0)), 2),
                "hazardous":   o.get("is_potentially_hazardous_asteroid", False),
                "magnitude":   o.get("absolute_magnitude_h"),
                "jpl_url":     o.get("nasa_jpl_url", ""),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    def classify(row):
        km = row["miss_mkm"] * 1_000_000
        if km < 1_000_000 or (row["hazardous"] and km < 10_000_000):
            return "HIGH"
        if km < 10_000_000:
            return "MEDIUM"
        return "LOW"

    df["risk"]  = df.apply(classify, axis=1)
    df["theta"] = (pd.to_datetime(df["date"]).dt.dayofyear / 365 * 360).round(1)
    return df.sort_values("miss_mkm")


@st.cache_data(ttl=1800)
def get_eonet() -> pd.DataFrame:
    """Fetch last 60 days of all events (open + closed) for global diversity."""
    try:
        r = requests.get(f"{EONET_BASE}/events",
                         params={"days": 60, "limit": 500}, timeout=25)
        r.raise_for_status()
        events = r.json().get("events", [])
    except Exception as e:
        logger.error(f"EONET: {e}")
        return pd.DataFrame()

    rows = []
    for ev in events:
        cat  = ev.get("categories", [{}])[0]
        geos = ev.get("geometry", [])
        for geo in reversed(geos):
            coords = geo.get("coordinates")
            if coords and len(coords) >= 2:
                try:
                    rows.append({
                        "id":       ev["id"],
                        "title":    ev["title"],
                        "category": cat.get("title", "Unknown"),
                        "status":   "closed" if ev.get("closed") else "open",
                        "date":     geo.get("date", "")[:10],
                        "lon":      float(coords[0]),
                        "lat":      float(coords[1]),
                        "mag":      geo.get("magnitudeValue"),
                        "mag_unit": geo.get("magnitudeUnit") or "",
                    })
                except (ValueError, TypeError):
                    pass
                break
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600)
def get_flares() -> pd.DataFrame:
    start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    end   = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        r = requests.get(f"{NASA_BASE}/DONKI/FLR",
                         params={"startDate": start, "endDate": end,
                                 "api_key": NASA_API_KEY}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            return pd.DataFrame()
        rows = []
        for f in data:
            cls = (f.get("classType") or "B").strip()
            rows.append({
                "date":     f.get("beginTime", "")[:10],
                "cls":      cls,
                "letter":   cls[0].upper() if cls else "B",
                "location": f.get("sourceLocation") or "Unknown",
                "link":     f.get("link") or "",
            })
        return pd.DataFrame(rows)
    except Exception as e:
        logger.error(f"DONKI FLR: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_cme() -> pd.DataFrame:
    """Coronal Mass Ejections — last 30 days."""
    start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    end   = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        r = requests.get(f"{NASA_BASE}/DONKI/CME",
                         params={"startDate": start, "endDate": end,
                                 "api_key": NASA_API_KEY}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            return pd.DataFrame()
        rows = []
        for c in data:
            ana = c.get("cmeAnalyses") or []
            speed = None
            if ana:
                speed = ana[0].get("speed")
            rows.append({
                "date":  c.get("startTime", "")[:10],
                "time":  c.get("startTime", "")[:16],
                "speed": float(speed) if speed else None,
                "type":  ana[0].get("type", "Unknown") if ana else "Unknown",
            })
        df = pd.DataFrame(rows)
        df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
        return df.dropna(subset=["date_dt"])
    except Exception as e:
        logger.error(f"DONKI CME: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_storms() -> pd.DataFrame:
    start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    end   = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        r = requests.get(f"{NASA_BASE}/DONKI/GST",
                         params={"startDate": start, "endDate": end,
                                 "api_key": NASA_API_KEY}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            return pd.DataFrame()
        rows = []
        for s in data:
            for kp in s.get("allKpIndex", []):
                rows.append({
                    "time": kp.get("observedTime", "")[:16],
                    "kp":   float(kp.get("kpIndex", 0)),
                })
        df = pd.DataFrame(rows)
        df["time_dt"] = pd.to_datetime(df["time"], errors="coerce")
        return df.dropna(subset=["time_dt"]).sort_values("time_dt")
    except Exception as e:
        logger.error(f"DONKI GST: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=7200)
def get_epic():
    try:
        r = requests.get(f"{NASA_BASE}/EPIC/api/natural/images",
                         params={"api_key": NASA_API_KEY}, timeout=15)
        r.raise_for_status()
        imgs = r.json()
        if not imgs:
            return None, None
        img  = imgs[0]
        d    = img["date"][:10].replace("-", "/")
        url  = f"https://epic.gsfc.nasa.gov/archive/natural/{d}/jpg/{img['image']}.jpg"
        return img, url
    except Exception as e:
        logger.error(f"EPIC: {e}")
        return None, None


def yt_thumbnail(url: str):
    """Extract YouTube video ID and return thumbnail URL."""
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url or "")
    return f"https://img.youtube.com/vi/{m.group(1)}/hqdefault.jpg" if m else None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:1.5rem 0 1rem;'>
        <div style='font-family:Syne,sans-serif; font-size:16px; font-weight:800;
                    letter-spacing:0.05em; color:#f8fafc;'>SPACE HAZARD</div>
        <div style='font-family:JetBrains Mono,monospace; font-size:9px; color:#1e293b;
                    letter-spacing:0.2em; margin-top:4px;'>TRACKER · v2.1</div>
    </div>
    <hr>
    """, unsafe_allow_html=True)

    st.markdown("<p>NEO WINDOW (DAYS)</p>", unsafe_allow_html=True)
    neo_days = st.slider("", 1, 7, 7, label_visibility="collapsed")

    st.markdown("<p style='margin-top:1rem;'>THREAT FILTER</p>", unsafe_allow_html=True)
    risk_filter = st.multiselect("", ["HIGH", "MEDIUM", "LOW"],
                                 default=["HIGH", "MEDIUM", "LOW"],
                                 label_visibility="collapsed")

    st.markdown("<p style='margin-top:1rem;'>EVENT STATUS</p>", unsafe_allow_html=True)
    event_status = st.multiselect("", ["open", "closed"],
                                  default=["open", "closed"],
                                  label_visibility="collapsed")

    st.markdown("<hr>", unsafe_allow_html=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(f"""
    <div style='font-family:JetBrains Mono,monospace; font-size:10px;
                color:#1e293b; line-height:2.2;'>
        STATUS &nbsp;<span style='color:#22c55e;'>● NOMINAL</span><br>
        SYNC &nbsp;{ts}
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("↻  REFRESH DATA", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:2rem 0 1.5rem; border-bottom:1px solid rgba(255,255,255,0.05);
            margin-bottom:1.5rem;'>
    <div style='font-family:Syne,sans-serif; font-size:28px; font-weight:800;
                letter-spacing:0.04em; color:#f8fafc;'>SPACE HAZARD TRACKER</div>
    <div style='font-family:JetBrains Mono,monospace; font-size:10px; color:#1e293b;
                letter-spacing:0.2em; margin-top:6px;'>
        PLANETARY DEFENSE INTELLIGENCE &nbsp;·&nbsp;
        NASA OPEN APIS &nbsp;·&nbsp; REAL-TIME DATA
    </div>
</div>
""", unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Fetching data from NASA..."):
    apod_data       = get_apod()
    neo_df          = get_neo(days=neo_days)
    eonet_df        = get_eonet()
    flares_df       = get_flares()
    cme_df          = get_cme()
    storms_df       = get_storms()
    epic_img, epic_url = get_epic()


# ── KPI strip ─────────────────────────────────────────────────────────────────
total_neos = len(neo_df)                                       if not neo_df.empty    else 0
high_neos  = len(neo_df[neo_df["risk"] == "HIGH"])             if not neo_df.empty    else 0
hazardous  = int(neo_df["hazardous"].sum())                    if not neo_df.empty    else 0
total_evts = len(eonet_df)                                     if not eonet_df.empty  else 0
n_cats     = eonet_df["category"].nunique()                    if not eonet_df.empty  else 0
total_flr  = len(flares_df)                                    if not flares_df.empty else 0
x_flares   = len(flares_df[flares_df["letter"] == "X"])        if not flares_df.empty else 0
total_cme  = len(cme_df)                                       if not cme_df.empty    else 0
max_kp     = round(storms_df["kp"].max(), 1)                   if not storms_df.empty else 0.0
kp_lbl, kp_clr = kp_meta(max_kp)

kpis = [
    ("NEAR-EARTH OBJECTS", total_neos, f"{neo_days}-day window",   "#f97316"),
    ("HIGH RISK ASTEROIDS", high_neos, f"{hazardous} NASA-hazardous", "#ef4444"),
    ("ACTIVE EARTH EVENTS", total_evts, f"{n_cats} event types",   "#eab308"),
    ("SOLAR FLARES (30D)",  total_flr,  f"{x_flares} X-class",     "#a78bfa"),
    ("CME / KP MAX (30D)",  total_cme,  f"Kp {max_kp} · {kp_lbl}", kp_clr),
]

cols = st.columns(5)
for col, (label, val, sub, color) in zip(cols, kpis):
    with col:
        st.markdown(f"""
        <div class='kpi'>
            <div class='kpi-accent' style='background:{color};'></div>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-num' style='color:{color};'>{val}</div>
            <div class='kpi-sub'>{sub}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🌌  ASTRONOMY",
    "☄️  ASTEROIDS",
    "⚡  SPACE WEATHER",
    "🌍  EARTH SENTINEL",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — APOD + EPIC
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    if apod_data:
        media = apod_data.get("media_type", "image")
        url   = apod_data.get("hdurl") or apod_data.get("url", "")

        st.markdown(f"""
        <div style='margin:1.5rem 0 1.2rem;'>
            <div style='font-family:Syne,sans-serif; font-size:22px; font-weight:800;
                        color:#f8fafc; letter-spacing:0.02em;'>
                {apod_data.get("title","")}
            </div>
            <div style='font-family:JetBrains Mono,monospace; font-size:10px;
                        color:#334155; margin-top:6px; letter-spacing:0.1em;'>
                {apod_data.get("date","")}
                &nbsp;·&nbsp;
                © {apod_data.get("copyright","NASA / Public Domain")}
                &nbsp;·&nbsp;
                <span style='color:#f97316;'>{media.upper()}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_img, col_txt = st.columns([3, 2])
        with col_img:
            if media == "image":
                st.image(url, use_container_width=True)
            elif media == "video":
                thumb = yt_thumbnail(url)
                if thumb:
                    st.image(thumb, use_container_width=True)
                st.markdown(f"""
                <a href='{url}' target='_blank'
                   style='display:inline-block; margin-top:10px;
                          background:#f97316; color:#000; font-weight:700;
                          font-family:JetBrains Mono,monospace; font-size:11px;
                          padding:8px 20px; border-radius:4px;
                          text-decoration:none; letter-spacing:0.08em;'>
                    ▶ WATCH VIDEO
                </a>
                """, unsafe_allow_html=True)

        with col_txt:
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.02);
                        border:1px solid rgba(255,255,255,0.05);
                        border-radius:8px; padding:1.5rem;
                        font-family:Inter,sans-serif; font-size:14px;
                        line-height:1.9; color:#475569;
                        height:420px; overflow-y:auto;'>
                {apod_data.get("explanation","")}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("APOD temporarily unavailable. NASA may be rate-limiting your key.")

    # EPIC ────────────────────────────────────────────────────────────────────
    if epic_img and epic_url:
        section("DSCOVR EPIC — Full Disc Earth Image · L1 Lagrange Point", "#38bdf8")
        c1, c2 = st.columns([2, 3])
        with c1:
            st.image(epic_url, use_container_width=True)
        with c2:
            caption = epic_img.get("caption", "")
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.02);
                        border:1px solid rgba(255,255,255,0.05);
                        border-radius:8px; padding:1.5rem; height:100%;'>
                <div style='font-family:Syne,sans-serif; font-size:15px;
                            font-weight:700; color:#38bdf8; margin-bottom:8px;'>
                    LIVE EARTH IMAGE
                </div>
                <div style='font-family:JetBrains Mono,monospace; font-size:10px;
                            color:#334155; margin-bottom:1rem;'>
                    {epic_img.get("date","")}
                </div>
                <div style='font-family:Inter,sans-serif; font-size:13px;
                            color:#475569; line-height:1.8; margin-bottom:1.5rem;'>
                    {caption if caption else
                     "Full disc Earth captured by the EPIC camera aboard DSCOVR. "
                     "The satellite sits at the L1 Lagrange point — 1.5 million km "
                     "from Earth — providing a continuous sunlit view of our planet."}
                </div>
                <div style='display:grid; grid-template-columns:1fr 1fr; gap:10px;'>
                    {"".join([
                        f"<div style='background:rgba(255,255,255,0.02); "
                        f"border:1px solid rgba(255,255,255,0.05); "
                        f"border-radius:6px; padding:10px; "
                        f"font-family:JetBrains Mono,monospace; font-size:10px;'>"
                        f"<div style='color:#334155; margin-bottom:4px;'>{lbl}</div>"
                        f"<div style='color:#64748b;'>{val}</div></div>"
                        for lbl, val in [
                            ("INSTRUMENT","EPIC / DSCOVR"),
                            ("DISTANCE","~1.5M km"),
                            ("POSITION","L1 LAGRANGE"),
                            ("TYPE","NATURAL COLOR"),
                        ]
                    ])}
                </div>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ASTEROIDS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    if neo_df.empty:
        st.warning("No asteroid data.")
    else:
        disp = neo_df[neo_df["risk"].isin(risk_filter)].copy() if risk_filter else neo_df.copy()

        section("Proximity Radar — Approach Distance & Diameter", "#ef4444")
        c1, c2 = st.columns(2)

        with c1:
            fig_r = go.Figure()
            for rl, grp in disp.groupby("risk"):
                sizes = [max(6, float(d) * 60) for d in grp["diam_avg_m"].clip(upper=500) / 1000]
                fig_r.add_trace(go.Scatterpolar(
                    r=grp["miss_mkm"].tolist(),
                    theta=grp["theta"].tolist(),
                    mode="markers",
                    name=rl,
                    marker=dict(size=sizes, color=RISK[rl], opacity=0.85,
                                line=dict(width=1, color="rgba(255,255,255,0.1)")),
                    text=grp.apply(
                        lambda r: f"{r['name']}<br>{r['date']}<br>"
                                  f"{r['miss_mkm']:.3f}M km<br>⌀ {r['diam_avg_m']}m<br>"
                                  f"{r['vel_kms']} km/s",
                        axis=1).tolist(),
                    hoverinfo="text",
                ))
            fig_r.update_layout(
                polar=dict(
                    bgcolor=CARD,
                    radialaxis=dict(
                        visible=True,
                        range=[0, disp["miss_mkm"].max() * 1.1],
                        gridcolor="rgba(255,255,255,0.04)",
                        linecolor="rgba(255,255,255,0.08)",
                        tickfont=dict(family="JetBrains Mono", size=9, color="#334155"),
                        ticksuffix="M km",
                    ),
                    angularaxis=dict(
                        gridcolor="rgba(255,255,255,0.04)",
                        linecolor="rgba(255,255,255,0.06)",
                        tickfont=dict(family="JetBrains Mono", size=9, color="#334155"),
                        tickmode="array",
                        tickvals=list(range(0,360,30)),
                        ticktext=["Jan","Feb","Mar","Apr","May","Jun",
                                  "Jul","Aug","Sep","Oct","Nov","Dec"],
                    ),
                ),
                paper_bgcolor=BG, showlegend=True, height=420,
                legend=dict(font=dict(family="JetBrains Mono", size=11, color="#475569"),
                            bgcolor=BG),
                title=dict(text="Approach Radar · dot size = diameter",
                           font=dict(family="Syne", size=12, color="#64748b")),
            )
            st.plotly_chart(fig_r, use_container_width=True)

        with c2:
            SIZE_REF = [
                ("Bus", 12), ("Football field", 91), ("Eiffel Tower", 324),
                ("Burj Khalifa", 828), ("Small city", 5000),
            ]
            top = disp.nsmallest(14, "miss_mkm").copy()
            top["color"] = top["risk"].map(RISK)

            fig_sz = go.Figure(go.Bar(
                x=top["diam_avg_m"].tolist(),
                y=top["name"].str[:24].tolist(),
                orientation="h",
                marker_color=top["color"].tolist(),
                marker_line_width=0,
                text=[f"{v:.0f} m" for v in top["diam_avg_m"]],
                textposition="outside",
                textfont=dict(family="JetBrains Mono", size=10, color="#475569"),
                hovertemplate="<b>%{y}</b><br>⌀ %{x:.1f} m<extra></extra>",
            ))
            max_m = top["diam_avg_m"].max()
            for val, lbl in SIZE_REF:
                if val < max_m * 1.6:
                    fig_sz.add_vline(
                        x=val, line_dash="dot",
                        line_color="rgba(255,255,255,0.07)",
                        annotation_text=lbl,
                        annotation_font=dict(size=9, color="#334155",
                                             family="JetBrains Mono"),
                        annotation_position="top",
                    )
            chart(fig_sz, h=420, title="Closest 14 Asteroids — Estimated Size",
                  extra={"showlegend": False,
                         "xaxis_title": "Diameter (meters)"})
            fig_sz.update_yaxes(**AX, autorange="reversed")
            st.plotly_chart(fig_sz, use_container_width=True)

        section("Daily Count + Velocity Distribution", "#eab308")
        c1, c2 = st.columns([2, 1])
        with c1:
            daily = disp.groupby(["date", "risk"]).size().reset_index(name="n")
            fig_d = px.bar(daily, x="date", y="n", color="risk",
                           color_discrete_map=RISK,
                           labels={"n": "Objects", "date": ""})
            chart(fig_d, h=300, title="Daily Near-Earth Objects")
            st.plotly_chart(fig_d, use_container_width=True)
        with c2:
            fig_v = px.histogram(disp, x="vel_kmh", nbins=20,
                                 color="risk", color_discrete_map=RISK,
                                 labels={"vel_kmh": "Velocity (km/h)"})
            chart(fig_v, h=300, title="Velocity Distribution",
                  extra={"showlegend": False})
            st.plotly_chart(fig_v, use_container_width=True)

        section("Full Asteroid Intelligence Log", "#22c55e")
        tbl = disp[[
            "name","date","risk","miss_mkm","miss_ld",
            "diam_avg_m","vel_kmh","vel_kms","magnitude","hazardous"
        ]].rename(columns={
            "miss_mkm": "miss (M km)", "miss_ld": "miss (LD)",
            "diam_avg_m": "diam (m)",  "vel_kmh": "vel (km/h)",
            "vel_kms":  "vel (km/s)",  "magnitude": "abs mag",
        })
        st.dataframe(
            tbl.style.map(
                lambda v: f"color:{RISK.get(v,'#e2e8f0')};font-weight:600",
                subset=["risk"]
            ),
            use_container_width=True, hide_index=True, height=360,
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SPACE WEATHER
# ══════════════════════════════════════════════════════════════════════════════
with tab3:

    # ── Solar flares ─────────────────────────────────────────────────────────
    section("Solar Flare Activity — Last 30 Days (NASA DONKI)", "#f97316")

    if not flares_df.empty:
        c1, c2 = st.columns([1, 2])
        with c1:
            for letter, color in [("X","#ef4444"),("M","#f97316"),
                                   ("C","#eab308"),("B","#38bdf8")]:
                cnt = len(flares_df[flares_df["letter"] == letter])
                desc = {"X":"Major — radio blackouts","M":"Moderate — minor blackouts",
                        "C":"Minor — small effects","B":"Very minor — no effects"}[letter]
                st.markdown(f"""
                <div style='display:flex; justify-content:space-between;
                            align-items:center; padding:14px 0;
                            border-bottom:1px solid rgba(255,255,255,0.04);'>
                    <div>
                        <span style='background:rgba(255,255,255,0.03);
                                     border:1px solid {color}30;
                                     color:{color}; padding:3px 12px;
                                     border-radius:4px;
                                     font-family:JetBrains Mono,monospace;
                                     font-size:11px; font-weight:500;'>{letter}-class</span>
                        <div style='font-family:JetBrains Mono,monospace;
                                    font-size:9px; color:#1e293b;
                                    margin-top:4px; letter-spacing:0.06em;'>
                            {desc}
                        </div>
                    </div>
                    <div style='font-family:Syne,sans-serif; font-size:32px;
                                font-weight:800; color:{color};'>{cnt}</div>
                </div>
                """, unsafe_allow_html=True)

        with c2:
            fig_tl = go.Figure()
            for letter, color in FLARE.items():
                sub = flares_df[flares_df["letter"] == letter]
                if not sub.empty:
                    fig_tl.add_trace(go.Scatter(
                        x=pd.to_datetime(sub["date"]).tolist(),
                        y=[letter] * len(sub),
                        mode="markers",
                        name=f"{letter}-class",
                        marker=dict(size=16, color=color, opacity=0.9,
                                    symbol="diamond",
                                    line=dict(width=1, color="rgba(0,0,0,0.3)")),
                        text=sub["location"].tolist(),
                        hovertemplate=f"<b>{letter}-class</b><br>%{{x}}<br>%{{text}}<extra></extra>",
                    ))
            chart(fig_tl, h=320, title="Flare Timeline by Class",
                  extra={"showlegend": False})
            fig_tl.update_yaxes(**AX, categoryorder="array",
                                categoryarray=["A","B","C","M","X"])
            st.plotly_chart(fig_tl, use_container_width=True)
    else:
        st.info("No solar flare data for the last 30 days.")

    # ── CME ──────────────────────────────────────────────────────────────────
    section("Coronal Mass Ejections (CME) — Last 30 Days", "#a78bfa")

    if not cme_df.empty:
        c1, c2 = st.columns([2, 1])
        with c1:
            fig_cme = go.Figure()
            speed_data = cme_df.dropna(subset=["speed"])
            if not speed_data.empty:
                fig_cme.add_trace(go.Scatter(
                    x=speed_data["date_dt"].tolist(),
                    y=speed_data["speed"].tolist(),
                    mode="lines+markers",
                    line=dict(color="#a78bfa", width=2),
                    marker=dict(size=8, color="#a78bfa",
                                line=dict(width=1, color="rgba(255,255,255,0.2)")),
                    fill="tozeroy", fillcolor="rgba(167,139,250,0.05)",
                    hovertemplate="Speed: <b>%{y:.0f} km/s</b><br>%{x}<extra></extra>",
                ))
                fig_cme.add_hline(y=2000, line_dash="dot",
                                   line_color="rgba(239,68,68,0.4)",
                                   annotation_text="Major CME threshold",
                                   annotation_font=dict(size=9, color="#ef4444",
                                                        family="JetBrains Mono"))
            chart(fig_cme, h=280, title="CME Speed Over Time (km/s)")
            st.plotly_chart(fig_cme, use_container_width=True)
        with c2:
            avg_speed = cme_df["speed"].mean() if not cme_df["speed"].isna().all() else 0
            max_speed = cme_df["speed"].max()  if not cme_df["speed"].isna().all() else 0
            for lbl, val, clr in [
                ("TOTAL CMEs", len(cme_df), "#a78bfa"),
                ("AVG SPEED", f"{avg_speed:.0f} km/s" if avg_speed else "N/A", "#64748b"),
                ("MAX SPEED", f"{max_speed:.0f} km/s" if max_speed else "N/A", "#ef4444"),
            ]:
                st.markdown(f"""
                <div style='background:rgba(255,255,255,0.02);
                            border:1px solid rgba(255,255,255,0.05);
                            border-radius:8px; padding:16px; margin-bottom:10px;
                            text-align:center;'>
                    <div style='font-family:JetBrains Mono,monospace; font-size:9px;
                                color:#334155; letter-spacing:0.15em;
                                margin-bottom:6px;'>{lbl}</div>
                    <div style='font-family:Syne,sans-serif; font-size:24px;
                                font-weight:800; color:{clr};'>{val}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No CME data for the last 30 days.")

    # ── Geomagnetic Kp ───────────────────────────────────────────────────────
    section("Geomagnetic Storm Activity — Kp Index", "#eab308")

    if not storms_df.empty:
        cur_kp = float(storms_df["kp"].iloc[-1])
        lbl, clr = kp_meta(cur_kp)

        c1, c2 = st.columns([3, 1])
        with c1:
            fig_kp = go.Figure()
            fig_kp.add_trace(go.Scatter(
                x=storms_df["time_dt"].tolist(),
                y=storms_df["kp"].tolist(),
                mode="lines+markers",
                line=dict(color="#eab308", width=2),
                marker=dict(size=7,
                            color=[kp_meta(k)[1] for k in storms_df["kp"]],
                            line=dict(width=1, color="rgba(0,0,0,0.3)")),
                fill="tozeroy", fillcolor="rgba(234,179,8,0.05)",
                hovertemplate="Kp: <b>%{y}</b><br>%{x}<extra></extra>",
            ))
            for val, lbl_r, c_r in [(5,"Moderate","#84cc16"),
                                     (6,"Strong","#eab308"),
                                     (7,"Severe","#f97316"),
                                     (8,"Extreme","#ef4444")]:
                fig_kp.add_hline(y=val, line_dash="dot",
                                  line_color=f"{c_r}50",
                                  annotation_text=lbl_r,
                                  annotation_font=dict(size=9, color=c_r,
                                                       family="JetBrains Mono"),
                                  annotation_position="right")
            chart(fig_kp, h=300, title="Planetary Kp Index — 30 Day History")
            fig_kp.update_yaxes(**AX, range=[0, 9.5], title="Kp")
            st.plotly_chart(fig_kp, use_container_width=True)

        with c2:
            lbl2, clr2 = kp_meta(cur_kp)
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.02);
                        border:1px solid rgba(255,255,255,0.05);
                        border-radius:8px; padding:1.5rem;
                        text-align:center; margin-top:1.5rem;'>
                <div style='font-family:JetBrains Mono,monospace; font-size:9px;
                            color:#334155; letter-spacing:0.15em;
                            margin-bottom:10px;'>LATEST Kp</div>
                <div style='font-family:Syne,sans-serif; font-size:52px;
                            font-weight:800; color:{clr2}; line-height:1;'>{cur_kp}</div>
                <div style='font-family:JetBrains Mono,monospace; font-size:11px;
                            color:{clr2}; margin-top:8px;
                            letter-spacing:0.1em;'>{lbl2}</div>
            </div>
            <div style='margin-top:1rem; font-family:JetBrains Mono,monospace;
                        font-size:9px; color:#1e293b; line-height:2.2;'>
                0–3 · QUIET<br>4 · MINOR STORM<br>5 · MODERATE<br>
                6 · STRONG<br>7 · SEVERE<br>8–9 · EXTREME
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No geomagnetic activity in the last 30 days.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — EARTH SENTINEL
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    if eonet_df.empty:
        st.warning("No Earth event data.")
    else:
        # Filters
        all_cats = sorted(eonet_df["category"].unique())
        c1, c2 = st.columns([3, 1])
        with c1:
            sel_cats = st.multiselect(
                "Event categories",
                options=all_cats, default=all_cats,
                format_func=lambda c: f"{cicon(c)} {c}",
            )
        with c2:
            sel_status = event_status

        filtered = eonet_df.copy()
        if sel_cats:
            filtered = filtered[filtered["category"].isin(sel_cats)]
        if sel_status:
            filtered = filtered[filtered["status"].isin(sel_status)]

        section(f"Global Natural Events Map — {len(filtered)} events, {filtered['category'].nunique()} types", "#eab308")

        filtered = filtered.copy()
        filtered["color"] = filtered["category"].apply(ccolor)
        filtered["icon"]  = filtered["category"].apply(cicon)
        filtered["label"] = filtered.apply(
            lambda r: f"{cicon(r['category'])} {r['title']}<br>"
                      f"{r['category']} · {r['date']} · {r['status'].upper()}"
                      + (f"<br>magnitude: {r['mag']} {r['mag_unit']}"
                         if r['mag'] else ""),
            axis=1)

        fig_map = px.scatter_geo(
            filtered, lat="lat", lon="lon", color="category",
            color_discrete_map={c: ccolor(c) for c in all_cats},
            hover_name="label",
            hover_data={"lat": False, "lon": False, "color": False,
                        "icon": False, "label": False, "category": False},
            projection="natural earth",
        )
        fig_map.update_geos(
            bgcolor="#060810",
            landcolor="#0d1117",
            oceancolor="#060810",
            coastlinecolor="rgba(255,255,255,0.08)",
            countrycolor="rgba(255,255,255,0.04)",
            showland=True, showocean=True,
            showcoastlines=True, showcountries=True,
            showframe=False, showlakes=True,
            lakecolor="#060810",
        )
        fig_map.update_traces(
            marker=dict(size=10, opacity=0.9,
                        line=dict(width=0.5, color="rgba(0,0,0,0.5)"))
        )
        fig_map.update_layout(
            paper_bgcolor=BG, height=520,
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(font=dict(family="JetBrains Mono", size=10, color="#475569"),
                        bgcolor=BG, orientation="h", y=-0.06),
        )
        st.plotly_chart(fig_map, use_container_width=True)

        # Category breakdown + timeline
        c1, c2 = st.columns([1, 2])

        with c1:
            section("By Category", "#ef4444")
            cat_cnt = (filtered.groupby("category")
                       .size().reset_index(name="count")
                       .sort_values("count", ascending=False))
            fig_h = px.bar(cat_cnt, x="count", y="category", orientation="h",
                           color="category",
                           color_discrete_map={c: ccolor(c) for c in all_cats},
                           labels={"count": "Events", "category": ""})
            chart(fig_h, h=350, title="", extra={"showlegend": False})
            fig_h.update_yaxes(**AX, autorange="reversed")
            st.plotly_chart(fig_h, use_container_width=True)

        with c2:
            section("Event Timeline — Last 60 Days", "#38bdf8")
            tl = filtered[filtered["date"] != ""].copy()
            tl["date_dt"] = pd.to_datetime(tl["date"], errors="coerce")
            tl = tl.dropna(subset=["date_dt"])
            if not tl.empty:
                daily_ev = (tl.groupby(["date_dt","category"])
                            .size().reset_index(name="n"))
                fig_ev = px.bar(daily_ev, x="date_dt", y="n", color="category",
                                color_discrete_map={c: ccolor(c) for c in all_cats},
                                labels={"n": "Events", "date_dt": ""})
                chart(fig_ev, h=350, title="",
                      extra={"showlegend": False})
                st.plotly_chart(fig_ev, use_container_width=True)
            else:
                st.info("No dated events for timeline.")

        # Detail table
        section("Event Log", "#22c55e")
        tbl2 = filtered[["icon","title","category","status","date","lat","lon","mag","mag_unit"]].rename(
            columns={"icon": "", "mag": "magnitude", "mag_unit": "unit",
                     "lat": "latitude", "lon": "longitude"})
        st.dataframe(tbl2, use_container_width=True, hide_index=True, height=360)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='border-top:1px solid rgba(255,255,255,0.04); margin-top:3rem; padding:1rem 0;
            display:flex; justify-content:space-between;
            font-family:JetBrains Mono,monospace; font-size:9px; color:#1e293b;
            letter-spacing:0.1em;'>
    <span>NASA APOD · NeoWs · EONET · DONKI · EPIC</span>
    <span>github.com/emilianomal · {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</span>
</div>
""", unsafe_allow_html=True)