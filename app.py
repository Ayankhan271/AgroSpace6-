"""AgroSpace6 — Production Satellite Intelligence Dashboard."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

import folium
import numpy as np
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

logger = logging.getLogger(name="agrospace_dashboard")

OPEN_METEO_BASE_URL = "https://open-meteo.com"
DEFAULT_LAT = 31.5204
DEFAULT_LON = 74.3587
MOISTURE_INITIAL = 0.25


def fetch_open_meteo(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "past_days": 14,
        "forecast_days": 7,
        "hourly": "soil_moisture_0_to_1cm,soil_moisture_3_to_9cm,soil_temperature_0cm,shortwave_radiation",
        "daily": "temperature_2m_max,precipitation_sum,et0_fao_evapotranspiration",
        "timezone": "auto",
    }
    response = requests.get(OPEN_METEO_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _series(data: dict, key: str) -> List[float]:
    raw = data.get("hourly", {}).get(key, [])
    if isinstance(raw, dict):
        raw = raw.get("data", [])
    return [float(v) for v in raw if v is not None]


def _daily_series(daily: dict, key: str) -> List[float]:
    raw = daily.get(key, [])
    if isinstance(raw, dict):
        raw = raw.get("data", [])
    return [float(v) if v is not None else 0.0 for v in raw]


def compute_metrics(data: dict) -> dict:
    daily = data.get("daily") or {}

    soil_0 = _series(data, "soil_moisture_0_to_1cm")
    soil_3 = _series(data, "soil_moisture_3_to_9cm")
    temp = _series(data, "soil_temperature_0cm")
    shortwave = _series(data, "shortwave_radiation")
    precip = _daily_series(daily, "precipitation_sum")
    et0 = _daily_series(daily, "et0_fao_evapotranspiration")
    temp_daily = _daily_series(daily, "temperature_2m_max")

    soil_moisture = float(soil_0[-1]) if soil_0 else MOISTURE_INITIAL
    soil_moisture_deep = float(soil_3[-1]) if soil_3 else MOISTURE_INITIAL
    soil_temp = float(temp[-1]) if temp else 25.0
    sw = float(np.mean(shortwave[-24:])) if shortwave else 250.0
    precipitation = float(precip[-1]) if precip else 0.0
    et0_value = float(et0[-1]) if et0 else 0.0
    daily_temp_max = float(temp_daily[-1]) if temp_daily else 25.0

    avg_soil_0 = float(np.mean(soil_0[-24:])) if soil_0 else MOISTURE_INITIAL
    avg_temp = float(np.mean(temp[-24:])) if temp else 25.0
    cvi = float(np.clip((sw / 600.0) * 0.4 + (soil_moisture / 0.45) * 0.6, 0.15, 0.92))
    disease_risk = float(np.clip((avg_soil_0 / 0.4) * 0.5 + ((avg_temp - 25.0) / 10.0) * 0.5, 0.05, 0.95))
    estimated_yield = float(max(0.5, cvi * 6.8))

    return {
        "soil_moisture": soil_moisture,
        "soil_moisture_deep": soil_moisture_deep,
        "soil_temperature": soil_temp,
        "shortwave_radiation": sw,
        "precipitation": precipitation,
        "et0": et0_value,
        "daily_temp_max": daily_temp_max,
        "cvi": cvi,
        "disease_risk": disease_risk,
        "estimated_yield": estimated_yield,
        "times": daily.get("time", []),
        "precip_data": precip,
        "et0_data": et0,
    }


def render_water_balance_chart(metrics: dict):
    times = metrics.get("times", [])
    precip_data = metrics.get("precip_data", [])
    et0_data = metrics.get("et0_data", [])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=precip_data, mode="lines+markers", name="Precipitation (mm)"))
    fig.add_trace(go.Scatter(x=times, y=et0_data, mode="lines+markers", name="ET0 Water Loss (mm)"))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0B0E14",
        plot_bgcolor="#0B0E14",
        font=dict(color="#E6EDF3", family="Inter, sans-serif"),
        xaxis=dict(title="Date", gridcolor="#1F2937", zerolinecolor="#1F2937"),
        yaxis=dict(title="Precipitation / ET0 (mm)", gridcolor="#1F2937", zerolinecolor="#1F2937"),
        title=dict(text="21-Day Water Balance (Rainfall vs ET0)", x=0.5, xanchor="center"),
        hovermode="x unified",
    )
    return fig


def generate_ai_response(question: str, metrics: dict) -> str:
    q = question.lower()
    base = (
        f"Live Open-Meteo telemetry indicates a Canopy Vigour Index of **{metrics.get('cvi', 0.0):.3f}**, "
        f"an estimated yield of **{metrics.get('estimated_yield', 0.0):.2f} t/ha**, and a disease risk score of **{metrics.get('disease_risk', 0.0):.2f}**."
    )
    if "yield" in q or "production" in q:
        return f"{base} The yield forecast is derived from the current canopy vigour and should be validated against ground truth before underwriting."
    if "disease" in q or "fungal" in q or "pest" in q:
        return f"{base} The 10-15 day fungal/pest early warning risk is calculated based on current soil moisture and temperature conditions."
    if "water" in q or "irrigation" in q or "balance" in q:
        return f"{base} The 21-day water balance shows ET0 of **{metrics.get('et0', 0.0):.2f} mm/day** against precipitation of **{metrics.get('precipitation', 0.0):.2f} mm/day**."
    if "soil" in q or "moisture" in q:
        return f"{base} Current surface soil moisture is **{metrics.get('soil_moisture', 0.0)*100:.1f}%**, with deep-layer moisture at **{metrics.get('soil_moisture_deep', 0.0)*100:.1f}%**."
    return f"{base} I recommend combining this satellite-derived signal with ground IoT soil measurements for final underwriting."


def generate_report(metrics: dict, lat: float, lon: float, start_date: str, end_date: str) -> str:
    return (
        "AgroSpace6 Field Verification Report\n"
        "==========================================\n"
        f"Generated: {datetime.now().isoformat()}\n"
        f"Coordinates: {lat}, {lon}\n"
        f"Date Range: {start_date} to {end_date}\n"
        f"Canopy Vigour Index: {metrics.get('cvi', 0.0):.3f}\n"
        f"Estimated Yield: {metrics.get('estimated_yield', 0.0):.2f} t/ha\n"
        f"Disease Risk: {metrics.get('disease_risk', 0.0):.2f}\n"
        f"Soil Moisture: {metrics.get('soil_moisture', 0.0)*100:.1f}%\n"
        f"ET0: {metrics.get('et0', 0.0):.2f} mm/day\n"
        f"Precipitation: {metrics.get('precipitation', 0.0):.2f} mm/day\n"
        "==========================================\n"
    )


def make_folium_map(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> folium.Map:
    center_lat = (min_lat + max_lat) / 2.0
    center_lon = (min_lon + max_lon) / 2.0
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    folium.TileLayer(
        tiles="https://arcgisonline.com{z}/{y}/{x}",
        name="Satellite",
        attr="Esri",
        overlay=False,
    ).add_to(fmap)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        name="OpenStreetMap",
        attr="OpenStreetMap",
        overlay=False,
    ).add_to(fmap)
    folium.Rectangle(
        bounds=[[min_lat, min_lon], [max_lat, max_lon]],
        color="green",
        fill=True,
        fill_color="green",
        fill_opacity=0.2,
        weight=2,
    ).add_to(fmap)
    folium.CircleMarker(
        location=[center_lat, center_lon],
        radius=5,
        color="red",
        fill=True,
        fill_color="red",
    ).add_to(fmap)
    folium.LayerControl().add_to(fmap)
    return fmap


def main() -> None:
    st.set_page_config(page_title="AgroSpace6", layout="wide", initial_sidebar_state="expanded")
    st.title("🌾 AgroSpace6 — Production Satellite Intelligence")
    st.markdown("Real-time open-source satellite and soil telemetry for elite crop intelligence.")

    with st.sidebar:
        st.header("📡 Plot Coordinates")
        lat = st.number_input("Center Latitude", value=DEFAULT_LAT, step=0.0001, format="%.4f")
        lon = st.number_input("Center Longitude", value=DEFAULT_LON, step=0.0001, format="%.4f")
        min_lat = st.number_input("Min Latitude", value=round(lat - 0.01, 4), step=0.0001, format="%.4f")
        min_lon = st.number_input("Min Longitude", value=round(lon - 0.01, 4), step=0.0001, format="%.4f")
        max_lat = st.number_input("Max Latitude", value=round(lat + 0.01, 4), step=0.0001, format="%.4f")
        max_lon = st.number_input("Max Longitude", value=round(lon + 0.01, 4), step=0.0001, format="%.4f")
        fetch_button = st.button("🚀 Fetch Live Open-Meteo Telemetry", type="primary")

    st.header("🗺️ Field Map")
    fmap = make_folium_map(min_lat, min_lon, max_lat, max_lon)
    st_folium(fmap, width=900, height=450)

    if fetch_button:
        with st.spinner("Fetching live Open-Meteo Agri-Satellite & Soil data..."):
            data = fetch_open_meteo(lat=lat, lon=lon)
            st.session_state["agrospace_metrics"] = compute_metrics(data)
            st.session_state["agrospace_start_date"] = (datetime.now().date() - timedelta(days=14)).isoformat()
            st.session_state["agrospace_end_date"] = (datetime.now().date() + timedelta(days=7)).isoformat()

    metrics = st.session_state.get("agrospace_metrics")
    if metrics is None:
        st.info("👈 Click **Fetch Live Open-Meteo Telemetry** in the sidebar to load real satellite & soil intelligence.")
        return

    st.header("📊 Live Crop Intelligence")
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        st.metric(label="Canopy Vigour Index", value=f"{metrics.get('cvi', 0.0):.3f}")
    with metric_col2:
        st.metric(label="Estimated Yield (t/ha)", value=f"{metrics.get('estimated_yield', 0.0):.2f}")
    with metric_col3:
        st.metric(label="Disease Risk", value=f"{metrics.get('disease_risk', 0.0):.2f}")
    with metric_col4:
        st.metric(label="Soil Moisture", value=f"{metrics.get('soil_moisture', 0.0)*100:.1f}%")

    st.header("💧 21-Day Water Balance")
