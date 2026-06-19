import logging
from typing import Dict, Any, List
from collections import Counter

logger = logging.getLogger(__name__)

class ContextAnalyzer:
    """
    Analyzes historical RAG context to determine historical consensus.
    """
    def analyze(self, context: List[Dict[str, Any]]) -> Dict[str, Any]:
        result = {
            "has_history": False,
            "consensus_decision": None,
            "consensus_strength": 0.0,
            "reasoning": "No strong historical matches found to assist routing."
        }
        
        if not context:
            return result
            
        past_decisions = [
            c.get("metadata", {}).get("decision") 
            for c in context 
            if c.get("metadata", {}).get("decision")
        ]
        
        if past_decisions:
            most_common = Counter(past_decisions).most_common(1)[0]
            decision = most_common[0]
            strength = most_common[1] / len(past_decisions)
            
            result["has_history"] = True
            result["consensus_decision"] = decision
            result["consensus_strength"] = strength
            result["reasoning"] = f"Validated against {len(context)} past cases showing {strength*100:.0f}% alignment with decision: '{decision}'."
        else:
            result["reasoning"] = f"Looked at {len(context)} similar past contexts but no definitive historical decision was found."
            
        return result
