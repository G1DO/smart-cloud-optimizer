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
        from dashboard import costs

        costs.render()

    elif page == "📈 Forecasts":
        from dashboard import forecasts

        forecasts.render()

    elif page == "💡 Recommendations":
        from dashboard import recommendations

        recommendations.render()

    elif page == "⚙️ Settings":
        from dashboard import settings

        settings.render()

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Smart Cloud Optimizer**")
    st.sidebar.markdown("Version: 0.1.0 (Alpha)")
    st.sidebar.markdown("Last Updated: Feb 2026")


if __name__ == "__main__":
    main()
