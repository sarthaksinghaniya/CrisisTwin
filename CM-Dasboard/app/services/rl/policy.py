import logging
from typing import Dict
from .feedback_manager import FeedbackManager

logger = logging.getLogger("cm_dashboard.engines.dynamic_policy")

class DynamicPolicyEngine:
    """
    Adjusts the pipeline manager's thresholds dynamically based on 
    Reinforcement Learning (RL) reward trends to optimize automated routing.
    """
    def __init__(self):
        # Tied directly to the production feedback manager module
        self.feedback_manager = FeedbackManager()
        
        # Base operational constants for fallback safety
        self.BASE_CONFIDENCE_THRESHOLD = 0.75
        self.BASE_RAG_AGREEMENT = 0.7
        self.BASE_RAG_SIMILARITY = 0.8

    def get_current_policy(self) -> Dict[str, float]:
        """
        Calculates dynamic threshold constraints based on rolling reward histories.
        Tighter boundaries are applied during negative trends to lower assignment errors.
        """
        try:
            # Analyze a moving window of the last 20 citizen interactions
            avg_reward = self.feedback_manager.get_average_reward(last_n=20)
        except Exception as exc:
            logger.error(f"[POLICY_ENGINE] Error calculating moving reward trend: {exc}. Using default policy.")
            avg_reward = 0.3  # Safe neutral baseline assumption

        # Instantiate safe default parameters
        policy = {
            "confidence_storage_threshold": self.BASE_CONFIDENCE_THRESHOLD,
            "rag_override_agreement": self.BASE_RAG_AGREEMENT,
            "rag_override_similarity": self.BASE_RAG_SIMILARITY
        }
        
        # Scenario A: Negative trend detected (System is making assignment mistakes)
        if avg_reward < 0.0:
            policy["confidence_storage_threshold"] = 0.85
            policy["rag_override_agreement"] = 0.8
            policy["rag_override_similarity"] = 0.85
            logger.warning(
                f"[POLICY_ENGINE] Low system accuracy detected (Avg Reward: {avg_reward:.2f}). "
                f"Policy boundaries tightened for high-precision validation."
            )
            
        # Scenario B: Highly accurate trend detected (Trust model classifications more)
        elif avg_reward > 0.5:
            policy["confidence_storage_threshold"] = 0.65
            policy["rag_override_agreement"] = 0.6
            policy["rag_override_similarity"] = 0.75
            logger.info(
                f"[POLICY_ENGINE] High system accuracy verified (Avg Reward: {avg_reward:.2f}). "
                f"Policy parameters relaxed for accelerated routing throughput."
            )
            
        else:
            logger.info(f"[POLICY_ENGINE] Stable system metrics verified (Avg Reward: {avg_reward:.2f}). Maintaining base constants.")

        # Final sanity check: clamp values between 0.0 and 1.0 to prevent configuration drift
        for key in policy:
            policy[key] = max(0.0, min(1.0, float(policy[key])))

        return policy
