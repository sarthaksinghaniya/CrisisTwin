from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    """
    Abstract base class for all AI agents in the system.
    """
    
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def process(self, input_data: Any) -> Dict[str, Any]:
        """
        Process the input data and return a structured output.
        
        Args:
            input_data (Any): The input data for the agent to process.
            
        Returns:
            Dict[str, Any]: Structured output from the agent.
        """
        pass
