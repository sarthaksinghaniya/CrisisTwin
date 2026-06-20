import logging
import asyncio
from typing import List, Dict, Any

from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.core.config import settings

# -----------------------------------------------------------------------------
# LOGGING SETUP
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cm_dashboard.main")

# -----------------------------------------------------------------------------
# MODULAR IMPORTS
# -----------------------------------------------------------------------------
from app.services.ml.inference import MLInferenceService
from app.services.memory.retriever import ContextRetriever
from app.api.routes import api_router
from app.services.memory.faiss_memory import FaissMemory
from app.services.agents.decision_agent import DecisionAgent
from app.schemas.incident import (
    ComplaintRequest, 
    ClassificationResponse, 
    QueryRequest, 
    RAGResponse, 
    AgentDecisionResponse, 
    MemorySearchResponse, 
    PipelineResponse
)
from app.db.session import AsyncSessionLocal
from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.complaint_update import ComplaintUpdate
from app.services.routing.engine import RoutingEngine
from sqlalchemy.future import select

# -----------------------------------------------------------------------------
# DEPENDENCY INJECTION
# -----------------------------------------------------------------------------
def get_classifier_service() -> MLInferenceService:
    return MLInferenceService()

def get_rag_service() -> ContextRetriever:
    return ContextRetriever()

def get_memory_service() -> FaissMemory:
    return FaissMemory()

def get_agent_service() -> DecisionAgent:
    return DecisionAgent()

# -----------------------------------------------------------------------------
# ROUTERS
# -----------------------------------------------------------------------------
complaints_router = APIRouter(prefix=f"{settings.API_V1_STR}/complaints", tags=["Complaints"])

@complaints_router.post("/classify", response_model=ClassificationResponse)
async def classify_complaint(
    request: ComplaintRequest,
    service: MLInferenceService = Depends(get_classifier_service)
):
    try:
        res = service.predict(request.text)
        return ClassificationResponse(labels=res.get("category_pred", []), confidence=res.get("confidence_score", 0.0))
    except Exception as e:
        logger.error(f"Classification failure: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing classification request")

@complaints_router.post("/rag/query", response_model=RAGResponse)
async def query_rag(
    request: QueryRequest,
    service: ContextRetriever = Depends(get_rag_service)
):
    try:
        # get_context returns a dict with 'similar_cases'
        res = service.get_context(request.query)
        contexts = [c.get("metadata", {}).get("text", "") for c in res.get("similar_cases", [])]
        return RAGResponse(context=contexts)
    except Exception as e:
        logger.error(f"RAG retrieval failure: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error during RAG retrieval")

@complaints_router.post("/agent/decide", response_model=AgentDecisionResponse)
async def agent_decide(
    request: ComplaintRequest,
    rag_service: ContextRetriever = Depends(get_rag_service),
    memory_service: FaissMemory = Depends(get_memory_service),
    agent_service: DecisionAgent = Depends(get_agent_service),
    classifier_service: MLInferenceService = Depends(get_classifier_service)
):
    try:
        ml_res = classifier_service.predict(request.text)
        rag_result = rag_service.get_context(request.text)
        
        # In this implementation, memory and RAG overlap in FAISS, but we pass it structured
        decision = await agent_service.process(
            text=request.text,
            context=rag_result.get("similar_cases", []),
            ml_predictions=ml_res.get("category_pred", [])
        )
        return AgentDecisionResponse(
            decision=decision.get("decision", "No decision"), 
            reasoning=decision.get("reasoning", "No reasoning")
        )
    except Exception as e:
        logger.error(f"Agent decision failure: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error computing agent decision")

@complaints_router.get("/memory/search", response_model=MemorySearchResponse)
async def search_memory(
    query: str,
    service: FaissMemory = Depends(get_memory_service)
):
    try:
        res = service.search_similar(query)
        incidents = [r.get("metadata", {}) for r in res]
        return MemorySearchResponse(incidents=incidents)
    except Exception as e:
        logger.error(f"Memory search failure: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching memory")

# -----------------------------------------------------------------------------
# ASYNC PIPELINE TASK
# -----------------------------------------------------------------------------
async def execute_pipeline_task(ticket_id: str):
    """
    Background worker function that runs the complete CM-Dashboard pipeline.
    """
    logger.info(f"Starting async pipeline execution for ticket: {ticket_id}")
    
    try:
        classifier = get_classifier_service()
        rag = get_rag_service()
        memory = get_memory_service()
        agent = get_agent_service()
        
        async with AsyncSessionLocal() as session:
            # 1. Fetch Complaint
            query = select(Complaint).filter(Complaint.ticket_id == ticket_id)
            result = await session.execute(query)
            complaint = result.scalars().first()
            
            if not complaint:
                logger.error(f"Pipeline failed: Complaint {ticket_id} not found.")
                return

            text = complaint.description or complaint.title

            # 2. AI Classification
            classification_res = classifier.predict(text)
            labels = classification_res.get("category_pred", ["OTHER"])
            confidence = classification_res.get("confidence_score", 0.5)
            logger.info(f"[Ticket {ticket_id}] Classification complete: {labels}")
            
            # Predict Priority
            pred_priority_str = classifier.predict_severity(text)
            complaint.priority = PriorityEnum[pred_priority_str]
            complaint.category = labels[0] if labels else "OTHER"
            complaint.department = RoutingEngine.get_department(complaint.category)

            # 3. Routing & Assignment
            if confidence >= 0.7:
                assigned_to = await RoutingEngine.route_complaint(complaint.category, complaint.district, session)
                complaint.assigned_to = assigned_to
                if assigned_to:
                    complaint.status = ComplaintStatus.ASSIGNED
                    update = ComplaintUpdate(
                        complaint_id=complaint.id,
                        status=ComplaintStatus.ASSIGNED.value,
                        note="Assigned by AI Pipeline Engine.",
                        updated_by=None
                    )
                    session.add(update)
            
            # Save DB changes
            await session.commit()

        # 4. RAG & Agent Decision (Optional analytics)
        rag_res = rag.get_context(text)
        similar_cases = rag_res.get("similar_cases", [])
        decision_res = await agent.process(text, context=similar_cases, ml_predictions=labels)
        
        metadata = {
            "ticket_id": ticket_id,
            "decision": decision_res.get('decision'),
            "labels": labels
        }
        memory.add_memory(text=text, metadata=metadata)
        
        logger.info(f"Successfully completed pipeline execution for ticket {ticket_id}")
        
    except Exception as e:
        logger.error(f"Async pipeline execution failed for ticket {ticket_id}: {str(e)}", exc_info=True)

class PipelineRunRequest(BaseModel):
    ticket_id: str


@complaints_router.post("/pipeline/run", response_model=PipelineResponse)
async def run_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks
):
    try:
        background_tasks.add_task(execute_pipeline_task, request.ticket_id)
        return PipelineResponse(task_id=f"bg-{request.ticket_id}", status="accepted")
    except Exception as e:
        logger.error(f"Failed to trigger pipeline: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error triggering pipeline")

# -----------------------------------------------------------------------------
# FASTAPI APPLICATION
# -----------------------------------------------------------------------------
from contextlib import asynccontextmanager
from app.services.scheduler import start_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    shutdown_scheduler()

app = FastAPI(
    title="Complaint Intelligence Dashboard API",
    description="Central brain and integration layer for CM-Dashboard: Multi-label classification, FAISS RAG, FAISS Memory, and Decision System.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.include_router(complaints_router)
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok"}
