from pydantic import BaseModel, Field
from typing import Dict, List
from .analytics import OfficerRankItem

class CMMetrics(BaseModel):
    total_complaints: int = Field(..., description="Total active complaints count")
    pending: int = Field(..., description="Count of pending complaints")
    resolved: int = Field(..., description="Count of resolved complaints")
    escalated: int = Field(..., description="Count of escalated complaints")
    average_resolution_time: float = Field(..., description="Average resolution time in hours")
    average_sla: float = Field(..., description="Average SLA in hours")

class CMAnalyticsResponse(BaseModel):
    metrics: CMMetrics = Field(..., description="General performance counters")
    district_distribution: Dict[str, int] = Field(..., description="Districts with complaint counts")
    category_distribution: Dict[str, int] = Field(..., description="Categories with complaint counts")
    heatmap: Dict[str, int] = Field(..., description="Geographic heatmap mapping district to count")
    sla_metrics: Dict[str, float] = Field(..., description="Department average resolution times in hours")
    officer_ranking: List[OfficerRankItem] = Field(..., description="Officer ranking resolved counts descending")
