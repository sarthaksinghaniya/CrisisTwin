import logging
from typing import List, Dict, Any
from app.services.memory.faiss_memory import FaissMemory

logger = logging.getLogger(__name__)

class ContextRetriever:
    """
    RAG Context Retriever Service.
    Queries the FAISS memory store for similar incidents and formats them into a context list.
    """
    
    def __init__(self):
        self.memory = FaissMemory()

    def get_context(self, text: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Retrieves similar past incidents and formats them.
        
        Returns:
            Dict[str, Any]: A dictionary containing a list of 'similar_cases' with their metadata.
        """
        logger.info(f"Retrieving context for text: '{text[:50]}...'")
        
        raw_results = self.memory.search_similar(text, top_k=top_k)
        
        similar_cases = []
        for result in raw_results:
            meta = result.get("metadata", {})
            case_info = {
                "metadata": {
                    "text": meta.get("complaint", meta.get("text", "Unknown")),
                    "decision": meta.get("decision", "Unknown"),
                    "outcome": meta.get("outcome", "Unknown"),
                    "labels": meta.get("labels", [])
                },
                "distance": result.get("distance", 0.0)
            }
            similar_cases.append(case_info)
            
        return {
            "similar_cases": similar_cases
        }
