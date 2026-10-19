from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from pydantic import Field
from typing import List

class TelemetryCreate(BaseModel):
    node_id: str
    timestamp: datetime
    flow_rate: float
    pressure: float
    ph_level: float
    tds_level: float

class GrievanceCreate(BaseModel):
    user_id: str
    village_id: int
    description: str
    image_url: Optional[str] = None
    timestamp: datetime

class TelemetrySummarySchema(BaseModel):
    total_daily_flow_liters: float = Field(..., description="Total aggregated flow over the past 24h")
    average_pressure_bar: float = Field(..., description="Mean pipeline pressure over the past 24h")
    meets_55_lpcd_benchmark: bool

class CriticalAnomalySchema(BaseModel):
    alert_id: int
    node_id: str
    anomaly_type: str
    severity: str
    timestamp: str

class ResolvedGrievanceSchema(BaseModel):
    grievance_id: int
    user_id: str
    description: str
    resolved_timestamp: str

class SujalGaonSyncRecord(BaseModel):
    sujal_gaon_id: str = Field(..., description="Official ID combining Infrastructure ID and Service Area ID")
    village_name: str
    infrastructure_id: str
    service_area_id: str
    reporting_period_start: str
    reporting_period_end: str
    telemetry_summary: TelemetrySummarySchema
    critical_anomalies: List[CriticalAnomalySchema]
    resolved_grievances: List[ResolvedGrievanceSchema]

class IMISSyncPayload(BaseModel):
    sync_batch_id: str
    sync_timestamp: str
    architecture_version: str = "Sujalam_Bharat_v1.0"
    village_records: List[SujalGaonSyncRecord]