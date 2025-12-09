"""
Date Utilities for Month-by-Month Data Collection
Handles splitting time ranges into monthly chunks for AWS API calls
"""
from datetime import datetime, timedelta
from typing import List, Tuple
from calendar import monthrange


def get_last_n_months(n: int = 5) -> List[Tuple[str, str]]:
    """
    Get the last N months as (start_date, end_date) tuples
    
    Args:
        n: Number of months to get (default: 5)
    
    Returns:
        List of tuples: [("2024-06-01", "2024-06-30"), ...]
    """
    today = datetime.now()
    months = []
    
    for i in range(n):
        # Calculate month (n months ago)
        target_month = today.month - i
        target_year = today.year
        
        # Handle year rollover
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        # Get start and end dates for this month
        start_date, end_date = month_start_end(target_year, target_month)
        months.append((start_date, end_date))
    
    # Reverse to get chronological order (oldest first)
    return list(reversed(months))


def month_start_end(year: int, month: int) -> Tuple[str, str]:
    """
    Get start and end dates for a specific month
    
    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)
    
    Returns:
        Tuple of (start_date, end_date) as ISO format strings
    """
    # First day of month
    start_date = datetime(year, month, 1)
    
    # Last day of month
    last_day = monthrange(year, month)[1]
    end_date = datetime(year, month, last_day)
    
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def list_month_ranges(n: int = 5) -> List[Tuple[str, str]]:
    """
    Alias for get_last_n_months - returns list of month ranges
    
    Args:
        n: Number of months
    
    Returns:
        List of (start_date, end_date) tuples
    """
    return get_last_n_months(n)


def get_month_key(start_date: str) -> str:
    """
    Extract month key from start date (e.g., "2024-06-01" -> "2024-06")
    
    Args:
        start_date: Start date string in YYYY-MM-DD format
    
    Returns:
        Month key in YYYY-MM format
    """
    return start_date[:7]  # Extract YYYY-MM


def get_date_range_for_cost(start_date: str, end_date: str) -> Tuple[str, str]:
    """
    Format dates for Cost Explorer API
    Cost Explorer uses dates in YYYY-MM-DD format
    
    Args:
        start_date: Start date string
        end_date: End date string
    
    Returns:
        Tuple of formatted dates
    """
    # Ensure dates are in correct format
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Cost Explorer end date is exclusive, so we add 1 day
    end_exclusive = (end + timedelta(days=1)).strftime("%Y-%m-%d")
    
    return start.strftime("%Y-%m-%d"), end_exclusive


def get_datetime_range(start_date: str, end_date: str) -> Tuple[datetime, datetime]:
    """
    Convert date strings to datetime objects for CloudWatch
    
    Args:
        start_date: Start date string
        end_date: End date string
    
    Returns:
        Tuple of datetime objects (with timezone)
    """
    from datetime import timezone
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Set to end of day for end_date
    end = end.replace(hour=23, minute=59, second=59)
    
    # Add timezone
    start = start.replace(tzinfo=timezone.utc)
    end = end.replace(tzinfo=timezone.utc)
    
    return start, end

