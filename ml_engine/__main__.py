"""CLI entry point for ml_engine module.

Usage:
    python -m ml_engine --user-id USER_ID [options]
"""
import argparse
import sys
from pathlib import Path

from storage import db
from ml_engine.data_prep import load_cost_data
from ml_engine.forecaster import ETSForecaster, NaiveForecaster, SeasonalNaiveForecaster


def main():
    """Run ML cost forecasting and print a short summary."""
    parser = argparse.ArgumentParser(
        description="Run ML cost forecasting from stored daily costs"
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="User ID to forecast for",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=30,
        help="Forecast horizon in days (default: 30)",
    )
    parser.add_argument(
        "--model",
        choices=["naive", "seasonal", "ets"],
        default="naive",
        help="Forecaster to use (default: naive)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to database (default: data/cloud_optimizer.db)",
    )

    args = parser.parse_args()

    conn = db.get_connection(args.db_path)
    try:
        df = load_cost_data(conn, args.user_id)
        if df.empty:
            print(f"No daily cost data for user: {args.user_id}", file=sys.stderr)
            print("Sync a connection first, then re-run the forecast.")
            return 1

        if args.model == "seasonal":
            forecaster = SeasonalNaiveForecaster()
        elif args.model == "ets":
            forecaster = ETSForecaster()
        else:
            forecaster = NaiveForecaster()

        forecaster.fit(df)
        preds = forecaster.predict(horizon=args.horizon)

        total = float(preds["forecast"].sum())
        print(f"Forecast for user: {args.user_id}")
        print(f"  Model: {forecaster.name}")
        print(f"  Horizon: {args.horizon} days")
        print(f"  Total forecasted cost: ${total:,.2f}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
