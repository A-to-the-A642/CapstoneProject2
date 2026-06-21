"""
MQTT Subscriber Service
Connects to the MQTT broker and listens for JSON sensor payloads published
by ESP32 devices on the 'hydrolux/sensors/#' topic tree.

Expected JSON payload from ESP32:
{
    "device_id": "esp32_node_01",
    "ph": 6.5,
    "ec": 1.8,
    "water_temp": 22.4,
    "ambient_temp": 26.1,
    "humidity": 63.0
}
"""

import json
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from firebase.client import FirebaseClient


class MQTTSubscriber:
    def __init__(self):
        self.broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        self.broker_port = int(os.getenv("MQTT_BROKER_PORT", 1883))
        self.topic = os.getenv("MQTT_TOPIC", "hydrolux/sensors/#")

        # Reuse the Firebase singleton — no extra initialisation cost
        self.firebase = FirebaseClient()

        self.client = mqtt.Client(client_id="hydrolux_backend_subscriber")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        """Called once the broker acknowledges the connection."""
        if rc == 0:
            print(f"[MQTT] Connected to broker at {self.broker_host}:{self.broker_port}")
            # Subscribe after connect so resubscription happens automatically
            # on reconnect as well.
            client.subscribe(self.topic, qos=1)
            print(f"[MQTT] Subscribed to topic: {self.topic}")
        else:
            # rc codes: 1=bad protocol, 2=client id rejected, 3=server unavailable,
            # 4=bad credentials, 5=not authorised
            print(f"[MQTT] Connection refused — return code {rc}")

    def _on_message(self, client, userdata, msg):
        """Called each time a message arrives on a subscribed topic."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            print(f"[MQTT] Message received on {msg.topic}: {payload}")

            # Attach routing metadata before handing off to Firebase
            payload["mqtt_topic"] = msg.topic
            payload["received_at"] = datetime.now(timezone.utc).isoformat()

            self.firebase.store_sensor_reading(payload)

        except json.JSONDecodeError as exc:
            print(f"[MQTT] Invalid JSON payload on {msg.topic}: {exc}")
        except Exception as exc:
            print(f"[MQTT] Unexpected error processing message: {exc}")

    def _on_disconnect(self, client, userdata, rc):
        """Called when the connection to the broker is lost."""
        if rc != 0:
            print(f"[MQTT] Unexpected disconnection (rc={rc}). Paho will attempt to reconnect.")
        else:
            print("[MQTT] Disconnected cleanly.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self):
        """Connect to the broker and block in the network loop forever."""
        try:
            print(f"[MQTT] Connecting to {self.broker_host}:{self.broker_port} ...")
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            # loop_forever handles reconnection automatically
            self.client.loop_forever()
        except ConnectionRefusedError:
            print(
                f"[MQTT] Could not reach broker at {self.broker_host}:{self.broker_port}. "
                "Make sure Mosquitto (or another broker) is running."
            )
        except Exception as exc:
            print(f"[MQTT] Fatal error in subscriber: {exc}")
