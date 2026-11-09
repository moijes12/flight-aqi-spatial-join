import json
import sys
from datetime import UTC, datetime

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.transforms import trigger, window
from loguru import logger

BQ_TABLE = "flight-aqi-spatial-join:geo_analytics.fct_flight_air_quality"

BQ_SCHEMA = {
    "fields": [
        {"name": "flight_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "latitude", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "longitude", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "altitude", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "speed", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "sensor_location_id", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "pm25", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "window_start", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]
}


class ParseAndFlattenPayload(beam.DoFn):
    """Parses raw Pub/Sub message bytes and flattens flights/sensors for analysis."""

    def process(self, element, window=beam.DoFn.WindowParam):
        try:
            if isinstance(element, bytes):
                element = element.decode("utf-8")

            data = json.loads(element)

            # Universal fallback extraction for nested or flat payloads
            flights = data.get("flights") or data.get("response") or data.get("data")
            if not flights and (
                isinstance(data, dict)
                and ("flight_id" in data or "lat" in data or "hex" in data)
            ):
                flights = [data]
            elif not flights and isinstance(data, list):
                flights = data

            flights = flights or []
            sensors = data.get("sensors", data.get("results", []))
            ingest_time = data.get("timestamp") or data.get("time")

            win_start_str = (
                datetime.fromtimestamp(window.start.micros / 1e6, tz=UTC).isoformat()
                + "Z"
            )

            if not flights:
                logger.warning(
                    f"No flights found in payload keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                )
                return

            for flight in flights:
                if not isinstance(flight, dict):
                    continue

                sensor_id = None
                pm25_val = None
                if sensors and isinstance(sensors, list) and len(sensors) > 0:
                    first_sensor = sensors[0]
                    if isinstance(first_sensor, dict):
                        sensor_id = first_sensor.get("id") or first_sensor.get(
                            "location_id"
                        )
                        params = first_sensor.get(
                            "parameters", first_sensor.get("measurements", [])
                        )
                        if params and isinstance(params, list) and len(params) > 0:
                            pm25_val = params[0].get("value") or params[0].get(
                                "parameterValue"
                            )

                yield {
                    "flight_id": str(
                        flight.get(
                            "flight_id",
                            flight.get("hex", flight.get("flight_number", "UNKNOWN")),
                        )
                    ),
                    "latitude": flight.get("lat") or flight.get("latitude"),
                    "longitude": flight.get("lng")
                    or flight.get("longitude")
                    or flight.get("lon"),
                    "altitude": flight.get("alt") or flight.get("altitude"),
                    "speed": flight.get("speed"),
                    "sensor_location_id": int(sensor_id)
                    if sensor_id is not None
                    else None,
                    "pm25": float(pm25_val) if pm25_val is not None else None,
                    "timestamp": ingest_time or datetime.now(tz=UTC).isoformat() + "Z",
                    "window_start": win_start_str,
                }
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"Error parsing payload in Beam worker: {e} | Raw element: {str(element)[:200]}"
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
            )
        )  # type: ignore


if __name__ == "__main__":
    logger.remove()
    logger.add(
        sys.stdout,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    run_pipeline()
