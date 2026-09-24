# AI Module

The AI module builds a questionnaire prompt and calls Gemini for architecture
advice. This is separate from the inventory-based [cost optimizer](optimizer.md).
The configured model is `GOOGLE_MODEL`; see [Configuration](../../reference/configuration.md).
A valid `GOOGLE_API_KEY` is needed even for the synthetic demo workspace.

## Entry points and persistence

| Entry point | Behavior |
| --- | --- |
| Next.js guided questions → [FastAPI onboarding router](../../../backend_api/routers/on_boarding.py) | Fetches questions, builds a prompt, and returns generated recommendations and raw text. The router does not persist them to SQLite. |
| Legacy [Streamlit Home](../../../dashboard/home.py) | Offers the questionnaire during cold start and stores generated recommendations for the selected user. |
| Standalone [ai_module/ui.py](../../../ai_module/ui.py) | Writes recommendations to the synthetic user; running it can modify the tracked demo DB. Use a disposable checkout/database for experiments. |
| Python callers | Decide whether to store the returned result through `storage.insert_ai_recommendations()`. |

HTTP request/response schemas are generated at http://localhost:8000/docs and
http://localhost:8000/openapi.json when the backend runs. The generate endpoint
caps prompts at 4000 characters (HTTP 400), returns HTTP 502 for in-band Gemini
errors, and optionally requires `X-API-Token` when `ONBOARDING_API_TOKEN` is set.
The current Next.js client does not send that header. These guards do not provide
session authentication or validate the factual correctness of AI advice.

## Python contract

- [guided_questions.py](../../../ai_module/guided_questions.py) owns the question IDs,
  text, and options. Use `get_guided_questions()` instead of maintaining another
  questionnaire definition.
- [prompt_builder.py](../../../ai_module/prompt_builder.py) maps answers to a prompt
  requesting `recommended_setup`, `estimated_cost`, and `explanation`.
- [recommender.py](../../../ai_module/recommender.py) creates `google.genai.Client`,
  calls `client.models.generate_content()` with the configured model and
  temperature `0.3`, extracts the text between the first `{` and last `}`, and
  parses JSON.
- `get_ai_recommendations(prompt)` returns `(parsed_result, raw_response_text)`.
  Missing credentials, API failures, empty responses, and JSON failures return
  `({"error": message}, "")`. Parsing does not enforce the requested output
  fields or prove that the recommendation or price is correct.

A Python caller can construct the prompt without making an external request:

```python
from ai_module import get_guided_questions, build_prompt

questions = get_guided_questions()
answers = {
    question["id"]: question["options"][0] if question["options"] else ""
    for question in questions
}
prompt = build_prompt(answers)
print(prompt)
```

Calling `get_ai_recommendations(prompt)` then uses the configured Gemini service.
Check the error result before consuming fields. For persistence,
`recommended_setup` is JSON-serialized into a TEXT column; include the input
profile, prompt, estimated cost, model identifier, and raw response according to
`insert_ai_recommendations()` in [storage/db.py](../../../storage/db.py).
The caller commits and closes the connection; see [Storage API](../../api/storage.md).

## Verification

```bash
python -m pytest tests/test_ai_module.py tests/test_home.py tests/test_frontend_backend_contract.py -v
```

These tests use mocks and local fixtures. They verify integration/error behavior,
not live Gemini availability, generated advice, or forecast/optimizer accuracy.
