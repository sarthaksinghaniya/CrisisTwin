import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

class FeedbackManager:
    """
    Handles the Reinforcement Learning feedback loop, calculating rewards,
    and persisting the feedback ledger for future fine-tuning.
    """
    def __init__(self, ledger_path: str = "outputs/feedback_ledger.json"):
        self.ledger_path = ledger_path
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        self.ledger = self._load_ledger()
        
    def _load_ledger(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, 'r') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception:
                return []
        return []
        
    def _save_ledger(self):
        try:
            with open(self.ledger_path, 'w') as f:
                json.dump(self.ledger, f, indent=2)
        except Exception as e:
            print(f"[FEEDBACK_MANAGER_ERROR] Failed saving ledger: {str(e)}")
            
    def calculate_reward(self, predicted: Dict[str, Any], actual: Dict[str, Any], rag_agreement: bool = False) -> float:
        """
        Calculates the reward based on the prediction accuracy and confidence parameters.
        """
        pred_cat = predicted.get("category")
        actual_cat = actual.get("category")
        
        pred_sev = predicted.get("severity")
        actual_sev = actual.get("severity")
        
        confidence = predicted.get("confidence", 0.5)
        reward = 0.0
        
        # Exact match structural validation check
        if pred_cat == actual_cat and pred_sev == actual_sev:
            reward += 1.0
        else:
            # Wrong prediction penalty adjustments
            if confidence > 0.8:
                reward -= 2.0  # High confidence penalization penalty
            else:
                reward -= 1.0
                
        # RAG reward alignment allocation 
        if rag_agreement:
            reward += 0.5
            
        return reward

    def submit_feedback(self, incident_text: str, predicted: Dict[str, Any], actual: Dict[str, Any], rag_agreement: bool = False) -> float:
        """
        Submits human-corrected feedback, calculates reward mechanics, and writes records.
        """
        reward = self.calculate_reward(predicted, actual, rag_agreement)
        
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "incident": incident_text,
            "predicted": predicted,
            "actual": actual,
            "reward": reward,
            "rag_agreement": rag_agreement
        }
        
        self.ledger.append(record)
        self._save_ledger()
        return reward
        
    def get_average_reward(self, last_n: int = 50) -> float:
        if not self.ledger:
            return 0.0
        recent = self.ledger[-last_n:]
        total = sum(r.get("reward", 0.0) for r in recent)
        return total / len(recent) if recent else 0.0