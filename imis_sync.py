import sys
import uuid
import json
import logging
import requests
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from database import SessionLocal
import models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("IMIS_Sync_Engine")

IMIS_ENDPOINT_URL = "http://localhost:8000/api/v1/imis_sync"

def aggregate_and_format_data() -> dict:
    db = SessionLocal()
    now = datetime.utcnow()
    past_24h = now - timedelta(hours=24)

    payload = {
        "sync_batch_id": f"JJM-BATCH-{uuid.uuid4().hex[:8].upper()}",
        "sync_timestamp": now.isoformat() + "Z",
        "architecture_version": "Sujalam_Bharat_v1.0",
        "village_records": []
    }

    try:
        villages = db.query(models.SujalGaon).all()
        if not villages:
            logger.warning("No villages found in 'sujal_gaon_ids' table.")
            return payload

        telemetry_stats = (
            db.query(
                func.sum(models.SensorTelemetry.flow_rate).label("total_flow"),
                func.avg(models.SensorTelemetry.pressure).label("avg_pressure")
            )
            .filter(models.SensorTelemetry.timestamp >= past_24h)
            .first()
        )

        total_flow = round(float(telemetry_stats.total_flow or 0.0), 2)
        avg_pressure = round(float(telemetry_stats.avg_pressure or 0.0), 2)

        critical_alerts = (
            db.query(models.MLAlert)
            .filter(
                models.MLAlert.timestamp >= past_24h,
                models.MLAlert.severity == models.SeverityEnum.CRITICAL
            )
            .order_by(models.MLAlert.timestamp.desc())
            .all()
        )

        formatted_alerts = [
            {
                "alert_id": alert.alert_id,
                "node_id": alert.node_id,
                "anomaly_type": alert.anomaly_type,
                "severity": alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity),
                "timestamp": alert.timestamp.isoformat() + "Z"
            }
            for alert in critical_alerts
        ]

        for village in villages:
            official_sujal_gaon_id = f"SG-{village.infrastructure_id}-{village.service_area_id}"

            resolved_complaints = (
                db.query(models.CitizenGrievance)
                .filter(
                    models.CitizenGrievance.village_id == village.village_id,
                    models.CitizenGrievance.status == models.StatusEnum.RESOLVED
                )
                .all()
            )

            formatted_grievances = [
                {
                    "grievance_id": comp.grievance_id,
                    "user_id": comp.user_id,
                    "description": comp.description,
                    "resolved_timestamp": comp.timestamp.isoformat() + "Z"
                }
                for comp in resolved_complaints
            ]

            village_bundle = {
                "sujal_gaon_id": official_sujal_gaon_id,
                "village_name": village.village_name,
                "infrastructure_id": village.infrastructure_id,
                "service_area_id": village.service_area_id,
                "reporting_period_start": past_24h.isoformat() + "Z",
                "reporting_period_end": now.isoformat() + "Z",
                "telemetry_summary": {
                    "total_daily_flow_liters": total_flow,
                    "average_pressure_bar": avg_pressure,
                    "meets_55_lpcd_benchmark": (total_flow / 5.0) >= 55.0
                },
                "critical_anomalies": formatted_alerts,
                "resolved_grievances": formatted_grievances
            }

            payload["village_records"].append(village_bundle)

        logger.info(f"Successfully aggregated data for {len(villages)} village(s).")
        return payload

    except SQLAlchemyError as db_err:
        logger.error(f"Database query failed during IMIS aggregation: {db_err}")
        raise
    except Exception as exc:
        logger.error(f"Unexpected error during data formatting: {exc}")
        raise
    finally:
        db.close()

def push_to_imis():
    logger.info("Starting daily IMIS synchronization job...")
    try:
        sync_payload = aggregate_and_format_data()
        if not sync_payload["village_records"]:
            logger.warning("Sync aborted: No village records available to transmit.")
            return

        logger.info(f"Generated Sujalam Bharat Payload:\n{json.dumps(sync_payload, indent=2)}")

        headers = {"Content-Type": "application/json"}
        response = requests.post(
            IMIS_ENDPOINT_URL,
            json=sync_payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        logger.info(f"✅ Sync Successful! Server responded ({response.status_code}): {response.json()}")

    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Network Error: Could not connect to IMIS endpoint at {IMIS_ENDPOINT_URL}. Ensure FastAPI is running.")
    except Exception as err:
        logger.error(f"❌ IMIS Sync Job Failed: {err}")

def start_scheduler():
    scheduler = BlockingScheduler()
    scheduler.add_job(
        push_to_imis,
        trigger=CronTrigger(hour=0, minute=0),
        id="daily_imis_sync",
        name="Jal Jeevan Mission Daily Central IMIS Handover",
        replace_existing=True
    )
    logger.info("🕒 APScheduler initialized. IMIS sync job scheduled to run daily at 00:00 (Midnight).")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("IMIS Sync Scheduler stopped cleanly.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logger.info("Manual trigger detected (--now). Executing sync immediately...")
        push_to_imis()
    else:
        start_scheduler()