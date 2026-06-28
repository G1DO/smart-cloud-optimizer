import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ai_module.guided_questions import get_guided_questions
from ai_module.prompt_builder import build_prompt
from ai_module.recommender import get_ai_recommendations

router = APIRouter(prefix="/api/ai-onboarding", tags=["ai-onboarding"])

# Abuse guard for the AI generate endpoint (it spends Gemini quota):
# - PROMPT_MAX_CHARS always bounds the request body to cap spend/injection.
# - ONBOARDING_API_TOKEN is an OPTIONAL token gate, OFF by default so the demo
#   works with no config. When the env var is set, callers must send a matching
#   X-API-Token header (401 otherwise). Enabling it requires the frontend to
#   start sending the header (intentionally deferred).
PROMPT_MAX_CHARS = 4000


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
def generate_ai_recommendations(
    payload: PromptRequest,
    x_api_token: str | None = Header(default=None),
):
    expected_token = os.getenv("ONBOARDING_API_TOKEN")
    if expected_token and x_api_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")

    if len(payload.prompt) > PROMPT_MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"prompt exceeds {PROMPT_MAX_CHARS} character limit",
        )

    try:
        structured, raw_output = get_ai_recommendations(payload.prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # get_ai_recommendations signals failure in-band as ({"error": msg}, "")
    # rather than raising; surface it as an upstream (502) error instead of a
    # fake HTTP 200 carrying the error payload.
    if isinstance(structured, dict) and "error" in structured:
        raise HTTPException(status_code=502, detail=structured["error"])

    return {
        "recommendation": structured,
        "raw_output": raw_output,
    }