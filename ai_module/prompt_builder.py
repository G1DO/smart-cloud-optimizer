
def build_prompt(user_answers: dict) -> str:
    """
    Convert guided question answers into a structured prompt
    for the AI recommendation model.
    """

    return f"""
You are a senior AWS cloud cost optimization architect.

The following information was collected during user onboarding.
This user has NO existing AWS usage data yet.

User profile:
- Application type: {user_answers['business_type']}
- Primary goal: {user_answers['priority']}
- Traffic pattern: {user_answers['traffic_pattern']}
- Availability requirement: {user_answers['availability']}
- AWS experience level: {user_answers['experience_level']}

Your task:
1. Design a cost-optimized AWS architecture suitable for a beginner.
2. Prefer serverless or Graviton-based services where possible.
3. Clearly justify each service choice in terms of cost vs performance.
4. Provide a realistic monthly cost estimate (USD).
5. Mention how this setup can scale in the future.

CRITICAL RULES:
- Prefer serverless or Spot where applicable.
- Use modern instance families only (t4g, m7g, c7g).
- Consider AWS Free Tier when possible.
- Keep the solution beginner-friendly.

OUTPUT FORMAT:
Return ONLY valid JSON with this structure:
DO NOT include markdown.
DO NOT wrap JSON in ```json
Return pure JSON only.

{{
  "recommended_setup": {{
    "service_name": "configuration"
  }},
  "monthly_estimate": {{
    "service_name": "cost"
  }},
  "explanation": "text"
}}
"""