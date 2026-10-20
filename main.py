import os
import joblib
import pandas as pd
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
import uuid

import models, schemas
from database import engine, get_db

try:
    from notifier import send_vwsc_alert
except ImportError:
    def send_vwsc_alert(*args, **kwargs):
        print("Twilio alert skipped: notifier.py not found.")

ml_artifacts = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    model_path = "water_anomaly_detector.joblib"
    if os.path.exists(model_path):
        ml_artifacts["model"] = joblib.load(model_path)
        print(f"[ML Init] Loaded Isolation Forest model from '{model_path}' successfully.")
    else:
        ml_artifacts["model"] = None
        print(f"[ML Init Warning] Model file '{model_path}' not found!")
    yield
    ml_artifacts.clear()

models.Base.metadata.create_all(bind=engine)
os.makedirs("uploaded_grievances", exist_ok=True)

app = FastAPI(title="JJM Water Monitoring & AI Alerting API", lifespan=lifespan)
app.mount("/uploaded_grievances", StaticFiles(directory="uploaded_grievances"), name="uploaded_grievances")

def classify_anomaly(flow_rate: float, pressure: float) -> tuple[str, str]:
    if flow_rate <= 5.0 and pressure <= 0.15:
        return "PIPE_BURST_OR_OUTAGE", "CRITICAL"
    elif pressure < 0.28:
        return "GRADUAL_PIPELINE_LEAK", "HIGH"
    elif flow_rate > 70.0:
        return "OVERFLOW_OR_UNREGULATED_SUPPLY", "MEDIUM"
    else:
        return "UNUSUAL_PRESSURE_FLOW_PATTERN", "LOW"

# 1. Single Root Route: Serves dashboard.html if present, otherwise returns status JSON
@app.get("/")
async def serve_dashboard():
    if os.path.exists("dashboard.html"):
        return FileResponse("dashboard.html")
    return {
        "status": "online",
        "service": "JJM Water Monitoring API",
        "model_loaded": ml_artifacts.get("model") is not None
    }

# 2. Health Check Endpoint (if you ever want to check JSON status directly)
@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "JJM Water Monitoring API",
        "model_loaded": ml_artifacts.get("model") is not None
    }

# 3. Restored Telemetry & ML Scoring Endpoint
@app.post("/api/telemetry", status_code=201)
def ingest_telemetry(
    payload: schemas.TelemetryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    new_data = models.SensorTelemetry(**payload.model_dump())
    db.add(new_data)
    db.commit()
    db.refresh(new_data)

    model = ml_artifacts.get("model")
    ml_flagged = False
    anomaly_details = None

    if model is not None:
        input_features = pd.DataFrame([{"flow_rate": payload.flow_rate, "pressure": payload.pressure}])
        prediction = model.predict(input_features)[0]

        if prediction == -1:
            ml_flagged = True
            anomaly_type, severity = classify_anomaly(payload.flow_rate, payload.pressure)

            alert_entry = models.MLAlert(
                node_id=payload.node_id,
                timestamp=payload.timestamp or datetime.utcnow(),
                anomaly_type=anomaly_type,
                severity=models.SeverityEnum(severity)
            )
            db.add(alert_entry)
            db.commit()

            anomaly_details = {"anomaly_type": anomaly_type, "severity": severity}

            if severity in ["CRITICAL", "HIGH"]:
                background_tasks.add_task(
                    send_vwsc_alert,
                    node_id=payload.node_id,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    flow_rate=payload.flow_rate,
                    pressure=payload.pressure
                )

    return {
        "status": "success",
        "message": "Telemetry received and scored",
        "anomaly_detected": ml_flagged,
        "details": anomaly_details
    }

# 4. Citizen Grievance & Photo Upload Endpoint


@app.post("/api/grievances", status_code=201)
async def submit_grievance(
    user_id: str = Form(...),
    village_id: int = Form(1),
    description: str = Form(...),
    latitude: float = Form(0.0),
    longitude: float = Form(0.0),
    timestamp: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    village = db.query(models.SujalGaon).filter(models.SujalGaon.village_id == village_id).first()
    if not village:
        raise HTTPException(status_code=404, detail="Village ID not found")

    image_location = None
    if image:
        # Sanitize filename to avoid spaces or special characters breaking the HTML <img> tag
        ext = os.path.splitext(image.filename)[1] or ".jpg"
        safe_filename = f"grievance_{uuid.uuid4().hex[:8]}{ext}"
        image_location = f"uploaded_grievances/{safe_filename}"
        with open(image_location, "wb") as f:
            f.write(await image.read())

    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        parsed_timestamp = datetime.utcnow()

    full_description = f"{description} [GPS: {latitude}, {longitude}]"

    new_grievance = models.CitizenGrievance(
        user_id=user_id,
        village_id=village_id,
        description=full_description,
        image_url=image_location,
        timestamp=parsed_timestamp
    )
    db.add(new_grievance)
    db.commit()

    return {"status": "success", "message": "Grievance saved to Aiven MySQL"}

# 5. Central IMIS Handover Endpoint
@app.post("/api/v1/imis_sync", status_code=200)
def mock_imis_sync(payload: schemas.IMISSyncPayload):
    print(f"🏛️ [CENTRAL IMIS SERVER] SUJALAM BHARAT HANDOVER RECEIVED: {payload.sync_batch_id}")
    return {
        "status": "success",
        "message": "Data successfully validated and ingested into Central IMIS.",
        "batch_id": payload.sync_batch_id,
        "processed_villages": len(payload.village_records),
        "ingestion_timestamp": datetime.utcnow().isoformat() + "Z"
    }

# 6. Dashboard Data Feed
@app.get("/api/dashboard/data")
def get_dashboard_data(limit: int = 50, db: Session = Depends(get_db)):
    telemetry = db.query(models.SensorTelemetry).order_by(desc(models.SensorTelemetry.timestamp)).limit(limit).all()
    alerts = db.query(models.MLAlert).order_by(desc(models.MLAlert.timestamp)).limit(limit).all()
    grievances = db.query(models.CitizenGrievance).order_by(desc(models.CitizenGrievance.timestamp)).limit(limit).all()
    return {
        "recent_telemetry": telemetry,
        "recent_alerts": alerts,
        "recent_grievances": grievances
    }