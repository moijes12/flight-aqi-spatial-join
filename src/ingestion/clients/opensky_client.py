import asyncio
import os

from loguru import logger
from opensky_api import OpenSkyApi, StateVector, TokenManager

from src.ingestion.schemas import FlightTelemetry


class OpenSkyClient:
    """Asynchronous client for fetching flight telemetry from the OpenSky Network API."""

    def __init__(self, credentials_path: str = "credentials.json") -> None:
        self.credentials_path = credentials_path

    def fetch_flights(self) -> list[FlightTelemetry]:
        """Query the OpenSky API and get a list of states parsed to FlightTelemetry objects."""
        api = None

        # Create an OpenSky api object
        if self.credentials_path and os.path.exists(self.credentials_path):
            try:
                token_manager = TokenManager.from_json_file(self.credentials_path)
                api = OpenSkyApi(token_manager=token_manager)
                logger.info("Created an OpenSky api object with a Token manager.")
            except Exception as e:  # noqa: BLE001
                logger.error(
                    f"Error creating an api object using tokens. Reverting to anonymous client. See error : {e}."
                )
                api = OpenSkyApi()
        else:
            logger.info(
                "Invalid or no credentials provided for OpenSky Api. Creating api object with anonymous client."
            )
            api = OpenSkyApi()

        try:
            with api:
                response = api.get_states()
        except Exception as e:  # noqa: BLE001
            logger.error(f"OpenSky API call failed with exception: {e}")
            return []

        if not response or not hasattr(response, "states") or not response.states:
            logger.warning("OpenSky returned empty states or null response.")
            return []

        states: list[StateVector] = response.states
        flights: list[FlightTelemetry] = []

        for state in states:
            if state.longitude is None or state.latitude is None:
                continue  # Skip records missing coordinates
            try:
                flight_data = FlightTelemetry(
                    icao24=state.icao24,
                    callsign=state.callsign.strip() if state.callsign else "UNKNOWN",
                    origin_country=state.origin_country,
                    longitude=state.longitude,
                    latitude=state.latitude,
                    baro_altitude=state.baro_altitude,
                    vertical_rate=state.vertical_rate,
                )
                flights.append(flight_data)
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    f"Error converting to FlightTelemetry data for StateVector {state.icao24}: {e}"
                )

        logger.info(
            f"Successfully validated and converted {len(flights)} flight records."
        )
        return flights

    async def fetch_flight_data(self) -> list[FlightTelemetry]:
        """Asynchronous wrapper for the blocking OpenSky SDK call."""
        logger.info("Initiating asynchronous OpenSky fetch via SDK...")
        return await asyncio.to_thread(self.fetch_flights)
