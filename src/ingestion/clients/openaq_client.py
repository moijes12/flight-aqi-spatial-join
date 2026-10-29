import asyncio
from typing import Any

from httpx2 import AsyncClient, HTTPStatusError, RequestError
from loguru import logger

from ingestion.schemas import AirQualitySensor


class OpenAQClient:
    """Asynchronous client for fetching air quality sensors from OpenAQ API v3."""

    BASE_URL = "https://api.openaq.org/v3/locations"

    def __init__(self, api_key: str, timeout: float = 15.0, max_retries: int = 3):
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    async def fetch_pm25_sensors(
        self,
        radius_meters: int | None = None,
        coordinates: tuple[float, float] | None = None,
        limit: int = 100,
        client: AsyncClient | None = None,
    ):
        """Fetch stations and extract PM2.5 sensor measurements asynchronously."""
        close_client = False
        if client is None:
            client = AsyncClient(timeout=self.timeout)
            close_client = True

        headers = {"X-API-Key": self.api_key}
        params: dict[str, Any] = {"parameters_id": 2, "limit": limit}

        if coordinates and radius_meters:
            lat, long = coordinates
            params["coordinates"] = f"{long},{lat}"
            params["radius"] = radius_meters

        retries = 0
        backoff_factor = 2.0

        try:
            while retries < self.max_retries:
                try:
                    logger.info(
                        f"Querying OpenAQ API v3 at {self.BASE_URL} with params: {params}"
                    )
                    response = await client.get(
                        self.BASE_URL, headers=headers, params=params
                    )

                    if response.status_code == 429:
                        wait_time = backoff_factor**retries
                        logger.warning(
                            f"OpenAQ rate limit hit (429). Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                        retries += 1
                        continue

                    response.raise_for_status()
                    data = response.json()
                    results = data.get("results", [])

                    if not results:
                        logger.warning(
                            "OpenAQ returned zero location records for the given parameters."
                        )
                        return []

                    extracted_sensors: list[AirQualitySensor] = []
                    for location in results:
                        sensors = AirQualitySensor.from_openaq_location(location)
                        extracted_sensors.extend(sensors)

                    logger.info(
                        f"Successfully extracted {len(extracted_sensors)} PM2.5 sensors from OpenAQ."
                    )
                    return extracted_sensors
                except (RequestError, HTTPStatusError) as e:
                    retries += 1
                    if retries >= self.max_retries:
                        logger.error(
                            f"OpenAQ request failed permanently after {self.max_retries} attempts: {e}"
                        )
                        raise
                    wait_time = backoff_factor**retries
                    logger.warning(
                        f"OpenAQ network/HTTP error ({e}). Retrying in {wait_time}s (Attempt {retries}/{self.max_retries})..."
                    )
                    await asyncio.sleep(wait_time)
            return []
        finally:
            if close_client:
                await client.aclose()
