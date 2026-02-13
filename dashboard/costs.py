"""
dashboard/costs.py — Cost Analysis page for Smart Cloud Optimizer dashboard.

Displays detailed cost breakdown:
- Line chart: daily costs over time
- Bar chart: cost breakdown by service
- Stacked area chart: service costs over time
- Data table: daily costs with export option
- Date range selector
- Service filter
"""
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import components


def create_stacked_area_chart(
    user_id: str, start_date: datetime.date, end_date: datetime.date
) -> go.Figure:
    """Create stacked area chart showing service costs over time.

    Args:
        user_id: User identifier
        start_date: Start date for data
        end_date: End date for data

    Returns:
        Plotly Figure object
    """
    conn = components.get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT date, service, cost
        FROM service_costs
        WHERE user_id = ? AND date >= ? AND date <= ?
        ORDER BY date, service
        """,
        (user_id, start_date, end_date),
    )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        # Return empty chart
        fig = go.Figure()
        fig.add_annotation(
            text="No service cost data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": "gray"},
        )
        fig.update_layout(
            title="Cost by Service Over Time",
            height=500,
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return fig

    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=["date", "service", "cost"])

    # Pivot to get services as columns
    df_pivot = df.pivot_table(
        index="date", columns="service", values="cost", fill_value=0
    )

    # Create stacked area chart
    fig = go.Figure()

    for service in df_pivot.columns:
        fig.add_trace(
            go.Scatter(
                x=df_pivot.index,
                y=df_pivot[service],
                name=service,
                mode="lines",
                stackgroup="one",
                hovertemplate=f"<b>{service}</b><br>"
                + "Date: %{x}<br>"
                + "Cost: $%{y:.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Cost by Service Over Time",
        xaxis_title="",
        yaxis_title="Cost (USD)",
        height=500,
        hovermode="x unified",
        showlegend=True,
        legend={
            "orientation": "v",
            "yanchor": "top",
            "y": 1,
            "xanchor": "left",
            "x": 1.02,
        },
    )

    return fig


def render():
    """Render the Cost Analysis page."""
    # User selection
    user_id = components.select_user()

    # Page header
    st.header("💰 Cost Analysis")
    st.markdown(f"**Account:** `{user_id}`")
    st.markdown("---")

    # =========================================================================
    # Date Range Selector
    # =========================================================================

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        # Preset date ranges
        date_preset = st.selectbox(
            "Quick Select",
            [
                "Last 7 Days",
                "Last 30 Days",
                "Last 90 Days",
                "Last 6 Months",
                "Last Year",
                "All Time",
                "Custom",
            ],
            index=1,  # Default to Last 30 Days
        )

    # Calculate date range based on preset
    end_date = datetime.now().date()

    if date_preset == "Last 7 Days":
        start_date = end_date - timedelta(days=7)
    elif date_preset == "Last 30 Days":
        start_date = end_date - timedelta(days=30)
    elif date_preset == "Last 90 Days":
        start_date = end_date - timedelta(days=90)
    elif date_preset == "Last 6 Months":
        start_date = end_date - timedelta(days=180)
    elif date_preset == "Last Year":
        start_date = end_date - timedelta(days=365)
    elif date_preset == "All Time":
        start_date = end_date - timedelta(days=730)  # 2 years max
    else:  # Custom
        with col2:
            start_date = st.date_input(
                "Start Date",
                value=end_date - timedelta(days=30),
                max_value=end_date,
            )
        with col3:
            end_date = st.date_input(
                "End Date",
                value=end_date,
                max_value=end_date,
                min_value=start_date,
            )

    # Calculate number of days
    num_days = (end_date - start_date).days + 1

    st.markdown("---")

    # =========================================================================
    # Load Data
    # =========================================================================

    try:
        # Load cost data for date range
        conn = components.get_db_connection()
        df_daily = components.db.get_cost_data(conn, user_id, start_date, end_date)

        # Load service costs
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
        service_rows = cursor.fetchall()
        df_services = pd.DataFrame(
            service_rows, columns=["service", "total_cost"]
        ) if service_rows else pd.DataFrame()

        conn.close()

    except Exception as e:
        components.show_error(
            "Failed to load cost data",
            details=str(e),
        )
        st.stop()

    # Check if we have data
    if df_daily.empty:
        components.show_empty_state(
            f"No cost data available for {start_date} to {end_date}",
            instruction="Generate sample data by running:\n"
            "```bash\n"
            "python -m data_generation.synthetic --days 365\n"
            "```",
        )
        st.stop()

    # =========================================================================
    # Summary Metrics
    # =========================================================================

    total_cost = df_daily["total_cost"].sum()
    avg_daily = df_daily["total_cost"].mean()
    min_cost = df_daily["total_cost"].min()
    max_cost = df_daily["total_cost"].max()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Cost", components.format_currency(total_cost))

    with col2:
        st.metric(
            "Average Daily",
            components.format_currency(avg_daily),
        )

    with col3:
        st.metric("Min Daily", components.format_currency(min_cost))

    with col4:
        st.metric("Max Daily", components.format_currency(max_cost))

    st.markdown("---")

    # =========================================================================
    # Daily Cost Trend (Line Chart)
    # =========================================================================

    st.subheader(f"📈 Daily Cost Trend ({num_days} days)")

    fig_line = components.create_cost_line_chart(
        df_daily, title=f"Daily Costs ({start_date} to {end_date})"
    )
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("---")

    # =========================================================================
    # Service Cost Breakdown (Side by Side)
    # =========================================================================

    st.subheader("💸 Cost Breakdown by Service")

    col1, col2 = st.columns(2)

    with col1:
        # Bar chart
        if not df_services.empty:
            fig_bar = components.create_service_bar_chart(
                df_services, title="Total Cost by Service"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            components.show_empty_state("No service breakdown available")

    with col2:
        # Pie chart
        if not df_services.empty:
            fig_pie = px.pie(
                df_services.head(10),
                values="total_cost",
                names="service",
                title="Cost Distribution (Top 10 Services)",
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            components.show_empty_state("No service breakdown available")

    st.markdown("---")

    # =========================================================================
    # Stacked Area Chart (Service Costs Over Time)
    # =========================================================================

    st.subheader("📊 Service Costs Over Time")

    fig_stacked = create_stacked_area_chart(user_id, start_date, end_date)
    st.plotly_chart(fig_stacked, use_container_width=True)

    st.markdown("---")

    # =========================================================================
    # Detailed Service Cost Table
    # =========================================================================

    st.subheader("📋 Service Cost Details")

    if not df_services.empty:
        # Add percentage column
        df_table = df_services.copy()
        df_table["percentage"] = (df_table["total_cost"] / total_cost * 100).round(1)
        df_table["total_cost_formatted"] = df_table["total_cost"].apply(
            components.format_currency
        )
        df_table["percentage_formatted"] = df_table["percentage"].astype(str) + "%"

        # Display table
        st.dataframe(
            df_table[["service", "total_cost_formatted", "percentage_formatted"]],
            column_config={
                "service": "Service",
                "total_cost_formatted": "Total Cost",
                "percentage_formatted": "% of Total",
            },
            use_container_width=True,
            hide_index=True,
        )

        # Show summary
        st.caption(
            f"💡 Top service ({df_services.iloc[0]['service']}) accounts for "
            f"{df_table.iloc[0]['percentage']:.1f}% of total costs"
        )
    else:
        components.show_empty_state("No service cost details available")

    st.markdown("---")

    # =========================================================================
    # Daily Cost Table (with Export)
    # =========================================================================

    st.subheader("📅 Daily Cost Records")

    # Show/hide daily records
    show_records = st.checkbox("Show all daily records", value=False)

    if show_records:
        # Prepare table
        df_table = df_daily.copy()
        df_table["date"] = pd.to_datetime(df_table["date"]).dt.strftime("%Y-%m-%d")
        df_table["total_cost_formatted"] = df_table["total_cost"].apply(
            components.format_currency
        )

        st.dataframe(
            df_table[["date", "total_cost_formatted"]],
            column_config={
                "date": "Date",
                "total_cost_formatted": "Total Cost",
            },
            use_container_width=True,
            hide_index=True,
            height=400,
        )

    # =========================================================================
    # Export Options
    # =========================================================================

    st.markdown("---")
    st.subheader("📥 Export Data")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        # Export daily costs as CSV
        csv_daily = df_daily.to_csv(index=False)
        st.download_button(
            label="📄 Export Daily Costs (CSV)",
            data=csv_daily,
            file_name=f"daily_costs_{user_id}_{start_date}_to_{end_date}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col2:
        # Export service breakdown as CSV
        if not df_services.empty:
            csv_services = df_services.to_csv(index=False)
            st.download_button(
                label="📄 Export Service Costs (CSV)",
                data=csv_services,
                file_name=f"service_costs_{user_id}_{start_date}_to_{end_date}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # Footer
    st.markdown("")
    st.caption(
        f"💡 **Tip:** Showing {num_days} days of cost data. "
        "Adjust the date range to see different time periods."
    )
