import sys

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.transforms import window
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

            data = eval(element)
            flights = data.get("flights", [])
            sensors = data.get("sensors", [])
            ingest_time = data.get("timestamp")

            for flight in flights:
                yield {
                    "flight_id": str(
                        flight.get("hex", flight.get("flight_number", "UNKNOWN"))
                    ),
                    "latitude": flight.get("lat"),
                    "longitude": flight.get("lng"),
                    "altitude": flight.get("alt"),
                    "speed": flight.get("speed"),
                    "sensor_location_id": sensors[0].get("id") if sensors else None,
                    "pm25": sensors[0].get("parameters", [{}])[0].get("value")
                    if sensors
                    else None,
                    "timestamp": ingest_time,
                    "window_start": str(window.start),
                }
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error parsing payload in Beam worker: {e}")


def run_pipeline(argv=None):
    pipeline_options = PipelineOptions(argv)
    pipeline_options.view_as(StandardOptions).streaming = True

    topic_path = "projects/flight-aqi-spatial-join/topics/flight-telemetry-topic"

    with beam.Pipeline(options=pipeline_options) as p:
        (
            p
            | "ReadFromPubSub" >> beam.io.ReadFromPubSub(topic=topic_path)
            | "WindowInto" >> beam.WindowInto(window.FixedWindows(300))
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
