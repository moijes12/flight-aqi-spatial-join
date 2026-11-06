import pydeck as pdk
import streamlit as st
from google.cloud import bigquery

st.set_page_config(
    page_title="Flight & Air Quality Spatial Analytics", page_layout="wide"
)

st.title("✈️ Flight Telemetry & Air Quality Spatial Join")
st.markdown(
    "Real-time correlation of aircraft proximity and atmospheric $PM_{2.5}$ readings."
)


@st.cache_data(ttl=600)
def load_spatial_data():
    """Query recent joined spatial data from BigQuery."""
    client = bigquery.Client()
    query = """
        SELECT
            timestamp,
            icao24,
            callsign,
            ST_Y(flight_location) as flight_lat,
            ST_X(flight_location) as flight_lon,
            sensor_id,
            ST_Y(sensor_location) as sensor_lat,
            ST_X(sensor_location) as sensor_lon,
            pm25,
            distance_meters
        FROM `geo_analytics.fct_flight_air_quality`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        ORDER BY timestamp DESC
        LIMIT 1000
    """
    return client.query(query).to_dataframe()


# Load data
with st.spinner("Fetching spatial join metrics from BigQuery..."):
    df = load_spatial_data()

if df.empty:
    st.warning(
        "No spatial join records found in BigQuery for the last 24 hours. Ensure your pipeline is streaming data."
    )
else:
    # Sidebar filters
    st.sidebar.header("Filter Controls")
    max_distance = st.sidebar.slider(
        "Max Distance Threshold (meters)", 1000, 20000, 10000, step=500
    )

    filtered_df = df[df["distance_meters"] <= max_distance]

    st.metric(label="Matched Intersections (24h)", value=len(filtered_df))

    # PyDeck Map Layer
    flight_layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_df,
        get_position=["flight_lon", "flight_lat"],
        get_color=[255, 75, 75, 160],
        get_radius=3000,
        pickable=True,
    )

    sensor_layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_df,
        get_position=["sensor_lon", "sensor_lat"],
        get_color=[0, 150, 255, 200],
        get_radius=5000,
        pickable=True,
    )

    # Initial view centered around Pune / target airspace
    initial_view_state = pdk.ViewState(
        latitude=float(filtered_df["flight_lat"].mean())
        if not filtered_df.empty
        else 18.5204,
        longitude=float(filtered_df["flight_lon"].mean())
        if not filtered_df.empty
        else 73.8567,
        zoom=9,
        pitch=30,
    )

    r = pdk.Deck(
        layers=[flight_layer, sensor_layer],
        initial_view_state=initial_view_state,
        tooltip={
            "text": "Flight: {callsign} ({icao24})\nSensor: {sensor_id}\nPM2.5: {pm25} µg/m³\nDistance: {distance_meters}m"
        },
    )

    st.pydeck_chart(r)

    # Data Table Preview
    with st.expander("View Raw Spatial Records"):
        st.dataframe(filtered_df)
