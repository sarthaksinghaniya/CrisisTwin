import numpy as np
import faiss
import logging
from typing import List, Dict, Any
from app.services.memory.embedding import MemoryEmbeddingService

from threading import Lock

logger = logging.getLogger(__name__)

faiss_lock = Lock()

class FaissMemory:
    """
    FAISS-based memory system for high-performance vector similarity search.
    Maps text embeddings to structured metadata.
    """
    
    # Singleton pattern to prevent re-initializing FAISS over and over
    _instance = None
    
    def __new__(cls, embedding_dim: int = 384):
        if cls._instance is None:
            cls._instance = super(FaissMemory, cls).__new__(cls)
            cls._instance.embedding = MemoryEmbeddingService()
            cls._instance.embedding_dim = embedding_dim
            
            # Initialize FAISS IndexFlatL2 (L2 distance)
            cls._instance.index = faiss.IndexFlatL2(embedding_dim)
            
            # Map FAISS internal IDs (0, 1, 2...) to incident metadata
            cls._instance.metadata_store = {}
            cls._instance._current_id = 0
        return cls._instance

    def add_memory(self, text: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Generates embeddings for the text and stores it in the FAISS index.
        """
        vec = self.embedding.embed(text).reshape(1, -1)
        with faiss_lock:
            self.index.add(vec)
            self.metadata_store[self._current_id] = {
                "text": text,
                "deprecated": False,
                **(metadata or {})
            }
            self._current_id += 1
        return True

    def save_memory(self, index_path="memory.faiss", meta_path="meta.json"):
        """Saves the FAISS index and metadata to disk."""
        import json
        faiss.write_index(self.index, index_path)
        with open(meta_path, "w") as f:
            json.dump(self.metadata_store, f)
        logger.info(f"Saved FAISS memory to {index_path} and {meta_path}")

    def load_memory(self, index_path="memory.faiss", meta_path="meta.json"):
        """Loads the FAISS index and metadata from disk if they exist."""
        import os, json
        if os.path.exists(index_path) and os.path.exists(meta_path):
            self.index = faiss.read_index(index_path)
            with open(meta_path, "r") as f:
                store_str = json.load(f)
                self.metadata_store = {int(k): v for k, v in store_str.items()}
            self._current_id = max(self.metadata_store.keys(), default=-1) + 1
            logger.info(f"Loaded FAISS memory from {index_path} and {meta_path}")
        else:
            logger.info("No existing FAISS memory found. Starting fresh.")
        
    def apply_rl_reward(self, text: str, reward: float, metadata: Dict[str, Any] = None):
        """
        Adjusts memory persistence based on RL reward.
        If reward is very high, we duplicate the vector slightly offset to boost it.
        If reward is low, we flag it as deprecated so it is filtered from results.
        """
        if reward <= -1.0:
            # We must search and deprecate the matching incident
            vec = self.embedding.embed(text).reshape(1, -1)
            with faiss_lock:
                D, I = self.index.search(vec, 1)
                idx = int(I[0][0])
                if idx != -1 and idx in self.metadata_store:
                    self.metadata_store[idx]["deprecated"] = True
                    logger.info(f"RL Loop: Deprecated bad memory [ID: {idx}] due to negative reward.")
        elif reward >= 1.0:
            # Boost the memory by adding it explicitly as a corrected standard
            logger.info(f"RL Loop: Boosting high-reward memory by appending to FAISS.")
            self.add_memory(text, metadata)

    def search_similar(self, text: str, top_k: int = 5, distance_threshold: float = 1.5) -> List[Dict[str, Any]]:
        """
        Searches the FAISS index for the most similar past incidents.
        Filters out matches beyond a certain distance threshold and deprecated matches.
        """
        if self.index.ntotal == 0:
            return []
            
        k = min(top_k * 2, self.index.ntotal) # search deeper to account for deprecated
        query_vec = self.embedding.embed(text).reshape(1, -1)
        distances, indices = self.index.search(query_vec, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and dist <= distance_threshold:
                meta = self.metadata_store.get(int(idx), {})
                # RL Check: Filter out deprecated bad memories
                if not meta.get("deprecated", False):
                    results.append({
                        "faiss_id": int(idx),
                        "distance": float(dist),
                        "metadata": meta
                    })
            if len(results) >= top_k:
                break
                
        return results
        
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """
        Retrieves all valid (non-deprecated) metadata from the FAISS store.
        Used for geographic clustering and dashboard analytics.
        """
        return [meta for idx, meta in self.metadata_store.items() if not meta.get("deprecated", False)]
