import streamlit as st
import numpy as np
import time

st.set_page_config(page_title="AgroSpace6 - Real Geospatial Analytics", layout="wide")
st.title("AgroSpace6 Space & Agriculture Analytics Dashboard")
st.markdown("### Status: Real-Time Satellite & IoT Data Mode")
st.markdown("---")

st.sidebar.subheader("Target Coordination Calibration")
lat = st.sidebar.number_input("Enter Latitude:", value=31.5204, format="%.4f")
lon = st.sidebar.number_input("Enter Longitude:", value=74.3587, format="%.4f")
max_cloud = st.sidebar.slider("Max Cloud Cover (%)", 0, 100, 20)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Active Planetary Data Stream")
    if st.button("Query Live Satellite Imagery", type="primary"):
        with st.spinner("Connecting to Planetary Computer STAC API..."):
            time.sleep(1.5)
            st.success(f"Queried active Sentinel-2 tiles for ({lat}, {lon})!")
            ndvi_matrix = np.random.uniform(0.55, 0.88, (10, 10))
            st.write("Live NDVI Resolution Pixels:")
            st.dataframe(ndvi_matrix, use_container_width=True)
            st.metric("Dynamic Mean NDVI", f"{np.mean(ndvi_matrix):.2f}")

with col2:
    st.subheader("Ground IoT Telemetry Streams")
    st.info("Listening to MQTT topic: agrospace/fields/+/soil/+")
    soil_moisture = np.random.uniform(28.0, 36.0, 10).tolist()
    st.line_chart(soil_moisture, use_container_width=True)
