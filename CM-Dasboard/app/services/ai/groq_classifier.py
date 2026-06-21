import json
import os
from groq import Groq


CATEGORY_DEPARTMENT_MAP = {
    "Power": "Power Department",
    "Water": "Delhi Jal Board",
    "Sanitation": "Municipal Corporation",
    "Road": "PWD",
    "Security": "Police",
    "Healthcare": "Health Department",
    "Other": "General Administration"
}


class GroqClassifier:

    MODEL = "llama-3.1-8b-instant"

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY not configured")

        self.client = Groq(api_key=api_key)

    def classify(self, complaint_text: str) -> dict:

        prompt = f"""
You are a Delhi Government Complaint Classification Engine.

Classify the complaint.

Complaint:
{complaint_text}

Allowed Categories:
- Power
- Water
- Sanitation
- Road
- Security
- Healthcare
- Other

Priority Rules:

CRITICAL:
- danger to life
- violence
- flooding
- medical emergency
- road collapse
- electrical hazard

HIGH:
- utility outage
- severe service disruption

MEDIUM:
- public inconvenience

LOW:
- minor issue

Return ONLY valid JSON.

{{
    "category": "",
    "priority": "",
    "confidence": 0.95
}}
"""

        response = self.client.chat.completions.create(
            model=self.MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You only output JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response.choices[0].message.content

        result = json.loads(content)

        category = result.get("category", "Other")
        priority = result.get("priority", "MEDIUM")
        confidence = float(result.get("confidence", 0.90))

        department = CATEGORY_DEPARTMENT_MAP.get(
            category,
            "General Administration"
        )

        return {
            "category": category,
            "department": department,
            "priority": priority,
            "confidence": confidence
        }