"""Prompt builder for AI recommendation engine.

Converts guided question answers into a structured prompt for the LLM.

Part of the Smart Cloud Optimizer graduation project.
"""


def build_prompt(user_answers: dict) -> str:
    """Convert guided question answers into LLM prompt.

    Builds a detailed prompt with user requirements and output format
    specification for the AI model.

    Args:
        user_answers: Dict mapping question IDs to user's selected answers.
            Expected keys: business_type, expected_users, uptime_requirement,
            priority, traffic_pattern, availability, monthly_budget,
            experience_level, extra_notes (optional).

    Returns:
        Formatted prompt string ready for LLM API call.

    Examples:
        >>> answers = {
        ...     "business_type": "Web application",
        ...     "expected_users": "1,000-10,000",
        ...     "priority": "Balance cost and performance",
        ...     "monthly_budget": "$500-2,000"
        ... }
        >>> prompt = build_prompt(answers)
        >>> assert "Web application" in prompt
    """
    extra = user_answers.get("extra_notes", "None specified")

    return f"""
You are a senior AWS cloud cost optimization architect.

The following information was collected during user onboarding.
This user has NO existing AWS usage data yet.

User profile:
- Application type: {user_answers['business_type']}
- Expected users: {user_answers.get('expected_users', 'Not specified')}
- Uptime requirement: {user_answers.get('uptime_requirement', 'Not specified')}
- Primary goal: {user_answers['priority']}
- Traffic pattern: {user_answers['traffic_pattern']}
- Availability requirement: {user_answers['availability']}
- Monthly budget: {user_answers.get('monthly_budget', 'Not specified')}
- AWS experience level: {user_answers['experience_level']}
- Additional requirements: {extra}

Your task:
1. Design a cost-optimized AWS architecture suitable for their experience level.
2. Prefer serverless or Graviton-based services where possible.
3. Clearly justify each service choice in terms of cost vs performance.
4. Provide a realistic monthly cost estimate (USD).
5. Mention how this setup can scale in the future.

CRITICAL RULES:
- Prefer serverless or Spot instances where applicable.
- Use modern instance families only (t4g, m7g, c7g, r7g for Graviton).
- Consider AWS Free Tier when budget is tight.
- Keep the solution appropriate for their experience level.
- Account for the uptime requirement when choosing multi-AZ or single-AZ.
- Match the architecture complexity to the expected user count.

OUTPUT FORMAT:
Return ONLY valid JSON with this exact structure.
DO NOT include markdown code blocks or ```json wrappers.
Return pure JSON only.

{{
  "recommended_setup": {{
    "compute": "detailed configuration",
    "database": "detailed configuration",
    "storage": "detailed configuration",
    "networking": "detailed configuration",
    "other_services": "any additional services"
  }},
  "estimated_cost": 123.45,
  "explanation": "Detailed explanation covering: why each service was chosen, how it meets their requirements (uptime, traffic pattern, availability), cost breakdown by service, and how to scale this architecture in the future."
}}

Key points for the explanation:
- Justify choices relative to their priority ({user_answers['priority']})
- Address their traffic pattern ({user_answers['traffic_pattern']})
- Match availability to their needs ({user_answers['availability']})
- Explain cost vs Free Tier tradeoffs if budget < $100/month
- Provide next steps for scaling beyond current expected users
"""
