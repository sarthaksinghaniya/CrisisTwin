import logging
from typing import Dict, Any, List

from .components.context_analyzer import ContextAnalyzer
from .components.prediction_validator import PredictionValidator

logger = logging.getLogger(__name__)

class DecisionAgent:
    """
    Orchestrator that utilizes ContextAnalyzer and PredictionValidator
    to formulate a structured response.
    """
    def __init__(self):
        self.context_analyzer = ContextAnalyzer()
        self.prediction_validator = PredictionValidator()
    
    async def process(self, text: str, context: List[Dict[str, Any]] = None, ml_predictions: List[str] = None) -> Dict[str, Any]:
        """
        Process the complaint text with supporting memory and predictions.
        """
        logger.info(f"DecisionAgent Orchestrator processing: {text[:30]}...")
        
        # 1. Analyze historical consensus from RAG context
        history_analysis = self.context_analyzer.analyze(context)
        
        # 2. Validate ML predictions against history
        final_validation = self.prediction_validator.validate(ml_predictions, history_analysis)
            
        return {
            "decision": final_validation["final_decision"],
            "reasoning": final_validation["reasoning"],
            "confidence": final_validation["confidence"]
        }
