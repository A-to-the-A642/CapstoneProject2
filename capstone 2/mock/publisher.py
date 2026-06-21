"""
Mock Sensor Publisher
Simulates an ESP32 microcontroller publishing JSON sensor data to the MQTT
broker so you can develop and test the backend without real hardware.

Run this in a separate terminal:
    python mock/publisher.py

The script publishes to 'hydrolux/sensors/data' every PUBLISH_INTERVAL seconds.
With --anomaly flag active (default), roughly 20 % of messages contain
out-of-range values to exercise the alert pipeline.
"""

import json
import os
import random
import sys
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
PUBLISH_TOPIC = "hydrolux/sensors/data"
PUBLISH_INTERVAL = 5          # seconds between publishes
ANOMALY_PROBABILITY = 0.20    # 20 % chance of an out-of-range reading
DEVICE_ID = "esp32_mock_001"


# ---------------------------------------------------------------------------
# Sensor data generation
# ---------------------------------------------------------------------------

def _normal_reading() -> dict:
    """Generate a reading where every value is inside the safe range."""
    return {
        "device_id": DEVICE_ID,
        "ph":           round(random.uniform(5.6, 7.4), 2),
        "ec":           round(random.uniform(0.6, 2.9), 2),
        "water_temp":   round(random.uniform(18.5, 27.5), 2),
        "ambient_temp": round(random.uniform(20.0, 30.0), 2),
        "humidity":     round(random.uniform(51.0, 79.0), 2),
    }


def _anomaly_reading() -> dict:
    """
    Generate a reading where at least one value is outside its safe range.
    Each run picks a random parameter to violate so all alert types get
    exercised over time.
    """
    reading = _normal_reading()

    # Pick 1-2 parameters to push out of range
    violators = random.sample(["ph", "ec", "water_temp", "humidity"], k=random.randint(1, 2))
    for param in violators:
        if param == "ph":
            reading["ph"] = round(random.choice([
                random.uniform(4.0, 5.4),   # too low
                random.uniform(7.6, 9.0),   # too high
            ]), 2)
        elif param == "ec":
            reading["ec"] = round(random.choice([
                random.uniform(0.1, 0.4),   # too low
                random.uniform(3.1, 5.0),   # too high
            ]), 2)
        elif param == "water_temp":
            reading["water_temp"] = round(random.choice([
                random.uniform(10.0, 17.9), # too cold
                random.uniform(28.1, 35.0), # too hot
            ]), 2)
        elif param == "humidity":
            reading["humidity"] = round(random.choice([
                random.uniform(20.0, 49.9), # too dry
                random.uniform(80.1, 98.0), # too humid
            ]), 2)

    return reading


def generate_reading(enable_anomalies: bool = True) -> dict:
    if enable_anomalies and random.random() < ANOMALY_PROBABILITY:
        return _anomaly_reading()
    return _normal_reading()


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[Mock] Connected to MQTT broker at {BROKER_HOST}:{BROKER_PORT}")
    else:
        print(f"[Mock] Connection failed — rc={rc}")
        sys.exit(1)


def _on_publish(client, userdata, mid):
    pass  # confirmation printed in the main loop for readability


# ---------------------------------------------------------------------------
# Publisher loop
# ---------------------------------------------------------------------------

def run(interval: int = PUBLISH_INTERVAL, enable_anomalies: bool = True):
    """Connect to the broker and publish simulated readings indefinitely."""
    client = mqtt.Client(client_id="hydrolux_mock_publisher")
    client.on_connect = _on_connect
    client.on_publish = _on_publish

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except ConnectionRefusedError:
        print(
            f"[Mock] Cannot connect to MQTT broker at {BROKER_HOST}:{BROKER_PORT}.\n"
            "       Start Mosquitto first:  brew services start mosquitto\n"
            "       or on Linux:            sudo systemctl start mosquitto"
        )
        sys.exit(1)

    client.loop_start()

    print(f"[Mock] Publishing to '{PUBLISH_TOPIC}' every {interval}s — Ctrl-C to stop")
    print(f"[Mock] Anomaly mode: {'ON' if enable_anomalies else 'OFF'}\n")

    msg_count = 0
    try:
        while True:
            msg_count += 1
            reading = generate_reading(enable_anomalies)
            payload = json.dumps(reading)
            result = client.publish(PUBLISH_TOPIC, payload, qos=1)
            result.wait_for_publish()

            # Pretty-print so out-of-range values are easy to spot
            print(f"[Mock] #{msg_count:04d} → {json.dumps(reading)}")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[Mock] Stopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    run()
