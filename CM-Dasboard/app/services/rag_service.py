import os
from typing import List
from google import genai
from google.genai import types
from fastapi import HTTPException, Depends
from app.services.memory.faiss_memory import FaissMemory

class RAGQueryService:
    def __init__(self, memory: FaissMemory = Depends()):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("CRITICAL: GEMINI_API_KEY environment variable is not set.")
        
        self.client = genai.Client(api_key=api_key)
        self.memory = memory  # Injected persistent memory layer

    async def process_rag_query(self, query: str, top_k: int = 3) -> dict:
        # 1. Fetch real contextual documents based on the incoming query string from FAISS
        search_results = self.memory.search(query, top_k)
        
        # Extract just the raw text strings from metadata
        contexts = [item["text"] for item in search_results]
        
        # Fallback if your vector database index is completely empty right now
        if not contexts:
            context_str = "No specific system procedures found in vector index storage files."
        else:
            context_str = "\n".join([f"- {c}" for c in contexts])

        # 2. Build strict ground rules for the LLM pipeline
        system_instruction = (
            "You are an expert AI operator managing the City & Facility Operations Dashboard.\n"
            "Your job is to answer incoming queries or process citizen complaints using ONLY the factual context provided below.\n"
            "If the provided context does not contain enough information to form a conclusive answer, state clearly "
            "that the required information is missing from the system's Standard Operating Procedures (SOPs).\n"
            "Do not use external background knowledge or invent facts.\n\n"
            f"=== SYSTEM CONTEXT AND SOPS ===\n{context_str}"
        )

        try:
            response = self.client.models.generate_content(
                model='Gemini 3.1 Flash-Lite',
                contents=query,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,
                )
            )
            
            return {
                "query": query,
                "answer": response.text,
                "context_retrieved": contexts
            }

        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Gemini API Engine failure during text generation: {str(e)}"
            )