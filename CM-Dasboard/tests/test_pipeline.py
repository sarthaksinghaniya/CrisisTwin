import pytest
import asyncio
from app.services.ml.inference import MLInferenceService
from app.services.memory.retriever import ContextRetriever
from app.services.memory.faiss_memory import FaissMemory
from app.services.agents.decision_agent import DecisionAgent

@pytest.fixture
def test_text():
    return "The garbage is overflowing on 5th Avenue and smells terrible."

@pytest.fixture
def memory_system():
    mem = FaissMemory()
    mem.add_memory("Garbage bin overflowing", metadata={"complaint": "Garbage bin overflowing", "decision": "SANITATION", "outcome": "Resolved", "labels": ["SANITATION"]})
    return mem

@pytest.fixture
def rag_system(memory_system):
    return ContextRetriever()

@pytest.fixture
def decision_agent():
    return DecisionAgent()

@pytest.mark.asyncio
async def test_agent_decision_with_context(test_text, rag_system, decision_agent):
    context = rag_system.get_context(test_text).get("similar_cases", [])
    assert len(context) > 0, "RAG should retrieve the mock context"
    
    decision_res = await decision_agent.process(test_text, context=context, ml_predictions=["SANITATION"])
    
    assert "SANITATION" in decision_res["decision"]
    assert "reasoning" in decision_res
    assert decision_res["confidence"] > 0.8

@pytest.mark.asyncio
async def test_pipeline_edge_case_empty_string(rag_system, decision_agent):
    empty_text = "   "
    context = rag_system.get_context(empty_text).get("similar_cases", [])
    
    decision_res = await decision_agent.process(empty_text, context=context, ml_predictions=["OTHER"])
    
    assert "decision" in decision_res
    assert "OTHER" in decision_res["decision"]

def test_inference_fallback():
    service = MLInferenceService()
    # Assuming model isn't trained in the test environment, should fallback gracefully
    res = service.predict("Test complaint")
    assert "category_pred" in res
    assert isinstance(res["category_pred"], list)
    assert res["confidence_score"] >= 0.0
