import streamlit as st
import guided_questions as gq
from prompt_builder import build_prompt
from recommender import get_ai_recommendations
from storage.db import get_connection, insert_ai_recommendations


st.set_page_config(page_title="Smart Cloud Optimizer", layout="centered")

st.title("Smart Cloud Optimizer")
st.subheader("AI-powered AWS Cost Optimization")

st.write("Answer a few questions so we can understand your workload 👇")

questions = gq.get_guided_questions()
user_answers = {}

with st.form("guided_questions_form"):
    for q in questions:
        user_answers[q["id"]] = st.selectbox(
            q["question"],
            q["options"]
        )

    submitted = st.form_submit_button("Get Recommendations")

if submitted:
    prompt_text = build_prompt(user_answers)

    st.success("Prompt generated")
    st.write("### Prompt sent to AI:")
    st.code(prompt_text)

    with st.spinner("Generating AI recommendations..."):
        structured, raw_output = get_ai_recommendations(prompt_text)

    if "error" in structured:
        st.error(structured["error"])
    else:
        conn = get_connection()

        insert_ai_recommendations(
            conn,
            user_id="aws-demo-user",
            rows=[{
                "app_type": user_answers["app_type"],
                "expected_users": user_answers.get("expected_users"),
                "uptime_hours": user_answers.get("uptime_hours"),
                "importance": user_answers.get("importance"),
                "budget_monthly": user_answers.get("budget"),
                "extra_requirements": user_answers.get("extra"),

                "prompt_text": prompt_text,
                "recommended_setup": structured["setup"],
                "estimated_cost": structured["estimated_cost"],
                "explanation": structured["explanation"],

                "llm_model": "gemini-2.0-flash",
                "llm_response_raw": raw_output
            }]
        )

        conn.commit()
        conn.close()

        st.success("AI Recommendations ready")
        st.json(structured)

