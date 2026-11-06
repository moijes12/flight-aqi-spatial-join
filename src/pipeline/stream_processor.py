import argparse
import sys

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.transforms.window import FixedWindows
from loguru import logger


class LogAndFormat(beam.DoFn):
    """Simple DoFn to inspect elements inside windowed panes."""

    def process(self, element, window=beam.DoFn.WindowParam):
        logger.info(f"Window [{window.start} - {window.end}]: Data -> {element}")
        yield element


def run(argv=None):
    parser = argparse.ArgumentParser()
    _known_args, pipeline_args = parser.parse_known_args(argv)

    pipeline_options = PipelineOptions(pipeline_args)

    with beam.Pipeline(options=pipeline_options) as p:
        # For local testing via DirectRunner, we can ingest from a mock source
        # or read from a Pub/Sub topic when running on Cloud Dataflow.
        _lines = (
            p
            | "CreateMockStream"
            >> beam.Create(
                [
                    {"icao24": "abc123", "lat": 18.5204, "lon": 73.8567, "alt": 35000},
                    {"icao24": "def456", "lat": 18.5314, "lon": 73.8446, "alt": 32000},
                ]
            )
            | "AddTimestamps"
            >> beam.WindowInto(
                FixedWindows(300)
            )  # 5-minute tumbling window (300 seconds)
            | "LogWindows" >> beam.ParDo(LogAndFormat())
        )


if __name__ == "__main__":
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    run()
