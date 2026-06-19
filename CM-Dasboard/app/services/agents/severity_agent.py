from typing import Dict, Any
from .base_agent import BaseAgent
from app.services.ml.inference import MLInferenceService

class SeverityAgent(BaseAgent):
    """
    Agent responsible for predicting the severity of an incident based on its text,
    utilizing the ML Inference Service.
    """
    
    def __init__(self):
        self.inference = MLInferenceService()
    
    async def process(self, text: str, **kwargs) -> Dict[str, Any]:
        # Connect to the ML inference layer
        ml_result = self.inference.predict(text)
        
        # Use ML prediction to determine severity
        prediction = ml_result.get("prediction_class", "OTHER")
        severity = "LOW"
        if prediction in ["FIRE", "HAZMAT"]:
            severity = "CRITICAL"
        elif prediction in ["MEDICAL", "POLICE"]:
            severity = "HIGH"
            
        return {
            "agent": "SeverityAgent",
            "severity": severity,
            "confidence": ml_result.get("confidence", 0.0),
            "raw_ml_prediction": prediction
        }
