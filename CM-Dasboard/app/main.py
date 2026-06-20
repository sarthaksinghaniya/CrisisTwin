import logging
import asyncio
from google import genai
from google.genai import types
import os


from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from app.services.memory.faiss_memory import FaissMemory

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
from app.engines.faiss_rag import FaissMemory
from app.services.agents.decision_agent import DecisionAgent
from app.schemas.incident import (
    ComplaintRequest, 
    ClassificationResponse, 
    QueryRequest, 
    RAGResponse, 
    AgentDecisionResponse, 
    MemorySearchResponse, 
    PipelineRunRequest,
    PipelineResponse
)
from app.db.session import AsyncSessionLocal
from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.complaint_update import ComplaintUpdate
from app.engines.routing import RoutingEngine
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

# ==========================================
# GEMINI ENGINE GLOBAL CLIENT CONFIGURATION
# ==========================================
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not api_key:
    logger.error("CRITICAL: Neither GEMINI_API_KEY nor GOOGLE_API_KEY is defined in the environment context.")
    ai_client = None 
else:
    ai_client = genai.Client(api_key=api_key)

# -----------------------------------------------------------------------------
# ROUTERS
# -----------------------------------------------------------------------------
complaints_router = APIRouter(prefix=f"{settings.API_V1_STR}/complaints", tags=["Complaints"])

# ==========================================
# 1. CLASSIFY COMPLAINT ROUTE (FIXED DI INJECTION)
# ==========================================
@complaints_router.post("/classify", response_model=ClassificationResponse)
async def classify_complaint(
    request: ComplaintRequest,
    service: MLInferenceService = Depends(get_classifier_service) # Fixed: Kept original DI intact
):
    """
    Classifies complaints using the local MLInferenceService pipeline. 
    If the local model fails, it automatically runs the Gemini fallback.
    """
    try:
        if service is None:
            raise ValueError("Local MLInferenceService dependency returned None.")
            
        # Execute the primary local service prediction model in a safe threadpool
        res = await asyncio.to_thread(service.predict, request.text)
        return ClassificationResponse(
            labels=res.get("category_pred", []), 
            confidence=res.get("confidence_score", 0.0)
        )
        
    except Exception as local_exception:
        logger.warning(
            f"[CLASSIFY_FALLBACK] Local service encountered an issue ({str(local_exception)}). "
            "Routing request to live Gemini fallback engine..."
        )
        
        if not ai_client:
            raise HTTPException(
                status_code=500, 
                detail="Local classification failed and live Gemini GenAI Client is offline."
            )

        try:
            # Enforce an exact structural JSON response format matching your schema
            classification_schema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "category": types.Schema(type=types.Type.STRING, description="Department like Water, Power, Sanitation, Roads, Security"),
                    "confidence": types.Schema(type=types.Type.NUMBER, description="Confidence score from 0.0 to 1.0")
                },
                required=["category", "confidence"]
            )

            response = await asyncio.to_thread(
                ai_client.models.generate_content,
                model='gemini-2.5-flash',
                contents=f"Classify the target department for this citizen issue text:\n\"{request.text}\"",
                config=types.GenerateContentConfig(
                    system_instruction="You are a routing classification system for city operations. Return JSON only.",
                    response_mime_type="application/json",
                    response_schema=classification_schema,
                    temperature=0.1
                )
            )
            
            import json
            payload = json.loads(response.text)
            return ClassificationResponse(
                labels=[payload.get("category", "General")],
                confidence=payload.get("confidence", 0.95)
            )
            
        except Exception as fallback_err:
            logger.error(f"[CRITICAL] Both local classifier and Gemini fallback failed: {str(fallback_err)}", exc_info=True)
            raise HTTPException(status_code=500, detail="All classification engine variations failed.")


# ==========================================
# 2. COLD-START IMMUNE RAG QUERY ROUTE (FIXED DI INJECTION)
# ==========================================
@complaints_router.post("/rag/query", response_model=RAGResponse)
async def query_rag(
    request: QueryRequest,
    service: ContextRetriever = Depends(get_rag_service) # Re-enabled production DI engine
):
    """
    RAG Route. Utilizes local ContextRetriever. Pre-renders the answer text 
    and appends it safely as the first element of the context array payload 
    to preserve downstream field compatibility with RAGResponse schema restrictions.
    """
    try:
        contexts = []
        
        # 1. Safely extract historical cases via your local retrieval service threadpool
        if service:
            try:
                res = await asyncio.to_thread(service.get_context, request.query)
                if res and "similar_cases" in res:
                    contexts = [
                        c.get("metadata", {}).get("text", "") 
                        for c in res.get("similar_cases", []) 
                        if c.get("metadata")
                    ]
            except Exception as retrieval_err:
                logger.warning(f"[RAG_RETRIEVAL_WARN] Local vector store lookup skipped: {str(retrieval_err)}")

        # 2. Mitigate cold starts by setting up fallback grounding text
        if not contexts:
            context_str = "No specific system procedures found in local FAISS memory store database (Index Cold Start State)."
            logger.info("[RAG_ENGINE] Empty context state encountered. Shifting to standard grounding baseline.")
        else:
            context_str = "\n".join([f"- {c}" for c in contexts])

        # 3. Assemble clear system operational boundaries for Gemini matching
        system_instruction = (
            "You are an expert AI operator managing the City & Facility Operations Dashboard.\n"
            "Your job is to answer incoming queries or process citizen complaints using ONLY the factual context provided below.\n"
            "If the provided context does not contain enough information, state clearly that the database is currently "
            "empty, then provide a helpful, generalized resolution process for the citizen.\n"
            "Do not invent system variables or operational histories.\n\n"
            f"=== SYSTEM CONTEXT AND SOPS ===\n{context_str}"
        )

        if not ai_client:
            raise HTTPException(status_code=500, detail="Gemini Engine API client is offline.")

        # 4. Generate the response text within a thread-isolated container lookahead
        response = await asyncio.to_thread(
            ai_client.models.generate_content,
            model='gemini-2.5-flash',
            contents=request.query,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            )
        )

        # 5. Fix Schema Filter Drop: Format generated text elements directly into context array payload
        # This keeps the exact structure expected by your response model contract
        response_payload = [f"GENERATED_ANSWER: {response.text}"] + contexts

        return RAGResponse(
            context=response_payload
        )

    except Exception as e:
        logger.error(f"[RAG_CRASH] Execution failure across processing pipelines: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error during RAG retrieval and generation execution phase.")


# ==========================================
# 3. AGENT DECIDE ROUTE (FIXED DI INJECTION)
# ==========================================
@complaints_router.post("/agent/decide", response_model=AgentDecisionResponse)
async def agent_decide(
    request: ComplaintRequest,
    rag_service: ContextRetriever = Depends(get_rag_service),          # Fixed DI
    memory_service: FaissMemory = Depends(get_memory_service),         # Fixed DI
    agent_service: DecisionAgent = Depends(get_agent_service),         # Fixed DI
    classifier_service: MLInferenceService = Depends(get_classifier_service) # Fixed DI
):
    """
    Combines local classification, historical memory, and RAG contexts to determine 
    officer assignment instructions.
    """
    try:
        # Step A: Run local classification with safe fallback handling
        try:
            class_res = await classify_complaint(request, service=classifier_service)
            assigned_labels = class_res.labels
        except Exception:
            assigned_labels = ["General Operations"]

        # Step B: Secure historical context paths
        contexts = []
        if rag_service:
            try:
                rag_result = await asyncio.to_thread(rag_service.get_context, request.text)
                contexts = rag_result.get("similar_cases", [])
            except Exception:
                pass

        # Step C: Generate decision via local agent service
        if agent_service:
            try:
                decision_payload = await asyncio.to_thread(
                    agent_service.process, 
                    text=request.text, 
                    context=contexts, 
                    ml_predictions=assigned_labels
                )
                return AgentDecisionResponse(
                    decision=decision_payload.get("decision", "Assign to General Queue"),
                    reasoning=decision_payload.get("reasoning", "Processed by core agent engine matrix.")
                )
            except Exception:
                pass

        # Safe programmatic backup if agent execution layer errors out
        target_dept = assigned_labels[0] if assigned_labels else "General Desk"
        return AgentDecisionResponse(
            decision=f"Route ticket automatically to {target_dept} Central Department Handler Pool",
            reasoning="System fallback auto-triggered because the agent execution layer was unreachable."
        )

    except Exception as e:
        logger.error(f"[AGENT_DECIDE_CRASH] Primary orchestration pipeline failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error computing automated agent decision matrix rules.")
    
# ==========================================
# 4. MEMORY SEARCH ROUTE (PRODUCTION FIX)
# ==========================================
@complaints_router.get("/memory/search", response_model=MemorySearchResponse)
async def search_memory(
    query: str,
    service=Depends(get_memory_service)  # Re-linked your actual backend dependency manager
):
    """
    Searches historical memory indices. Gracefully hooks into your 
    production store file to pull historical complaint records.
    """
    try:
        # Fallback to empty container safely if dependency fails to initialize
        if not service:
            logger.warning("FaissMemory service uninitialized during query lookups.")
            return MemorySearchResponse(incidents=[])
            
        # Execute vectorized similarity query inside threadpool
        res = await asyncio.to_thread(service.search_similar, query)
        
        # Parse result objects, ensuring it captures metadata payloads safely
        incidents = []
        if res and isinstance(res, list):
            for r in res:
                if isinstance(r, dict) and r.get("metadata"):
                    incidents.append(r.get("metadata"))
                elif hasattr(r, "metadata") and r.metadata:
                    incidents.append(r.metadata if isinstance(r.metadata, dict) else vars(r.metadata))
                    
        return MemorySearchResponse(incidents=incidents)
        
    except Exception as e:
        logger.error(f"Memory search extraction pipeline crashed: {str(e)}", exc_info=True)
        return MemorySearchResponse(incidents=[])


# ==========================================
# 5. PIPELINE RUN ROUTE (FIXED SCHEMA CONTRACT)
# ==========================================
@complaints_router.post("/pipeline/run", response_model=PipelineResponse)
async def run_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks
):
    """
    Triggers the automated classification, assignment, and vector persistence pipeline.
    Captures background task IDs to strictly satisfy the PipelineResponse contract.
    """
    try:
        from app.tasks.pipeline import execute_core
        
        # Enforce tracking string formatting based on ticket references
        assigned_task_id = f"task_pipeline_{request.ticket_id}"
        
        try:
            from app.main import scheduler
            # Append execution payload directly onto your active APScheduler instance
            job = scheduler.add_job(
                execute_core, 
                args=[request.ticket_id],
                id=assigned_task_id,
                replace_existing=True
            )
            # Use the registered job id string explicitly
            assigned_task_id = str(job.id)
            logger.info(f"[PIPELINE_SCHEDULER] Task registered via APScheduler. ID: {assigned_task_id}")
            
        except Exception as scheduler_err:
            logger.warning(
                f"[PIPELINE_SCHEDULER_WARN] APScheduler unavailable ({str(scheduler_err)}). "
                "Switching to native FastAPI BackgroundTasks worker..."
            )
            # Safe local async container threadpool fallback
            background_tasks.add_task(execute_core, request.ticket_id)
            logger.info(f"[PIPELINE_WORKER] Task registered via BackgroundTasks. ID: {assigned_task_id}")
        
        # FIX: Construct object using only the keys allowed by your exact Pydantic schema
        return PipelineResponse(
            task_id=assigned_task_id
        )
        
    except Exception as e:
        logger.error(f"[PIPELINE_CRITICAL_ERR] Validation or submission failed for ticket {request.ticket_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Failed to submit target execution pipeline background tracking worker process."
        )


# -----------------------------------------------------------------------------
# FASTAPI APPLICATION
# -----------------------------------------------------------------------------
from contextlib import asynccontextmanager
from app.engines.scheduler import SchedulerEngine

# Global Scheduler Instance
scheduler_engine = SchedulerEngine()
scheduler = scheduler_engine.scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    get_memory_service().load_memory()
    
    # Boot SchedulerEngine
    scheduler_engine.start()
    
    yield
    
    # Shutdown
    scheduler_engine.stop()
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
    from fastapi.responses import JSONResponse
    
    # --- DB check ---
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # --- Scheduler check (direct reference, no celery import) ---
    try:
        scheduler_status = "running" if scheduler.running else "stopped"
    except Exception:
        scheduler_status = "unknown"
    
    # --- FAISS check (resilient to None) ---
    try:
        mem = get_memory_service()
        faiss_loaded = mem.index is not None and mem.index.ntotal >= 0
    except Exception:
        faiss_loaded = False
    
    is_ok = db_status == "connected" and scheduler_status == "running"
    
    response_data = {
        "status": "ok" if is_ok else "degraded",
        "database": db_status,
        "scheduler": scheduler_status,
        "faiss_loaded": faiss_loaded,
        "faiss_vectors": mem.index.ntotal if faiss_loaded else 0,
    }
    
    if not is_ok:
        return JSONResponse(status_code=503, content=response_data)
        
    return response_data
