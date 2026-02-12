"""Streamlit UI for AI-powered cost optimization recommendations.

Interactive onboarding flow for new users who don't have existing AWS usage.
Collects requirements through guided questions, generates AI recommendations
via Google Gemini, and stores results in the database.

Part of the Smart Cloud Optimizer graduation project.
"""

import json
import streamlit as st

import storage
from ai_module.guided_questions import get_guided_questions
from ai_module.prompt_builder import build_prompt
from ai_module.recommender import get_ai_recommendations


st.set_page_config(page_title="Smart Cloud Optimizer", layout="centered")

st.title("Smart Cloud Optimizer")
st.subheader("AI-powered AWS Cost Optimization")

st.write("Answer a few questions so we can understand your workload 👇")

questions = get_guided_questions()
user_answers = {}

with st.form("guided_questions_form"):
    for q in questions:
        # Handle extra_notes as text area, everything else as selectbox
        if q["id"] == "extra_notes":
            user_answers[q["id"]] = st.text_area(
                q["question"],
                placeholder="e.g., must use specific AWS region, compliance requirements, etc.",
                help="Optional: any additional constraints or requirements"
            )
        else:
            user_answers[q["id"]] = st.selectbox(
                q["question"],
                q["options"]
            )

    submitted = st.form_submit_button("Get Recommendations")

if submitted:
    prompt_text = build_prompt(user_answers)

    st.success("Prompt generated")
    with st.expander("View prompt sent to AI"):
        st.code(prompt_text, language="text")

    with st.spinner("Generating AI recommendations..."):
        structured, raw_output = get_ai_recommendations(prompt_text)

    if "error" in structured:
        st.error(f"❌ {structured['error']}")
        st.info("Please check that GOOGLE_API_KEY environment variable is set correctly.")
    else:
        conn = storage.get_connection()

        # Map question answers to database schema
        storage.insert_ai_recommendations(
            conn,
            user_id="aws-SYNTHETIC-001",
            rows=[{
                "app_type": user_answers["business_type"],
                "expected_users": user_answers.get("expected_users"),
                "uptime_hours": user_answers.get("uptime_requirement"),
                "importance": user_answers.get("availability"),
                "budget_monthly": user_answers.get("monthly_budget"),
                "extra_requirements": user_answers.get("extra_notes"),

                "prompt_text": prompt_text,
                "recommended_setup": json.dumps(structured["recommended_setup"]),
                "estimated_cost": structured["estimated_cost"],
                "explanation": structured["explanation"],

                "llm_model": "gemini-2.5-flash",
                "llm_response_raw": raw_output
            }]
        )

        conn.commit()
        conn.close()

        st.success("✅ AI Recommendations ready")
        st.subheader("Recommended Setup")
        st.json(structured["recommended_setup"])

        st.subheader(f"Estimated Monthly Cost: ${structured['estimated_cost']}")

        st.subheader("Explanation")
        st.write(structured["explanation"])

        with st.expander("View raw AI response"):
            st.text(raw_output)
