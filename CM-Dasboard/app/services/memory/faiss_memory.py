import os
import pickle
import numpy as np
import faiss
from typing import List, Dict, Any
from google import genai
from fastapi import HTTPException

class FaissMemory:
    def __init__(self, index_path: str = "storage/faiss_index.bin", metadata_path: str = "storage/faiss_meta.pkl"):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.dimension = 768  # Native dimensions for gemini 'text-embedding-004'

        # Initialize the modern official Google GenAI Client
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("CRITICAL: GEMINI_API_KEY environment variable is not set.")
        self.client = genai.Client(api_key=api_key)

        # Initialize or load an existing index
        self.index = None
        self.metadata: List[Dict[str, Any]] = []
        self._load_storage()

    def _load_storage(self):
        """Loads vector file system markers or boots clean matrix structures."""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, "rb") as f:
                self.metadata = pickle.load(f)
        else:
            # L2 Distance index (Euclidean). Use IndexFlatIP for Cosine Similarity if preferred
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []

    def _save_storage(self):
        """Persists binary data payloads out to system files."""
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generates a raw vector embedding using native Gemini models."""
        try:
            response = self.client.models.embed_content(
                model="text-embedding-004",
                contents=text,
            )
            # Handle list array extraction
            embedding = response.embeddings[0].values
            return np.array(embedding, dtype=np.float32).reshape(1, -1)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini Embedding Generation Error: {str(e)}")

    def add_document(self, text: str, extra_metadata: Dict[str, Any] = None):
        """Embeds and indexes a single document string with trackable metadata."""
        vector = self._get_embedding(text)
        self.index.add(vector)
        
        meta_entry = {"text": text}
        if extra_metadata:
            meta_entry.update(extra_metadata)
            
        self.metadata.append(meta_entry)
        self._save_storage()

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Queries vectors using L2 distance tracking and returns documents."""
        if self.index.ntotal == 0:
            return []

        query_vector = self._get_embedding(query)
        distances, indices = self.index.search(query_vector, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue
            item = self.metadata[idx].copy()
            item["distance"] = float(dist)
            results.append(item)
            
        return results
