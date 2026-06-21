import logging
import asyncio
import json
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



from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

# Groq SDK Client Import
from groq import Groq

# Core project system dependencies 
from app.core.config import settings
from app.schemas.incident import ComplaintRequest, ClassificationResponse
from app.services.ml.inference import MLInferenceService

logger = logging.getLogger("uvicorn.error")
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

from app.models.complaint import Complaint

from app.schemas.agent import (
    AgentAssignRequest,
    AgentDecisionResponse
)

from app.services.routing.officer_router import OfficerRouter

# ==========================================
# GROQ ENGINE GLOBAL CLIENT CONFIGURATION
# ==========================================
GROQ_CLASSIFIER_MODEL = "llama-3.1-8b-instant"
GROQ_AGENT_MODEL = "openai/gpt-oss-120b"

groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=groq_api_key) if groq_api_key else None
if not groq_client:
    logger.error("CRITICAL: GROQ_API_KEY environment variable is not defined.")
 

# -----------------------------------------------------------------------------
# ROUTERS
# -----------------------------------------------------------------------------
complaints_router = APIRouter(prefix=f"{settings.API_V1_STR}/complaints", tags=["Complaints"])


# ==========================================
# 1. CLASSIFY COMPLAINT ROUTE (GROQ FALLBACK)
# ==========================================
from app.services.ai.groq_classifier import GroqClassifier


@complaints_router.post(
    "/classify",
    response_model=ClassificationResponse
)
async def classify_complaint(
    request: ComplaintRequest
):
    try:

        classifier = GroqClassifier()

        result = await asyncio.to_thread(
            classifier.classify,
            request.text
        )

        return ClassificationResponse(
            category=result["category"],
            department=result["department"],
            priority=result["priority"],
            confidence=result["confidence"]
        )

    except Exception as e:
        logger.exception("Classification failed")

        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )

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
@complaints_router.post(
    "/agent/decide",
    response_model=AgentDecisionResponse
)
async def agent_decide(
    request: AgentAssignRequest,
    db: AsyncSession = Depends(get_db)
):
    try:

        complaint_stmt = (
            select(Complaint)
            .where(
                Complaint.ticket_id == request.ticket_id,
                Complaint.is_deleted == False
            )
        )

        complaint_result = await db.execute(
            complaint_stmt
        )

        complaint = complaint_result.scalar_one_or_none()

        if not complaint:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found"
            )

        officer = await OfficerRouter.assign_officer(
            db,
            complaint
        )

        if not officer:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No officer available "
                    f"for department {complaint.department}"
                )
            )

        complaint.assigned_to = officer.id

        await db.commit()

        await db.refresh(complaint)

        return AgentDecisionResponse(
            decision=f"Assigned to {officer.name}",
            reasoning=(
                f"Department={officer.department}, "
                f"District={officer.district}"
            )
        )

    except HTTPException:
        raise

    except Exception as e:

        await db.rollback()

        logger.exception(
            "Officer assignment failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
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

# -----------------------------------------------------------------------------
# MIDDLEWARE & SECURITY (Helmet, CORS, Rate Limit)
# -----------------------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request
import time
from collections import defaultdict

# 1. CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Security Headers (Helmet Alternative)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 3. Rate Limiting Middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, window_ms: int = 900000, max_requests: int = 100):
        super().__init__(app)
        self.window_ms = window_ms
        self.max_requests = max_requests
        self.clients = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if "PYTEST_CURRENT_TEST" in os.environ:
            return await call_next(request)
            
        client_ip = request.client.host if request.client else "unknown"
        now = time.time() * 1000
        
        # Clean old records
        self.clients[client_ip] = [req_time for req_time in self.clients[client_ip] if now - req_time < self.window_ms]
        
        if len(self.clients[client_ip]) >= self.max_requests:
            return JSONResponse(status_code=429, content={"msg": "Too many requests, try again later"})
        
        self.clients[client_ip].append(now)
        return await call_next(request)

app.add_middleware(RateLimitMiddleware)

# 4. Global Error Handling Middleware
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Unhandled Error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"msg": "Server Error"}
    )


app.include_router(complaints_router)
app.include_router(api_router, prefix=settings.API_V1_STR)

# Root-level Reports Router for exact endpoint requirements
from typing import Optional
from app.api.deps import get_db
from sqlalchemy.ext.asyncio import AsyncSession

reports_root_router = APIRouter(prefix="/reports", tags=["Reports Root"])

@reports_root_router.get("/pdf")
async def root_pdf_report(
    type: str = "monthly",
    month: Optional[str] = None,
    week: Optional[str] = None,
    department: Optional[str] = None,
    district: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    from app.api.routes.reports import download_pdf_report
    return await download_pdf_report(type=type, month=month, week=week, department=department, district=district, db=db)

@reports_root_router.get("/csv")
async def root_csv_export(
    department: Optional[str] = None,
    district: Optional[str] = None,
    priority: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    from app.api.routes.reports import download_csv_export
    prio_enum = None
    if priority:
        try:
            from app.models.complaint import PriorityEnum
            prio_enum = PriorityEnum(priority.upper())
        except Exception:
            pass
    return await download_csv_export(department=department, district=district, priority=prio_enum, start_date=start_date, end_date=end_date, db=db)

app.include_router(reports_root_router)


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

@app.get(f"{settings.API_V1_STR}/health", tags=["System"])
async def api_v1_health_check(db: AsyncSession = Depends(get_db)):
    return await health_check(db=db)

# -----------------------------------------------------------------------------
# SOCKET.IO ASGI WRAPPER
# -----------------------------------------------------------------------------
import socketio
from app.api.socket import sio

app = socketio.ASGIApp(sio, other_asgi_app=app)
