"""
dashboard/forecasts.py — Forecasts page for Smart Cloud Optimizer dashboard.

Displays ML cost predictions:
- Forecast visualization with confidence intervals
- Historical vs predicted costs
- Model comparison table
- Forecast horizon selector
- Accuracy metrics (if actual data available)
"""
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import components
from ml_engine import forecaster, data_prep


def render():
    """Render the Forecasts page."""
    # User selection
    user_id = components.select_user()

    # Page header
    st.header("📈 Cost Forecasts")
    st.markdown(f"**Account:** `{user_id}`")
    st.markdown("---")

    # =========================================================================
    # Forecast Configuration
    # =========================================================================

    col1, col2 = st.columns([2, 2])

    with col1:
        forecast_horizon = st.selectbox(
            "Forecast Horizon",
            [7, 14, 30, 60, 90],
            index=2,  # Default 30 days
            format_func=lambda x: f"{x} days",
        )

    with col2:
        model_choice = st.selectbox(
            "Model",
            [
                "Prophet",
                "SARIMAX",
                "ETS",
                "Seasonal Naive",
                "Naive",
            ],
            index=0,  # Default to Prophet
        )

    st.markdown("---")

    # =========================================================================
    # Load Historical Data
    # =========================================================================

    try:
        conn = components.get_db_connection()
        # Get up to 365 days of historical data, constrained to available range
        start_date, end_date = components.calculate_date_range(user_id, days=365)
        historical_costs = components.db.get_daily_costs(
            conn,
            user_id,
            start_date=start_date,
            end_date=end_date,
        )
        df_historical = pd.DataFrame(historical_costs)
        # Note: Don't close cached connection - cache manages lifecycle

    except Exception as e:
        components.show_error(
            "Failed to load historical cost data",
            details=str(e),
        )
        st.stop()

    # Check if we have enough data
    if df_historical.empty or len(df_historical) < 30:
        components.show_empty_state(
            "Insufficient historical data for forecasting",
            instruction=(
                f"Need at least 30 days of cost data. Currently have {len(df_historical)} days.\n\n"
                "Generate sample data by running:\n"
                "```bash\n"
                "python -m data_generation.synthetic --days 365\n"
                "```"
            ),
        )
        st.stop()

    # =========================================================================
    # Generate Forecast
    # =========================================================================

    st.info("🔮 Generating forecast... This may take a few seconds.")

    try:
        # Prepare data for ML model
        df_prepared = df_historical[["date", "total_cost"]].copy()
        df_prepared["date"] = pd.to_datetime(df_prepared["date"])
        df_prepared = df_prepared.sort_values("date")

        # Select model
        if model_choice == "Prophet":
            model = forecaster.ProphetForecaster()
        elif model_choice == "SARIMAX":
            model = forecaster.SARIMAXForecaster()
        elif model_choice == "ETS":
            model = forecaster.ETSForecaster()
        elif model_choice == "Seasonal Naive":
            model = forecaster.SeasonalNaiveForecaster(season_length=7)
        else:  # Naive
            model = forecaster.NaiveForecaster()

        # Train model
        with st.spinner(f"Training {model_choice} model..."):
            model.fit(df_prepared)

        # Generate predictions
        with st.spinner("Generating predictions..."):
            df_forecast = model.predict(horizon=forecast_horizon)

    except Exception as e:
        components.show_error(
            f"Failed to generate forecast with {model_choice} model",
            details=str(e),
        )
        st.stop()

    # Clear info message
    st.success(f"✅ Forecast generated using {model_choice} model")

    st.markdown("---")

    # =========================================================================
    # Forecast Summary Metrics
    # =========================================================================

    st.subheader(f"🔮 {forecast_horizon}-Day Forecast Summary")

    if not df_forecast.empty:
        # Calculate forecast metrics
        avg_predicted = df_forecast["forecast"].mean()
        total_predicted = df_forecast["forecast"].sum()
        min_predicted = df_forecast["forecast"].min()
        max_predicted = df_forecast["forecast"].max()

        # Compare to historical average
        historical_avg = df_historical["total_cost"].mean()
        predicted_vs_historical = (
            (avg_predicted - historical_avg) / historical_avg * 100
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Predicted Total",
                components.format_currency(total_predicted),
            )

        with col2:
            st.metric(
                "Avg Daily (Forecast)",
                components.format_currency(avg_predicted),
                delta=f"{predicted_vs_historical:+.1f}% vs historical",
                delta_color="inverse",
            )

        with col3:
            st.metric(
                "Min (Forecast)",
                components.format_currency(min_predicted),
            )

        with col4:
            st.metric(
                "Max (Forecast)",
                components.format_currency(max_predicted),
            )

    st.markdown("---")

    # =========================================================================
    # Forecast Visualization
    # =========================================================================

    st.subheader("📊 Forecast Visualization")

    if not df_forecast.empty:
        # Create figure
        fig = go.Figure()

        # Plot historical data (last 90 days for context)
        df_recent = df_historical.tail(90).copy()
        df_recent["date"] = pd.to_datetime(df_recent["date"])

        fig.add_trace(
            go.Scatter(
                x=df_recent["date"],
                y=df_recent["total_cost"],
                name="Historical",
                mode="lines",
                line={"color": "#1f77b4", "width": 2},
                hovertemplate="<b>Historical</b><br>"
                + "Date: %{x}<br>"
                + "Cost: $%{y:.2f}<extra></extra>",
            )
        )

        # Plot forecast
        fig.add_trace(
            go.Scatter(
                x=df_forecast["date"],
                y=df_forecast["forecast"],
                name="Forecast",
                mode="lines",
                line={"color": "#ff7f0e", "width": 2, "dash": "dash"},
                hovertemplate="<b>Forecast</b><br>"
                + "Date: %{x}<br>"
                + "Cost: $%{y:.2f}<extra></extra>",
            )
        )

        # Add confidence intervals if available
        if "lower" in df_forecast.columns and "upper" in df_forecast.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_forecast["date"],
                    y=df_forecast["upper"],
                    mode="lines",
                    line={"width": 0},
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=df_forecast["date"],
                    y=df_forecast["lower"],
                    mode="lines",
                    fill="tonexty",
                    fillcolor="rgba(255, 127, 14, 0.2)",
                    line={"width": 0},
                    name="Confidence Interval (80%)",
                    hovertemplate="<b>Confidence Interval</b><br>"
                    + "Date: %{x}<br>"
                    + "Upper: $%{y:.2f}<extra></extra>",
                )
            )

        # Update layout
        fig.update_layout(
            title=f"{model_choice} Forecast ({forecast_horizon} days)",
            xaxis_title="Date",
            yaxis_title="Cost (USD)",
            height=500,
            hovermode="x unified",
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # =========================================================================
    # Forecast Data Table
    # =========================================================================

    st.subheader("📅 Forecast Details")

    if not df_forecast.empty:
        # Prepare table
        df_table = df_forecast.copy()
        df_table["date"] = pd.to_datetime(df_table["date"]).dt.strftime("%Y-%m-%d")
        df_table["forecast_formatted"] = df_table["forecast"].apply(
            components.format_currency
        )

        # Add confidence intervals if available
        if "lower" in df_table.columns and "upper" in df_table.columns:
            df_table["range"] = df_table.apply(
                lambda row: f"{components.format_currency(row['lower'])} - "
                f"{components.format_currency(row['upper'])}",
                axis=1,
            )
            display_cols = ["date", "forecast_formatted", "range"]
            col_config = {
                "date": "Date",
                "forecast_formatted": "Predicted Cost",
                "range": "80% Confidence Range",
            }
        else:
            display_cols = ["date", "forecast_formatted"]
            col_config = {
                "date": "Date",
                "forecast_formatted": "Predicted Cost",
            }

        st.dataframe(
            df_table[display_cols],
            column_config=col_config,
            use_container_width=True,
            hide_index=True,
            height=400,
        )

    st.markdown("---")

    # =========================================================================
    # Model Comparison (if user wants to see)
    # =========================================================================

    st.subheader("🔬 Model Comparison")

    if st.checkbox("Run all models and compare performance", value=False):
        st.info("🔄 Running all 5 forecasting models... This will take 30-60 seconds.")

        try:
            # Run all models
            models = {
                "Prophet": forecaster.ProphetForecaster(),
                "SARIMAX": forecaster.SARIMAXForecaster(),
                "ETS": forecaster.ETSForecaster(),
                "Seasonal Naive": forecaster.SeasonalNaiveForecaster(season_length=7),
                "Naive": forecaster.NaiveForecaster(),
            }

            results = []

            for name, mdl in models.items():
                with st.spinner(f"Training {name}..."):
                    try:
                        mdl.fit(df_prepared)
                        pred = mdl.predict(horizon=forecast_horizon)

                        # Calculate simple metrics (predicted average)
                        avg_pred = pred["forecast"].mean()
                        total_pred = pred["forecast"].sum()

                        results.append(
                            {
                                "Model": name,
                                "Avg Daily Forecast": components.format_currency(
                                    avg_pred
                                ),
                                "Total Forecast": components.format_currency(
                                    total_pred
                                ),
                                "vs Historical": f"{((avg_pred - historical_avg) / historical_avg * 100):+.1f}%",
                            }
                        )
                    except Exception as e:
                        st.warning(f"⚠️ {name} failed: {str(e)}")

            if results:
                st.success("✅ Model comparison complete!")

                df_comparison = pd.DataFrame(results)
                st.dataframe(
                    df_comparison,
                    use_container_width=True,
                    hide_index=True,
                )

                st.caption(
                    "💡 **Note:** Comparison is based on predicted values only. "
                    "For actual accuracy, use historical backtesting (coming soon)."
                )

        except Exception as e:
            components.show_error(
                "Failed to run model comparison",
                details=str(e),
            )

    st.markdown("---")

    # =========================================================================
    # Export Forecast
    # =========================================================================

    st.subheader("📥 Export Forecast")

    if not df_forecast.empty:
        csv_forecast = df_forecast.to_csv(index=False)
        st.download_button(
            label="📄 Export Forecast (CSV)",
            data=csv_forecast,
            file_name=f"forecast_{user_id}_{model_choice}_{forecast_horizon}days.csv",
            mime="text/csv",
            use_container_width=False,
        )

    # Footer
    st.markdown("")
    st.caption(
        f"💡 **Tip:** {model_choice} model trained on {len(df_historical)} days "
        f"of historical data. Try different models to compare predictions!"
    )
