"""Tests for date utilities in aws_collector.metrics"""
from datetime import datetime, timezone

from aws_collector.metrics import (
    get_last_n_months,
    get_month_key,
    get_date_range_for_cost,
    get_datetime_range,
    month_start_end,
)


class TestMonthStartEnd:
    def test_regular_month(self):
        start, end = month_start_end(2024, 3)
        assert start == "2024-03-01"
        assert end == "2024-03-31"

    def test_february_leap_year(self):
        start, end = month_start_end(2024, 2)
        assert end == "2024-02-29"

    def test_february_non_leap(self):
        start, end = month_start_end(2023, 2)
        assert end == "2023-02-28"

    def test_december(self):
        start, end = month_start_end(2024, 12)
        assert start == "2024-12-01"
        assert end == "2024-12-31"


class TestGetLastNMonths:
    def test_returns_correct_count(self):
        result = get_last_n_months(3)
        assert len(result) == 3

    def test_chronological_order(self):
        result = get_last_n_months(5)
        # Each start date should be before the next
        for i in range(len(result) - 1):
            assert result[i][0] < result[i + 1][0]

    def test_twelve_months_crosses_year(self):
        result = get_last_n_months(12)
        assert len(result) == 12
        # First and last should be ~11 months apart
        first_start = datetime.strptime(result[0][0], "%Y-%m-%d")
        last_start = datetime.strptime(result[-1][0], "%Y-%m-%d")
        diff_days = (last_start - first_start).days
        assert 300 < diff_days < 370

    def test_single_month(self):
        result = get_last_n_months(1)
        assert len(result) == 1
        start, end = result[0]
        assert start.endswith("-01")


class TestGetMonthKey:
    def test_extracts_year_month(self):
        assert get_month_key("2024-06-01") == "2024-06"
        assert get_month_key("2023-12-15") == "2023-12"


class TestGetDateRangeForCost:
    def test_end_date_exclusive(self):
        start, end = get_date_range_for_cost("2024-03-01", "2024-03-31")
        assert start == "2024-03-01"
        assert end == "2024-04-01"  # exclusive end

    def test_month_boundary(self):
        start, end = get_date_range_for_cost("2024-01-01", "2024-01-31")
        assert end == "2024-02-01"


class TestGetDatetimeRange:
    def test_returns_utc_datetimes(self):
        start, end = get_datetime_range("2024-03-01", "2024-03-31")
        assert start.tzinfo == timezone.utc
        assert end.tzinfo == timezone.utc

    def test_end_is_end_of_day(self):
        _, end = get_datetime_range("2024-03-01", "2024-03-31")
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59

    def test_start_is_start_of_day(self):
        start, _ = get_datetime_range("2024-03-01", "2024-03-31")
        assert start.hour == 0
        assert start.minute == 0
