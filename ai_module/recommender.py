import os
import json
import google.generativeai as genai

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)


def get_ai_recommendations(prompt: str) -> tuple:
    model = genai.GenerativeModel("gemini-2.0-flash")

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.3}
    )

    raw_output = response.text.strip()
    parsed = json.loads(extract_json(raw_output))

    return parsed, raw_output


def extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return text[start:end + 1]
    raise ValueError("No JSON found in response")
