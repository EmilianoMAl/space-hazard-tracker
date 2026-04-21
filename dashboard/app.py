"""
app.py — Space Hazard Tracker Dashboard
Tema oscuro estilo NASA mission control.
Tres tabs: APOD / Asteroid Tracker / Earth Events
"""

import os
import logging
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

# ── Config ────────────────────────────────────────────────────────────────────
NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
NASA_BASE = "https://api.nasa.gov"
EONET_BASE = "https://eonet.gsfc.nasa.gov/api/v3"

st.set_page_config(
    page_title="Space Hazard Tracker",
    page_icon="☄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling: tema oscuro NASA mission control ─────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap');

html, body, [data-testid="stApp"] {
    background-color: #050A14 !important;
    color: #C8D8E8 !important;
}

[data-testid="stSidebar"] {
    background-color: #080F1E !important;
    border-right: 1px solid #0D2137 !important;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Rajdhani', sans-serif !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}

p, div, span, label, .stMarkdown {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important;
}

[data-testid="metric-container"] {
    background: #080F1E !important;
    border: 1px solid #0D2137 !important;
    border-radius: 4px !important;
    padding: 16px !important;
}
[data-testid="metric-container"] label {
    color: #4A7C9E !important;
    font-size: 11px !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Share Tech Mono', monospace !important;
    color: #00D4FF !important;
    font-size: 28px !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    color: #FFB800 !important;
}

[data-testid="stTabs"] button {
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: #4A7C9E !important;
    border-bottom: 2px solid transparent !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00D4FF !important;
    border-bottom: 2px solid #00D4FF !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #0D2137 !important;
}

[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p {
    color: #4A7C9E !important;
    letter-spacing: 0.06em !important;
}

hr { border-color: #0D2137 !important; }

.section-bar {
    background: linear-gradient(90deg, #0D2137 0%, transparent 100%);
    border-left: 3px solid #00D4FF;
    padding: 8px 16px;
    margin: 1.5rem 0 1rem;
    font-family: 'Rajdhani', sans-serif;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #C8D8E8;
}
</style>
""", unsafe_allow_html=True)

# ── Plotly: mismo tema oscuro para todas las gráficas ────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="#050A14",
    plot_bgcolor="#080F1E",
    font=dict(family="Share Tech Mono", color="#C8D8E8", size=11),
    colorway=["#00D4FF", "#FFB800", "#FF4444", "#00FF9F", "#FF6B35"],
    xaxis=dict(gridcolor="#0D2137", linecolor="#0D2137"),
    yaxis=dict(gridcolor="#0D2137", linecolor="#0D2137"),
    margin=dict(l=40, r=20, t=40, b=40),
)

RISK_COLORS = {"HIGH": "#FF4444", "MEDIUM": "#FFB800", "LOW": "#00D4FF"}

# ── Funciones NASA API ────────────────────────────────────────────────────────


@st.cache_data(ttl=3600)
def get_apod():
    """Trae la foto del día. Cache de 1 hora."""
    try:
        r = requests.get(
            f"{NASA_BASE}/planetary/apod",
            params={"api_key": NASA_API_KEY},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"APOD error: {e}")
        return None


@st.cache_data(ttl=3600)
def get_neo_feed(days: int = 7) -> pd.DataFrame:
    """Trae asteroides para los próximos N días. Cache de 1 hora."""
    start = datetime.utcnow().strftime("%Y-%m-%d")
    end = (datetime.utcnow() + timedelta(days=days - 1)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{NASA_BASE}/neo/rest/v1/feed",
            params={"start_date": start, "end_date": end,
                    "api_key": NASA_API_KEY},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"NeoWs error: {e}")
        return pd.DataFrame()

    rows = []
    for date_str, objects in data.get("near_earth_objects", {}).items():
        for obj in objects:
            ap = obj["close_approach_data"][0] if obj.get(
                "close_approach_data") else {}
            diam = obj.get("estimated_diameter", {}).get("kilometers", {})
            miss = float(ap.get("miss_distance", {}).get("kilometers", 0))
            rows.append({
                "name":         obj["name"].strip("()"),
                "date":         date_str,
                "diam_min_km":  round(float(diam.get("estimated_diameter_min", 0)), 4),
                "diam_max_km":  round(float(diam.get("estimated_diameter_max", 0)), 4),
                "miss_km":      round(miss / 1_000_000, 3),
                "miss_lunar":   round(float(ap.get("miss_distance", {}).get("lunar", 0)), 1),
                "velocity_kmh": round(float(ap.get("relative_velocity", {}).get("kilometers_per_hour", 0))),
                "hazardous":    obj.get("is_potentially_hazardous_asteroid", False),
                "magnitude":    obj.get("absolute_magnitude_h"),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    def risk(row):
        km = row["miss_km"] * 1_000_000
        if km < 1_000_000 or (row["hazardous"] and km < 10_000_000):
            return "HIGH"
        if km < 10_000_000:
            return "MEDIUM"
        return "LOW"

    df["risk"] = df.apply(risk, axis=1)
    df = df.sort_values(["date", "miss_km"])
    return df


@st.cache_data(ttl=1800)
def get_eonet_events() -> pd.DataFrame:
    """Trae eventos naturales activos. Cache de 30 minutos."""
    try:
        r = requests.get(
            f"{EONET_BASE}/events",
            params={"status": "open", "limit": 200},
            timeout=20,
        )
        r.raise_for_status()
        events = r.json().get("events", [])
    except Exception as e:
        logger.error(f"EONET error: {e}")
        return pd.DataFrame()

    rows = []
    for ev in events:
        cat = ev.get("categories", [{}])[0]
        geo = ev.get("geometry", [{}])[-1] if ev.get("geometry") else {}
        coords = geo.get("coordinates", [None, None])
        if not coords or len(coords) < 2:
            continue
        rows.append({
            "id":       ev["id"],
            "title":    ev["title"],
            "category": cat.get("title", "Unknown"),
            "date":     geo.get("date", "")[:10],
            "lon":      coords[0],
            "lat":      coords[1],
        })

    return pd.DataFrame(rows)


# ── Colores e iconos por categoría de evento ──────────────────────────────────
CATEGORY_ICON = {
    "Wildfires":        "🔥",
    "Severe Storms":    "🌀",
    "Volcanoes":        "🌋",
    "Floods":           "🌊",
    "Earthquakes":      "⚡",
    "Landslides":       "⛰",
    "Sea and Lake Ice": "❄️",
    "Drought":          "🌵",
}
CATEGORY_COLOR = {
    "Wildfires":        "#FF4444",
    "Severe Storms":    "#00D4FF",
    "Volcanoes":        "#FF6B35",
    "Floods":           "#4488FF",
    "Earthquakes":      "#FFB800",
    "Landslides":       "#AA7700",
    "Sea and Lake Ice": "#AADDFF",
    "Drought":          "#FFD080",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 1rem 0 0.5rem;'>
        <div style='font-family:Rajdhani,sans-serif; font-size:22px; font-weight:700;
                    letter-spacing:0.15em; color:#00D4FF;'>☄ SPACE HAZARD</div>
        <div style='font-family:Rajdhani,sans-serif; font-size:14px; font-weight:600;
                    letter-spacing:0.2em; color:#4A7C9E;'>TRACKER v1.0</div>
    </div>
    <hr>
    """, unsafe_allow_html=True)

    st.markdown("**NEO WINDOW**")
    neo_days = st.slider("Days to look ahead", min_value=1, max_value=7, value=7)

    st.markdown("**RISK FILTER**")
    risk_filter = st.multiselect(
        "Show risk levels",
        options=["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM", "LOW"],
    )

    st.markdown("<hr>", unsafe_allow_html=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d  %H:%M UTC")
    st.markdown(
        f"<small style='color:#4A7C9E'>LAST SYNC<br>{ts}</small>",
        unsafe_allow_html=True,
    )

    if st.button("↻  Refresh data"):
        st.cache_data.clear()
        st.rerun()


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='border-bottom: 1px solid #0D2137; padding-bottom: 12px; margin-bottom: 1.5rem;'>
    <span style='font-family:Rajdhani,sans-serif; font-size:32px; font-weight:700;
                 letter-spacing:0.15em; color:#C8D8E8;'>SPACE HAZARD TRACKER</span>
    <span style='font-family:Share Tech Mono,monospace; font-size:12px;
                 color:#4A7C9E; margin-left:16px;'>// NASA OPEN APIS — LIVE DATA</span>
</div>
""", unsafe_allow_html=True)


# ── Carga de datos ────────────────────────────────────────────────────────────
with st.spinner("Establishing link with NASA servers..."):
    apod_data = get_apod()
    neo_df    = get_neo_feed(days=neo_days)
    eonet_df  = get_eonet_events()


# ── KPIs ──────────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

total_neos = len(neo_df)          if not neo_df.empty   else 0
high_neos  = len(neo_df[neo_df["risk"] == "HIGH"]) if not neo_df.empty else 0
hazardous  = int(neo_df["hazardous"].sum())        if not neo_df.empty else 0
total_evts = len(eonet_df)        if not eonet_df.empty else 0
categories = eonet_df["category"].nunique()        if not eonet_df.empty else 0

col1.metric("NEAR-EARTH OBJECTS",    total_neos, f"{neo_days}d window")
col2.metric("HIGH RISK",             high_neos,  "asteroids")
col3.metric("POTENTIALLY HAZARDOUS", hazardous,  "flagged by NASA")
col4.metric("ACTIVE EARTH EVENTS",   total_evts, "EONET open")
col5.metric("EVENT TYPES",           categories, "categories")

st.markdown("<hr>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🌌  Astronomy Picture",
    "☄️  Asteroid Tracker",
    "🌍  Earth Events",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — APOD
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    if apod_data:
        st.markdown(
            f'<div class="section-bar">{apod_data.get("title", "")}</div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns([3, 2])
        with left:
            media = apod_data.get("media_type", "image")
            url   = apod_data.get("hdurl") or apod_data.get("url", "")
            if media == "image" and url:
                st.image(url, use_container_width=True)
            elif media == "video":
                st.video(url)
        with right:
            date_str  = apod_data.get("date", "")
            copyright = apod_data.get("copyright", "NASA / Public Domain")
            st.markdown(f"""
            <div style='font-family:Share Tech Mono,monospace; font-size:11px;
                        color:#4A7C9E; letter-spacing:0.1em; margin-bottom:8px;'>
                DATE: {date_str} &nbsp;|&nbsp; © {copyright}
            </div>
            """, unsafe_allow_html=True)
            explanation = apod_data.get("explanation", "")
            st.markdown(f"""
            <div style='font-family:Share Tech Mono,monospace; font-size:13px;
                        line-height:1.8; color:#C8D8E8;'>{explanation}</div>
            """, unsafe_allow_html=True)
    else:
        st.warning("Could not load APOD. Check your API key or try again later.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ASTEROID TRACKER
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    if neo_df.empty:
        st.warning("No asteroid data available.")
    else:
        display_df = neo_df[neo_df["risk"].isin(risk_filter)].copy() if risk_filter else neo_df.copy()

        st.markdown('<div class="section-bar">Close Approach Risk Map</div>', unsafe_allow_html=True)

        # Scatter: tamaño vs distancia
        fig_scatter = px.scatter(
            display_df,
            x="miss_km",
            y="diam_max_km",
            color="risk",
            color_discrete_map=RISK_COLORS,
            size="velocity_kmh",
            size_max=28,
            hover_name="name",
            hover_data={
                "date": True, "miss_lunar": True,
                "hazardous": True, "velocity_kmh": True, "risk": True,
            },
            labels={
                "miss_km":    "Miss Distance (million km)",
                "diam_max_km": "Estimated Diameter (km)",
                "velocity_kmh": "Velocity (km/h)",
            },
            title="Asteroid Risk Map — Size vs Miss Distance",
        )
        fig_scatter.add_vline(
            x=1.0, line_dash="dot", line_color="#FF4444",
            annotation_text="1M km", annotation_font_color="#FF4444",
        )
        fig_scatter.add_vline(
            x=10.0, line_dash="dot", line_color="#FFB800",
            annotation_text="10M km", annotation_font_color="#FFB800",
        )
        fig_scatter.update_layout(**PLOTLY_LAYOUT, height=420)
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Bar + Pie
        c1, c2 = st.columns([2, 1])
        with c1:
            daily = (
                display_df.groupby(["date", "risk"])
                .size()
                .reset_index(name="count")
            )
            fig_bar = px.bar(
                daily, x="date", y="count", color="risk",
                color_discrete_map=RISK_COLORS,
                labels={"count": "NEOs", "date": ""},
                title="Daily Near-Earth Object Count",
            )
            fig_bar.update_layout(**PLOTLY_LAYOUT, height=320)
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            risk_count = display_df["risk"].value_counts().reset_index()
            risk_count.columns = ["risk", "count"]
            fig_pie = px.pie(
                risk_count, names="risk", values="count",
                color="risk", color_discrete_map=RISK_COLORS,
                title="Risk Distribution",
                hole=0.55,
            )
            fig_pie.update_traces(textfont_family="Share Tech Mono")
            fig_pie.update_layout(
                **PLOTLY_LAYOUT, height=320,
                showlegend=True,
                legend=dict(orientation="h", y=-0.1),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        # Tabla de datos
        st.markdown('<div class="section-bar">Asteroid Data Log</div>', unsafe_allow_html=True)
        table_df = display_df[[
            "name", "date", "risk", "miss_km", "miss_lunar",
            "diam_max_km", "velocity_kmh", "hazardous",
        ]].rename(columns={
            "miss_km":      "miss dist (M km)",
            "miss_lunar":   "miss dist (LD)",
            "diam_max_km":  "diam max (km)",
            "velocity_kmh": "velocity (km/h)",
        })
        st.dataframe(
            table_df.style.map(
                lambda v: f"color: {RISK_COLORS.get(v, '#C8D8E8')}",
                subset=["risk"],
            ),
            use_container_width=True,
            hide_index=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EARTH EVENTS
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    if eonet_df.empty:
        st.warning("No Earth events available.")
    else:
        all_cats = sorted(eonet_df["category"].unique())
        selected_cats = st.multiselect(
            "Filter categories",
            options=all_cats,
            default=all_cats,
            format_func=lambda c: f"{CATEGORY_ICON.get(c, '🌐')} {c}",
        )

        filtered = (
            eonet_df[eonet_df["category"].isin(selected_cats)]
            if selected_cats else eonet_df
        )

        st.markdown(
            '<div class="section-bar">Active Natural Events — World Map</div>',
            unsafe_allow_html=True,
        )

        filtered = filtered.copy()
        filtered["color"] = filtered["category"].map(CATEGORY_COLOR).fillna("#FFFFFF")
        filtered["icon"]  = filtered["category"].map(CATEGORY_ICON).fillna("🌐")

        fig_map = px.scatter_geo(
            filtered,
            lat="lat", lon="lon",
            color="category",
            color_discrete_map=CATEGORY_COLOR,
            hover_name="title",
            hover_data={"date": True, "category": True, "lat": False, "lon": False},
            projection="natural earth",
        )
        fig_map.update_geos(
            bgcolor="#050A14",
            landcolor="#0D2137",
            oceancolor="#080F1E",
            coastlinecolor="#1A3855",
            countrycolor="#0D2137",
            showland=True, showocean=True,
            showcoastlines=True, showcountries=True,
            showframe=False,
        )
        fig_map.update_traces(
            marker=dict(size=10, opacity=0.85, line=dict(width=0.5, color="#050A14"))
        )
        fig_map.update_layout(
            **PLOTLY_LAYOUT, height=520,
            legend=dict(orientation="h", y=-0.06, font=dict(size=11)),
        )
        st.plotly_chart(fig_map, use_container_width=True)

        # Breakdown por categoría
        c1, c2 = st.columns([1, 2])
        with c1:
            cat_counts = (
                filtered.groupby("category")
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
            )
            for _, row in cat_counts.iterrows():
                color = CATEGORY_COLOR.get(row["category"], "#FFFFFF")
                icon  = CATEGORY_ICON.get(row["category"], "🌐")
                st.markdown(
                    f"<div style='font-family:Share Tech Mono,monospace; font-size:13px;"
                    f"color:{color}; padding:3px 0;'>"
                    f"{icon} {row['category']}: <strong>{row['count']}</strong></div>",
                    unsafe_allow_html=True,
                )
        with c2:
            fig_cat = px.bar(
                cat_counts,
                x="count", y="category",
                orientation="h",
                color="category",
                color_discrete_map=CATEGORY_COLOR,
                labels={"count": "Active events", "category": ""},
                title="Events by Category",
            )
            fig_cat.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
            st.plotly_chart(fig_cat, use_container_width=True)

        # Lista de eventos
        st.markdown('<div class="section-bar">Event Log</div>', unsafe_allow_html=True)
        st.dataframe(
            filtered[["icon", "title", "category", "date", "lat", "lon"]].rename(
                columns={"icon": "", "lat": "latitude", "lon": "longitude"}
            ),
            use_container_width=True,
            hide_index=True,
        )


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='border-top:1px solid #0D2137; margin-top:2rem; padding-top:12px;
            font-family:Share Tech Mono,monospace; font-size:11px; color:#4A7C9E;
            text-align:center;'>
    DATA SOURCES: NASA NeoWs &nbsp;|&nbsp; NASA EONET &nbsp;|&nbsp; NASA APOD
    &nbsp;//&nbsp; Built with Streamlit + Plotly
    &nbsp;//&nbsp; github.com/emilianomal
</div>
""", unsafe_allow_html=True)