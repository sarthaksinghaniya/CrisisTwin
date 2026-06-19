from typing import Dict, Any
from .base_agent import BaseAgent

class ClassificationAgent(BaseAgent):
    """
    Agent responsible for predicting the specific type or category of an incident.
    """
    
    async def process(self, text: str, **kwargs) -> Dict[str, Any]:
        # TODO: Integrate actual ML classification model here
        
        # Stub logic for demonstration
        text_lower = text.lower()
        incident_type = "OTHER"
        
        if any(word in text_lower for word in ["fire", "smoke", "burn", "arson"]):
            incident_type = "FIRE"
        elif any(word in text_lower for word in ["medical", "injured", "blood", "heart attack", "unconscious"]):
            incident_type = "MEDICAL"
        elif any(word in text_lower for word in ["gun", "robbery", "police", "assault", "trespassing"]):
            incident_type = "POLICE"
        elif any(word in text_lower for word in ["leak", "chemical", "hazard", "spill"]):
            incident_type = "HAZMAT"
            
        return {
            "agent": "ClassificationAgent",
            "type": incident_type,
            "confidence": 0.90, # Stub confidence score
        }
