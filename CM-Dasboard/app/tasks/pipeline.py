import asyncio
import logging
from app.worker.celery_app import celery_app
from sqlalchemy.future import select
from app.db.session import AsyncSessionLocal
from app.models.complaint import Complaint, ComplaintStatus, ComplaintUpdate, PriorityEnum
from app.services.routing.engine import RoutingEngine

logger = logging.getLogger(__name__)

async def execute_pipeline_task(ticket_id: str):
    logger.info(f"Starting async pipeline execution for ticket: {ticket_id}")
    
    from app.services.classification.service import get_classifier_service
    from app.services.rag.service import get_rag_service
    from app.services.memory.faiss_memory import get_memory_service
    from app.services.agent.service import get_agent_service

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
            classification_res = await asyncio.to_thread(classifier.predict, text)
            labels = classification_res.get("category_pred", ["OTHER"])
            confidence = classification_res.get("confidence_score", 0.5)
            logger.info(f"[Ticket {ticket_id}] Classification complete: {labels}")
            
            # Predict Priority
            pred_priority_str = await asyncio.to_thread(classifier.predict_severity, text)
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
        rag_res = await asyncio.to_thread(rag.get_context, text)
        similar_cases = rag_res.get("similar_cases", [])
        decision_res = await agent.process(text, context=similar_cases, ml_predictions=labels)
        
        metadata = {
            "ticket_id": ticket_id,
            "decision": decision_res.get('decision'),
            "labels": labels
        }
        await asyncio.to_thread(memory.add_memory, text, metadata)
        
        logger.info(f"Successfully completed pipeline execution for ticket {ticket_id}")
        
    except Exception as e:
        logger.error(f"Async pipeline execution failed for ticket {ticket_id}: {str(e)}", exc_info=True)
        try:
            async with AsyncSessionLocal() as session:
                query = select(Complaint).filter(Complaint.ticket_id == ticket_id)
                result = await session.execute(query)
                complaint = result.scalars().first()
                if complaint:
                    if complaint.retry_count >= 3:
                        complaint.status = ComplaintStatus.FAILED_FINAL
                    else:
                        complaint.status = ComplaintStatus.FAILED
                    complaint.failure_reason = str(e)
                    await session.commit()
        except Exception as db_e:
            logger.error(f"Failed to update database with failure state for ticket {ticket_id}: {db_e}", exc_info=True)

@celery_app.task(bind=True, name="app.tasks.pipeline.process_pipeline_task", max_retries=3)
def process_pipeline_task(self, ticket_id: str):
    """
    Celery task that executes the complete CM-Dashboard pipeline in the background.
    Since Celery workers run synchronously and the pipeline is async, we execute
    it via an asyncio event loop.
    """
    logger.info(f"Celery Task: Processing pipeline for ticket {ticket_id}")
    
    # Safely get or create an event loop for this worker thread
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        # Execute the async pipeline
        loop.run_until_complete(execute_pipeline_task(ticket_id))
    except Exception as exc:
        logger.error(f"Celery Task failed for ticket {ticket_id}: {exc}", exc_info=True)
        # Exponential backoff retry
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
