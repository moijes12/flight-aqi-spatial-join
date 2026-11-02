import asyncio
import os
import sys

from loguru import logger

from ingestion.clients.openaq_client import OpenAQClient
from ingestion.clients.opensky_client import OpenSkyClient

logger.remove()
logger.add(
    sys.stdout, level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


async def run_pipeline() -> None:
    logger.info("Starting ingestion pipeline worker cycle...")

    openaq_api_key = os.getenv("OPENAQ_API_KEY", "").strip()
    if not openaq_api_key:
        logger.error(
            "CRITICAL: OPENAQ_API_KEY environment variable is missing or set to placeholder!"
        )

    sky_client = OpenSkyClient()
    aq_client = OpenAQClient(api_key=openaq_api_key)

    async with asyncio.TaskGroup() as tg:
        sky_task = tg.create_task(sky_client.fetch_flight_data())
        aq_task = tg.create_task(
            aq_client.fetch_pm25_sensors(
                radius_meters=25000, coordinates=(72.8774, 19.0760)
            )
        )

    flights = sky_task.result()
    sensors = aq_task.result()

    logger.info(
        f"Pipeline cycle complete. Fetched {len(flights)} flight records and {len(sensors)} air quality sensors."
    )


if __name__ == "__main__":
    asyncio.run(run_pipeline())
