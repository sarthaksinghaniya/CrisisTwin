import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.services.ml.inference import MLInferenceService
from app.services.memory.retriever import ContextRetriever
from app.services.memory.faiss_memory import FaissMemory
from app.services.agents.decision_agent import DecisionAgent

@pytest.fixture
def mock_faiss_memory():
    with patch('app.services.memory.faiss_memory.FaissMemory.search_similar') as mock_search:
        mock_search.return_value = [
            {"distance": 0.1, "metadata": {"complaint": "Garbage bin overflowing", "decision": "SANITATION_DEPT", "outcome": "Resolved", "labels": ["SANITATION"]}}
        ]
        yield mock_search

@pytest.fixture
def test_text():
    return "The garbage is overflowing on 5th Avenue and smells terrible."

@pytest.fixture
def decision_agent():
    return DecisionAgent()

@pytest.mark.asyncio
async def test_agent_decision_with_context(test_text, mock_faiss_memory, decision_agent):
    retriever = ContextRetriever()
    context = retriever.get_context(test_text).get("similar_cases", [])
    
    assert len(context) > 0, "RAG should retrieve the mock context"
    
    decision_res = await decision_agent.process(test_text, context=context, ml_predictions=["SANITATION"])
    
    assert "SANITATION" in decision_res["decision"]
    assert "reasoning" in decision_res
    assert decision_res["confidence"] > 0.8

@pytest.mark.asyncio
async def test_pipeline_edge_case_empty_string(mock_faiss_memory, decision_agent):
    empty_text = "   "
    retriever = ContextRetriever()
    context = retriever.get_context(empty_text).get("similar_cases", [])
    
    decision_res = await decision_agent.process(empty_text, context=context, ml_predictions=["OTHER"])
    
    assert "decision" in decision_res
    assert "reasoning" in decision_res

def test_inference_fallback():
    with patch('app.services.ml.model_loader.ModelLoader.load_models', return_value=None), \
         patch('app.ml.embeddings.EmbeddingService', return_value=MagicMock()):
        service = MLInferenceService()
        # Should fallback gracefully since models are mocked to None
        res = service.predict("Test complaint")
        assert "category_pred" in res
        assert isinstance(res["category_pred"], list)
        assert res["confidence_score"] >= 0.0
