"""
HydroLux Hydroponics Monitoring System
Main entry point — starts the MQTT subscriber in a background thread
and launches the FastAPI server.
"""

import threading
import os
import uvicorn
from dotenv import load_dotenv

# Load .env before importing modules that read env vars at import time
load_dotenv()

from mqtt.subscriber import MQTTSubscriber
from api.routes import app  # noqa: F401  (imported so uvicorn can find it)


def start_mqtt_subscriber():
    """Run the MQTT subscriber loop (blocking — intended for a daemon thread)."""
    subscriber = MQTTSubscriber()
    subscriber.start()


if __name__ == "__main__":
    # MQTT runs in a daemon thread so it exits automatically when the main
    # process (FastAPI/uvicorn) is stopped with Ctrl-C.
    mqtt_thread = threading.Thread(target=start_mqtt_subscriber, daemon=True, name="mqtt-subscriber")
    mqtt_thread.start()
    print("[HydroLux] MQTT subscriber thread started")

    # FastAPI server — blocks until stopped
    uvicorn.run(
        "api.routes:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=False,
    )
