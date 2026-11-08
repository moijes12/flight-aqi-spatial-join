import os
import threading
import time
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI
from google.cloud import pubsub_v1
from loguru import logger

# Configuration from environment variables
PROJECT_ID = os.getenv("PROJECT_ID", "flight-aqi-spatial-join")
PUBSUB_TOPIC_ID = os.getenv("PUBSUB_TOPIC_ID", "flight-telemetry-topic")
AIRLABS_API_KEY = os.getenv("AIRLABS_API_KEY", "")
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "")

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_ID)


def fetch_airlabs_data():
    """Poll live flight telemetry from AirLabs API (Pune regional bounding box)."""
    url = f"https://airlabs.co/api/v9/flights?api_key={AIRLABS_API_KEY}&box=18.0,73.0,19.0,74.0"
    try:
        with httpx2.Client() as client:
            response = client.get(url)
            if response.status_code == 200:
                return response.json().get("response", [])
            logger.error(f"AirLabs API error: {response.status_code} - {response.text}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Exception fetching AirLabs data: {e}")
    return []


def fetch_openaq_data():
    """Poll atmospheric air quality readings from OpenAQ API."""
    url = "https://api.openaq.org/v3/locations"
    headers = {"X-API-Key": OPENAQ_API_KEY} if OPENAQ_API_KEY else {}
    try:
        with httpx2.Client() as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json().get("results", [])
            logger.error(f"OpenAQ API error: {response.status_code} - {response.text}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Exception fetching OpenAQ data: {e}")
    return []


def background_ingestion_loop():
    """Continuous background worker loop for polling APIs and pushing to Pub/Sub."""
    logger.info(
        "Starting continuous flight telemetry & air quality ingestion worker..."
    )
    while True:
        try:
            logger.info("Polling AirLabs and OpenAQ APIs...")
            flights = fetch_airlabs_data()
            sensors = fetch_openaq_data()

            payload = {
                "flights": flights,
                "sensors": sensors,
                "timestamp": time.time(),
            }
            data_bytes = str(payload).encode("utf-8")
            future = publisher.publish(topic_path, data=data_bytes)
            logger.info(f"Published batch to Pub/Sub: message_id={future.result()}")

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error during ingestion poll cycle: {e}")

        time.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager to spawn the background ingestion thread on startup."""
    logger.info("Initializing background ingestion thread...")
    ingestion_thread = threading.Thread(target=background_ingestion_loop, daemon=True)
    ingestion_thread.start()
    yield
    logger.info("Shutting down ingestion service...")


# Initialize FastAPI app with lifespan handler
app = FastAPI(title="Flight AQI Ingestion Worker", lifespan=lifespan)


@app.get("/")
def health_check():
    """Cloud Run health check endpoint."""
    return {"status": "healthy", "service": "flight-aqi-ingestion"}
