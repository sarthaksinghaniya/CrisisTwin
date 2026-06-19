import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class PredictionValidator:
    """
    Validates machine learning predictions against historical consensus.
    """
    def validate(self, ml_predictions: List[str], history_analysis: Dict[str, Any]) -> Dict[str, Any]:
        if not ml_predictions:
            ml_predictions = ["OTHER"]
            
        base_decision = ml_predictions[0]
        reasoning = f"Based on machine learning predictions: {ml_predictions}."
        
        # Override if history provides a very strong consensus
        if history_analysis["has_history"] and history_analysis["consensus_strength"] > 0.6:
            historical_decision = history_analysis["consensus_decision"]
            if base_decision != historical_decision:
                reasoning += f" However, historical override applied. {history_analysis['reasoning']}"
                base_decision = historical_decision
            else:
                reasoning += f" This is reinforced by history. {history_analysis['reasoning']}"
        else:
            reasoning += " " + history_analysis["reasoning"]
            
        return {
            "final_decision": base_decision,
            "reasoning": reasoning.strip(),
            "confidence": 0.85 if base_decision == history_analysis.get("consensus_decision") else 0.70
        }
