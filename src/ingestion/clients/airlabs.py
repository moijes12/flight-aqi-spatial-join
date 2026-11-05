import asyncio
import os
import time

import httpx
from loguru import logger

from src.ingestion.schemas import FlightTelemetry


class AirLabsClient:
    """Cloud-safe asynchronous client for fetching live flight telemetry from AirLabs API."""

    def __init__(self, max_retries: int = 3) -> None:
        self.api_key = os.getenv("AIRLABS_API_KEY", None)
        self.base_url = "https://airlabs.co/api/v9/flights"
        self.max_retries = max_retries

        # Optional bounding box: min_lat,min_lng,max_lat,max_lng (e.g. covering India/region)
        self.bbox = os.getenv("AIRLABS_BBOX", None)

    def fetch_flights(self) -> list[FlightTelemetry]:
        """Synchronous fetch executed via worker thread."""
        if not self.api_key:
            logger.error("AIRLABS_API_KEY environment variable is missing.")
            return []

        params = {"api_key": self.api_key}
        if self.bbox:
            params["bbox"] = self.bbox

        response_data = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Attempt {attempt}/{self.max_retries}: Calling AirLabs API..."
                )
                with httpx.Client(timeout=15.0) as client:
                    response = client.get(self.base_url, params=params)
                    response.raise_for_status()
                    response_data = response.json()
                    break
            except Exception as e:  # noqa: BLE001
                logger.error(f"AirLabs attempt #{attempt} failed: {e}")
                if attempt == self.max_retries:
                    logger.error("All AirLabs retry attempts exhausted.")
                    return []
                time.sleep(2**attempt)

        if not response_data or "response" not in response_data:
            logger.warning("AirLabs returned empty or malformed response.")
            return []

        raw_flights = response_data["response"]
        flights: list[FlightTelemetry] = []

        for item in raw_flights:
            lat = item.get("lat")
            lon = item.get("lng")
            if lat is None or lon is None:
                continue

            try:
                flight_data = FlightTelemetry(
                    icao24=item.get("hex", "UNKNOWN"),
                    callsign=item.get("flight_number") or item.get("reg") or "UNKNOWN",
                    origin_country=item.get("flag", "UNKNOWN"),
                    longitude=float(lon),
                    latitude=float(lat),
                    baro_altitude=float(item.get("alt", 0.0) or 0.0),
                    vertical_rate=float(item.get("vs", 0.0) or 0.0),
                )
                flights.append(flight_data)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Error parsing AirLabs flight item: {e}")

        logger.info(
            f"Successfully validated and converted {len(flights)} AirLabs flight records."
        )
        return flights

    async def fetch_flight_data(self) -> list[FlightTelemetry]:
        """Asynchronous wrapper for the AirLabs HTTP client call."""
        logger.info("Initiating asynchronous AirLabs fetch...")
        return await asyncio.to_thread(self.fetch_flights)
