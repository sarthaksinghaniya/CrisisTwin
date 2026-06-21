import os
import json
import logging
from groq import Groq
from .vector_store import ProductionComplaintVectorStore

logger = logging.getLogger("cm_dashboard.routing_engine")

class AIRoutingAssignmentEngine:
    def __init__(self, vector_store: ProductionComplaintVectorStore):
        """
        AI Routing Engine powered by Groq Cloud SDK.
        Utilizes high-speed Llama models with JSON mode for structured data extraction.
        """
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Production Error: GROQ_API_KEY environment variable is not defined.")
            
        self.client = Groq(api_key=api_key)
        self.classifier_model = "llama3-8b-8192"          # Sub-50ms token parsing speed
        self.routing_agent_model = "llama-3.3-70b-versatile" # High-reasoning agent evaluation
        self.vector_store = vector_store

    def classify_complaint_text(self, text: str) -> dict:
        """
        Executes complaint categorization via Groq JSON mode.
        """
        prompt = (
            f"Analyze this citizen complaint and extract structural operational categories.\n"
            f"Complaint text: \"{text}\"\n\n"
            f"You must respond with a JSON object following this exact schema structure:\n"
            f"{{\n"
            f"  \"category\": \"Department string like: Water, Power, Sanitation, Roads, or Security\",\n"
            f"  \"urgency_level\": \"LOW, MEDIUM, HIGH, or CRITICAL\",\n"
            f"  \"confidence\": 0.95\n"
            f"}}\n"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.classifier_model,
                messages=[
                    {"role": "system", "content": "You are an expert automated routing classifier. You output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Direct text inspection for debugging
            raw_json = response.choices[0].message.content
            logger.info(f"[DEBUG_CLASSIFIER] Groq Raw Response: {raw_json}")
            return json.loads(raw_json)
            
        except Exception as err:
            logger.error(f"[CLASSIFIER_CRASH] Groq parsing crashed: {str(err)}", exc_info=True)
            # Safe fallthrough backup to keep your system operational during network outages
            return {"category": "General Desk", "urgency_level": "MEDIUM", "confidence": 0.5}

    def evaluate_optimal_officer(self, complaint_text: str, available_officers: list[dict]) -> dict:
        """
        Evaluates active officer rosters, balancing current workloads against department specializations.
        """
        # 1. Pull historical operational context via local FAISS RAG
        past_cases = self.vector_store.search_similar_complaints(complaint_text, top_k=2)
        
        # 2. Run Classification
        classification = self.classify_complaint_text(complaint_text)
        
        system_context = (
            "You are the Core AI Officer Assignment Module for the Chief Minister's Dashboard.\n"
            "Your objective is to evaluate a new citizen complaint against currently active department officers, "
            "taking into account historical patterns and keeping workloads balanced.\n"
            "You must respond with a JSON object following this exact structure:\n"
            "{\n"
            "  \"assigned_officer_id\": \"The unique string ID of the chosen officer.\",\n"
            "  \"routing_reasoning\": \"Granular rationale explaining why this officer fits best over others.\",\n"
            "  \"estimated_sla_hours\": 48\n"
            "}"
        )
        
        analysis_payload = {
            "target_complaint": {
                "text": complaint_text,
                "extracted_metadata": classification
            },
            "historical_rag_precedents": past_cases,
            "candidate_officers": available_officers
        }

        try:
            response = self.client.chat.completions.create(
                model=self.routing_agent_model,
                messages=[
                    {"role": "system", "content": system_context},
                    {"role": "user", "content": json.dumps(analysis_payload)}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            decision = json.loads(response.choices[0].message.content)
            return {
                "complaint_analysis": classification,
                "routing_decision": decision
            }
        except Exception as err:
            logger.error(f"[ROUTING_CRASH] Groq decision failed: {str(err)}", exc_info=True)
            fallback_officer = available_officers[0]["id"] if available_officers else "FALLBACK_QUEUE_HEAD"
            return {
                "complaint_analysis": classification,
                "routing_decision": {
                    "assigned_officer_id": fallback_officer,
                    "routing_reasoning": "System fallback auto-triggered due to Groq cluster generation timeout.",
                    "estimated_sla_hours": 72
                }
            }

    def execute_pipeline_run(self, raw_complaint: dict, available_officers: list[dict]) -> dict:
        """
        Runs the full end-to-end pipeline: executes classification, 
        evaluates officer assignments, and saves the history in FAISS.
        """
        pipeline_result = self.evaluate_optimal_officer(raw_complaint['text'], available_officers)
        
        record_entry = {
            "id": raw_complaint.get("id", "UNKNOWN"),
            "text": raw_complaint["text"],
            "category": pipeline_result["complaint_analysis"]["category"],
            "assigned_officer_id": pipeline_result["routing_decision"]["assigned_officer_id"]
        }
        self.vector_store.add_complaints([record_entry])
        
        return pipeline_result
