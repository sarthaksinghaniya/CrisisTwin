from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime

class ComplaintRequest(BaseModel):
    text: str = Field(..., description="The text of the complaint to analyze", example="The AC in my room is leaking water.")

class ClassificationResponse(BaseModel):
    labels: List[str] = Field(..., description="Predicted categories", example=["maintenance", "water_leak"])
    confidence: float = Field(..., description="Confidence score", example=0.95)

class QueryRequest(BaseModel):
    query: str = Field(..., description="Search query", example="How to fix AC leak")

class RAGResponse(BaseModel):
    context: List[str] = Field(..., description="Retrieved context from FAISS", example=["AC units might leak if the drain pipe is clogged."])

class AgentDecisionResponse(BaseModel):
    decision: str = Field(..., description="The recommended action", example="Dispatch maintenance team immediately.")
    reasoning: str = Field(..., description="Reasoning behind the decision", example="Water leak can cause property damage.")

class MemorySearchResponse(BaseModel):
    incidents: List[Dict[str, Any]] = Field(..., description="Similar past incidents retrieved from memory", example=[{"complaint": "AC leaking", "decision": "Fixed drain", "outcome": "Success"}])

class PipelineResponse(BaseModel):
    task_id: str = Field(..., description="ID of the background task", example="task-456")
    status: str = Field(..., description="Status of the pipeline execution", example="accepted")

class PipelineRunRequest(BaseModel):
    ticket_id: str
