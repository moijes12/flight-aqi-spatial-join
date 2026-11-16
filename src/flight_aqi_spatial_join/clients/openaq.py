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
            if not isinstance(location, dict):
                continue
            extracted = AirQualitySensor.from_openaq_location(location)
            if any(sensor.pm25_value is None for sensor in extracted):
                latest = await self._latest_by_sensor(
                    client, headers, location.get("id")
                )
                extracted = [
                    sensor.model_copy(
                        update={
                            "pm25_value": latest[sensor.sensor_id][0],
                            "measured_at": latest[sensor.sensor_id][1]
                            or sensor.measured_at,
                        }
                    )
                    if sensor.pm25_value is None and sensor.sensor_id in latest
                    else sensor
                    for sensor in extracted
                ]
            sensors.extend(extracted)
        logger.info("Extracted {} PM2.5 sensors from OpenAQ.", len(sensors))
        return sensors

    async def _latest_by_sensor(
        self,
        client: httpx2.AsyncClient,
        headers: dict[str, str],
        location_id: Any,
    ) -> dict[int, tuple[float | None, str | None]]:
        """OpenAQ location documents omit the latest reading; /latest has it."""
        if location_id is None:
            return {}
        url = f"https://api.openaq.org/v3/locations/{location_id}/latest"
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            body = response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            logger.warning("OpenAQ latest readings failed for {}: {}", location_id, exc)
            return {}
        readings = body.get("results") if isinstance(body, dict) else None
        if not isinstance(readings, list):
            return {}
        values: dict[int, tuple[float | None, str | None]] = {}
        for reading in readings:
            if not isinstance(reading, dict) or reading.get("sensorsId") is None:
                continue
            measured_at = reading.get("datetime")
            if isinstance(measured_at, dict):
                measured_at = measured_at.get("utc")
            value = reading.get("value")
            values[int(reading["sensorsId"])] = (
                float(value) if value is not None else None,
                str(measured_at) if measured_at else None,
            )
        return values

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
                if response.status_code >= 400:
                    logger.warning(
                        "OpenAQ HTTP {}: {}",
                        response.status_code,
                        response.text[:300],
                    )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("OpenAQ response was not a JSON object")
                return body
            except httpx2.HTTPStatusError as exc:
                # A 422 is a bad query, such as a radius above OpenAQ's 25 km cap.
                if exc.response.status_code != 429 or attempt == self.max_retries:
                    raise
                await asyncio.sleep(2**attempt)
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
