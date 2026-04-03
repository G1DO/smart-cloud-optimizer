"""
dashboard/home.py — Home page for Smart Cloud Optimizer dashboard.

Displays:
- User selection
- Overview metrics (total cost, potential savings, anomalies)
- Cost trend chart (last 30 days)
- Top 3 recommendations

When data is insufficient (< COLD_START_DAYS), shows AI-powered
guided questionnaire instead of the normal dashboard.
"""
import json

import streamlit as st

import config
import storage.db as storage_db
from ai_module.guided_questions import get_guided_questions
from ai_module.prompt_builder import build_prompt
from ai_module.recommender import get_ai_recommendations
from dashboard import components


def render():
    """Render the Home page."""
    # Get active AWS account
    user_id = components.get_current_user_id()

    # Page header
    st.header("🏠 Dashboard Overview")
    st.markdown(f"**Selected Account:** `{user_id}`")
    st.markdown("---")

    # Cold-start gate: show questionnaire if not enough data yet
    data_days = components.get_data_days_count(user_id)
    if data_days < config.COLD_START_DAYS:
        _render_cold_start(user_id, data_days)
        st.stop()

    # Load data
    try:
        cost_data = components.load_cost_summary(user_id, days=30)
        recommendations = components.load_recommendations(user_id, limit=3 )
        anomalies = components.load_anomalies(user_id, days=30)
        service_costs = components.load_service_costs(user_id, days=30)

    except Exception as e:
        components.show_error(
            "Failed to load dashboard data",
            details=str(e),
        )
        st.stop()

    # Check if we have data
    if cost_data["daily"].empty:
        components.show_empty_state(
            "No cost data available for this account",
            instruction=(
                "Generate sample data by running:\n\n"
                "```bash\n"
                "python -m data_generation.synthetic --days 365\n"
                "```"
            ),
        )
        st.stop()

    # =========================================================================
    # Section 1: Key Metrics (3 columns)
    # =========================================================================

    col1, col2, col3 = st.columns(3)

    with col1:
        # Total cost with trend
        delta_str = (
            f"{cost_data['change_pct']:+.1f}%"
            if cost_data["change_pct"] != 0
            else None
        )
        components.display_metric_card(
            label="💰 Total Cost (30 days)",
            value=components.format_currency(cost_data["total"]),
            delta=delta_str,
            delta_color="inverse",  # Red for increase, green for decrease
        )

    with col2:
        # Potential savings
        total_savings = sum(r["monthly_savings"] for r in recommendations)
        rec_count = len(recommendations)
        components.display_metric_card(
            label="💡 Potential Savings",
            value=components.format_currency(total_savings) + "/mo",
            delta=f"{rec_count} recommendations" if rec_count > 0 else None,
        )

    with col3:
        # Anomalies detected
        anomaly_count = len(anomalies)
        components.display_metric_card(
            label="⚠️ Anomalies Detected",
            value=str(anomaly_count),
            delta="Last 30 days" if anomaly_count > 0 else None,
            delta_color="off",
        )

    st.markdown("---")

    # =========================================================================
    # Section 2: Cost Trend Chart
    # =========================================================================

    st.subheader("📊 Cost Trend (Last 30 Days)")

    if not cost_data["daily"].empty:
        fig = components.create_cost_line_chart(
            cost_data["daily"], title="Daily Total Costs"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Summary stats below chart
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Average Daily",
                components.format_currency(cost_data["avg_daily"]),
            )
        with col2:
            st.metric("Total (30d)", components.format_currency(cost_data["total"]))
        with col3:
            min_cost = cost_data["daily"]["total_cost"].min()
            max_cost = cost_data["daily"]["total_cost"].max()
            st.metric(
                "Range",
                f"{components.format_currency(min_cost)} - {components.format_currency(max_cost)}",
            )
    else:
        components.show_empty_state("No daily cost data available")

    st.markdown("---")

    # =========================================================================
    # Section 3: Top Services by Cost
    # =========================================================================

    st.subheader("💸 Top Services by Cost (30 days)")

    if not service_costs.empty:
        # Show top 5 in a clean table
        top_services = service_costs.head(5).copy()
        top_services["total_cost"] = top_services["total_cost"].apply(
            components.format_currency
        )
        top_services.columns = ["Service", "Total Cost"]

        st.dataframe(
            top_services,
            use_container_width=True,
            hide_index=True,
        )

        # Show percentage of total for top service
        if len(service_costs) > 0:
            top_pct = (
                service_costs.iloc[0]["total_cost"] / cost_data["total"] * 100
            )
            st.caption(
                f"💡 {service_costs.iloc[0]['service']} accounts for "
                f"{top_pct:.1f}% of total costs"
            )
    else:
        components.show_empty_state("No service cost breakdown available")

    st.markdown("---")

    # =========================================================================
    # Section 4: Top Recommendations
    # =========================================================================

    st.subheader("💡 Top Recommendations")

    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            # Priority badge
            priority = rec.get("priority", "medium")
            priority_emoji = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢",
            }.get(priority, "⚪")

            # Service icon
            service_emoji = {
                "ec2": "🖥️",
                "rds": "🗄️",
                "lambda": "⚡",
                "s3": "📦",
                "ebs": "💾",
                "dynamodb": "📊",
                "elasticache": "⚡",
                "nat_gateway": "🌐",
                "elb": "⚖️",
            }.get(rec.get("service", "").lower(), "☁️")

            # Build recommendation card
            with st.container():
                col1, col2 = st.columns([4, 1])

                with col1:
                    st.markdown(
                        f"{priority_emoji} **{service_emoji} "
                        f"{rec.get('recommendation_type', 'Optimization').replace('_', ' ').title()}**"
                    )
                    st.markdown(f"{rec.get('description', 'No description')}")
                    st.caption(
                        f"Resource: `{rec.get('resource_id', 'N/A')}` | "
                        f"Risk: {rec.get('risk', 'unknown')}"
                    )

                with col2:
                    st.markdown("**Monthly Savings**")
                    st.markdown(
                        f"## {components.format_currency(rec.get('monthly_savings', 0))}"
                    )

                if i < len(recommendations):
                    st.markdown("---")

        # Link to full recommendations page
        st.markdown("")
        st.info(
            "💡 **See all recommendations** on the Recommendations page (coming in Phase 3)"
        )

    else:
        components.show_empty_state(
            "No recommendations available",
            instruction="Run the optimizer to generate recommendations:\n"
            "```bash\n"
            "python -m optimizer.main --user-id " + user_id + "\n"
            "```",
        )

    # =========================================================================
    # Section 5: Anomalies (if any)
    # =========================================================================

    if anomalies:
        st.markdown("---")
        st.subheader("⚠️ Recent Anomalies")

        for anomaly in anomalies[:5]:  # Show up to 5
            date_str = components.format_date(anomaly["anomaly_date"])
            cost = components.format_currency(anomaly["actual_cost"])
            reason = anomaly.get("description", "Unknown")

            st.warning(
                f"**{date_str}**: Unusual cost of {cost} detected ({reason})"
            )

        if len(anomalies) > 5:
            st.caption(f"... and {len(anomalies) - 5} more anomalies")

    # =========================================================================
    # Footer Actions
    # =========================================================================

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with col2:
        if st.button("📥 Export Report", use_container_width=True):
            st.info("Export functionality coming soon!")

    st.markdown("")
    st.caption(
        "💡 **Tip:** Use the sidebar to navigate to detailed Cost Analysis "
        "and Forecasts pages (coming in Phase 2)"
    )


# =============================================================================
# Cold-start helpers (shown when data < COLD_START_DAYS)
# =============================================================================


def _render_cold_start(user_id: str, data_days: int) -> None:
    """Render cold-start experience: progress bar + questionnaire or stored results."""
    days_remaining = config.COLD_START_DAYS - data_days
    st.info(
        f"Collecting cost data... **{data_days}/{config.COLD_START_DAYS}** days. "
        f"Full dashboard available in **{days_remaining}** day{'s' if days_remaining != 1 else ''}."
    )
    st.progress(data_days / config.COLD_START_DAYS)

    # Check for existing AI recommendations
    conn = components.get_db_connection()
    existing = storage_db.get_ai_recommendations(conn, user_id)

    if existing and not st.session_state.get("retake_questionnaire"):
        _show_stored_recommendations(existing[0])
        st.markdown("---")
        if st.button("Retake Questionnaire"):
            st.session_state["retake_questionnaire"] = True
            st.rerun()
    else:
        _render_questionnaire_form(user_id)


def _render_questionnaire_form(user_id: str) -> None:
    """Render the guided questionnaire and handle submission."""
    st.subheader("Get AI-Powered Architecture Recommendations")
    st.write("Answer a few questions so we can recommend an optimized AWS setup.")

    questions = get_guided_questions()
    user_answers = {}

    with st.form("cold_start_questionnaire"):
        for q in questions:
            if q["id"] == "extra_notes":
                user_answers[q["id"]] = st.text_area(
                    q["question"],
                    placeholder="e.g., must use specific AWS region, compliance requirements, etc.",
                    help="Optional: any additional constraints or requirements",
                )
            else:
                user_answers[q["id"]] = st.selectbox(q["question"], q["options"])

        submitted = st.form_submit_button("Get Recommendations")

    if submitted:
        prompt_text = build_prompt(user_answers)

        with st.spinner("Generating AI recommendations..."):
            structured, raw_output = get_ai_recommendations(prompt_text)

        if "error" in structured:
            st.error(f"Error: {structured['error']}")
            st.info("Please check that GOOGLE_API_KEY environment variable is set correctly.")
        else:
            conn = components.get_db_connection()
            storage_db.insert_ai_recommendations(
                conn,
                user_id=user_id,
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
                    "llm_model": config.GOOGLE_MODEL,
                    "llm_response_raw": raw_output,
                }],
            )
            conn.commit()

            # Clear retake flag and rerun to show stored results
            st.session_state.pop("retake_questionnaire", None)
            st.rerun()


def _show_stored_recommendations(rec: dict) -> None:
    """Display previously stored AI recommendations."""
    st.subheader("Your AI Architecture Recommendations")
    st.caption(f"Generated on: {rec.get('created_at', 'Unknown')}")

    setup = rec["recommended_setup"]
    if isinstance(setup, str):
        setup = json.loads(setup)

    st.markdown("**Recommended Setup**")
    st.json(setup)

    estimated = rec.get("estimated_cost")
    if estimated is not None:
        st.markdown(f"**Estimated Monthly Cost:** {components.format_currency(float(estimated))}")

    explanation = rec.get("explanation")
    if explanation:
        st.markdown("**Explanation**")
        st.write(explanation)
