import streamlit as st
import folium
from streamlit_folium import st_folium
import pystac_client
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

st.set_page_config(page_title="AgroSpace6 - Enterprise Satellite Intelligence", layout="wide")

st.title("🛰️ AgroSpace6: Enterprise Satellite Crop Intelligence")
st.markdown("**Live ESA Sentinel-2 (10m Resolution) Orbital Analytics Engine**")
st.markdown("---")

st.sidebar.header("📡 Field Calibration & Target")
lat = st.sidebar.number_input("Field Latitude:", value=30.9010, format="%.4f")
lon = st.sidebar.number_input("Field Longitude:", value=75.8573, format="%.4f")
buffer_deg = st.sidebar.slider("Scan Radius (km approx):", 0.5, 5.0, 1.5) * 0.009
days_back = st.sidebar.slider("Lookback Window (Days):", 15, 90, 45)
max_cloud = st.sidebar.slider("Max Cloud Cover (%):", 5, 50, 20)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Click anywhere on the satellite map to see exact farm coordinates!")

col_map, col_data = st.columns([1.2, 1])

with col_map:
    st.subheader("🌍 Live Orbital Field Selector")
    m = folium.Map(
        location=[lat, lon],
        zoom_start=15,
        tiles="https://arcgisonline.com{z}/{y}/{x}",
        attr="Esri World Imagery"
    )
    
    min_lon, min_lat = lon - buffer_deg, lat - buffer_deg
    max_lon, max_lat = lon + buffer_deg, lat + buffer_deg
    bbox = [min_lon, min_lat, max_lon, max_lat]
    
    folium.Rectangle(
        bounds=[[min_lat, min_lon], [max_lat, max_lon]],
        color="#00FF00",
        weight=3,
        fill=True,
        fill_opacity=0.1,
        tooltip="Target Scan Zone"
    ).add_to(m)
    folium.Marker([lat, lon], tooltip="Field Center").add_to(m)
    
    map_data = st_folium(m, height=450, width="100%")
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]
        st.caption(f"📍 Last Clicked Coordinates: **{clicked_lat:.4f}, {clicked_lon:.4f}**")

with col_data:
    st.subheader("🧠 Real-Time Spectral & Crop Health Analysis")
    if st.button("🚀 Fetch Live Sentinel-2 Satellite Data", type="primary", use_container_width=True):
        with st.spinner("Connecting to ESA Sentinel-2 Open Orbital Catalog..."):
            try:
                catalog = pystac_client.Client.open("https://element84.com")
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=days_back)
                time_range = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"

                search = catalog.search(
                    collections=["sentinel-2-l2a"],
                    bbox=bbox,
                    datetime=time_range,
                    query={"eo:cloud_cover": {"lt": max_cloud}},
                )
                items = list(search.items())

                if not items:
                    st.warning("No cloud-free satellite pass found. Increase 'Lookback Window' or 'Max Cloud Cover'.")
                else:
                    best_item = sorted(items, key=lambda x: x.properties["eo:cloud_cover"])
                    scene_date = best_item.datetime.strftime("%Y-%m-%d")
                    cloud_pct = best_item.properties["eo:cloud_cover"]
                    
                    st.success(f"✔ Satellite Pass Locked! Date: **{scene_date}** | Cloud Cover: **{cloud_pct:.1f}%**")

                    red_href = best_item.assets["red"].href
                    nir_href = best_item.assets["nir"].href

                    with rasterio.open(red_href) as src_red, rasterio.open(nir_href) as src_nir:
                        proj_bbox = transform_bounds("EPSG:4326", src_red.crs, *bbox)
                        win_red = from_bounds(*proj_bbox, src_red.transform)
                        win_nir = from_bounds(*proj_bbox, src_nir.transform)

                        red = src_red.read(1, window=win_red).astype("float32")
                        nir = src_nir.read(1, window=win_nir).astype("float32")

                    np.seterr(divide="ignore", invalid="ignore")
                    ndvi = (nir - red) / (nir + red)
                    ndvi = np.clip(ndvi, -1.0, 1.0)
                    mean_ndvi = float(np.nanmean(ndvi))

                    if mean_ndvi > 0.6:
                        status = "🟢 Thriving / High Biomass"
                        est_yield = 4.5 + (mean_ndvi - 0.6) * 3.0
                    elif mean_ndvi > 0.35:
                        status = "🟡 Moderate / Needs Irrigation Check"
                        est_yield = 3.0 + (mean_ndvi - 0.35) * 5.0
                    else:
                        status = "🔴 Stressed / Bare Soil or Fallow"
                        est_yield = 1.2

                    m1, m2, m3 = st.columns(3)
                    m1.metric("True Mean NDVI", f"{mean_ndvi:.3f}")
                    m2.metric("Est. Yield (t/ha)", f"{est_yield:.2f}")
                    m3.metric("Satellite", "Sentinel-2 L2A")
                    st.info(f"**Crop Diagnosis:** {status}")

                    fig, ax = plt.subplots(figsize=(6, 4))
                    im = ax.imshow(ndvi, cmap="RdYlGn", vmin=-0.1, vmax=0.9)
                    plt.colorbar(im, ax=ax, label="NDVI Index")
                    ax.set_title(f"Live NDVI Crop Health Map ({scene_date})")
                    ax.axis("off")
                    st.pyplot(fig)

                    report_text = f"""AGROSPACE6 ENTERPRISE SATELLITE INTELLIGENCE REPORT
--------------------------------------------------
Date Generated : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
Satellite Pass : {scene_date} (Sentinel-2 L2A)
Coordinates    : {lat:.4f}, {lon:.4f}
Cloud Cover    : {cloud_pct:.1f}%
True Mean NDVI : {mean_ndvi:.3f}
Crop Status    : {status}
Estimated Yield: {est_yield:.2f} Metric Tons / Hectare
--------------------------------------------------
Verified by AgroSpace6 Orbital Engine
"""
                    st.download_button(
                        label="📥 Download Official Bank/Insurance Report",
                        data=report_text,
                        file_name=f"AgroSpace6_Report_{scene_date}.txt",
                        mime="text/plain"
                    )

            except Exception as e:
                st.error(f"Orbital Connection Error: {e}")
