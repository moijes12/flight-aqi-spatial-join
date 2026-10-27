from src.ingestion.schemas import AirQualitySensor, FlightTelemetry


def test_flight_telemetry_parser_valid():
    # Mock OpenSky raw state vector
    vector = [
        "abc123",  # 0: icao24
        "BAW123 ",  # 1: callsign (with trailing whitespace)
        "United Kingdom",  # 2: origin_country
        0,
        0,  # 3, 4
        -0.1278,  # 5: longitude
        51.5074,  # 6: latitude
        1000.5,  # 7: altitude
        False,
        0,
        0,
        0,
        0,
        -1.5,  # 13: vertical_rate
        0,
        0,
        0,
    ]

    telemetry = FlightTelemetry.from_opensky_vector(vector)
    assert telemetry is not None
    assert telemetry.icao24 == "abc123"
    assert telemetry.callsign == "BAW123"
    assert telemetry.latitude == 51.5074
    assert telemetry.longitude == -0.1278


def test_flight_telemetry_missing_coords():
    vector = [
        "abc123",
        "BAW123",
        "UK",
        0,
        0,
        None,
        None,
        None,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ]
    telemetry = FlightTelemetry.from_opensky_vector(vector)
    assert telemetry is None


def test_air_quality_sensor_extractor():
    raw_location = {
        "id": 42,
        "name": "Central London Monitor",
        "coordinates": {"latitude": 51.5000, "longitude": -0.1000},
        "sensors": [
            {
                "id": 999,
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "latest": {"value": 12.5, "datetime": {"utc": "2026-03-30T12:00:00Z"}},
            }
        ],
    }

    sensors = AirQualitySensor.from_openaq_location(raw_location)
    assert len(sensors) == 1
    assert sensors[0].sensor_id == 999
    assert sensors[0].pm25_value == 12.5
    assert sensors[0].latitude == 51.5000
