# HydroLux — IoT Hydroponics Monitoring System (Python Backend)

HydroLux is a backend service for an ESP32-based hydroponics monitoring system.
ESP32 nodes publish sensor data over MQTT; this service subscribes, validates, stores readings in Firebase Firestore, raises alerts when values go out of range, and exposes the data via a REST API.

---

## Project Structure

```
capstone 2/
├── main.py                 # Entry point — starts MQTT thread + FastAPI server
├── requirements.txt
├── .env                    # Runtime configuration (edit before running)
├── serviceAccount.json     # Firebase credentials — ADD THIS MANUALLY
│
├── mqtt/
│   └── subscriber.py       # Subscribes to MQTT broker, forwards data to Firebase
│
├── firebase/
│   └── client.py           # Firestore read/write + threshold alert logic
│
├── api/
│   └── routes.py           # FastAPI REST endpoints
│
└── mock/
    └── publisher.py        # Simulated ESP32 — publishes fake sensor data for testing
```

---

## Sensor Parameters & Safe Ranges

| Parameter        | Safe Range      | Alert if outside |
|-----------------|-----------------|-----------------|
| pH              | 5.5 – 7.5       | LOW / HIGH      |
| EC              | 0.5 – 3.0 mS/cm | LOW / HIGH      |
| Water Temp      | 18 – 28 °C      | LOW / HIGH      |
| Humidity        | 50 – 80 %       | LOW / HIGH      |
| Ambient Temp    | logged only     | —               |

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| Python ≥ 3.10 | Runtime |
| Mosquitto (or any MQTT broker) | Message broker |
| Firebase project + Firestore enabled | Database |

### Install Mosquitto

**macOS**
```bash
brew install mosquitto
brew services start mosquitto
```

**Ubuntu / Debian**
```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

---

## Setup

### 1. Clone / open the project folder

```bash
cd "capstone 2"
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add Firebase credentials

Download your service account key from the Firebase console:

> Firebase Console → Project Settings → Service Accounts → Generate new private key

Save the downloaded file as **`serviceAccount.json`** in the project root.

### 5. Configure environment variables

Edit `.env` to match your setup:

```dotenv
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_TOPIC=hydrolux/sensors/#
FIREBASE_CREDENTIALS_PATH=serviceAccount.json
API_HOST=0.0.0.0
API_PORT=8000
```

---

## Running the Backend

```bash
# Make sure the venv is active and Mosquitto is running
python main.py
```

You will see:

```
[HydroLux] MQTT subscriber thread started
[MQTT] Connecting to localhost:1883 ...
[MQTT] Connected to broker at localhost:1883
[MQTT] Subscribed to topic: hydrolux/sensors/#
[Firebase] App initialised with credentials from 'serviceAccount.json'
[Firebase] Firestore client ready
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Testing Without Hardware (Mock Publisher)

Open a **second terminal**, activate the venv, and run:

```bash
python mock/publisher.py
```

The publisher sends a new simulated reading every 5 seconds to
`hydrolux/sensors/data`. About 20 % of messages contain out-of-range values
so you can verify that alerts are written to Firestore's `alert_log` collection.

---

## REST API Endpoints

Base URL: `http://localhost:8000`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/readings/latest` | Most recent sensor reading |
| GET | `/readings/history` | All readings from the last 24 hours |

Interactive docs (Swagger UI): `http://localhost:8000/docs`

### Example responses

**GET /readings/latest**
```json
{
  "status": "success",
  "data": {
    "id": "abc123",
    "device_id": "esp32_node_01",
    "ph": 6.5,
    "ec": 1.8,
    "water_temp": 22.4,
    "ambient_temp": 26.1,
    "humidity": 63.0,
    "received_at": "2026-06-08T10:00:00+00:00",
    "server_timestamp": "..."
  }
}
```

**GET /readings/history**
```json
{
  "status": "success",
  "count": 42,
  "data": [ ... ]
}
```

---

## MQTT Topic & Payload Format

**Topic:** `hydrolux/sensors/data` (matches the `hydrolux/sensors/#` subscription)

**Payload (JSON):**
```json
{
  "device_id": "esp32_node_01",
  "ph": 6.5,
  "ec": 1.8,
  "water_temp": 22.4,
  "ambient_temp": 26.1,
  "humidity": 63.0
}
```

---

## Firebase Collections

| Collection | Contents |
|-----------|---------|
| `sensor_readings` | One document per incoming payload |
| `alert_log` | One document per threshold violation |

---

## Deactivating the Environment

```bash
deactivate
```
