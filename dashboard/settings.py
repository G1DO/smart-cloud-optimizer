"""
dashboard/settings.py — Settings page for Smart Cloud Optimizer dashboard.

Displays and manages:
- User profile information (editable)
- AWS account connections (add / remove / test)
- Forecast and optimization parameters
- Demo mode indicator
- Data refresh controls
"""
import streamlit as st

import config
from dashboard import components
from storage.db import (
    add_aws_connection,
    delete_aws_connection,
    get_aws_connections,
    get_user_by_id,
    update_user_profile,
)


def render():
    """Render the Settings page."""
    # Settings works even without a selected AWS account (that's how you add one)
    user_id = st.session_state.get("selected_user", "")

    # Page header
    st.header("⚙️ Settings")
    if user_id:
        st.markdown(f"**Account:** `{user_id}`")
    st.markdown("---")

    # =========================================================================
    # Section 1: User Profile
    # =========================================================================

    st.subheader("👤 User Profile")

    is_demo = st.session_state.get("demo_mode", False)
    auth_uid = st.session_state.get("auth_user_id", "")
    conn = components.get_db_connection()

    if is_demo:
        st.text_input("User", value="Demo Mode (Synthetic Data)", disabled=True)
    else:
        profile = get_user_by_id(conn, auth_uid)
        if profile:
            st.text_input("Email", value=profile["email"], disabled=True)
            with st.form("profile_form"):
                new_name = st.text_input(
                    "Display Name", value=profile["profile_name"],
                )
                if st.form_submit_button("Save Profile"):
                    if new_name and new_name != profile["profile_name"]:
                        update_user_profile(conn, auth_uid, new_name)
                        st.session_state.user_profile_name = new_name
                        st.success("Profile updated.")
                    else:
                        st.info("No changes to save.")
        else:
            components.show_error("User not found in database")

    st.markdown("---")

    # =========================================================================
    # Section 2: AWS Account Connections
    # =========================================================================

    st.subheader("☁️ AWS Account Connections")

    if is_demo:
        st.info("📊 **Demo Mode** — Using synthetic data. "
                "Register an account to connect real AWS accounts.")
        st.code(f"Data User ID: {user_id}\nSource: Synthetic Generator\nCoverage: 365 days")
    else:
        # -- Add new connection form --
        with st.expander("Add AWS Account", expanded=False):
            with st.form("add_aws_form"):
                acol1, acol2 = st.columns(2)
                with acol1:
                    conn_name = st.text_input("Connection Name", placeholder="Production")
                    acct_id = st.text_input("AWS Account ID", placeholder="123456789012")
                with acol2:
                    role_arn = st.text_input(
                        "IAM Role ARN",
                        placeholder="arn:aws:iam::123456789012:role/CloudOptimizer",
                    )
                    ext_id = st.text_input("External ID (optional)")

                region = st.selectbox(
                    "Primary Region",
                    ["us-east-1", "us-east-2", "us-west-1", "us-west-2",
                     "eu-west-1", "eu-west-2", "eu-central-1",
                     "ap-southeast-1", "ap-northeast-1"],
                    index=0,
                )

                col_test, col_add = st.columns(2)
                with col_test:
                    test_btn = st.form_submit_button("Test Connection")
                with col_add:
                    add_btn = st.form_submit_button("Add Account")

            if test_btn:
                if not acct_id or not role_arn:
                    st.error("Account ID and Role ARN are required.")
                else:
                    try:
                        import boto3
                        sts = boto3.client("sts")
                        params = {"RoleArn": role_arn, "RoleSessionName": "cloud-optimizer-test"}
                        if ext_id:
                            params["ExternalId"] = ext_id
                        sts.assume_role(**params)
                        st.success(f"Connection to {acct_id} succeeded.")
                    except Exception as exc:
                        st.error(f"Connection test failed: {exc}")

            if add_btn:
                if not acct_id or not role_arn:
                    st.error("Account ID and Role ARN are required.")
                else:
                    try:
                        add_aws_connection(
                            conn, auth_uid, acct_id, role_arn,
                            connection_name=conn_name,
                            external_id=ext_id,
                            aws_region=region,
                        )
                        st.success(f"Added AWS account {acct_id}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to add account: {exc}")

        # -- List existing connections --
        connections = get_aws_connections(conn, auth_uid)

        if connections:
            st.markdown(f"**{len(connections)} connected account(s):**")
            for c in connections:
                with st.container():
                    cc1, cc2, cc3 = st.columns([3, 2, 1])
                    with cc1:
                        st.markdown(
                            f"**{c.get('connection_name', c['aws_account_id'])}**  \n"
                            f"`{c['aws_account_id']}` — {c['aws_region']}"
                        )
                    with cc2:
                        status_emoji = {"never": "⚪", "success": "🟢",
                                        "failed": "🔴", "in_progress": "🟡"
                                        }.get(c["sync_status"], "⚪")
                        st.markdown(f"Sync: {status_emoji} {c['sync_status']}")
                    with cc3:
                        if st.button("Remove", key=f"del_{c['id']}"):
                            delete_aws_connection(conn, c["id"], auth_uid)
                            st.rerun()
                    st.markdown("---")
        else:
            st.info("No AWS accounts connected yet. Use the form above to add one.")

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
