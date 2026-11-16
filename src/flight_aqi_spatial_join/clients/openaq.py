import asyncio
from typing import Any

import httpx2
from loguru import logger

from flight_aqi_spatial_join.schemas import AirQualitySensor


class OpenAQClient:
    """Fetch OpenAQ v3 locations and reduce them to PM2.5 sensors."""

    BASE_URL = "https://api.openaq.org/v3/locations"

    def __init__(
        self, api_key: str, timeout: float = 20.0, max_retries: int = 3
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    async def fetch_pm25_sensors(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_meters: int,
        limit: int = 100,
        client: httpx2.AsyncClient | None = None,
    ) -> list[AirQualitySensor]:
        owns_client = client is None
        if client is None:
            client = httpx2.AsyncClient(timeout=self.timeout)

        headers = {"X-API-Key": self.api_key}
        # OpenAQ expects coordinates as latitude,longitude. Parameter id 2 is PM2.5.
        params: dict[str, Any] = {
            "parameters_id": 2,
            "limit": limit,
            "coordinates": f"{latitude},{longitude}",
            "radius": radius_meters,
        }
        try:
            payload = await self._get_json(client, headers, params)
        finally:
            if owns_client:
                await client.aclose()

        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list) or not results:
            logger.warning("OpenAQ returned no locations for the requested area.")
            return []

        sensors: list[AirQualitySensor] = []
        for location in results:
            if isinstance(location, dict):
                sensors.extend(AirQualitySensor.from_openaq_location(location))
        logger.info("Extracted {} PM2.5 sensors from OpenAQ.", len(sensors))
        return sensors

    async def _get_json(
        self,
        client: httpx2.AsyncClient,
        headers: dict[str, str],
        params: dict[str, Any],
    ) -> dict:
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(
                    self.BASE_URL, headers=headers, params=params
                )
                if response.status_code == 429 and attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("OpenAQ response was not a JSON object")
                return body
            except (httpx2.HTTPError, ValueError) as exc:
                logger.warning(
                    "OpenAQ attempt {}/{} failed: {}",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(2**attempt)
        return {}
