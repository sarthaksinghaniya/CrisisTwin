import os
import pickle
import numpy as np
import logging

logger = logging.getLogger("cm_dashboard.vector_store")

class ProductionComplaintVectorStore:
    def __init__(
        self, 
        index_path: str = "data/complaints_faiss.index", 
        metadata_path: str = "data/complaints_metadata.pkl"
    ):
        """
        Hardened Local Embeddings store using sentence-transformers and FAISS.
        Guarantees local embedding production without API network dependency risks.
        """
        self.index_path = index_path
        self.metadata_path = metadata_path
        
        # Local model produces 384-dimensional dense vectors
        self.dimension = 384  
        self._transformer_model = None
        self._faiss_module = None
        
        self.metadata_store = {}
        self.index = None
        self._is_initialized = False

    def _lazy_init(self):
        if self._is_initialized:
            return
            
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            self._faiss_module = faiss
            self._transformer_model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError as e:
            logger.critical(f"Missing underlying ML packages for Vector Store: {str(e)}")
            raise RuntimeError("Run: pip install faiss-cpu sentence-transformers") from e

        os.makedirs(os.path.dirname(self.index_path) or '.', exist_ok=True)
        
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = self._faiss_module.read_index(self.index_path)
                with open(self.metadata_path, 'rb') as f:
                    self.metadata_store = pickle.load(f)
            except Exception as e:
                logger.error(f"Index corruption encountered ({str(e)}). Building fresh index.")
                self._create_blank_index()
        else:
            self._create_blank_index()
            
        self._is_initialized = True

    def _create_blank_index(self):
        self.index = self._faiss_module.IndexFlatIP(self.dimension)
        self.metadata_store = {}

    def _generate_local_embeddings(self, texts: list[str]) -> np.ndarray:
        # Vector strings are calculated locally without crashing due to network timeouts
        embeddings = self._transformer_model.encode(texts, convert_to_numpy=True)
        self._faiss_module.normalize_L2(embeddings)
        return embeddings.astype('float32')

    def add_complaints(self, complaints: list[dict]):
        if not complaints:
            return
        self._lazy_init()
        
        texts = [item['text'] for item in complaints]
        embeddings = self._generate_local_embeddings(texts)
        
        start_idx = self.index.ntotal
        self.index.add(embeddings)
        
        for i, complaint in enumerate(complaints):
            global_idx = start_idx + i
            self.metadata_store[global_idx] = complaint
            
        self._faiss_module.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata_store, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"[VECTOR_STORE] Synced {len(complaints)} records. Total index size: {self.index.ntotal}")

    def search_similar_complaints(self, query_text: str, top_k: int = 3) -> list[dict]:
        self._lazy_init()
        if self.index.ntotal == 0:
            return []

        query_embedding = self._generate_local_embeddings([query_text])
        similarities, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for score, idx in zip(similarities[0], indices[0]):
            if idx == -1 or idx not in self.metadata_store:
                continue
            complaint_record = self.metadata_store[idx].copy()
            complaint_record['semantic_score'] = float(score)
            results.append(complaint_record)
            
        return results
