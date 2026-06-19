from typing import Dict, Any
from .base_agent import BaseAgent

class RoutingAgent(BaseAgent):
    """
    Agent responsible for assigning incidents to the proper team or specific agent.
    Takes the output of other agents (severity, type) as context.
    """
    
    async def process(self, text: str, severity: str = None, incident_type: str = None, **kwargs) -> Dict[str, Any]:
        """
        Routes the incident. Optionally utilizes pre-computed severity and incident_type.
        """
        # TODO: Integrate actual routing logic, possibly an LLM prompt or a rules engine.
        
        assigned_team = "GENERAL_SUPPORT"
        
        # Determine team based on type
        if incident_type == "FIRE":
            assigned_team = "FIRE_DEPARTMENT"
        elif incident_type == "MEDICAL":
            assigned_team = "EMS"
        elif incident_type == "POLICE":
            assigned_team = "LAW_ENFORCEMENT"
        elif incident_type == "HAZMAT":
            assigned_team = "HAZMAT_RESPONSE"
            
        # Determine priority based on severity
        priority = "NORMAL"
        if severity in ["HIGH", "CRITICAL"]:
            priority = "EXPEDITED"
            
        return {
            "agent": "RoutingAgent",
            "assigned_team": assigned_team,
            "priority": priority,
            "requires_human_review": severity == "CRITICAL" # Example of a derived field
        }
