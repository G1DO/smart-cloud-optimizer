"""
Compatibility helper for backend_api.

This file does NOT create or modify the database.
It simply re-exports the storage helpers from db.py
so the rest of the backend can import from one place.
"""

try:
    from storage.db import get_connection, get_daily_costs
except ImportError:
    from db import get_connection, get_daily_costs

__all__ = ["get_connection", "get_daily_costs"]
