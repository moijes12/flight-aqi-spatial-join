import asyncio

from httpx2 import AsyncClient, HTTPStatusError, RequestError
from loguru import logger

from ingestion.schemas import FlightTelemetry


class OpenSkyClient:
    """Asynchronous client for fetching flight telemetry from the OpenSky Network API."""

    BASE_URL = "https://opensky-network.org/api"  # The root URL of OpenSky REST API
    STATES_PATH = "/states/all"  # The states API

    def __init__(self, timeout: float = 10.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    async def fetch_flights(
        self, client: AsyncClient | None = None
    ) -> list[FlightTelemetry]:
        """Fetch current flight states asynchronously with retry and rate-limit handling."""
        close_client = False

        if client is None:
            client = AsyncClient(timeout=self.timeout)
            close_client = True

        retries = 0
        backoff_factor = 2.0

        try:
            while retries < self.max_retries:
                try:
                    response = await client.get(f"{self.BASE_URL}{self.STATES_PATH}")
                    if response.status_code == 429:
                        wait_time = backoff_factor**retries
                        logger.warning(
                            f"OpenSky rate limit hit (429). Retrying in {wait_time} seconds..."
                        )
                        await asyncio.sleep(wait_time)
                        retries += 1
                        continue
                    response.raise_for_status()
                    data = response.json()
                    states = data.get("states", [])
                    if not states:
                        logger.info("OpenSky returned zero flight states.")
                        return []

                    parsed_flights = []
                    for vector in states:
                        flight = FlightTelemetry.from_opensky_vector(vector)
                        if flight:
                            parsed_flights.append(flight)
                    return parsed_flights
                except (RequestError, HTTPStatusError) as e:
                    retries += 1
                    if retries >= self.max_retries:
                        logger.error(
                            f"OpenSky request failed after {self.max_retries} attempts: {e}"
                        )
                        raise
                    wait_time = backoff_factor**retries
                    logger.warning(
                        f"Request error ({e}). Retrying in {wait_time}s (Attempt {retries}/{self.max_retries})..."
                    )
                    await asyncio.sleep(wait_time)

            return []
        finally:
            if close_client:
                await client.aclose()
