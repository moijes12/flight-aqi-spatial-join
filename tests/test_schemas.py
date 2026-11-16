from flight_aqi_spatial_join.schemas import AirQualitySensor, FlightTelemetry


def test_flight_telemetry_from_airlabs():
    item = {
        "hex": "abc123",
        "flight_icao": " AIC123 ",
        "flag": "IN",
        "lat": 18.52,
        "lng": 73.85,
        "alt": 3200,
        "v_speed": -1.5,
    }
    telemetry = FlightTelemetry.from_airlabs(item)
    assert telemetry is not None
    assert telemetry.icao24 == "abc123"
    assert telemetry.callsign == "AIC123"
    assert telemetry.latitude == 18.52
    assert telemetry.longitude == 73.85
    assert telemetry.baro_altitude == 3200
    assert telemetry.vertical_rate == -1.5


def test_flight_telemetry_missing_coords():
    assert FlightTelemetry.from_airlabs({"hex": "abc123"}) is None


def test_air_quality_sensor_extractor_keeps_pm25_only():
    raw_location = {
        "id": 42,
        "name": "Pune Monitor",
        "coordinates": {"latitude": 18.52, "longitude": 73.85},
        "sensors": [
            {
                "id": 999,
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "latest": {"value": 12.5, "datetime": {"utc": "2026-03-30T12:00:00Z"}},
            },
            {
                "id": 1000,
                "parameter": {"name": "pm10", "units": "µg/m³"},
                "latest": {"value": 20.0, "datetime": {"utc": "2026-03-30T12:00:00Z"}},
            },
        ],
    }

    sensors = AirQualitySensor.from_openaq_location(raw_location)
    assert len(sensors) == 1
    assert sensors[0].sensor_id == 999
    assert sensors[0].pm25_value == 12.5
    assert sensors[0].latitude == 18.52
