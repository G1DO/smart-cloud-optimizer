# AI Recommendations Engine

## Overview

This document explains the AI-powered recommendation pipeline used for generating AWS architecture and cost optimization suggestions for new users.

Unlike the ML forecasting engine (which works on historical cost data), this module is designed for new users without AWS data.

It uses a guided questionnaire → structured prompt builder → Google Gemini (Flash 2.0/2.5) → structured JSON response → stored in database.

## High-Level Flow
User (Streamlit UI)
        │
        ▼
Guided Questions (ai_module/guided_questions.py)
        │
        ▼
Prompt Builder (ai_module/prompt_builder.py)
        │
        ▼
Gemini Model (ai_module/recommender.py)
        │
        ▼
Structured JSON Output
        │
        ▼
storage.insert_ai_recommendations()
        │
        ▼
SQLite: ai_recommendations table

## 1. Guided Questions

Located in:
    ai_module/guided_questions.py

Returns a structured list of questions:
    [
    {
        "id": "app_type",
        "question": "What type of application are you building?",
        "options": ["website", "api", "database", "ml_training"]
    },
    ...
    ]

Purpose
    - Collect user workload profile
    - Understand scale, uptime, budget, importance
    - Capture non-technical user intent
    - Normalize inputs before prompt construction

## 2. Prompt Builder
Located in:
    ai_module/prompt_builder.py

Function:
    build_prompt(user_answers: dict) -> str

What It Does
    - Converts structured answers into an LLM-ready prompt
    - Adds system instructions
    - Forces strict JSON output format
    - Defines required fields

Example generated prompt:
    You are a senior AWS cloud architect.
    Based on the user requirements below, recommend:

    Return strictly JSON:
    {
    "setup": "...",
    "estimated_cost": 0,
    "explanation": "..."
    }

    User inputs:
    - App type: website
    - Expected users: 1000
    - Uptime: 24 hours
    - Budget: 500 USD
    ...

Why Structured Prompting?

We enforce JSON output so the system can:
    - Parse reliably
    - Store in DB
    - Compare later with ML optimizer
    - Avoid hallucinated text formatting

## 3. Gemini Model Integration
Located in:
    ai_module/recommender.py

Core Function
    get_ai_recommendations(prompt: str) -> dict

Internal Steps
1.Load API key from environment:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

2.Configure Gemini:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

3.Generate response:
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.3}
    )

4.Extract JSON:
    raw_output = response.text.strip()
    parsed = json.loads(extract_json(raw_output))

Output Format

Expected JSON from model:
    {
    "setup": "EC2 t3.medium + RDS db.t3.medium + S3",
    "estimated_cost": 320,
    "explanation": "Based on expected users..."
    }

## 4. Database Storage

Table:
    ai_recommendations
Defined in schema.sql.

Insert Function
    insert_ai_recommendations(conn, user_id, rows)

Stored Fields:
| Column                | Description                       |  
| app_type              | User workload type                |
| expected_users        | Daily active users                |
| uptime_hours          | Required uptime                   |
| importance            | low / medium / high / critical    |
| budget_monthly        | User budget                       |
| extra_requirements    | Free text                         |
| prompt_text           | Full prompt sent to LLM           |
| recommended_setup     | JSON string                       |
| estimated_cost        | Numeric                           |
| explanation           | LLM reasoning                     |
| llm_model             | Model used (gemini-2.0-flash)     |
| llm_response_raw      | Full raw LLM output               |
| created_at            | Timestamp                         |

## 5. Streamlit UI Integration

Located in:
    ai_module/ui.py

Flow
    prompt_text = build_prompt(user_answers)
    structured, raw_output = get_ai_recommendations(prompt_text)

    conn = get_connection()

    insert_ai_recommendations(
        conn,
        user_id="aws-demo-user",
        rows=[{...}]
    )

    conn.commit()
    conn.close()

The UI:
    - Displays generated prompt
    - Shows structured JSON output
    - Saves results to database

## 6. Design Decisions

Why Gemini Flash?
    - Fast
    - Cost-efficient
    - Good reasoning for infrastructure planning
    - Lower latency for interactive UI

Why Temperature = 0.3?
    - Reduce randomness
    - More deterministic infrastructure recommendations
    - Easier comparison across runs

Why Save Raw LLM Output?
    - Debugging
    - Model comparison later
    - Auditing hallucinations
    - Fine-tuning analysis

