import asyncio
from typing import Protocol

from loguru import logger

from flight_aqi_spatial_join.bigquery_sink import BigQuerySink
from flight_aqi_spatial_join.clients.airlabs import AirLabsClient
from flight_aqi_spatial_join.clients.openaq import OpenAQClient
from flight_aqi_spatial_join.config import Settings
from flight_aqi_spatial_join.join import join_flights_to_sensors
from flight_aqi_spatial_join.publisher import PubSubPublisher
from flight_aqi_spatial_join.schemas import AirQualitySensor, FlightTelemetry


class EventPublisher(Protocol):
    def publish(
        self,
        flights: list[FlightTelemetry],
        sensors: list[AirQualitySensor],
    ) -> tuple[int, int]: ...


class TableSink(Protocol):
    def write(self, rows: list[dict]) -> int: ...


async def run_once(
    settings: Settings,
    *,
    airlabs: AirLabsClient,
    openaq: OpenAQClient,
    publisher: EventPublisher,
    sink: TableSink,
) -> int:
    """Poll both APIs, publish models, and load the spatial join."""
    async with asyncio.TaskGroup() as group:
        flights_task = group.create_task(airlabs.fetch_flights())
        sensors_task = group.create_task(
            openaq.fetch_pm25_sensors(
                latitude=settings.openaq_latitude,
                longitude=settings.openaq_longitude,
                radius_meters=settings.openaq_radius_meters,
                limit=settings.openaq_limit,
            )
        )

    flights = flights_task.result()
    sensors = sensors_task.result()
    publisher.publish(flights, sensors)
    rows = join_flights_to_sensors(
        flights,
        sensors,
        radius_meters=settings.join_radius_meters,
        max_sensors_per_flight=settings.max_sensors_per_flight,
    )
    written = sink.write(rows)
    logger.info(
        "Cycle complete: {} flights, {} sensors, {} joined rows.",
        len(flights),
        len(sensors),
        written,
    )
    return written


def main() -> None:
    settings = Settings.from_env()
    airlabs = AirLabsClient(settings.airlabs_api_key, bbox=settings.airlabs_bbox)
    openaq = OpenAQClient(settings.openaq_api_key)
    publisher = PubSubPublisher(
        settings.project_id, settings.flights_topic, settings.aqi_topic
    )
    sink = BigQuerySink(settings.project_id, settings.bq_table, settings.bq_location)
    sink.ensure_schema()
    asyncio.run(
        run_once(
            settings,
            airlabs=airlabs,
            openaq=openaq,
            publisher=publisher,
            sink=sink,
        )
    )


if __name__ == "__main__":
    main()
