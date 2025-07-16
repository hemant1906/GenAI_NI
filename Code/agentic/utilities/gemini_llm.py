import os
import google.generativeai as genai
from langchain.llms.base import LLM
from typing import ClassVar, List
from dotenv import load_dotenv

# Load API Key from .env
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class GeminiLLM(LLM):
    model_name: ClassVar[str] = "gemini-2.5-pro"

    def _call(self, prompt: str, stop: List[str] = None) -> str:
        model = genai.GenerativeModel(self.model_name)
        response = model.generate_content(prompt)
        return response.text.strip() if hasattr(response, "text") else str(response)

    @property
    def _llm_type(self):
        return "gemini-custom"