"""
dashboard/home.py — Home page for Smart Cloud Optimizer dashboard.

Displays:
- User selection
- Overview metrics (total cost, potential savings, anomalies)
- Cost trend chart (last 30 days)
- Top 3 recommendations
"""
import streamlit as st

from dashboard import components


def render():
    """Render the Home page."""
    # User selection (in sidebar)
    user_id = components.select_user()

    # Page header
    st.header("🏠 Dashboard Overview")
    st.markdown(f"**Selected Account:** `{user_id}`")
    st.markdown("---")

    # Load data
    try:
        cost_data = components.load_cost_summary(user_id, days=30)
        recommendations = components.load_recommendations(user_id, limit=3)
        anomalies = components.load_anomalies(user_id, days=30)
        service_costs = components.load_service_costs(user_id, days=30)

    except Exception as e:
        components.show_error(
            "Failed to load dashboard data",
            details=str(e),
        )
        st.stop()

    # Check if we have data
    if cost_data["total"] == 0:
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
