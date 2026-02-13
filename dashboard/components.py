"""
dashboard/components.py — Reusable UI components for Streamlit dashboard.

Provides:
- Metric cards for displaying key numbers
- Chart creation helpers (Plotly)
- Data formatters (currency, numbers, percentages)
- Data loaders with caching
- Error and loading states
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from storage import db


# ==============================================================================
# Data Formatters
# ==============================================================================


def format_currency(value: float) -> str:
    """Format value as currency (USD).

    Args:
        value: Numeric value to format

    Returns:
        Formatted string like "$1,847.23"
    """
    return f"${value:,.2f}"


def format_number(value: int | float) -> str:
    """Format value as number with thousands separator.

    Args:
        value: Numeric value to format

    Returns:
        Formatted string like "1,234"
    """
    return f"{value:,.0f}"


def format_percent(value: float) -> str:
    """Format value as percentage.

    Args:
        value: Decimal value (0.052 for 5.2%)

    Returns:
        Formatted string like "5.2%"
    """
    return f"{value * 100:.1f}%"


def format_date(value: datetime | str) -> str:
    """Format date in readable format.

    Args:
        value: Date as datetime or ISO string

    Returns:
        Formatted string like "Feb 13, 2026"
    """
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime("%b %d, %Y")


# ==============================================================================
# Data Loaders (with Streamlit caching)
# ==============================================================================


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_db_connection():
    """Get database connection.

    Returns:
        SQLite connection object

    Note:
        Cached to avoid reconnecting on every query.
        TTL = 5 minutes to allow data refresh.
    """
    return sqlite3.connect(str(config.DB_PATH))


@st.cache_data(ttl=300)
def load_users() -> list[dict]:
    """Load all users from database.

    Returns:
        List of user dicts: [{'user_id': 'SYNTHETIC-001', 'email': '...'}]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, email FROM users ORDER BY user_id")
    users = [{"user_id": row[0], "email": row[1]} for row in cursor.fetchall()]
    conn.close()
    return users


@st.cache_data(ttl=300)
def load_cost_summary(user_id: str, days: int = 30) -> dict:
    """Load cost summary for user.

    Args:
        user_id: User identifier
        days: Number of days to look back

    Returns:
        Dict with:
        - total: Total cost over period
        - daily: DataFrame with daily costs
        - change_pct: Percent change vs previous period
        - avg_daily: Average daily cost
    """
    conn = get_db_connection()
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # Get daily costs
    df = db.get_cost_data(conn, user_id, start_date, end_date)

    if df.empty:
        conn.close()
        return {
            "total": 0.0,
            "daily": pd.DataFrame(),
            "change_pct": 0.0,
            "avg_daily": 0.0,
        }

    # Calculate metrics
    total = df["total_cost"].sum()
    avg_daily = df["total_cost"].mean()

    # Calculate change vs previous period
    # Compare last 7 days to previous 7 days
    if len(df) >= 14:
        recent_7 = df.tail(7)["total_cost"].sum()
        previous_7 = df.iloc[-14:-7]["total_cost"].sum()
        change_pct = (
            (recent_7 - previous_7) / previous_7 if previous_7 > 0 else 0.0
        )
    else:
        change_pct = 0.0

    conn.close()
    return {
        "total": total,
        "daily": df,
        "change_pct": change_pct,
        "avg_daily": avg_daily,
    }


@st.cache_data(ttl=300)
def load_service_costs(user_id: str, days: int = 30) -> pd.DataFrame:
    """Load cost breakdown by service.

    Args:
        user_id: User identifier
        days: Number of days to look back

    Returns:
        DataFrame with columns: service, total_cost (sorted by cost desc)
    """
    conn = get_db_connection()
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT service, SUM(cost) as total_cost
        FROM service_costs
        WHERE user_id = ? AND date >= ? AND date <= ?
        GROUP BY service
        ORDER BY total_cost DESC
        """,
        (user_id, start_date, end_date),
    )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=["service", "total_cost"])

    return pd.DataFrame(rows, columns=["service", "total_cost"])


@st.cache_data(ttl=300)
def load_recommendations(
    user_id: str, limit: Optional[int] = None, min_savings: float = 0.0
) -> list[dict]:
    """Load cost optimization recommendations.

    Args:
        user_id: User identifier
        limit: Max number of recommendations to return (None = all)
        min_savings: Minimum monthly savings to include

    Returns:
        List of recommendation dicts sorted by savings (highest first)
    """
    conn = get_db_connection()
    recs = db.get_recommendations(conn, user_id, min_savings=min_savings)
    conn.close()

    if limit:
        recs = recs[:limit]

    return recs


@st.cache_data(ttl=300)
def load_anomalies(user_id: str, days: int = 30) -> list[dict]:
    """Load detected cost anomalies.

    Args:
        user_id: User identifier
        days: Number of days to look back

    Returns:
        List of anomaly dicts
    """
    conn = get_db_connection()
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    anomalies = db.get_anomalies(conn, user_id)
    conn.close()

    # Filter to date range
    filtered = [
        a
        for a in anomalies
        if start_date <= datetime.fromisoformat(a["date"]).date() <= end_date
    ]

    return filtered


# ==============================================================================
# Chart Helpers
# ==============================================================================


def create_cost_line_chart(df: pd.DataFrame, title: str = "Daily Costs") -> go.Figure:
    """Create line chart for daily costs.

    Args:
        df: DataFrame with 'date' and 'total_cost' columns
        title: Chart title

    Returns:
        Plotly Figure object
    """
    if df.empty:
        # Return empty chart with message
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": "gray"},
        )
        fig.update_layout(
            title=title,
            height=400,
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return fig

    fig = px.line(
        df,
        x="date",
        y="total_cost",
        title=title,
        labels={"date": "Date", "total_cost": "Cost (USD)"},
    )

    fig.update_traces(line_color="#1f77b4", line_width=2)
    fig.update_layout(
        height=400,
        hovermode="x unified",
        xaxis_title="",
        yaxis_title="Cost (USD)",
        showlegend=False,
    )

    return fig


def create_service_bar_chart(
    df: pd.DataFrame, title: str = "Cost by Service"
) -> go.Figure:
    """Create horizontal bar chart for service costs.

    Args:
        df: DataFrame with 'service' and 'total_cost' columns
        title: Chart title

    Returns:
        Plotly Figure object
    """
    if df.empty:
        # Return empty chart with message
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": "gray"},
        )
        fig.update_layout(
            title=title,
            height=400,
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return fig

    # Take top 10 services
    df_top = df.head(10).copy()

    fig = px.bar(
        df_top,
        x="total_cost",
        y="service",
        orientation="h",
        title=title,
        labels={"total_cost": "Cost (USD)", "service": "Service"},
    )

    fig.update_traces(marker_color="#1f77b4")
    fig.update_layout(
        height=400,
        xaxis_title="Cost (USD)",
        yaxis_title="",
        showlegend=False,
        yaxis={"categoryorder": "total ascending"},
    )

    return fig


# ==============================================================================
# UI State Helpers
# ==============================================================================


def show_loading(message: str = "Loading..."):
    """Display loading spinner with message.

    Args:
        message: Text to show while loading
    """
    with st.spinner(message):
        pass


def show_error(message: str, details: Optional[str] = None):
    """Display error message box.

    Args:
        message: Main error message
        details: Optional detailed error info (shown in expander)
    """
    st.error(f"❌ {message}")
    if details:
        with st.expander("Error Details"):
            st.code(details)


def show_empty_state(
    message: str = "No data available", instruction: Optional[str] = None
):
    """Display empty state placeholder.

    Args:
        message: Main message to display
        instruction: Optional instruction (e.g., how to generate data)
    """
    st.info(f"ℹ️ {message}")
    if instruction:
        st.markdown(f"**To get started:** {instruction}")


def display_metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: str = "normal",
):
    """Display metric card using st.metric.

    Args:
        label: Metric label/title
        value: Formatted value to display
        delta: Optional change indicator (e.g., "↑ 5.2%")
        delta_color: Color of delta ("normal", "inverse", "off")
    """
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


# ==============================================================================
# User Selection
# ==============================================================================


def select_user() -> str:
    """Display user selector and return selected user_id.

    Returns:
        Selected user_id string

    Note:
        Uses st.session_state to persist selection across page navigation.
    """
    users = load_users()

    if not users:
        show_error(
            "No users found in database",
            details=(
                "Run the following command to generate sample data:\n"
                "python -m data_generation.synthetic --days 365"
            ),
        )
        st.stop()

    # Initialize session state for user selection
    if "selected_user" not in st.session_state:
        st.session_state.selected_user = users[0]["user_id"]

    # User selector in sidebar
    user_options = {u["user_id"]: f"{u['user_id']} ({u['email']})" for u in users}

    selected = st.sidebar.selectbox(
        "Select User",
        options=list(user_options.keys()),
        format_func=lambda x: user_options[x],
        key="user_selector",
    )

    # Update session state
    st.session_state.selected_user = selected

    return selected
