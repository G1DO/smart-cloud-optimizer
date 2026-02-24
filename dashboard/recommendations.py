"""
dashboard/recommendations.py — Recommendations page for Smart Cloud Optimizer dashboard.

Displays cost optimization recommendations:
- All recommendations with detailed cards
- Filters: service, type, priority, minimum savings
- Sorting: by savings, priority, service
- Implementation guidance
- Export functionality
"""
import pandas as pd
import streamlit as st

from dashboard import components


def render():
    """Render the Recommendations page."""
    # Get active AWS account
    user_id = components.get_current_user_id()

    # Page header
    st.header("💡 Cost Optimization Recommendations")
    st.markdown(f"**Account:** `{user_id}`")
    st.markdown("---")

    # =========================================================================
    # Load Recommendations
    # =========================================================================

    try:
        # Load all recommendations
        all_recommendations = components.load_recommendations(
            user_id, limit=None, min_savings=0.0
        )

    except Exception as e:
        components.show_error(
            "Failed to load recommendations",
            details=str(e),
        )
        st.stop()

    # Check if we have recommendations
    if not all_recommendations:
        components.show_empty_state(
            "No recommendations available for this account",
            instruction=(
                "Generate recommendations by running the optimizer:\n\n"
                "```bash\n"
                f"python -m optimizer --user-id {user_id}\n"
                "```\n\n"
                "Or generate sample data first:\n"
                "```bash\n"
                "python -m data_generation.synthetic --days 365\n"
                "```"
            ),
        )
        st.stop()

    # =========================================================================
    # Summary Metrics
    # =========================================================================

    total_recommendations = len(all_recommendations)
    total_savings = sum(r["monthly_savings"] for r in all_recommendations)
    avg_savings = total_savings / total_recommendations if total_recommendations > 0 else 0

    # Count by priority
    priority_counts = {"high": 0, "medium": 0, "low": 0}
    for rec in all_recommendations:
        priority = rec.get("priority", "medium")
        if priority in priority_counts:
            priority_counts[priority] += 1

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Recommendations", str(total_recommendations))

    with col2:
        st.metric(
            "Potential Monthly Savings",
            components.format_currency(total_savings),
        )

    with col3:
        st.metric(
            "Avg Savings per Rec",
            components.format_currency(avg_savings),
        )

    with col4:
        st.metric(
            "High Priority",
            f"🔴 {priority_counts['high']}",
        )

    st.markdown("---")

    # =========================================================================
    # Filters and Sorting
    # =========================================================================

    st.subheader("🔍 Filter & Sort")

    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        # Service filter
        services = sorted(set(r.get("service", "unknown") for r in all_recommendations))
        service_filter = st.multiselect(
            "Service",
            options=["All"] + services,
            default=["All"],
        )

    with col2:
        # Type filter
        types = sorted(
            set(r.get("recommendation_type", "unknown") for r in all_recommendations)
        )
        type_filter = st.multiselect(
            "Recommendation Type",
            options=["All"] + types,
            default=["All"],
        )

    with col3:
        # Priority filter
        priority_filter = st.multiselect(
            "Priority",
            options=["All", "high", "medium", "low"],
            default=["All"],
        )

    with col4:
        # Minimum savings
        min_savings = st.number_input(
            "Min Monthly Savings ($)",
            min_value=0.0,
            max_value=10000.0,
            value=0.0,
            step=10.0,
        )

    # Sorting
    sort_by = st.selectbox(
        "Sort By",
        [
            "Savings (High to Low)",
            "Savings (Low to High)",
            "Priority (High to Low)",
            "Service (A-Z)",
        ],
        index=0,
    )

    st.markdown("---")

    # =========================================================================
    # Apply Filters
    # =========================================================================

    filtered_recs = all_recommendations.copy()

    # Service filter
    if "All" not in service_filter and service_filter:
        filtered_recs = [
            r for r in filtered_recs if r.get("service", "unknown") in service_filter
        ]

    # Type filter
    if "All" not in type_filter and type_filter:
        filtered_recs = [
            r
            for r in filtered_recs
            if r.get("recommendation_type", "unknown") in type_filter
        ]

    # Priority filter
    if "All" not in priority_filter and priority_filter:
        filtered_recs = [
            r for r in filtered_recs if r.get("priority", "medium") in priority_filter
        ]

    # Minimum savings filter
    filtered_recs = [r for r in filtered_recs if r["monthly_savings"] >= min_savings]

    # Apply sorting
    if sort_by == "Savings (High to Low)":
        filtered_recs.sort(key=lambda x: x["monthly_savings"], reverse=True)
    elif sort_by == "Savings (Low to High)":
        filtered_recs.sort(key=lambda x: x["monthly_savings"])
    elif sort_by == "Priority (High to Low)":
        priority_order = {"high": 0, "medium": 1, "low": 2}
        filtered_recs.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 1))
    elif sort_by == "Service (A-Z)":
        filtered_recs.sort(key=lambda x: x.get("service", "unknown"))

    # =========================================================================
    # Display Filtered Results
    # =========================================================================

    filtered_count = len(filtered_recs)
    filtered_savings = sum(r["monthly_savings"] for r in filtered_recs)

    if filtered_count == 0:
        components.show_empty_state(
            "No recommendations match your filters",
            instruction="Try adjusting the filters above to see more recommendations.",
        )
        st.stop()

    st.subheader(
        f"📋 Showing {filtered_count} Recommendation{'s' if filtered_count != 1 else ''} "
        f"(${filtered_savings:,.2f}/month potential savings)"
    )

    # =========================================================================
    # Recommendation Cards
    # =========================================================================

    # Service emoji mapping
    service_emojis = {
        "ec2": "🖥️",
        "rds": "🗄️",
        "lambda": "⚡",
        "s3": "📦",
        "ebs": "💾",
        "dynamodb": "📊",
        "elasticache": "⚡",
        "nat_gateway": "🌐",
        "elb": "⚖️",
    }

    # Priority emoji mapping
    priority_emojis = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🟢",
    }

    for i, rec in enumerate(filtered_recs, 1):
        # Extract recommendation details
        service = rec.get("service", "unknown").lower()
        rec_type = rec.get("recommendation_type", "optimization").replace("_", " ").title()
        resource_id = rec.get("resource_id", "N/A")
        monthly_savings = rec.get("monthly_savings", 0.0)
        priority = rec.get("priority", "medium")
        confidence = rec.get("confidence", "unknown")
        current_config = rec.get("current_config", "N/A")
        recommended_config = rec.get("recommended_config", "N/A")
        current_cost = rec.get("current_monthly_cost", 0.0)
        estimated_cost = rec.get("estimated_monthly_cost", 0.0)
        savings_pct = rec.get("savings_percent", 0.0)
        reasoning = rec.get("reasoning", "")

        # Get emojis
        service_emoji = service_emojis.get(service, "☁️")
        priority_emoji = priority_emojis.get(priority, "⚪")

        # Build card
        with st.container():
            # Header row: type + savings + priority
            col1, col2, col3 = st.columns([6, 2, 2])

            with col1:
                st.markdown(
                    f"### {priority_emoji} {service_emoji} {rec_type}"
                )

            with col2:
                st.markdown("**Monthly Savings**")
                st.markdown(f"## {components.format_currency(monthly_savings)}")

            with col3:
                st.markdown("**Priority**")
                priority_color = {
                    "high": "🔴 High",
                    "medium": "🟡 Medium",
                    "low": "🟢 Low",
                }.get(priority, "⚪ Unknown")
                st.markdown(f"## {priority_color}")

            # Change: current → recommended
            st.markdown(f"**Change:** `{current_config}`  →  `{recommended_config}`")

            # Cost comparison
            st.markdown(
                f"**Cost:** {components.format_currency(current_cost)}/mo  →  "
                f"{components.format_currency(estimated_cost)}/mo  "
                f"({savings_pct:.1f}% savings)"
            )

            # Reasoning
            if reasoning:
                st.markdown(f"**Why:** {reasoning}")

            # Metadata row
            col1, col2 = st.columns(2)

            with col1:
                st.caption(f"**Resource:** `{resource_id}`")

            with col2:
                if confidence and confidence != "unknown":
                    st.caption(f"**Confidence:** {confidence.capitalize()}")

            # Implementation guidance
            with st.expander("📝 Implementation Details"):
                st.markdown("**How to implement this recommendation:**")

                # Provide implementation guidance based on recommendation type
                impl_type = rec.get("recommendation_type", "")

                if "right_size" in impl_type.lower():
                    st.markdown(
                        f"""
                        1. Review current resource utilization for `{resource_id}`
                        2. Verify the recommended instance size meets your requirements
                        3. Schedule a maintenance window for resizing
                        4. Create a snapshot/backup before changes
                        5. Apply the recommended instance type change
                        6. Monitor performance for 24-48 hours
                        """
                    )
                elif "reserved" in impl_type.lower() or "spot" in impl_type.lower():
                    st.markdown(
                        f"""
                        1. Review the current pricing model for `{resource_id}`
                        2. Verify resource is stable/long-running (for Reserved Instances)
                        3. Purchase Reserved Instance or enable Spot pricing
                        4. Configure auto-scaling if using Spot instances
                        5. Monitor cost savings in AWS Cost Explorer
                        """
                    )
                elif "delete" in impl_type.lower() or "remove" in impl_type.lower():
                    st.markdown(
                        f"""
                        1. Verify `{resource_id}` is truly unused (check CloudWatch metrics)
                        2. Check for dependencies (applications, scripts referencing this resource)
                        3. Create a final snapshot/backup if applicable
                        4. Delete the resource via AWS Console or CLI
                        5. Verify charges stop appearing in billing
                        """
                    )
                else:
                    st.markdown(
                        f"""
                        1. Review the recommendation details above
                        2. Assess impact on your workload
                        3. Test changes in a non-production environment if possible
                        4. Apply the recommended changes via AWS Console or CLI
                        5. Monitor for 24-48 hours to verify expected results
                        """
                    )

                st.markdown("---")
                st.caption(
                    "⚠️ **Note:** Always test changes in non-production environments first. "
                    "Create backups before making infrastructure changes."
                )

            if i < len(filtered_recs):
                st.markdown("---")

    # =========================================================================
    # Bulk Actions (Placeholder)
    # =========================================================================

    st.markdown("---")
    st.subheader("⚡ Bulk Actions")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("📥 Export All (CSV)", use_container_width=True):
            # Convert recommendations to DataFrame
            df_export = pd.DataFrame(filtered_recs)

            # Format for export
            if not df_export.empty:
                df_export["monthly_savings"] = df_export["monthly_savings"].apply(
                    lambda x: f"${x:.2f}"
                )

                csv = df_export.to_csv(index=False)
                st.download_button(
                    label="📄 Download CSV",
                    data=csv,
                    file_name=f"recommendations_{user_id}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    with col2:
        if st.button("✅ Mark as Reviewed", use_container_width=True):
            st.info("💡 Bulk review functionality coming soon!")

    with col3:
        st.caption(
            "💡 **Coming Soon:** Apply recommendations directly from the dashboard"
        )

    # =========================================================================
    # Footer
    # =========================================================================

    st.markdown("")
    st.caption(
        f"💡 **Tip:** Showing {filtered_count} of {total_recommendations} recommendations. "
        f"Potential savings: {components.format_currency(filtered_savings)}/month"
    )
