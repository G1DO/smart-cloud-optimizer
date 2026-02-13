"""
dashboard/settings.py — Settings page for Smart Cloud Optimizer dashboard.

Displays and manages:
- User profile information
- AWS account connection (placeholder)
- Forecast and optimization parameters
- Demo mode indicator
- Data refresh controls
"""
import streamlit as st

import config
from dashboard import components


def render():
    """Render the Settings page."""
    # User selection
    user_id = components.select_user()

    # Page header
    st.header("⚙️ Settings")
    st.markdown(f"**Account:** `{user_id}`")
    st.markdown("---")

    # =========================================================================
    # Section 1: User Profile
    # =========================================================================

    st.subheader("👤 User Profile")

    try:
        # Load user information
        users = components.load_users()
        current_user = next((u for u in users if u["user_id"] == user_id), None)

        if current_user:
            col1, col2 = st.columns(2)

            with col1:
                st.text_input(
                    "User ID",
                    value=current_user["user_id"],
                    disabled=True,
                )

            with col2:
                st.text_input(
                    "Email",
                    value=current_user["email"],
                    disabled=True,
                )

            st.caption(
                "💡 **Note:** Profile editing will be available after login system is implemented."
            )

        else:
            components.show_error("User not found in database")

    except Exception as e:
        components.show_error("Failed to load user profile", details=str(e))

    st.markdown("---")

    # =========================================================================
    # Section 2: AWS Account Connection
    # =========================================================================

    st.subheader("☁️ AWS Account Connection")

    # Check if this is a synthetic/demo account
    is_demo = user_id.startswith("SYNTHETIC-") or user_id.startswith("aws-SYNTHETIC-")

    if is_demo:
        st.info("📊 **Demo Mode Active** — Using synthetic data for this account")

        with st.expander("What is Demo Mode?"):
            st.markdown(
                """
                **Demo mode** uses synthetic (generated) AWS cost and usage data instead of
                connecting to a real AWS account. This is perfect for:

                - Testing the dashboard without AWS credentials
                - Demos and presentations
                - Learning how the optimizer works

                **Real data** mode (coming soon) will connect to your actual AWS account
                via IAM credentials to collect real usage metrics and costs.
                """
            )

        st.markdown("**Demo Account Details:**")
        st.code(f"User ID: {user_id}\nData Source: Synthetic Generator\nCoverage: 365 days")

    else:
        st.warning("⚠️ **No AWS Connection** — This account is not connected to AWS")

        st.markdown("**To connect your AWS account:**")
        st.markdown(
            """
            1. Ensure you have AWS IAM credentials with required permissions
            2. Configure AWS CLI or provide access keys
            3. Run the data collector to sync your account

            ```bash
            # Configure AWS credentials
            aws configure

            # Run collector
            python -m aws_collector.main --user-id YOUR_USER_ID
            ```
            """
        )

        st.info(
            "💡 **Coming Soon:** Connect AWS accounts directly from the dashboard with "
            "a one-click setup wizard."
        )

    st.markdown("---")

    # =========================================================================
    # Section 3: System Status
    # =========================================================================

    st.subheader("🔧 System Status")

    col1, col2, col3 = st.columns(3)

    with col1:
        demo_status = "🟢 Active" if config.DEMO_MODE else "⚪ Inactive"
        st.metric("Demo Mode", demo_status)

    with col2:
        st.metric("AWS Region", config.AWS_REGION)

    with col3:
        st.metric("Database", "SQLite")

    # Data refresh controls
    st.markdown("**Data Management:**")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("🔄 Clear Cache", use_container_width=True):
            st.cache_data.clear()
            st.success("✅ Cache cleared! Data will be reloaded on next page visit.")

    with col2:
        if st.button("📊 View Database Stats", use_container_width=True):
            st.info("💡 Database statistics viewer coming soon!")

    st.caption("💡 **Tip:** Clear cache if you've updated data and want to see the latest values")

    st.markdown("---")

    # =========================================================================
    # Section 4: Forecast Parameters
    # =========================================================================

    st.subheader("📈 Forecast Configuration")

    st.markdown(
        "Configure default parameters for ML cost forecasting. "
        "These can be overridden on the Forecasts page."
    )

    col1, col2 = st.columns(2)

    with col1:
        forecast_horizon = st.number_input(
            "Default Forecast Horizon (days)",
            min_value=7,
            max_value=180,
            value=config.FORECAST_HORIZON_DAYS,
            step=1,
            help="Number of days to forecast into the future",
            disabled=True,
        )

        min_training_days = st.number_input(
            "Minimum Training Days",
            min_value=14,
            max_value=365,
            value=config.MIN_TRAINING_DAYS,
            step=1,
            help="Minimum historical data required for forecasting",
            disabled=True,
        )

    with col2:
        seasonality = st.number_input(
            "Seasonality Period (days)",
            min_value=1,
            max_value=30,
            value=config.SEASONALITY_PERIOD,
            step=1,
            help="Weekly=7, Monthly=30, Daily=1",
            disabled=True,
        )

        confidence_level = st.slider(
            "Confidence Interval",
            min_value=0.5,
            max_value=0.99,
            value=0.80,
            step=0.05,
            format="%.0f%%",
            help="Width of prediction confidence intervals",
            disabled=True,
        )

    st.caption(
        "💡 **Note:** Parameter customization will be enabled in a future update. "
        "Currently showing system defaults."
    )

    st.markdown("---")

    # =========================================================================
    # Section 5: Optimization Parameters
    # =========================================================================

    st.subheader("💡 Optimization Configuration")

    st.markdown(
        "Configure cost optimization engine behavior. These affect which "
        "recommendations are generated."
    )

    col1, col2 = st.columns(2)

    with col1:
        budget_cap = st.number_input(
            "Monthly Budget Cap ($)",
            min_value=0.0,
            max_value=100000.0,
            value=config.DEFAULT_BUDGET_CAP,
            step=100.0,
            help="Maximum monthly spend threshold for recommendations",
            disabled=True,
        )

        risk_tolerance = st.selectbox(
            "Risk Tolerance",
            options=["Conservative", "Moderate", "Aggressive"],
            index=1,
            help=(
                "Conservative: Only safe changes (Reserved Instances)\n"
                "Moderate: Some risk (right-sizing)\n"
                "Aggressive: All savings (Spot instances, deletions)"
            ),
            disabled=True,
        )

    with col2:
        min_savings = st.number_input(
            "Minimum Recommendation Savings ($/month)",
            min_value=0.0,
            max_value=1000.0,
            value=5.0,
            step=5.0,
            help="Don't show recommendations below this threshold",
            disabled=True,
        )

        spot_instances = st.checkbox(
            "Allow Spot Instance Recommendations",
            value=config.SPOT_RELIABILITY,
            help="Include potentially volatile Spot instances in recommendations",
            disabled=True,
        )

    st.caption(
        "💡 **Note:** Parameter customization will be enabled in a future update. "
        "Currently showing system defaults."
    )

    st.markdown("---")

    # =========================================================================
    # Section 6: Model Selection
    # =========================================================================

    st.subheader("🤖 ML Model Configuration")

    st.markdown("Default forecasting models for automated runs")

    col1, col2 = st.columns(2)

    with col1:
        default_model = st.selectbox(
            "Default Forecasting Model",
            options=["Prophet", "SARIMAX", "ETS", "Seasonal Naive", "Naive"],
            index=0,
            help="Model used for automated forecasting jobs",
            disabled=True,
        )

    with col2:
        enable_ensemble = st.checkbox(
            "Enable Ensemble Forecasting",
            value=False,
            help="Combine multiple models for improved accuracy (slower)",
            disabled=True,
        )

    st.caption(
        "💡 **Note:** You can always select different models manually on the Forecasts page."
    )

    st.markdown("---")

    # =========================================================================
    # Section 7: Notifications (Placeholder)
    # =========================================================================

    st.subheader("🔔 Notifications")

    st.markdown("Configure alerts for cost anomalies and recommendations")

    col1, col2 = st.columns(2)

    with col1:
        st.checkbox(
            "Email Notifications",
            value=False,
            help="Receive alerts via email",
            disabled=True,
        )

        st.text_input(
            "Email Address",
            value="",
            placeholder="your.email@example.com",
            disabled=True,
        )

    with col2:
        st.checkbox(
            "Slack Notifications",
            value=False,
            help="Send alerts to Slack channel",
            disabled=True,
        )

        st.text_input(
            "Slack Webhook URL",
            value="",
            placeholder="https://hooks.slack.com/...",
            disabled=True,
        )

    st.info("💡 **Coming Soon:** Email and Slack notifications for anomalies and recommendations")

    st.markdown("---")

    # =========================================================================
    # Section 8: Advanced
    # =========================================================================

    with st.expander("🔬 Advanced Settings"):
        st.markdown("**Data Collection:**")

        col1, col2 = st.columns(2)

        with col1:
            st.number_input(
                "Collection Interval (hours)",
                min_value=1,
                max_value=168,
                value=24,
                help="How often to collect new data from AWS",
                disabled=True,
            )

        with col2:
            st.number_input(
                "Retention Period (days)",
                min_value=30,
                max_value=730,
                value=365,
                help="How long to keep historical data",
                disabled=True,
            )

        st.markdown("**API Settings:**")

        col1, col2 = st.columns(2)

        with col1:
            st.number_input(
                "API Timeout (seconds)",
                min_value=10,
                max_value=300,
                value=config.API_TIMEOUT,
                disabled=True,
            )

        with col2:
            st.number_input(
                "Max API Retries",
                min_value=1,
                max_value=10,
                value=config.MAX_RETRIES,
                disabled=True,
            )

        st.markdown("**Logging:**")

        log_level = st.selectbox(
            "Log Level",
            options=["DEBUG", "INFO", "WARNING", "ERROR"],
            index=1,
            disabled=True,
        )

        st.caption("⚠️ Advanced settings should only be modified by system administrators")

    # =========================================================================
    # Footer Actions
    # =========================================================================

    st.markdown("---")

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        if st.button("💾 Save Settings", use_container_width=True):
            st.info("💡 Settings persistence coming soon!")

    with col2:
        if st.button("↩️ Reset to Defaults", use_container_width=True):
            st.info("💡 Reset functionality coming soon!")

    with col3:
        if st.button("📥 Export Config", use_container_width=True):
            st.info("💡 Config export coming soon!")

    with col4:
        if st.button("📤 Import Config", use_container_width=True):
            st.info("💡 Config import coming soon!")

    st.markdown("")
    st.caption(
        "💡 **Tip:** Most settings are read-only while the authentication system is "
        "being developed. You can override parameters on individual pages."
    )
