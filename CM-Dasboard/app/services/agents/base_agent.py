from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """
    Abstract base class for all AI agents in the service layer.
    """
    
    @abstractmethod
    async def process(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Takes incident text as input and returns a structured decision output.
        
        Args:
            text (str): The raw text description of the incident.
            **kwargs: Additional context if needed.
            
        Returns:
            Dict[str, Any]: A structured dictionary containing the agent's decision and metadata.
        """
        pass
