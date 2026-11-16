from datetime import UTC, datetime
from typing import Any

from geo_spatial_joiner.matcher import find_nearby_sensors

from flight_aqi_spatial_join.schemas import AirQualitySensor, FlightTelemetry


def join_flights_to_sensors(
    flights: list[FlightTelemetry],
    sensors: list[AirQualitySensor],
    radius_meters: float,
    max_sensors_per_flight: int = 3,
) -> list[dict[str, Any]]:
    """Match each flight to the nearest PM2.5 sensors inside the radius."""
    sensor_records = [sensor.model_dump() for sensor in sensors]
    rows: list[dict[str, Any]] = []

    for flight in flights:
        nearby = find_nearby_sensors(
            (flight.latitude, flight.longitude),
            sensor_records,
            radius_meters,
        )
        nearby.sort(key=lambda sensor: sensor["distance_meters"])
        observed_at = datetime.fromtimestamp(flight.timestamp, tz=UTC).isoformat()

        for sensor in nearby[:max_sensors_per_flight]:
            rows.append(
                {
                    "timestamp": observed_at,
                    "icao24": flight.icao24,
                    "callsign": flight.callsign,
                    "flight_location": f"POINT({flight.longitude} {flight.latitude})",
                    "sensor_id": str(sensor["sensor_id"]),
                    "sensor_location": (
                        f"POINT({sensor['longitude']} {sensor['latitude']})"
                    ),
                    "pm25": sensor.get("pm25_value"),
                    "distance_meters": round(float(sensor["distance_meters"]), 2),
                }
            )
    return rows
