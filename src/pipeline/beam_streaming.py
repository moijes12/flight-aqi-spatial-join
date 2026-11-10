import json
import logging
import sys
from datetime import UTC, datetime

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.transforms import trigger, window

BQ_TABLE = "flight-aqi-spatial-join:geo_analytics.fct_flight_air_quality"

BQ_SCHEMA = {
    "fields": [
        {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "icao24", "type": "STRING", "mode": "REQUIRED"},
        {"name": "callsign", "type": "STRING", "mode": "NULLABLE"},
        {"name": "flight_location", "type": "GEOGRAPHY", "mode": "REQUIRED"},
        {"name": "sensor_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "sensor_location", "type": "GEOGRAPHY", "mode": "REQUIRED"},
        {"name": "pm25", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "distance_meters", "type": "FLOAT", "mode": "REQUIRED"},
    ]
}

logger = logging.getLogger("beam_streaming")


class ParseAndFlattenPayload(beam.DoFn):
    """Parses raw Pub/Sub message bytes and maps them to the exact BigQuery schema."""

    def process(self, element, window=beam.DoFn.WindowParam):
        try:
            if isinstance(element, bytes):
                element = element.decode("utf-8")

            data = json.loads(element)

            # Universal fallback extraction for nested or flat payloads
            flights = data.get("flights") or data.get("response") or data.get("data")
            if not flights and (
                isinstance(data, dict)
                and (
                    "flight_id" in data
                    or "lat" in data
                    or "icao24" in data
                    or "hex" in data
                )
            ):
                flights = [data]
            elif not flights and isinstance(data, list):
                flights = data

            flights = flights or []
            sensors = data.get("sensors", data.get("results", []))
            ingest_time = (
                data.get("timestamp")
                or data.get("time")
                or datetime.now(tz=UTC).isoformat() + "Z"
            )

            if not flights:
                logger.warning(
                    "No flights found in payload keys: %s",
                    list(data.keys()) if isinstance(data, dict) else type(data),
                )
                return

            for flight in flights:
                if not isinstance(flight, dict):
                    continue

                # Extract identifiers & coordinates
                icao24 = str(
                    flight.get(
                        "icao24", flight.get("hex", flight.get("flight_id", "UNKNOWN"))
                    )
                )
                callsign = str(
                    flight.get("callsign", flight.get("flight_number", "UNKNOWN"))
                )
                lat = flight.get("lat") or flight.get("latitude")
                lon = flight.get("lng") or flight.get("longitude") or flight.get("lon")

                if lat is None or lon is None:
                    continue

                # Default sensor parsing
                sensor_id = "101"
                sensor_lat, sensor_lon = (
                    lat,
                    lon,
                )  # fallback proximity if sensor coords omitted
                pm25_val = None

                if sensors and isinstance(sensors, list) and len(sensors) > 0:
                    first_sensor = sensors[0]
                    if isinstance(first_sensor, dict):
                        sensor_id = str(
                            first_sensor.get("id")
                            or first_sensor.get("location_id", "101")
                        )
                        sensor_lat = first_sensor.get("lat", lat)
                        sensor_lon = first_sensor.get("lon", lon)

                        params = first_sensor.get(
                            "parameters", first_sensor.get("measurements", [])
                        )
                        if params and isinstance(params, list) and len(params) > 0:
                            pm25_val = params[0].get("value") or params[0].get(
                                "parameterValue"
                            )

                # Construct BigQuery GEOGRAPHY WKT strings ("POINT(lon lat)")
                flight_geo = f"POINT({lon} {lat})"
                sensor_geo = f"POINT({sensor_lon} {sensor_lat})"

                yield {
                    "timestamp": ingest_time,
                    "icao24": icao24,
                    "callsign": callsign,
                    "flight_location": flight_geo,
                    "sensor_id": sensor_id,
                    "sensor_location": sensor_geo,
                    "pm25": float(pm25_val) if pm25_val is not None else None,
                    "distance_meters": 0.0,  # Default or computed spatial distance
                }
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error parsing payload in Beam worker: %s | Raw element: %s",
                e,
                str(element)[:200],
            )


def run_pipeline(argv=None):
    pipeline_options = PipelineOptions(argv)
    pipeline_options.view_as(StandardOptions).streaming = True

    topic_path = "projects/flight-aqi-spatial-join/topics/flight-telemetry-topic"

    with beam.Pipeline(options=pipeline_options) as p:
        (
            p
            | "ReadFromPubSub" >> beam.io.ReadFromPubSub(topic=topic_path)
            | "WindowInto"
            >> beam.WindowInto(
                window.FixedWindows(300),
                trigger=trigger.Repeatedly(trigger.AfterProcessingTime(10)),
                accumulation_mode=trigger.AccumulationMode.DISCARDING,
            )
            | "ParsePayload" >> beam.ParDo(ParseAndFlattenPayload())
            | "WriteToBigQuery"
            >> beam.io.WriteToBigQuery(
                table=BQ_TABLE,
                schema=BQ_SCHEMA,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                method=beam.io.WriteToBigQuery.Method.FILE_LOADS,
                triggering_frequency=30,
            )
        )  # type: ignore


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    run_pipeline()
