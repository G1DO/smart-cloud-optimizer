"""
Smart Cloud Optimizer — Streamlit Entry Point.

Multi-page dashboard for AWS cost optimization:
- Home: Overview metrics and top recommendations
- Costs: Detailed cost analysis with charts
- Forecasts: ML predictions and model comparison
- Recommendations: Cost optimization opportunities
- Settings: User configuration and parameters
"""
import streamlit as st


def main() -> None:
    """Streamlit app entry point."""
    # Page config MUST be first Streamlit call
    st.set_page_config(
        page_title="Smart Cloud Optimizer",
        page_icon="☁️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # App header
    st.title("☁️ Smart Cloud Optimizer")
    st.markdown("AI-powered AWS cost optimization platform")
    st.markdown("---")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Page",
        ["🏠 Home", "💰 Costs", "📈 Forecasts", "💡 Recommendations", "⚙️ Settings"],
        label_visibility="collapsed",
    )

    # Route to appropriate page
    if page == "🏠 Home":
        from dashboard import home

        home.render()

    elif page == "💰 Costs":
        # Placeholder for Costs page (Phase 2)
        st.info("📊 Cost Analysis page coming soon...")
        st.markdown(
            """
            **Planned Features:**
            - Daily cost trends (line chart)
            - Cost breakdown by service (bar chart)
            - Top 5 most expensive resources
            - Date range selector
            - Export to CSV
            """
        )

    elif page == "📈 Forecasts":
        # Placeholder for Forecasts page (Phase 2)
        st.info("🔮 Forecasts page coming soon...")
        st.markdown(
            """
            **Planned Features:**
            - Cost predictions (30/60/90 days)
            - Confidence intervals
            - Model comparison (Prophet, SARIMAX, ETS)
            - Forecast accuracy metrics (RMSE, MAE, MAPE)
            """
        )

    elif page == "💡 Recommendations":
        # Placeholder for Recommendations page (Phase 3)
        st.info("💡 Recommendations page coming soon...")
        st.markdown(
            """
            **Planned Features:**
            - All optimization recommendations
            - Filter by service, type, priority
            - Sort by savings, risk, priority
            - Estimated monthly savings
            - Implementation instructions
            """
        )

    elif page == "⚙️ Settings":
        # Placeholder for Settings page (Phase 3)
        st.info("⚙️ Settings page coming soon...")
        st.markdown(
            """
            **Planned Features:**
            - User profile management
            - AWS account connection
            - Forecast/optimization parameters
            - Demo mode toggle
            - Data refresh controls
            """
        )

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Smart Cloud Optimizer**")
    st.sidebar.markdown("Version: 0.1.0 (Alpha)")
    st.sidebar.markdown("Last Updated: Feb 2026")


if __name__ == "__main__":
    main()
