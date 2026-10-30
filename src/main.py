import asyncio
import sys

from loguru import logger

from ingestion.clients.openaq_client import OpenAQClient
from ingestion.clients.opensky_client import OpenSkyClient

logger.remove()
logger.add(
    sys.stdout, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


async def run_pipeline() -> None:
    logger.info("Starting ingestion pipeline worker cycle...")

    sky_client = OpenSkyClient()
    aq_client = OpenAQClient(api_key="my-open-aq-api-key")

    async with asyncio.TaskGroup() as tg:
        sky_task = tg.create_task(sky_client.fetch_flights())
        aq_task = tg.create_task(
            aq_client.fetch_pm25_sensors(
                radius_meters=50000, coordinates=(51.5074, -0.1278)
            )
        )

    flights = sky_task.result()
    sensors = aq_task.result()

    logger.info(
        f"Pipeline cycle complete. Fetched {len(flights)} flight records and {len(sensors)} air quality sensors."
    )


if __name__ == "__main__":
    asyncio.run(run_pipeline())
