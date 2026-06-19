import threading
import logging

logger = logging.getLogger(__name__)

class ModelLoader:
    """
    Singleton class to ensure ML models are loaded into memory only once.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(ModelLoader, cls).__new__(cls)
                cls._instance._model = None
                cls._instance._tokenizer = None
                cls._instance._is_loaded = False
        return cls._instance
        
    def load_model(self, model_name_or_path: str = "bert-base-uncased"):
        """
        Loads the model and tokenizer into memory.
        """
        with self._lock:
            if self._is_loaded:
                return
                
            try:
                # In a real scenario, you would import transformers and load models here:
                # from transformers import AutoModel, AutoTokenizer
                # self._tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
                # self._model = AutoModel.from_pretrained(model_name_or_path)
                
                # Placeholder for actual model object
                self._model = f"MockModel({model_name_or_path})"
                self._tokenizer = f"MockTokenizer({model_name_or_path})"
                
                self._is_loaded = True
                logger.info(f"Model '{model_name_or_path}' loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading model '{model_name_or_path}': {e}")
                raise e
            
    def get_model(self):
        """Returns the loaded model instance."""
        if not self._is_loaded:
            self.load_model()
        return self._model
        
    def get_tokenizer(self):
        """Returns the loaded tokenizer instance."""
        if not self._is_loaded:
            self.load_model()
        return self._tokenizer
