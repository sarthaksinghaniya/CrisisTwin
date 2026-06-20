import os
import sys
import logging
import pickle
from typing import List, Dict, Any

logger = logging.getLogger("cm_dashboard.services.memory.faiss")

class FaissMemory:
    """
    Hardened, Lazy-Loading Vector Storage Service.
    Safe for cross-platform deployment; prevents startup failures on environments 
    lacking native faiss wheels or binaries until an actual invocation is made.
    """
    def __init__(
        self, 
        index_path: str = "data/complaints_faiss.index", 
        metadata_path: str = "data/complaints_metadata.pkl"
    ):
        self.index_path = index_path
        self.metadata_path = metadata_path
        
        # Core storage variables initialized as None to delay import-time execution
        self._faiss_module = None
        self.index = None
        self.metadata_store = {}
        self._is_initialized = False

    def _lazy_init_faiss(self):
        """
        Dynamically imports FAISS and loads tracking indexes only when needed.
        Guarantees that missing system binaries will not prevent FastAPI from starting up.
        """
        if self._is_initialized:
            return

        try:
            # Lazy internal mapping import
            import faiss
            self._faiss_module = faiss
            logger.info("[FAISS_MEMORY] Successfully loaded native faiss library context dynamically.")
        except ImportError as err:
            logger.critical(
                "[FAISS_MEMORY] C++ Binary dependency 'faiss' is missing in this runtime environment. "
                "Vector-space storage operations are deactivated."
            )
            raise RuntimeError("CRITICAL: FAISS native library is unavailable in this container context.") from err

        # Secure folder paths
        os.makedirs(os.path.dirname(self.index_path) or '.', exist_ok=True)

        # Thread-safe dual storage index recovery structure
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = self._faiss_module.read_index(self.index_path)
                with open(self.metadata_path, 'rb') as f:
                    self.metadata_store = pickle.load(f)
                logger.info(f"[FAISS_MEMORY] Recovered {self.index.ntotal} historical embedding coordinates securely.")
            except Exception as e:
                logger.error(f"[FAISS_MEMORY] Index recovery failed due to corruption ({str(e)}). Resetting mapping arrays.")
                self._initialize_empty_index()
        else:
            self._initialize_empty_index()

        self._is_initialized = True

    def _initialize_empty_index(self):
        """Builds an Inner Product Vector Space matching Gemini's 768-dimension structure."""
        # Native dimension for text-embedding-004
        dimension = 768 
        self.index = self._faiss_module.IndexFlatIP(dimension)
        self.metadata_store = {}
        logger.info("[FAISS_MEMORY] Brand new vector index framework successfully initialized.")

    def search_similar(self, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Safely searches for similar items. Initializes FAISS on demand,
        preventing crashes during app startup.
        """
        # Trigger explicit lazy verification
        try:
            self._lazy_init_faiss()
        except RuntimeError:
            logger.warning("[FAISS_MEMORY] Search bypassed — storage runtime is offline.")
            return []

        if not self.index or self.index.ntotal == 0:
            return []

        try:
            # Fallback connection mapping logic using the Gemini engine we built in Sprint 1
            from core_ai.vector_store import ProductionComplaintVectorStore
            shared_store = ProductionComplaintVectorStore(self.index_path, self.metadata_path)
            
            # Utilize the production-hardened remote API embeddings call to fetch search matches
            return shared_store.search_similar_complaints(query_text, top_k=top_k)
        except Exception as exc:
            logger.error(f"[FAISS_MEMORY] Similarity lookup failed: {str(exc)}", exc_info=True)
            return []
