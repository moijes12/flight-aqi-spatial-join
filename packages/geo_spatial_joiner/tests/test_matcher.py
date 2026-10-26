import pytest
from geo_spatial_joiner.matcher import (
    batch_find_nearby_sensors,
    calculate_distance_meters,
    find_nearby_sensors,
)


def test_calculate_distance_zero():
    # Distance between a point and itself should be 0.0 meters
    dist = calculate_distance_meters(12.9716, 77.5946, 12.9716, 77.5946)
    assert dist == 0.0


def test_calculate_distance_known():
    # Distance between New York (40.7128, -74.0060) and Washington DC (38.8951, -77.0364)
    # Expected approx 328 km (328,000 meters)
    dist = calculate_distance_meters(40.7128, -74.0060, 38.8951, -77.0364)
    assert 320_000 <= dist <= 335_000


def test_invalid_coordinates():
    with pytest.raises(AssertionError):
        calculate_distance_meters(95.0, 77.5946, 12.0, 77.0)  # Invalid latitude > 90

    with pytest.raises(AssertionError):
        calculate_distance_meters(12.0, 190.0, 12.0, 77.0)  # Invalid longitude > 180


def test_find_nearby_sensors():
    flight_coord = (12.9716, 77.5946)
    sensors = [
        {"id": 1, "latitude": 12.9720, "longitude": 77.5950},  # Very close (~60m)
        {"id": 2, "latitude": 15.0000, "longitude": 75.0000},  # Far away (>250km)
    ]

    nearby = find_nearby_sensors(flight_coord, sensors, radius_meters=500.0)
    assert len(nearby) == 1
    assert nearby[0]["id"] == 1
    assert "distance_meters" in nearby[0]


def test_batch_find_nearby_sensors():
    flights = [
        ("FL123", 12.9716, 77.5946),
        ("FL999", 50.0000, 50.0000),  # Far away
    ]
    sensors = [
        {"id": 101, "latitude": 12.9720, "longitude": 77.5950},
    ]
    results = batch_find_nearby_sensors(flights, sensors, radius_meters=500.0)
    assert len(results) == 1
    assert results[0]["flight_id"] == "FL123"
    assert results[0]["sensor_id"] == 101
