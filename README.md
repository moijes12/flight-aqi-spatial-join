# Flight and air-quality spatial join

Hourly pipeline that polls AirLabs and OpenAQ, validates the payloads, publishes them to Pub/Sub, loads nearby matches into BigQuery, and maps the result in Streamlit.

## Flow

1. Cloud Scheduler starts the Cloud Run Job `flight-aqi-worker` every hour.
2. The job calls AirLabs (`FlightTelemetry`) and OpenAQ (`AirQualitySensor`) with `httpx2`.
3. Each model is published as JSON to `flights-stream` or `air-quality-stream`.
4. Flights within `JOIN_RADIUS_METERS` of a PM2.5 sensor (default 15 km, nearest 3 sensors) are inserted into `geo_analytics.fct_flight_air_quality`.
5. Streamlit reads the existing view `geo_analytics.v_flight_aqi_spatial_join` and draws flights with pydeck. That view uses `flight_number`, `flight_lng`, `station_id`, and `distance_to_station_meters`.

The default bounding box is Pune (`AIRLABS_BBOX=18.4,73.7,18.7,74.0`, OpenAQ centered on 18.5204, 73.8567).

## Local setup

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --all-groups
uv run flight-aqi-job
uv run streamlit run src/dashboard/app.py
```

The job loads `OPENAQ_API_KEY` and `AIRLABS_API_KEY` from Secret Manager version `latest` in `PROJECT_ID` (default `flight-aqi-spatial-join`). Application Default Credentials must be allowed to access those secrets. The same credentials are used for Pub/Sub and BigQuery. The job creates the dataset, table, and view from `infra/schema.sql` when they are missing.

## Local image

`build.sh` is only for a local Docker build and one-shot run. It reads Secret Manager secrets `OPENAQ_API_KEY` and `AIRLABS_API_KEY` at version `latest` into the process environment. It does not print those values and it does not deploy Cloud Run or Cloud Scheduler.

Terraform in `infra/terraform` creates the Pub/Sub topics and the `geo_analytics` dataset.
