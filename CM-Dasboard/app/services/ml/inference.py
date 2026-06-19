import logging
from typing import Dict, Any, List
import numpy as np
from .model_loader import ModelLoader
from app.ml.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

class MLInferenceService:
    """
    Service layer providing inference functionality using fine-tuned models.
    """
    def __init__(self):
        self.loader = ModelLoader()
        self.loader.load_models()
        self.embedder = EmbeddingService()
        
    def get_embeddings(self, text: str) -> List[float]:
        """
        Generates BERT embeddings for the given text.
        """
        try:
            embeddings_matrix = self.embedder.generate_embeddings([text])
            return embeddings_matrix[0].tolist()
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []
        
    def predict(self, text: str) -> Dict[str, Any]:
        """
        Runs the main classifier on the provided text.
        Returns predicted categories and confidence scores.
        """
        try:
            embeddings = self.get_embeddings(text)
            if not embeddings:
                raise ValueError("Failed to generate embeddings")
                
            X_input = np.array([embeddings])
            
            classifier = self.loader.get_classifier()
            encoders = self.loader.get_encoders()
            
            if not classifier or not encoders or 'category' not in encoders:
                logger.warning("Models not fully loaded. Returning fallback predictions.")
                return self._fallback_predict()

            # Predict Categories (Multi-label from NNTrainer)
            # Depending on if it's PyTorch NNTrainer or sklearn
            if hasattr(classifier, 'predict'):
                if type(classifier).__name__ == "NNTrainer":
                    preds, probs = classifier.predict(X_input)
                    preds = preds[0]
                    probs = probs[0]
                    
                    class_names = encoders['category'].classes_
                    predicted_labels = []
                    confidences = []
                    for i, is_pred in enumerate(preds):
                        if is_pred == 1:
                            predicted_labels.append(class_names[i])
                            confidences.append(float(probs[i]))
                            
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
                    
                    if not predicted_labels:
                        predicted_labels = ["OTHER"]
                        avg_conf = 0.5
                        
                    return {
                        "category_pred": predicted_labels,
                        "confidence_score": avg_conf
                    }
                else:
                    # Legacy fallback
                    cat_probs = classifier.predict_proba(X_input)[0]
                    cat_idx = np.argmax(cat_probs)
                    cat_pred = encoders['category'].inverse_transform([cat_idx])[0]
                    cat_conf = float(cat_probs[cat_idx])
                    return {
                        "category_pred": [cat_pred.upper()],
                        "confidence_score": cat_conf
                    }
            return self._fallback_predict()
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return self._fallback_predict()
            
    def _fallback_predict(self) -> Dict[str, Any]:
        return {
            "category_pred": ["OTHER"],
            "confidence_score": 0.5
        }
