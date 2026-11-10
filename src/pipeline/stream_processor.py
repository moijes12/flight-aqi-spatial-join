import argparse
import logging
import sys

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.transforms.window import FixedWindows
from shapely.geometry import Point

logger = logging.getLogger("stream_processor")


class SpatialJoinDoFn(beam.DoFn):
    """Evaluates spatial distance between flight telemetry and air quality sensors."""

    def process(self, element, window=beam.DoFn.WindowParam):
        flight = element.get("flight")
        sensor = element.get("sensor")

        if not flight or not sensor:
            return

        # Create Shapely points for distance calculation
        flight_pt = Point(flight["longitude"], flight["latitude"])
        sensor_pt = Point(sensor["longitude"], sensor["latitude"])

        # Approximate distance calculation (or use Haversine formula / Shapely transform)
        # For simplicity in degrees (~1 degree ~ 111km at the equator, or precise geospatial handling)
        distance_meters = flight_pt.distance(sensor_pt) * 111000.0

        # Define spatial threshold (e.g., flight within 10,000 meters / 10km of sensor)
        THRESHOLD_METERS = 10000.0

        if distance_meters <= THRESHOLD_METERS:
            joined_record = {
                "timestamp": flight.get("timestamp"),
                "icao24": flight.get("icao24"),
                "callsign": flight.get("callsign"),
                "flight_location": f"POINT({flight['longitude']} {flight['latitude']})",
                "sensor_id": sensor.get("sensor_id"),
                "sensor_location": f"POINT({sensor['longitude']} {sensor['latitude']})",
                "pm25": sensor.get("pm25"),
                "distance_meters": round(distance_meters, 2),
            }
            logger.info(
                f"Spatial Match Found! Flight {flight['icao24']} near Sensor {sensor['sensor_id']} at {distance_meters:.2f}m"
            )
            yield joined_record


def run(argv=None):
    parser = argparse.ArgumentParser()
    _, pipeline_args = parser.parse_known_args(argv)

    pipeline_options = PipelineOptions(pipeline_args)

    project_id = "your-gcp-project-id"
    table_spec = f"{project_id}:geo_analytics.fct_flight_air_quality"

    with beam.Pipeline(options=pipeline_options) as p:
        # Simulated or Pub/Sub ingested streams
        flights = p | "CreateFlights" >> beam.Create(
            [
                {
                    "icao24": "abc123",
                    "callsign": "AI101",
                    "longitude": 73.8567,
                    "latitude": 18.5204,
                    "timestamp": "2026-11-06T12:00:00Z",
                }
            ]
        )

        sensors = p | "CreateSensors" >> beam.Create(
            [
                {
                    "sensor_id": "pune_aq_01",
                    "longitude": 73.8500,
                    "latitude": 18.5200,
                    "pm25": 45.2,
                }
            ]
        )

        # Windowing and joining streams
        windowed_flights = flights | "WindowFlights" >> beam.WindowInto(
            FixedWindows(300)
        )
        windowed_sensors = sensors | "WindowSensors" >> beam.WindowInto(
            FixedWindows(300)
        )

        # CoGroupByKey or Side Inputs can be used depending on stream size.
        # For this architecture, matching telemetry within the fixed window:
        joined_results = (
            {"flight": windowed_flights, "sensor": windowed_sensors}
            | "CoGroupStreams" >> beam.CoGroupByKey()
            | "SpatialJoin" >> beam.ParDo(SpatialJoinDoFn())
        )

        # Stream results directly into BigQuery
        joined_results | "WriteToBigQuery" >> beam.io.WriteToBigQuery(
            table=table_spec,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
        )  # type: ignore


if __name__ == "__main__":
    logger = logging.getLogger("beam_streaming")
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    run()
