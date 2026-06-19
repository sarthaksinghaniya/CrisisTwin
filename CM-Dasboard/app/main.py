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
async def execute_pipeline_task(text: str):
    """
    Background worker function that runs the complete CM-Dashboard pipeline.
    """
    task_id = hash(text)
    logger.info(f"Starting async pipeline execution [Task: {task_id}]")
    
    try:
        classifier = get_classifier_service()
        rag = get_rag_service()
        memory = get_memory_service()
        agent = get_agent_service()
        
        # 1. Classification
        classification_res = classifier.predict(text)
        labels = classification_res.get("category_pred", [])
        logger.info(f"[Task: {task_id}] Classification complete: {labels}")
        
        # 2. RAG Retrieval
        rag_res = rag.get_context(text)
        similar_cases = rag_res.get("similar_cases", [])
        logger.info(f"[Task: {task_id}] RAG retrieval complete. Context chunks: {len(similar_cases)}")
        
        # 3. Agent Decision
        decision_res = await agent.process(text, context=similar_cases, ml_predictions=labels)
        logger.info(f"[Task: {task_id}] Final Agent Decision: {decision_res.get('decision')}")
        
        # 4. Save outcome to memory
        metadata = {
            "complaint": text,
            "decision": decision_res.get('decision'),
            "outcome": "Resolved",
            "labels": labels
        }
        memory.add_memory(text=text, metadata=metadata)
        
        logger.info(f"Successfully completed async pipeline execution [Task: {task_id}]")
        
    except Exception as e:
        logger.error(f"Async pipeline execution failed [Task: {task_id}]: {str(e)}", exc_info=True)

@complaints_router.post("/pipeline/run", response_model=PipelineResponse)
async def run_pipeline(
    request: ComplaintRequest,
    background_tasks: BackgroundTasks
):
    try:
        background_tasks.add_task(execute_pipeline_task, request.text)
        return PipelineResponse(task_id=f"bg-{hash(request.text)}", status="accepted")
    except Exception as e:
        logger.error(f"Failed to trigger pipeline: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error triggering pipeline")

# -----------------------------------------------------------------------------
# FASTAPI APPLICATION
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Complaint Intelligence Dashboard API",
    description="Central brain and integration layer for CM-Dashboard: Multi-label classification, FAISS RAG, FAISS Memory, and Decision System.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(complaints_router)
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok"}
