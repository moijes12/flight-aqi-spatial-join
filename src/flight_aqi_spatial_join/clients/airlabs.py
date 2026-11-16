import asyncio

import httpx2
from loguru import logger

from flight_aqi_spatial_join.schemas import FlightTelemetry


class AirLabsClient:
    """Fetch live flights and validate them as FlightTelemetry."""

    def __init__(
        self,
        api_key: str,
        bbox: str,
        arr_iata: str = "PNQ",
        timeout: float = 20.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.bbox = bbox
        self.arr_iata = arr_iata.upper()
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = "https://airlabs.co/api/v9/flights"

    async def fetch_flights(
        self, client: httpx2.AsyncClient | None = None
    ) -> list[FlightTelemetry]:
        owns_client = client is None
        if client is None:
            client = httpx2.AsyncClient(timeout=self.timeout)

        params = {
            "api_key": self.api_key,
            "bbox": self.bbox,
            "arr_iata": self.arr_iata,
        }
        try:
            payload = await self._get_json(client, params)
        finally:
            if owns_client:
                await client.aclose()

        raw_flights = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(raw_flights, list):
            logger.warning("AirLabs returned no flight list.")
            return []

        flights: list[FlightTelemetry] = []
        for item in raw_flights:
            if not isinstance(item, dict):
                continue
            arrival = item.get("arr_iata")
            if isinstance(arrival, str) and arrival.strip().upper() != self.arr_iata:
                continue
            try:
                flight = FlightTelemetry.from_airlabs(item)
            except ValueError as exc:
                logger.debug("Skipping invalid AirLabs flight: {}", exc)
                continue
            if flight is not None:
                flights.append(flight)

        logger.info("Validated {} AirLabs flights.", len(flights))
        return flights

    async def _get_json(
        self, client: httpx2.AsyncClient, params: dict[str, str]
    ) -> dict:
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(self.base_url, params=params)
                if response.status_code == 429 and attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("AirLabs response was not a JSON object")
                return body
            except (httpx2.HTTPError, ValueError) as exc:
                logger.warning(
                    "AirLabs attempt {}/{} failed: {}",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(2**attempt)
        return {}
