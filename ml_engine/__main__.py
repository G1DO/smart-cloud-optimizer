"""CLI entry point for ml_engine module.

Usage:
    python -m ml_engine --user-id USER_ID [options]
"""
import argparse
import sys
from pathlib import Path

# TODO: Import forecaster when ready
# from storage import db
# from ml_engine import forecaster


def main():
    """Run ML cost forecasting (not yet implemented)."""
    parser = argparse.ArgumentParser(
        description="Run ML cost forecasting (placeholder)"
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="User ID to forecast for",
    )

    args = parser.parse_args()

    print("⚠️  ML Engine CLI not yet implemented")
    print(f"    User: {args.user_id}")
    print("    Use dashboard Forecasts page to run forecasts interactively")
    return 1


if __name__ == "__main__":
    sys.exit(main())
