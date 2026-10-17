from pydantic import BaseModel
from datetime import datetime
from typing import Optional

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