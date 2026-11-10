import pandas as pd
import pydeck as pdk
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

st.set_page_config(page_title="Flight & Air Quality Spatial Analytics", layout="wide")

st.title("✈️ Flight Telemetry & Air Quality Spatial Join")
st.markdown(
    "Real-time correlation of aircraft proximity and atmospheric $PM_{2.5}$ readings."
)


@st.cache_resource
def get_bigquery_client():
    # Production: Load from Streamlit Community Cloud secrets
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        return bigquery.Client(
            credentials=credentials, project=creds_dict["project_id"]
        )
    else:
        # Local development / fallback
        return bigquery.Client(project="flight-aqi-spatial-join")


client = get_bigquery_client()


@st.cache_data(ttl=60)
def load_spatial_data():
    """Query recent joined spatial data from the BigQuery spatial view."""
    query = """
        SELECT
            timestamp,
            icao24,
            callsign,
            flight_lat,
            flight_lon,
            sensor_id,
            sensor_lat,
            sensor_lon,
            pm25,
            distance_meters
        FROM `flight-aqi-spatial-join.geo_analytics.v_flight_air_quality_spatial`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        ORDER BY timestamp DESC
        LIMIT 1000
    """
    return client.query(query).to_dataframe()


# Load data
with st.spinner("Fetching spatial join metrics from BigQuery view..."):
    df = load_spatial_data()

if df.empty:
    st.warning(
        "No spatial join records found in BigQuery for the last 24 hours. Ensure "
        "your Beam streaming pipeline is active and pushing records."
    )
else:
    # Sidebar filters
    st.sidebar.header("Filter Controls")

    min_dist = int(df["distance_meters"].min()) if not df.empty else 0
    max_dist = int(df["distance_meters"].max()) if not df.empty else 50000
    if max_dist <= min_dist:
        max_dist = min_dist + 10000

    max_distance = st.sidebar.slider(
        "Max Distance Threshold (meters)",
        min_value=0,
        max_value=max(20000, max_dist),
        value=min(15000, max_dist),
        step=500,
    )

    filtered_df = df[df["distance_meters"] <= max_distance]

    # Metrics Row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Matched Intersections (24h)", value=len(filtered_df))
    with col2:
        avg_pm25 = filtered_df["pm25"].mean() if not filtered_df.empty else 0
        st.metric(
            label="Avg PM2.5 (µg/m³)",
            value=f"{avg_pm25:.1f}" if pd.notnull(avg_pm25) else "N/A",
        )
    with col3:
        avg_dist = filtered_df["distance_meters"].mean() if not filtered_df.empty else 0
        st.metric(label="Avg Proximity Distance", value=f"{avg_dist:.0f} m")

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

    # Initial view centered around Pune airspace
    initial_view_state = pdk.ViewState(
        latitude=(
            float(filtered_df["flight_lat"].mean())
            if not filtered_df.empty
            else 18.5204
        ),
        longitude=(
            float(filtered_df["flight_lon"].mean())
            if not filtered_df.empty
            else 73.8567
        ),
        zoom=9,
        pitch=30,
    )

    r = pdk.Deck(
        layers=[flight_layer, sensor_layer],
        initial_view_state=initial_view_state,
        tooltip={
            "text": (
                "Flight: {callsign} ({icao24})\n"
                "Sensor: {sensor_id}\n"
                "PM2.5: {pm25} µg/m³\n"
                "Distance: {distance_meters:.1f}m"
            )
        },  # type: ignore
    )

    st.pydeck_chart(r)

    # Data Table Preview
    with st.expander("View Raw Spatial Records"):
        st.dataframe(filtered_df)
