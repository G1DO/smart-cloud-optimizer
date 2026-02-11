
def get_guided_questions():
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
                "Stable",
                "Predictable peaks",
                "Highly variable"
            ]
        },
        {
            "id": "availability",
            "question": "How critical is availability?",
            "options": [
                "Can tolerate downtime",
                "Some downtime acceptable",
                "Must be highly available"
            ]
        },
        {
            "id": "experience_level",
            "question": "Your AWS experience level?",
            "options": [
                "Beginner",
                "Intermediate",
                "Advanced"
            ]
        }
    ]
