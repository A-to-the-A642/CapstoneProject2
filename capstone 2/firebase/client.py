"""
Firebase Firestore Client
Single-responsibility module for all Firestore interactions.

Collections used:
  sensor_readings — one document per incoming ESP32 payload
  alert_log       — one document per threshold violation
"""

import os
from datetime import datetime, timedelta, timezone

import firebase_admin
from firebase_admin import credentials, firestore


# ---------------------------------------------------------------------------
# Safe operating thresholds for each monitored parameter.
# ambient_temp is logged but has no defined alert range in the spec.
# ---------------------------------------------------------------------------
THRESHOLDS: dict[str, dict] = {
    "ph":         {"min": 5.5,  "max": 7.5,  "unit": ""},
    "ec":         {"min": 0.5,  "max": 3.0,  "unit": " mS/cm"},
    "water_temp": {"min": 18.0, "max": 28.0, "unit": "°C"},
    "humidity":   {"min": 50.0, "max": 80.0, "unit": "%"},
}


class FirebaseClient:
    """
    Singleton wrapper around the Firebase Admin SDK.
    The SDK itself must only be initialised once per process; the singleton
    pattern here enforces that even if FirebaseClient() is called from
    multiple modules.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ready = False
        return cls._instance

    def __init__(self):
        if not self._ready:
            self._init_firebase()
            self._ready = True

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_firebase(self):
        """Initialise the Firebase app and obtain a Firestore client."""
        creds_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccount.json")

        # Guard against double-initialisation if the module is reloaded
        if not firebase_admin._apps:
            cred = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(cred)
            print(f"[Firebase] App initialised with credentials from '{creds_path}'")

        self.db = firestore.client()
        print("[Firebase] Firestore client ready")

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def store_sensor_reading(self, data: dict):
        """
        Persist a sensor reading document and trigger threshold checks.
        Firestore's SERVER_TIMESTAMP is used so all timestamps are
        consistent regardless of device clock drift.
        """
        try:
            doc_data = {**data, "server_timestamp": firestore.SERVER_TIMESTAMP}
            _, doc_ref = self.db.collection("sensor_readings").add(doc_data)
            print(f"[Firebase] Stored reading — doc id: {doc_ref.id}")
            self._check_thresholds(data)
        except Exception as exc:
            print(f"[Firebase] Failed to store reading: {exc}")

    def _check_thresholds(self, data: dict):
        """
        Compare each measured value against its safe range.
        Writes one alert document per violation so every breach is recorded
        individually for later analysis.
        """
        device_id = data.get("device_id", "unknown")
        received_at = data.get("received_at", datetime.now(timezone.utc).isoformat())

        for param, limits in THRESHOLDS.items():
            value = data.get(param)
            if value is None:
                continue  # sensor not present in this payload

            below = value < limits["min"]
            above = value > limits["max"]

            if below or above:
                direction = "LOW" if below else "HIGH"
                safe_range = f"{limits['min']}–{limits['max']}{limits['unit']}"

                alert = {
                    "device_id": device_id,
                    "parameter": param,
                    "value": value,
                    "alert_type": direction,
                    "safe_range": safe_range,
                    "message": (
                        f"[{direction}] {param} = {value}{limits['unit']} "
                        f"(safe range: {safe_range})"
                    ),
                    "received_at": received_at,
                    "server_timestamp": firestore.SERVER_TIMESTAMP,
                }

                self.db.collection("alert_log").add(alert)
                print(f"[Firebase] ALERT — {alert['message']}")

    # ------------------------------------------------------------------
    # Read operations (used by the API)
    # ------------------------------------------------------------------

    def get_latest_reading(self) -> dict | None:
        """Return the most recently stored sensor reading, or None if empty."""
        try:
            docs = (
                self.db.collection("sensor_readings")
                .order_by("server_timestamp", direction=firestore.Query.DESCENDING)
                .limit(1)
                .stream()
            )
            for doc in docs:
                return {"id": doc.id, **doc.to_dict()}
            return None
        except Exception as exc:
            print(f"[Firebase] Error fetching latest reading: {exc}")
            return None

    def get_readings_last_24h(self) -> list[dict]:
        """Return all readings stored in the last 24 hours, newest first."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            docs = (
                self.db.collection("sensor_readings")
                .where("server_timestamp", ">=", cutoff)
                .order_by("server_timestamp", direction=firestore.Query.DESCENDING)
                .stream()
            )
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception as exc:
            print(f"[Firebase] Error fetching 24-hour history: {exc}")
            return []
