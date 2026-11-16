import pytest

from flight_aqi_spatial_join.clients.airlabs import AirLabsClient
from flight_aqi_spatial_join.clients.openaq import OpenAQClient
from flight_aqi_spatial_join.config import Settings
from flight_aqi_spatial_join.job import run_once
from flight_aqi_spatial_join.schemas import AirQualitySensor, FlightTelemetry


class MemoryPublisher:
    def __init__(self) -> None:
        self.flights: list[FlightTelemetry] = []
        self.sensors: list[AirQualitySensor] = []

    def publish(self, flights, sensors) -> tuple[int, int]:
        self.flights.extend(flights)
        self.sensors.extend(sensors)
        return len(flights), len(sensors)


class MemorySink:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def write(self, rows: list[dict]) -> int:
        self.rows.extend(rows)
        return len(rows)


def _settings() -> Settings:
    return Settings(
        project_id="flight-aqi-spatial-join",
        openaq_api_key="openaq",
        airlabs_api_key="airlabs",
        flights_topic="flights-stream",
        aqi_topic="air-quality-stream",
        bq_table="flight-aqi-spatial-join.geo_analytics.fct_flight_air_quality",
        bq_location="us-central1",
        airlabs_bbox="18.30,73.60,18.90,74.20",
        arr_iata="PNQ",
        openaq_latitude=18.5204,
        openaq_longitude=73.8567,
        openaq_radius_meters=25000,
        openaq_limit=100,
        join_radius_meters=15000,
        max_sensors_per_flight=3,
    )


@pytest.mark.asyncio
async def test_run_once_publishes_models_and_writes_join(monkeypatch):
    flight = FlightTelemetry(
        icao24="abc123",
        callsign="AI101",
        origin_country="IN",
        latitude=18.5204,
        longitude=73.8567,
        timestamp=1_700_000_000,
    )
    sensor = AirQualitySensor(
        sensor_id=7,
        location_id=3,
        location_name="Pune",
        latitude=18.5210,
        longitude=73.8570,
        pm25_value=41.0,
        measured_at="2026-03-30T12:00:00Z",
    )

    async def fake_flights(self, client=None):
        return [flight]

    async def fake_sensors(self, **kwargs):
        return [sensor]

    monkeypatch.setattr(AirLabsClient, "fetch_flights", fake_flights)
    monkeypatch.setattr(OpenAQClient, "fetch_pm25_sensors", fake_sensors)

    publisher = MemoryPublisher()
    sink = MemorySink()
    written = await run_once(
        _settings(),
        airlabs=AirLabsClient("airlabs", bbox="18.4,73.7,18.7,74.0"),
        openaq=OpenAQClient("openaq"),
        publisher=publisher,
        sink=sink,
    )

    assert written == 1
    assert publisher.flights == [flight]
    assert publisher.sensors == [sensor]
    assert sink.rows[0]["icao24"] == "abc123"
    assert sink.rows[0]["sensor_id"] == "7"
    assert sink.rows[0]["pm25"] == 41.0
    assert sink.rows[0]["flight_location"].startswith("POINT(")
