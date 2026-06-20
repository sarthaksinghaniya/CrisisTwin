import os
import json
from google import genai
from google.genai import types
from .vector_store import ProductionComplaintVectorStore

class AIRoutingAssignmentEngine:
    def __init__(self, vector_store: ProductionComplaintVectorStore):
        """
        AI Routing Engine handling Classification, RAG Context Matching,
        and Workload Optimization Assignment.
        """
        if not os.environ.get("GEMINI_API_KEY"):
            raise ValueError("Production Error: GEMINI_API_KEY environment variable is not set.")
            
        self.client = genai.Client()
        self.model_name = "gemini-2.5-flash"  # High reasoning capability for routing decisions
        self.vector_store = vector_store

    def classify_complaint_text(self, text: str) -> dict:
        """
        Executes `/api/v1/complaints/classify`.
        Uses structured output schema to force categorical accuracy.
        """
        prompt = f"Analyze this citizen complaint and extract structural metadata:\n\n\"{text}\""
        
        # Enforce exact JSON response schema
        json_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "category": types.Schema(type=types.Type.STRING, description="Department name like Water, Power, Sanitation, Roads, Security"),
                "urgency_level": types.Schema(type=types.Type.STRING, description="LOW, MEDIUM, HIGH, or CRITICAL"),
                "summary": types.Schema(type=types.Type.STRING, description="Brief 1-sentence analytical summary of the core issue.")
            },
            required=["category", "urgency_level", "summary"]
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=json_schema,
                temperature=0.1  # Highly deterministic
            )
        )
        return json.loads(response.text)

    def evaluate_optimal_officer(self, complaint_text: str, available_officers: list[dict]) -> dict:
        """
        Executes `/api/v1/complaints/agent/decide`.
        Evaluates active officer rosters, balancing current workloads against department specializations.
        """
        # 1. Pull historical operational context via RAG
        past_cases = self.vector_store.search_similar_complaints(complaint_text, top_k=2)
        
        # 2. Run Classification
        classification = self.classify_complaint_text(complaint_text)
        
        # 3. Construct Reasoning Framework for Gemini Decision Matrix
        system_context = (
            "You are the Core AI Officer Assignment Module for the Chief Minister's Dashboard.\n"
            "Your objective is to evaluate a new citizen complaint against currently active department officers, "
            "taking into account historical patterns and keeping workloads balanced."
        )
        
        analysis_payload = {
            "target_complaint": {
                "text": complaint_text,
                "extracted_metadata": classification
            },
            "historical_rag_precedents": past_cases,
            "candidate_officers": available_officers
        }

        assignment_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "assigned_officer_id": types.Schema(type=types.Type.STRING, description="The unique ID of the chosen officer."),
                "routing_reasoning": types.Schema(type=types.Type.STRING, description="Granular rationale for why this officer fits best over others."),
                "estimated_sla_hours": types.Schema(type=types.Type.INTEGER, description="Suggested time limit to fix the issue based on urgency.")
            },
            required=["assigned_officer_id", "routing_reasoning", "estimated_sla_hours"]
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=f"Determine optimal routing assignment based on this structure:\n{json.dumps(analysis_payload)}",
            config=types.GenerateContentConfig(
                system_instruction=system_context,
                response_mime_type="application/json",
                response_schema=assignment_schema,
                temperature=0.2
            )
        )
        
        decision = json.loads(response.text)
        
        # Merge structural properties to feed right into database adapters
        return {
            "complaint_analysis": classification,
            "routing_decision": decision
        }

    def execute_pipeline_run(self, raw_complaint: dict, available_officers: list[dict]) -> dict:
        """
        Executes `/api/v1/complaints/pipeline/run`.
        Handles everything at once: runs RAG, matches the best officer, and stores the history in FAISS.
        """
        # Step A: Perform evaluation and matching
        pipeline_result = self.evaluate_optimal_officer(raw_complaint['text'], available_officers)
        
        # Step B: Record the event in your FAISS store to keep learning
        record_entry = {
            "id": raw_complaint.get("id", "UNKNOWN"),
            "text": raw_complaint["text"],
            "category": pipeline_result["complaint_analysis"]["category"],
            "assigned_officer_id": pipeline_result["routing_decision"]["assigned_officer_id"]
        }
        self.vector_store.add_complaints([record_entry])
        
        return pipeline_result
