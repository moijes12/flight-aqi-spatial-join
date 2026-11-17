import os

import pandas as pd
import pydeck as pdk
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

PROJECT_ID = os.getenv("PROJECT_ID", "flight-aqi-spatial-join")
VIEW_ID = f"{PROJECT_ID}.geo_analytics.v_flight_aqi_spatial_join"

st.set_page_config(
    page_title="Flight & Air Quality Spatial Analytics",
    layout="wide",
    page_icon="✈️",
)
st_autorefresh(interval=60_000, key="datarefreshcounter")

st.title("Pune Airport arrivals and air quality")
st.markdown("Flights arriving at Pune Airport (PNQ) and nearby OpenAQ PM2.5 stations.")


def _service_account_info() -> dict | None:
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        return None
    return None


@st.cache_resource
def get_bigquery_client() -> bigquery.Client:
    creds_dict = _service_account_info()
    if creds_dict:
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        return bigquery.Client(
            credentials=credentials,
            project=creds_dict.get("project_id", PROJECT_ID),
        )
    return bigquery.Client(project=PROJECT_ID)


@st.cache_data(ttl=60)
def load_spatial_data() -> pd.DataFrame:
    """Query recent joined spatial data from the BigQuery view."""
    query = f"""
        SELECT
            timestamp,
            icao24,
            flight_number,
            flight_lat,
            flight_lng,
            station_id,
            station_name,
            station_lat,
            station_lng,
            pm25,
            distance_to_station_meters
        FROM `{VIEW_ID}`
        WHERE (
            timestamp IS NULL
            OR timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        )
          AND flight_lat BETWEEN 18.30 AND 18.90
          AND flight_lng BETWEEN 73.60 AND 74.20
        ORDER BY timestamp DESC
        LIMIT 1000
    """
    frame = get_bigquery_client().query(query).to_dataframe()
    if "station_name" in frame.columns:
        frame["station_name"] = frame["station_name"].fillna("Unknown station")
    return frame


try:
    df = load_spatial_data()
    query_error = None
except Exception as exc:  # noqa: BLE001
    df = pd.DataFrame()
    query_error = str(exc)

if query_error:
    st.error(f"BigQuery query error: {query_error}")
elif df.empty:
    st.warning("No Pune Airport arrival matches in BigQuery for the last 7 days.")
else:
    st.sidebar.header("Filter controls")
    min_dist = int(df["distance_to_station_meters"].min())
    max_dist = int(df["distance_to_station_meters"].max())
    if max_dist <= min_dist:
        max_dist = min_dist + 1000

    max_distance = st.sidebar.slider(
        "Max distance (meters)",
        min_value=0,
        max_value=max(50_000, max_dist),
        value=min(50_000, max_dist),
        step=500,
    )
    filtered_df = df[df["distance_to_station_meters"] <= max_distance]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Matched intersections", len(filtered_df))
    avg_pm25 = filtered_df["pm25"].mean() if not filtered_df.empty else None
    col2.metric(
        "Avg PM2.5",
        f"{avg_pm25:.1f} µg/m³" if pd.notnull(avg_pm25) else "N/A",
    )
    avg_dist = (
        filtered_df["distance_to_station_meters"].mean() if not filtered_df.empty else 0
    )
    col3.metric("Avg proximity", f"{avg_dist:.0f} m")
    col4.metric(
        "Unique flights",
        int(filtered_df["icao24"].nunique()) if not filtered_df.empty else 0,
    )

    line_layer = pdk.Layer(
        "LineLayer",
        data=filtered_df,
        get_source_position=["flight_lng", "flight_lat"],
        get_target_position=["station_lng", "station_lat"],
        get_color=[100, 150, 250, 110],
        get_width=2,
        pickable=True,
    )
    flight_layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_df,
        get_position=["flight_lng", "flight_lat"],
        get_color=[255, 75, 75, 180],
        get_radius=3000,
        pickable=True,
    )
    station_layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_df,
        get_position=["station_lng", "station_lat"],
        get_color=[0, 180, 130, 200],
        get_radius=4000,
        pickable=True,
    )
    view_state = pdk.ViewState(
        latitude=float(filtered_df["flight_lat"].mean())
        if not filtered_df.empty
        else 18.5204,
        longitude=float(filtered_df["flight_lng"].mean())
        if not filtered_df.empty
        else 73.8567,
        zoom=4,
        pitch=30,
    )
    deck = pdk.Deck(
        layers=[line_layer, flight_layer, station_layer],
        initial_view_state=view_state,
        tooltip={
            "text": (
                "Flight: {flight_number} ({icao24})\n"
                "Station: {station_name} ({station_id})\n"
                "PM2.5: {pm25} µg/m³\n"
                "Distance: {distance_to_station_meters} m"
            )
        },
    )
    st.pydeck_chart(deck, use_container_width=True)

    st.markdown("### Spatial join records")
    table_tab, export_tab = st.tabs(["Table", "Export"])
    with table_tab:
        st.dataframe(filtered_df, use_container_width=True)
    with export_tab:
        st.download_button(
            label="Download filtered CSV",
            data=filtered_df.to_csv(index=False).encode("utf-8"),
            file_name="flight_aqi_spatial_join_export.csv",
            mime="text/csv",
        )
