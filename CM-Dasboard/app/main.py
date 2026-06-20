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
        res = await asyncio.to_thread(service.predict, request.text)
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
        res = await asyncio.to_thread(service.get_context, request.query)
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
        ml_res = await asyncio.to_thread(classifier_service.predict, request.text)
        rag_result = await asyncio.to_thread(rag_service.get_context, request.text)
        
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
        res = await asyncio.to_thread(service.search_similar, query)
        incidents = [r.get("metadata", {}) for r in res]
        return MemorySearchResponse(incidents=incidents)
    except Exception as e:
        logger.error(f"Memory search failure: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching memory")

# -----------------------------------------------------------------------------
class PipelineRunRequest(BaseModel):
    ticket_id: str


@complaints_router.post("/pipeline/run", response_model=PipelineResponse)
async def run_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks
):
    try:
        from app.tasks.pipeline import process_pipeline_task
        process_pipeline_task.delay(request.ticket_id)
        return {"status": "accepted", "message": "Pipeline execution triggered successfully", "ticket_id": request.ticket_id}
    except Exception as e:
        logger.error(f"Failed to trigger pipeline: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error triggering pipeline")

# -----------------------------------------------------------------------------
# FASTAPI APPLICATION
# -----------------------------------------------------------------------------
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    get_memory_service().load_memory()
    yield
    # Shutdown
    get_memory_service().save_memory()

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

from app.api.deps import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    from fastapi import Response
    from app.worker.celery_app import celery_app
    import redis
    
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    try:
        ping_res = celery_app.control.ping(timeout=1.0)
        celery_worker_status = "running" if ping_res else "unreachable"
    except Exception:
        celery_worker_status = "error"

    faiss_loaded = get_memory_service().index is not None and get_memory_service().index.ntotal >= 0
    
    is_ok = db_status == "connected" and faiss_loaded and redis_status == "connected" and celery_worker_status == "running"
    
    response_data = {
        "status": "ok" if is_ok else "degraded",
        "database": db_status,
        "redis": redis_status,
        "celery_worker": celery_worker_status,
        "faiss_loaded": faiss_loaded
    }
    
    if not is_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=response_data)
        
    return response_data
