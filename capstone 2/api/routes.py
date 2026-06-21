"""
FastAPI REST API — HydroLux
Exposes HTTP endpoints that the dashboard or any external client can query
to retrieve sensor data stored in Firestore.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from firebase.client import FirebaseClient

app = FastAPI(
    title="HydroLux API",
    description="REST API for the HydroLux IoT Hydroponics Monitoring System",
    version="1.0.0",
)

# Allow all origins for development; tighten this in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Firebase singleton — safe to instantiate here; the SDK is already
# initialised by the time any request arrives.
_firebase = FirebaseClient()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def root():
    """Quick liveness probe — returns 200 if the API is up."""
    return {"status": "ok", "service": "HydroLux API", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Sensor readings
# ---------------------------------------------------------------------------

@app.get("/readings/latest", tags=["Readings"])
def get_latest_reading():
    """
    Return the single most recent sensor reading stored in Firestore.
    Raises 404 if no readings have been recorded yet.
    """
    reading = _firebase.get_latest_reading()
    if reading is None:
        raise HTTPException(status_code=404, detail="No sensor readings found in the database.")
    return {"status": "success", "data": reading}


@app.get("/readings/history", tags=["Readings"])
def get_readings_history():
    """
    Return all sensor readings from the last 24 hours, newest first.
    Returns an empty list (not 404) when there are no readings in that window.
    """
    readings = _firebase.get_readings_last_24h()
    return {
        "status": "success",
        "count": len(readings),
        "data": readings,
    }
