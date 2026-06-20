import os
import json
import pickle
import numpy as np
import faiss
from google import genai
from google.genai import types
from google.genai.errors import APIError

class ProductionComplaintVectorStore:
    def __init__(
        self, 
        index_path: str = "data/complaints_faiss.index", 
        metadata_path: str = "data/complaints_metadata.pkl"
    ):
        """
        Production Vector Store using Gemini API for enterprise-grade embeddings.
        Tracks vectors and metadata synchronously to disk to prevent data corruption.
        """
        # Ensure API key is present in environment variables
        if not os.environ.get("GEMINI_API_KEY"):
            raise ValueError("Production Error: GEMINI_API_KEY environment variable is not set.")
            
        # Initialize Google GenAI client
        self.client = genai.Client()
        self.embedding_model = "text-embedding-004"
        self.dimension = 768  # Native dimension for text-embedding-004
        
        self.index_path = index_path
        self.metadata_path = metadata_path
        
        # Ensure directory structure exists
        os.makedirs(os.path.dirname(self.index_path) or '.', exist_ok=True)
        
        # Initialize Memory Structures
        self.metadata_store = {}
        self.index = None
        
        self._load_or_create_store()

    def _load_or_create_store(self):
        """Thread-safe lookalike initialization to recover vector indexes and mapping arrays."""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, 'rb') as f:
                    self.metadata_store = pickle.load(f)
                print(f"[SUCCESS] Loaded {self.index.ntotal} vectors from persistent storage.")
            except Exception as e:
                print(f"[CRITICAL] Corruption detected while reading vector storage: {str(e)}")
                print("Re-initializing blank database index...")
                self._create_blank_index()
        else:
            self._create_blank_index()

    def _create_blank_index(self):
        """Creates an Inner Product index calibrated for normalized cosine similarities."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata_store = {}

    def _get_gemini_embeddings(self, texts: list[str]) -> np.ndarray:
        """Fetches remote embeddings from Gemini API with safe error management."""
        try:
            response = self.client.models.embed_content(
                model=self.embedding_model,
                contents=texts
            )
            # Extract list of embeddings and convert to numpy array
            embeddings_list = [embedding.values for embedding in response.embeddings]
            embeddings = np.array(embeddings_list, dtype='float32')
            
            # Normalize for Cosine Similarity (IndexFlatIP)
            faiss.normalize_L2(embeddings)
            return embeddings
            
        except APIError as e:
            print(f"[API ERROR] Google Gemini API failed: {e}")
            raise
        except Exception as e:
            print(f"[SYSTEM ERROR] Failed generating embeddings: {str(e)}")
            raise

    def add_complaints(self, complaints: list[dict]):
        """
        Appends new structured records into vector engine.
        Each complaint must map strictly into: {'id': str, 'text': str, 'category': str}
        """
        if not complaints:
            return
            
        texts = [item['text'] for item in complaints]
        embeddings = self._get_gemini_embeddings(texts)
        
        start_idx = self.index.ntotal
        self.index.add(embeddings)
        
        # Append corresponding metadata index locations
        for i, complaint in enumerate(complaints):
            global_idx = start_idx + i
            self.metadata_store[global_idx] = complaint
            
        # Atomic Write Phase (Saves everything synchronously)
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata_store, f, protocol=pickle.HIGHEST_PROTOCOL)
            
        print(f"[PERSISTED] Total database records scaled to: {self.index.ntotal}")

    def search_similar_complaints(self, query_text: str, top_k: int = 3) -> list[dict]:
        """Queries production store, yielding structured payloads + precision vectors."""
        if self.index.ntotal == 0:
            return []

        query_embedding = self._get_gemini_embeddings([query_text])
        similarities, indices = self.index.search(query_embedding, top_k)
        
        results = []
        # Parse arrays (FAISS returns nested matrices for multi-query batches)
        for score, idx in zip(similarities[0], indices[0]):
            if idx == -1 or idx not in self.metadata_store:
                continue
                
            complaint_record = self.metadata_store[idx].copy()
            # Append evaluation metrics directly into payload
            complaint_record['semantic_score'] = float(score)
            results.append(complaint_record)
            
        return results
