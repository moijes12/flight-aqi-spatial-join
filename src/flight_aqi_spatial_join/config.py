import os
from dataclasses import dataclass

from loguru import logger

from flight_aqi_spatial_join.secrets import access_latest_secret


@dataclass(frozen=True)
class Settings:
    """Runtime configuration. API keys come from Secret Manager version latest."""

    project_id: str
    openaq_api_key: str
    airlabs_api_key: str
    flights_topic: str
    aqi_topic: str
    bq_table: str
    bq_location: str
    airlabs_bbox: str
    openaq_latitude: float
    openaq_longitude: float
    openaq_radius_meters: int
    openaq_limit: int
    join_radius_meters: float
    max_sensors_per_flight: int

    @classmethod
    def from_env(cls) -> "Settings":
        project_id = os.getenv("PROJECT_ID", "flight-aqi-spatial-join").strip()
        openaq_api_key = _api_key(project_id, "OPENAQ_API_KEY")
        airlabs_api_key = _api_key(project_id, "AIRLABS_API_KEY")

        return cls(
            project_id=project_id,
            openaq_api_key=openaq_api_key,
            airlabs_api_key=airlabs_api_key,
            flights_topic=os.getenv("FLIGHTS_TOPIC", "flights-stream"),
            aqi_topic=os.getenv("AQI_TOPIC", "air-quality-stream"),
            bq_table=os.getenv(
                "BQ_TABLE",
                f"{project_id}.geo_analytics.fct_flight_air_quality",
            ),
            bq_location=os.getenv("BQ_LOCATION", "us-central1"),
            # min_lat,min_lng,max_lat,max_lng covering Pune.
            airlabs_bbox=os.getenv("AIRLABS_BBOX", "18.4,73.7,18.7,74.0"),
            openaq_latitude=float(os.getenv("OPENAQ_LATITUDE", "18.5204")),
            openaq_longitude=float(os.getenv("OPENAQ_LONGITUDE", "73.8567")),
            openaq_radius_meters=int(os.getenv("OPENAQ_RADIUS_METERS", "25000")),
            openaq_limit=int(os.getenv("OPENAQ_LIMIT", "100")),
            join_radius_meters=float(os.getenv("JOIN_RADIUS_METERS", "15000")),
            max_sensors_per_flight=int(os.getenv("MAX_SENSORS_PER_FLIGHT", "3")),
        )


def _api_key(project_id: str, secret_id: str) -> str:
    """Prefer Secret Manager version ``latest``, then an environment variable."""
    try:
        value = access_latest_secret(project_id, secret_id)
    except Exception as exc:
        logger.warning("Secret Manager read failed for {}: {}", secret_id, exc)
        value = ""
    if value:
        return value
    value = os.getenv(secret_id, "").strip()
    if not value:
        raise RuntimeError(
            f"Secret {secret_id} version latest was empty or unavailable, "
            f"and {secret_id} is not set in the environment."
        )
    return value
