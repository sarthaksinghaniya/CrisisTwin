import math
from typing import List, Dict, Any
from app.services.ml.inference import MLInferenceService

class MemoryService:
    """
    Memory system for AI agents to store and retrieve past incidents
    using vector embeddings.
    """
    
    def __init__(self):
        self.inference = MLInferenceService()
        # In a production environment, this should connect to pgvector, FAISS, Pinecone, or ChromaDB.
        # For demonstration, we use an in-memory list as our vector store.
        self._vector_store: List[Dict[str, Any]] = []
        
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Helper to calculate cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    async def save_memory(self, incident_id: str, text: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Generates embeddings for the incident text and stores it in the vector DB.
        
        Args:
            incident_id (str): Unique identifier for the incident.
            text (str): The text content of the incident.
            metadata (Dict): Optional metadata to store alongside the embeddings.
        """
        embeddings = self.inference.get_embeddings(text)
        
        # Save to our in-memory "database"
        record = {
            "incident_id": incident_id,
            "text": text,
            "embeddings": embeddings,
            "metadata": metadata or {}
        }
        self._vector_store.append(record)
        return True

    async def search_similar(self, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Embeds the search query and retrieves the top_k most similar past incidents.
        
        Args:
            text (str): The search query text.
            top_k (int): Number of top results to return.
            
        Returns:
            List[Dict]: A list of the most similar incidents sorted by similarity score.
        """
        query_embedding = self.inference.get_embeddings(text)
        
        # Calculate similarity for all stored records
        results = []
        for record in self._vector_store:
            sim = self._cosine_similarity(query_embedding, record["embeddings"])
            results.append({
                "incident_id": record["incident_id"],
                "text": record["text"],
                "similarity": sim,
                "metadata": record["metadata"]
            })
            
        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Return top K
        return results[:top_k]
