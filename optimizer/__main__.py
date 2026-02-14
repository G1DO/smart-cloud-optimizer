"""CLI entry point for optimizer module.

Usage:
    python -m optimizer --user-id USER_ID [options]
"""
import argparse
import sys
from pathlib import Path

from storage import db
from optimizer import optimize


def main():
    """Run cost optimizer and save recommendations."""
    parser = argparse.ArgumentParser(
        description="Run AWS cost optimization and generate recommendations"
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="User ID to optimize for (e.g., aws-SYNTHETIC-001)",
    )
    parser.add_argument(
        "--budget-cap",
        type=float,
        default=None,
        help="Monthly budget cap in USD (optional)",
    )
    parser.add_argument(
        "--services",
        nargs="+",
        default=None,
        help="Specific services to optimize (e.g., ec2 rds lambda)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to database (default: data/cloud_optimizer.db)",
    )

    args = parser.parse_args()

    # Create connection using storage helper (sets row_factory automatically)
    conn = db.get_connection(args.db_path)

    try:
        print(f"🔍 Running optimizer for user: {args.user_id}")

        # Call optimizer library
        recommendations = optimize(
            conn,
            args.user_id,
            budget_cap=args.budget_cap,
            services=args.services,
        )

        print(f"✅ Generated {len(recommendations)} recommendations")

        # Recommendations are already saved by optimize() via db.insert_recommendation()
        # Just report results
        total_savings = sum(r.get("monthly_savings", 0) for r in recommendations)
        print(f"💰 Total potential savings: ${total_savings:,.2f}/month")

        # Summary by priority
        priorities = {}
        for rec in recommendations:
            p = rec.get("priority", "unknown")
            priorities[p] = priorities.get(p, 0) + 1

        print("\n📊 Recommendations by priority:")
        for priority in ["high", "medium", "low"]:
            count = priorities.get(priority, 0)
            if count > 0:
                emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
                print(f"  {emoji} {priority.capitalize()}: {count}")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
