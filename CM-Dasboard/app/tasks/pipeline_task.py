from app.worker.celery_app import celery_app
from app.services.pipeline.pipeline_manager import PipelineManager
import asyncio

@celery_app.task(bind=True, name="app.tasks.pipeline_task.run_incident_pipeline")
def run_incident_pipeline(self, text: str):
    """
    Celery task that executes the multi-agent PipelineManager in the background.
    Since Celery workers run synchronously and the pipeline is async, we execute
    it via an asyncio event loop.
    """
    # Instantiate the pipeline manager
    pipeline = PipelineManager()
    
    # Safely get or create an event loop for this worker thread
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    # Execute the async multi-agent pipeline and return the enriched output
    result = loop.run_until_complete(pipeline.process_incident(text))
    
    return result
