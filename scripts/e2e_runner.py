import os
import sys
import json
import asyncio
import logging

# Set up logging to file
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "pipeline.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("e2e_runner")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CM-Dasboard')))

from app.services.ml.inference import MLInferenceService
from app.services.memory.retriever import ContextRetriever
from app.services.agents.decision_agent import DecisionAgent

async def run_pipeline():
    logger.info("Starting E2E Pipeline Run...")
    
    # 1. Input
    complaint_text = "The entire neighborhood is flooded and the water is reaching the houses. We need help immediately!"
    logger.info(f"Input Complaint: {complaint_text}")
    
    # Initialize components
    logger.info("Loading components...")
    classifier = MLInferenceService()
    retriever = ContextRetriever()
    decision_agent = DecisionAgent()
    
    # 2. ML Classification
    logger.info("Running ML Classification...")
    ml_res = classifier.predict(complaint_text)
    predicted_labels = ml_res.get("category_pred", ["OTHER"])
    logger.info(f"ML Output: {predicted_labels}")
    
    # 3. RAG Retrieval
    logger.info("Retrieving historical context from FAISS...")
    rag_res = retriever.get_context(complaint_text)
    similar_cases = rag_res.get("similar_cases", [])
    logger.info(f"Found {len(similar_cases)} similar past cases.")
    
    # 4. Agent Decision
    logger.info("Executing DecisionAgent...")
    decision_res = await decision_agent.process(
        text=complaint_text, 
        context=similar_cases, 
        ml_predictions=predicted_labels
    )
    logger.info(f"Final Decision: {decision_res['decision']}")
    logger.info(f"Reasoning: {decision_res['reasoning']}")
    
    # 5. Output
    output_data = {
        "input_complaint": complaint_text,
        "ml_predictions": predicted_labels,
        "context_retrieved": len(similar_cases),
        "decision": decision_res["decision"],
        "reasoning": decision_res["reasoning"],
        "confidence": decision_res["confidence"]
    }
    
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs'))
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "results.json")
    
    with open(out_path, "w") as f:
        json.dump(output_data, f, indent=4)
        
    logger.info(f"Results successfully saved to {out_path}")
    logger.info("E2E Pipeline Run Complete.")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
