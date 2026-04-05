"""ai_module — AI-powered cost optimization recommendations for new users.

Provides guided onboarding questions, prompt generation, and LLM-based
architecture recommendations via Google Gemini API.

Part of the Smart Cloud Optimizer graduation project.
"""

from .guided_questions import get_guided_questions
from .prompt_builder import build_prompt
from .recommender import get_ai_recommendations

__all__ = [
    "get_ai_recommendations",
    "build_prompt",
    "get_guided_questions",
]
