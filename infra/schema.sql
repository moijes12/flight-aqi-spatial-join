CREATE SCHEMA IF NOT EXISTS geo_analytics
OPTIONS(
    location="us-central1",
    description="Spatial analytics dataset for flight telemetry and air quality correlation."
);

CREATE TABLE IF NOT EXISTS geo_analytics.fct_flight_air_quality (
    timestamp TIMESTAMP NOT NULL,
    icao24 STRING NOT NULL,
    callsign STRING,
    flight_location GEOGRAPHY NOT NULL,
    sensor_id STRING NOT NULL,
    sensor_location GEOGRAPHY NOT NULL,
    pm25 FLOAT64,
    distance_meters FLOAT64 NOT NULL
)
PARTITION BY DATE(timestamp)
CLUSTER BY icao24, sensor_id
OPTIONS(
    description="Joined telemetry and air quality metrics evaluated within spatial bounding thresholds."
);

CREATE TABLE IF NOT EXISTS geo_analytics.flight_station_matches (
    timestamp TIMESTAMP,
    icao24 STRING,
    flight_number STRING,
    flight_lat FLOAT64,
    flight_lng FLOAT64,
    altitude_meters FLOAT64,
    speed_knots FLOAT64,
    station_id STRING,
    station_name STRING,
    station_lat FLOAT64,
    station_lng FLOAT64,
    pm25 FLOAT64,
    pm10 FLOAT64,
    distance_to_station_meters FLOAT64
);

CREATE OR REPLACE VIEW geo_analytics.v_flight_aqi_spatial_join AS
SELECT
    timestamp,
    icao24,
    flight_number,
    flight_lat,
    flight_lng,
    altitude_meters,
    speed_knots,
    station_id,
    station_name,
    station_lat,
    station_lng,
    pm25,
    pm10,
    distance_to_station_meters
FROM geo_analytics.flight_station_matches
UNION ALL
SELECT
    timestamp,
    icao24,
    callsign AS flight_number,
    ST_Y(flight_location) AS flight_lat,
    ST_X(flight_location) AS flight_lng,
    CAST(NULL AS FLOAT64) AS altitude_meters,
    CAST(NULL AS FLOAT64) AS speed_knots,
    sensor_id AS station_id,
    CAST(NULL AS STRING) AS station_name,
    ST_Y(sensor_location) AS station_lat,
    ST_X(sensor_location) AS station_lng,
    pm25,
    CAST(NULL AS FLOAT64) AS pm10,
    distance_meters AS distance_to_station_meters
FROM geo_analytics.fct_flight_air_quality;
