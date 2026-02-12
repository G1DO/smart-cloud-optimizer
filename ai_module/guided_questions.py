"""Guided onboarding questions for AI recommendations.

Collects user requirements through a structured questionnaire to generate
personalized AWS architecture recommendations.

Part of the Smart Cloud Optimizer graduation project.
"""


def get_guided_questions():
    """Return list of guided questions for user onboarding.

    Returns:
        List of dicts with keys: id, question, options.
        Each question dict contains:
        - id: Unique identifier used in answer dict
        - question: The question text shown to user
        - options: List of possible answers (strings)

    Examples:
        >>> questions = get_guided_questions()
        >>> print(questions[0]["question"])
        What best describes your workload?
    """
    return [
        {
            "id": "business_type",
            "question": "What best describes your workload?",
            "options": [
                "Web application",
                "Mobile backend",
                "Data analytics / ML",
                "E-commerce",
                "Internal / enterprise system"
            ]
        },
        {
            "id": "expected_users",
            "question": "How many users do you expect?",
            "options": [
                "< 100",
                "100-1,000",
                "1,000-10,000",
                "10,000-100,000",
                "> 100,000"
            ]
        },
        {
            "id": "uptime_requirement",
            "question": "What are your uptime requirements?",
            "options": [
                "8x5 (business hours only)",
                "24x5 (weekdays, 24 hours)",
                "24x7 (always on)",
                "Best effort (dev/test environment)"
            ]
        },
        {
            "id": "priority",
            "question": "What is your top priority?",
            "options": [
                "Minimize cost",
                "Balance cost and performance",
                "Maximize performance"
            ]
        },
        {
            "id": "traffic_pattern",
            "question": "How does your traffic behave?",
            "options": [
                "Stable throughout the day",
                "Predictable daily peaks",
                "Highly variable / unpredictable"
            ]
        },
        {
            "id": "availability",
            "question": "How critical is availability?",
            "options": [
                "Can tolerate downtime (dev/test)",
                "Some downtime acceptable (< 1 hour/month)",
                "Must be highly available (< 5 minutes/month)"
            ]
        },
        {
            "id": "monthly_budget",
            "question": "What is your monthly budget?",
            "options": [
                "< $100",
                "$100-500",
                "$500-2,000",
                "$2,000-10,000",
                "> $10,000"
            ]
        },
        {
            "id": "experience_level",
            "question": "Your AWS experience level?",
            "options": [
                "Beginner (new to AWS)",
                "Intermediate (some AWS projects)",
                "Advanced (production deployments)"
            ]
        },
        {
            "id": "extra_notes",
            "question": "Any additional requirements or constraints?",
            "options": []  # Will be rendered as text area in UI
        }
    ]
