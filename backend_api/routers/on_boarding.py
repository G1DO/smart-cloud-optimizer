from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_module.guided_questions import get_guided_questions
from ai_module.prompt_builder import build_prompt
from ai_module.recommender import get_ai_recommendations

router = APIRouter(prefix="/api/ai-onboarding", tags=["ai-onboarding"])


class AnswersRequest(BaseModel):
    answers: dict


class PromptRequest(BaseModel):
    prompt: str


@router.get("/questions")
def get_questions():
    try:
        return {"questions": get_guided_questions()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/build-prompt")
def build_ai_prompt(payload: AnswersRequest):
    try:
        prompt_text = build_prompt(payload.answers)
        return {"prompt": prompt_text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate")
def generate_ai_recommendations(payload: PromptRequest):
    try:
        structured, raw_output = get_ai_recommendations(payload.prompt)
        return {
            "recommendation": structured,
            "raw_output": raw_output,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))