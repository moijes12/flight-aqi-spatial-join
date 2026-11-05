CREATE SCHEMA IF NOT EXISTS geo_analytics
OPTIONS(
    location="us-central1",
    description="Spatial analytics dataset for flight telemetry and air quality correlation."
);

-- Create partition and clustered table for spatial join results
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
