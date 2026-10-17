
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# --------------------------------------------------
# PostgreSQL CONFIGURATION
# --------------------------------------------------

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "autosense_db",
    "user": "postgres",
    "password": "research123",
}


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(title="AutoSense API")


# CORS: Allow local HTML dashboard during development.
# Restrict this when deploying beyond local testing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "null",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# COLLECTION CONTROL STATE
# --------------------------------------------------

collection_enabled = False


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Database connection failed. Check PostgreSQL settings."
        ) from exc


# --------------------------------------------------
# SENSOR DATA MODEL
# --------------------------------------------------

class SensorReading(BaseModel):
    vehicle_id: str
    accel_x: Optional[int] = None
    accel_y: Optional[int] = None
    accel_z: Optional[int] = None
    temperature_c: Optional[float] = None
    voltage_adc: Optional[int] = None
    pin_voltage_v: Optional[float] = None


# --------------------------------------------------
# ROOT ENDPOINT
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "AutoSense API is running",
        "database": "autosense_db"
    }


# --------------------------------------------------
# DATABASE HEALTH CHECK
# --------------------------------------------------

@app.get("/health/db")
def database_health():
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()

        return {"database": "connected"}

    finally:
        conn.close()


# --------------------------------------------------
# START DATA COLLECTION
# --------------------------------------------------

@app.post("/control/start")
def start_collection():
    global collection_enabled

    collection_enabled = True

    return {
        "message": "Data collection started",
        "enabled": True
    }


# --------------------------------------------------
# STOP DATA COLLECTION
# --------------------------------------------------

@app.post("/control/stop")
def stop_collection():
    global collection_enabled

    collection_enabled = False

    return {
        "message": "Data collection stopped",
        "enabled": False
    }


# --------------------------------------------------
# GET COLLECTION STATUS
# --------------------------------------------------

@app.get("/control/status")
def collection_status():
    return {"enabled": collection_enabled}


# --------------------------------------------------
# SAVE SENSOR READINGS
# --------------------------------------------------

@app.post("/readings")
def save_reading(reading: SensorReading):
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sensor_readings (
                    vehicle_id,
                    accel_x,
                    accel_y,
                    accel_z,
                    temperature_c,
                    voltage_adc,
                    pin_voltage_v
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, recorded_at
                """,
                (
                    reading.vehicle_id,
                    reading.accel_x,
                    reading.accel_y,
                    reading.accel_z,
                    reading.temperature_c,
                    reading.voltage_adc,
                    reading.pin_voltage_v,
                )
            )

            saved = cur.fetchone()

        conn.commit()

        return {
            "message": "Reading saved",
            "id": saved[0],
            "recorded_at": saved[1].isoformat()
        }

    except psycopg2.Error as exc:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save sensor reading"
        ) from exc

    finally:
        conn.close()


# --------------------------------------------------
# GET LATEST SENSOR READINGS
# --------------------------------------------------

@app.get("/readings/latest")
def latest_readings(limit: int = 10):
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 500"
        )

    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    vehicle_id,
                    recorded_at,
                    accel_x,
                    accel_y,
                    accel_z,
                    temperature_c,
                    voltage_adc,
                    pin_voltage_v
                FROM sensor_readings
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,)
            )

            rows = cur.fetchall()

        # Return a JSON array, newest reading first.
        result = []

        for row in rows:
            item = dict(row)

            if item["recorded_at"] is not None:
                item["recorded_at"] = (
                    item["recorded_at"].isoformat()
                )

            result.append(item)

        return result

    finally:
        conn.close()
