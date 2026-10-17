from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models, schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="JJM Water Monitoring API")

@app.post("/api/telemetry", status_code=201)
def ingest_telemetry(payload: schemas.TelemetryCreate, db: Session = Depends(get_db)):
    new_data = models.SensorTelemetry(**payload.model_dump())
    db.add(new_data)
    db.commit()
    return {"status": "success", "message": "Telemetry data ingested successfully"}

@app.post("/api/grievances", status_code=201)
def submit_grievance(payload: schemas.GrievanceCreate, db: Session = Depends(get_db)):
    village = db.query(models.SujalGaon).filter(models.SujalGaon.village_id == payload.village_id).first()
    if not village:
        raise HTTPException(status_code=404, detail="Village ID not found")
        
    new_grievance = models.CitizenGrievance(**payload.model_dump())
    db.add(new_grievance)
    db.commit()
    return {"status": "success", "message": "Grievance submitted"}

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