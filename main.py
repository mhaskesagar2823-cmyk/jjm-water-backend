import os
import joblib
import pandas as pd
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models, schemas
from database import engine, get_db

# Assuming notifier.py exists in your project with the Twilio logic
try:
    from notifier import send_vwsc_alert
except ImportError:
    def send_vwsc_alert(*args, **kwargs):
        print(f"Twilio alert skipped: notifier.py not found.")

ml_artifacts = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the FastAPI application.
    Loads the machine learning model into memory before accepting traffic.
    """
    model_path = "water_anomaly_detector.joblib"
    if os.path.exists(model_path):
        ml_artifacts["model"] = joblib.load(model_path)
        print(f"[ML Init] Loaded Isolation Forest model from '{model_path}' successfully[cite: 6].")
    else:
        ml_artifacts["model"] = None
        print(f"[ML Init Warning] Model file '{model_path}' not found! Run train_model.py first[cite: 6].")
    
    # Ensure the directory for citizen photos exists[cite: 5]
    os.makedirs("uploaded_grievances", exist_ok=True)
    
    yield
    ml_artifacts.clear()

# Initialize tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="JJM Water Monitoring API", lifespan=lifespan)

def classify_anomaly(flow_rate: float, pressure: float) -> tuple[str, str]:
    """Classifies the severity of an anomaly based on operational thresholds[cite: 6]."""
    if flow_rate <= 5.0 and pressure <= 0.15:
        return "PIPE_BURST_OR_OUTAGE", "CRITICAL"
    elif pressure < 0.28:
        return "GRADUAL_PIPELINE_LEAK", "HIGH"
    elif flow_rate > 70.0:
        return "OVERFLOW_OR_UNREGULATED_SUPPLY", "MEDIUM"
    else:
        return "UNUSUAL_PRESSURE_FLOW_PATTERN", "LOW"

@app.post("/api/telemetry", status_code=201)
def ingest_telemetry(
    payload: schemas.TelemetryCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    # 1. Save Raw Telemetry[cite: 6]
    new_data = models.SensorTelemetry(**payload.model_dump())
    db.add(new_data)
    db.commit()
    db.refresh(new_data)

    model = ml_artifacts.get("model")
    ml_flagged = False
    anomaly_details = None

    # 2. Run AI Inference if model is loaded[cite: 6]
    if model is not None:
        input_features = pd.DataFrame([{"flow_rate": payload.flow_rate, "pressure": payload.pressure}])
        prediction = model.predict(input_features)[0] # -1 is anomaly, 1 is normal

        if prediction == -1:
            ml_flagged = True
            anomaly_type, severity = classify_anomaly(payload.flow_rate, payload.pressure)

            # 3. Save Alert to Database[cite: 6]
            alert_entry = models.MLAlert(
                node_id=payload.node_id,
                timestamp=payload.timestamp or datetime.utcnow(),
                anomaly_type=anomaly_type,
                severity=severity
            )
            db.add(alert_entry)
            db.commit()

            anomaly_details = {"anomaly_type": anomaly_type, "severity": severity}

            # 4. Trigger Twilio Alert asynchronously in the background[cite: 6]
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

@app.post("/api/grievances", status_code=201)
async def submit_grievance(
    user_id: str = Form(...),
    village_id: int = Form(...),
    description: str = Form(...),
    latitude: float = Form(0.0),
    longitude: float = Form(0.0),
    timestamp: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """Accepts multipart/form-data from the Flutter offline-sync engine[cite: 5]."""
    village = db.query(models.SujalGaon).filter(models.SujalGaon.village_id == village_id).first()
    if not village:
        raise HTTPException(status_code=404, detail="Village ID not found")
        
    image_location = None
    if image:
        image_location = f"uploaded_grievances/{image.filename}"
        with open(image_location, "wb") as f:
            f.write(await image.read())
            
    # Parse timestamp safely
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        parsed_timestamp = datetime.utcnow()

    new_grievance = models.CitizenGrievance(
        user_id=user_id,
        village_id=village_id,
        description=description,
        image_url=image_location,
        timestamp=parsed_timestamp
    )
    db.add(new_grievance)
    db.commit()
    
    return {"status": "success", "message": "Grievance submitted successfully"}

@app.post("/api/v1/imis_sync", status_code=200)
def mock_imis_sync(payload: schemas.IMISSyncPayload):
    """Validates the structured Sujalam Bharat JSON payload for central handover."""
    print(f"🏛️ [CENTRAL IMIS SERVER] BATCH RECEIVED: {payload.sync_batch_id}")
    return {
        "status": "success",
        "message": "Data successfully validated and ingested into Central IMIS.",
        "batch_id": payload.sync_batch_id,
        "processed_villages": len(payload.village_records),
        "ingestion_timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/api/dashboard/data")
def get_dashboard_data(limit: int = 50, db: Session = Depends(get_db)):
    telemetry = db.query(models.SensorTelemetry)\
                  .order_by(desc(models.SensorTelemetry.timestamp))\
                  .limit(limit).all()
    
    alerts = db.query(models.MLAlert)\
               .order_by(desc(models.MLAlert.timestamp))\
               .limit(limit).all()
               
    return {
        "recent_telemetry": telemetry,
        "recent_alerts": alerts
    }
