from collections.abc import Sequence

from google.cloud import pubsub_v1
from loguru import logger

from flight_aqi_spatial_join.schemas import AirQualitySensor, FlightTelemetry


class PubSubPublisher:
    """Publish validated models as JSON messages."""

    def __init__(self, project_id: str, flights_topic: str, aqi_topic: str) -> None:
        self._client = pubsub_v1.PublisherClient()
        self._flights_path = self._client.topic_path(project_id, flights_topic)
        self._aqi_path = self._client.topic_path(project_id, aqi_topic)

    def publish(
        self,
        flights: Sequence[FlightTelemetry],
        sensors: Sequence[AirQualitySensor],
    ) -> tuple[int, int]:
        futures = [
            self._client.publish(
                self._flights_path,
                flight.model_dump_json().encode("utf-8"),
                record_type="flight",
            )
            for flight in flights
        ]
        futures.extend(
            self._client.publish(
                self._aqi_path,
                sensor.model_dump_json().encode("utf-8"),
                record_type="air_quality",
            )
            for sensor in sensors
        )
        for future in futures:
            future.result(timeout=60)
        logger.info(
            "Published {} flights to {} and {} sensors to {}.",
            len(flights),
            self._flights_path,
            len(sensors),
            self._aqi_path,
        )
        return len(flights), len(sensors)
