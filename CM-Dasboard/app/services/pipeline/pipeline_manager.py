from typing import Dict, Any
import uuid
from app.services.agents.classification_agent import ClassificationAgent
from app.services.agents.severity_agent import SeverityAgent
from app.services.agents.routing_agent import RoutingAgent
from app.services.memory.faiss_memory import FaissMemory

class PipelineManager:
    """
    Orchestrates the sequential execution of AI agents to process an incident.
    Passes structured data between independent agents and enriches the final output.
    """
    
    def __init__(self):
        self.classification_agent = ClassificationAgent()
        self.severity_agent = SeverityAgent()
        self.routing_agent = RoutingAgent()
        self.memory = FaissMemory()

    async def process_incident(self, text: str) -> Dict[str, Any]:
        """
        Runs the incident text through the agent pipeline and combines the results.
        
        Args:
            text (str): The raw text description of the incident.
            
        Returns:
            Dict[str, Any]: The enriched, combined output of all agent decisions.
        """
        combined_result = {"original_text": text}
        incident_id = str(uuid.uuid4())
        
        # 0. Retrieve similar past incidents from FAISS memory
        similar_incidents = self.memory.search_similar(text, top_k=3)
        combined_result["similar_incidents_context"] = similar_incidents
        
        # 1. Classify the incident (passing context)
        classification_result = await self.classification_agent.process(text, context=similar_incidents)
        combined_result["classification"] = classification_result
        incident_type = classification_result.get("type")
        
        # 2. Determine severity (passing context)
        severity_result = await self.severity_agent.process(text, context=similar_incidents)
        combined_result["severity_assessment"] = severity_result
        severity = severity_result.get("severity")
        
        # 3. Route the incident based on previous outputs (passing context)
        routing_result = await self.routing_agent.process(
            text=text, 
            severity=severity, 
            incident_type=incident_type,
            context=similar_incidents
        )
        combined_result["routing"] = routing_result
        
        # 4. Generate final top-level summary combining all decisions
        final_decision = {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "severity_level": severity,
            "assigned_team": routing_result.get("assigned_team"),
            "priority": routing_result.get("priority"),
            "requires_human_review": routing_result.get("requires_human_review", False)
        }
        combined_result["final_decision"] = final_decision
        
        # 5. Store the final enriched incident result into FAISS memory
        self.memory.add_memory(text=text, metadata=final_decision)
        
        return combined_result
