import logging

logger = logging.getLogger(__name__)

class PipelineManager:
    """
    Deprecated. Pipeline logic is now directly handled via Background Tasks 
    and the strictly sequential DecisionAgent flow in app.main.
    """
    pass
