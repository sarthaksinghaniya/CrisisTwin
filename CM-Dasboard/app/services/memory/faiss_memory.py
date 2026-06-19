import numpy as np
import faiss
from typing import List, Dict, Any
from app.services.ml.inference import MLInferenceService

class FaissMemory:
    """
    FAISS-based memory system for high-performance vector similarity search.
    Maps text embeddings to structured metadata.
    """
    
    def __init__(self, embedding_dim: int = 4):
        # We use dimension 4 because the MLInferenceService stub currently returns 4 floats
        self.inference = MLInferenceService()
        self.embedding_dim = embedding_dim
        
        # Initialize FAISS IndexFlatL2 (L2 distance)
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        
        # Map FAISS internal IDs (0, 1, 2...) to incident metadata
        self.metadata_store: Dict[int, Dict[str, Any]] = {}
        self._current_id = 0

    def add_memory(self, text: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Generates embeddings for the text and stores it in the FAISS index.
        """
        # 1. Convert text to embeddings
        embeddings = self.inference.get_embeddings(text)
        
        # 2. Convert to numpy float32 array of shape (1, d)
        vec = np.array([embeddings], dtype=np.float32)
        
        # 3. Add to FAISS index
        self.index.add(vec)
        
        # 4. Map embedding to metadata
        self.metadata_store[self._current_id] = {
            "text": text,
            **(metadata or {})
        }
        self._current_id += 1
        
        return True

    def search_similar(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Searches the FAISS index for the most similar past incidents.
        Returns top_k results.
        """
        if self.index.ntotal == 0:
            return []
            
        k = min(top_k, self.index.ntotal)
        
        query_embedding = self.inference.get_embeddings(text)
        query_vec = np.array([query_embedding], dtype=np.float32)
        
        # Search FAISS index: distances and indices
        distances, indices = self.index.search(query_vec, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1:
                meta = self.metadata_store.get(int(idx), {})
                results.append({
                    "faiss_id": int(idx),
                    "distance": float(dist),
                    "metadata": meta
                })
                
        return results
