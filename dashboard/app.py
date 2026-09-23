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

from dashboard.auth import init_session_state, is_authenticated, render_auth_page, logout
from dashboard.components import render_account_switcher


def main() -> None:
    """Streamlit app entry point."""
    # Page config MUST be first Streamlit call
    st.set_page_config(
        page_title="Smart Cloud Optimizer",
        page_icon="☁️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # --- Auth gate ---
    init_session_state()
    if not is_authenticated():
        render_auth_page()
        st.stop()

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

    # Account switcher (below nav)
    render_account_switcher()

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
    user_label = st.session_state.get("user_email", "")
    if st.session_state.get("demo_mode"):
        user_label = "Demo Mode"
    st.sidebar.markdown(f"**{user_label}**")
    if st.sidebar.button("Logout", use_container_width=True):
        logout()
    st.sidebar.caption("Smart Cloud Optimizer v0.2.0")


if __name__ == "__main__":
    main()
