"""AI recommendation engine using Google Gemini API.

Calls Google Gemini 2.0 Flash to generate cost-optimized AWS architecture
recommendations based on user requirements.

Part of the Smart Cloud Optimizer graduation project.
"""

import json
import logging

from google import genai

import config

logger = logging.getLogger(__name__)

# Validate API key at module load
if not config.GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY not set - ai_module will fail at runtime")


def get_ai_recommendations(prompt: str) -> tuple[dict, str]:
    """Generate AI-powered AWS architecture recommendations.

    Calls Google Gemini API with the provided prompt and returns structured
    recommendations with cost estimates.

    Args:
        prompt: The formatted prompt containing user requirements.

    Returns:
        Tuple of (parsed_dict, raw_response_text).
        If an error occurs, parsed_dict will be {"error": "error message"}.

    Examples:
        >>> prompt = "Design a web app architecture..."
        >>> structured, raw = get_ai_recommendations(prompt)
        >>> if "error" in structured:
        ...     print(f"API failed: {structured['error']}")
        ... else:
        ...     print(f"Estimated cost: ${structured['estimated_cost']}")
    """
    if not config.GOOGLE_API_KEY:
        return {"error": "GOOGLE_API_KEY not set. Please set environment variable."}, ""

    try:
        # Create client and generate content using new API
        client = genai.Client(api_key=config.GOOGLE_API_KEY)

        response = client.models.generate_content(
            model=config.GOOGLE_MODEL,
            contents=prompt,
            config={"temperature": 0.3}
        )

        if not response or not response.text:
            return {"error": "API returned empty response"}, ""

        raw_output = response.text.strip()

        # Extract and parse JSON from response
        json_str = extract_json(raw_output)
        parsed = json.loads(json_str)

        return parsed, raw_output

    except ValueError as e:
        # JSON extraction or parsing failed
        logger.error(f"JSON parsing error: {e}")
        return {"error": f"Failed to parse JSON response: {str(e)}"}, ""

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in response: {e}")
        return {"error": f"Invalid JSON format: {str(e)}"}, ""

    except Exception as e:
        # Catch all other errors (API errors, network issues, etc.)
        logger.error(f"API call failed: {type(e).__name__}: {e}")
        return {"error": f"API error: {str(e)}"}, ""


def extract_json(text: str) -> str:
    """Extract JSON object from text response.

    Finds the first {...} block in the text and returns it.

    Args:
        text: Raw text that may contain JSON with surrounding text.

    Returns:
        Extracted JSON string.

    Raises:
        ValueError: If no JSON block is found in the text.
    """
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or start > end:
        raise ValueError("No valid JSON block found in response")

    return text[start:end + 1]
