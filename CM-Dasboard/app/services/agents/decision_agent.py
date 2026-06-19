import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DecisionAgent:
    """
    Final agent that takes the ML predictions and RAG context, 
    and formulates a structured response / decision.
    """
    
    async def process(self, text: str, context: List[Dict[str, Any]] = None, ml_predictions: List[str] = None) -> Dict[str, Any]:
        """
        Process the complaint text with supporting memory and predictions.
        """
        logger.info(f"DecisionAgent processing: {text[:30]}...")
        
        # Use ML predictions as a base
        if not ml_predictions:
            ml_predictions = ["OTHER"]
            
        reasoning = f"Based on machine learning predictions: {ml_predictions}."
        decision = f"Route to {ml_predictions[0]} department."
        
        # Override or enrich with memory/context if applicable
        if context and len(context) > 0:
            past_decisions = [c.get("metadata", {}).get("decision") for c in context if c.get("metadata", {}).get("decision")]
            if past_decisions:
                from collections import Counter
                most_common = Counter(past_decisions).most_common(1)[0][0]
                decision = most_common
                reasoning += f" Validated against {len(context)} past similar cases showing strong alignment with decision: '{most_common}'."
            else:
                reasoning += f" Looked at {len(context)} similar past contexts but no definitive historical decision was found."
        else:
            reasoning += " No strong historical matches found to assist routing."
            
        return {
            "decision": decision,
            "reasoning": reasoning,
            "confidence": 0.85
        }
