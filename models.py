from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text
import enum
import datetime
from database import Base

class SeverityEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class StatusEnum(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"

class SujalGaon(Base):
    __tablename__ = "sujal_gaon_ids"
    village_id = Column(Integer, primary_key=True, index=True)
    village_name = Column(String(255), nullable=False)
    infrastructure_id = Column(String(100), unique=True, nullable=False)
    service_area_id = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SensorTelemetry(Base):
    __tablename__ = "sensor_telemetry"
    telemetry_id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(100), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    flow_rate = Column(Float, nullable=False)
    pressure = Column(Float, nullable=False)
    ph_level = Column(Float, nullable=False)
    tds_level = Column(Float, nullable=False)

class MLAlert(Base):
    __tablename__ = "ml_alerts"
    alert_id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(100), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    anomaly_type = Column(String(100), nullable=False)
    severity = Column(Enum(SeverityEnum), nullable=False)

class CitizenGrievance(Base):
    __tablename__ = "citizen_grievances"
    grievance_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False)
    village_id = Column(Integer, ForeignKey("sujal_gaon_ids.village_id"), nullable=False)
    description = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(Enum(StatusEnum), default=StatusEnum.OPEN)