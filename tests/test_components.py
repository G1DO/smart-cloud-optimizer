"""Tests for dashboard/components.py — formatters, date helpers, chart builders."""
from datetime import datetime, date, timedelta
from unittest import mock

import pandas as pd
import plotly.graph_objects as go

from dashboard.components import (
    format_currency,
    format_number,
    format_percent,
    format_date,
    create_cost_line_chart,
    create_service_bar_chart,
)


# ======================================================================
# Data Formatters
# ======================================================================


class TestFormatCurrency:
    def test_basic(self):
        assert format_currency(1234.56) == "$1,234.56"

    def test_zero(self):
        assert format_currency(0) == "$0.00"

    def test_large_number(self):
        assert format_currency(1_000_000) == "$1,000,000.00"

    def test_small_decimal(self):
        assert format_currency(0.5) == "$0.50"

    def test_negative(self):
        assert format_currency(-99.99) == "$-99.99"


class TestFormatNumber:
    def test_integer(self):
        assert format_number(1234) == "1,234"

    def test_float_truncated(self):
        assert format_number(1234.7) == "1,235"

    def test_zero(self):
        assert format_number(0) == "0"

    def test_large_number(self):
        assert format_number(1_000_000) == "1,000,000"


class TestFormatPercent:
    def test_basic(self):
        assert format_percent(0.052) == "5.2%"

    def test_zero(self):
        assert format_percent(0.0) == "0.0%"

    def test_hundred_percent(self):
        assert format_percent(1.0) == "100.0%"

    def test_small_percent(self):
        assert format_percent(0.001) == "0.1%"

    def test_over_hundred(self):
        assert format_percent(1.5) == "150.0%"


class TestFormatDate:
    def test_datetime_object(self):
        dt = datetime(2026, 2, 13)
        assert format_date(dt) == "Feb 13, 2026"

    def test_iso_string(self):
        assert format_date("2026-02-13") == "Feb 13, 2026"

    def test_iso_string_with_time(self):
        assert format_date("2026-02-13T10:30:00") == "Feb 13, 2026"

    def test_january(self):
        assert format_date(datetime(2024, 1, 1)) == "Jan 01, 2024"

    def test_december(self):
        assert format_date(datetime(2024, 12, 31)) == "Dec 31, 2024"


# ======================================================================
# Chart Helpers
# ======================================================================


class TestCreateCostLineChart:
    def test_empty_dataframe(self):
        fig = create_cost_line_chart(pd.DataFrame())
        assert isinstance(fig, go.Figure)
        # Should have "No data available" annotation
        assert len(fig.layout.annotations) == 1
        assert "No data" in fig.layout.annotations[0].text

    def test_with_data(self):
        df = pd.DataFrame({
            "date": ["2024-03-01", "2024-03-02", "2024-03-03"],
            "total_cost": [100.0, 150.0, 120.0],
        })
        fig = create_cost_line_chart(df, title="Test Chart")
        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "Test Chart"
        assert fig.layout.height == 400

    def test_custom_title(self):
        df = pd.DataFrame({"date": ["2024-03-01"], "total_cost": [100.0]})
        fig = create_cost_line_chart(df, title="My Costs")
        assert fig.layout.title.text == "My Costs"


class TestCreateServiceBarChart:
    def test_empty_dataframe(self):
        fig = create_service_bar_chart(pd.DataFrame())
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) == 1
        assert "No data" in fig.layout.annotations[0].text

    def test_with_data(self):
        df = pd.DataFrame({
            "service": ["EC2", "S3", "RDS"],
            "total_cost": [500.0, 200.0, 300.0],
        })
        fig = create_service_bar_chart(df, title="Service Costs")
        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "Service Costs"

    def test_top_10_limit(self):
        df = pd.DataFrame({
            "service": [f"Service-{i}" for i in range(15)],
            "total_cost": [float(i) for i in range(15)],
        })
        fig = create_service_bar_chart(df)
        # Should only use top 10 rows
        assert isinstance(fig, go.Figure)
