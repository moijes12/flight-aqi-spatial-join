import math
from typing import Any


def validate_coordinates(latitude: float, longitude: float) -> None:
    """Test that a given latitude longitude pair is within acceptable ranges."""
    assert -90.0 <= latitude <= 90.0, "Invalid latitude for point"
    assert -180.0 <= longitude <= 180.0, "Invalid longitude for point"


def calculate_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate the great-circle distance between two points on Earth in meters using the Haversine formula."""
    validate_coordinates(lat1, lon1)
    validate_coordinates(lat2, lon2)

    R = 6371000.0  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def find_nearby_sensors(
    flight_coord: tuple[float, float],
    sensors: list[dict[str, Any]],
    radius_meters: float,
) -> list[dict[str, Any]]:
    """Get the list of sensors within a given radius of the flight."""
    latitude, longitude = flight_coord
    validate_coordinates(latitude=latitude, longitude=longitude)

    # Assume no sensors nearby
    nearby_sensors = []
    for sensor in sensors:
        s_latitude = sensor["latitude"]
        s_longitude = sensor["longitude"]

        validate_coordinates(s_latitude, s_longitude)
        distance = calculate_distance_meters(
            lat1=latitude, lon1=longitude, lat2=s_latitude, lon2=s_longitude
        )
        if distance <= radius_meters:
            sensor_record = sensor.copy()
            sensor_record["distance_meters"] = distance
            nearby_sensors.append(sensor_record)

    return nearby_sensors


def batch_find_nearby_sensors(
    flights: list[tuple[str, float, float]],
    sensors: list[dict[str, Any]],
    radius_meters: float,
) -> list[dict[str, Any]]:
    """Perform batch spatial matching for multiple flights (flight_id, lat, lon) against sensors."""
    results = []
    for flight_id, lat, lon in flights:
        nearby_sensors = find_nearby_sensors((lat, lon), sensors, radius_meters)
        for sensor in nearby_sensors:
            results.append(
                {
                    "flight_id": flight_id,
                    "sensor_id": sensor.get("id"),
                    "distance_meters": sensor["distance_meters"],
                    "sensor_data": sensor,
                }
            )
    return results
