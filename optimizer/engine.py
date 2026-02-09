"""Optimizer orchestrator — runs all analyzers and writes recommendations.

Single entry point that runs the LP solver for compute services and
rule-based checks for everything else, then writes results to the
recommendations table.

Part of the Smart Cloud Optimizer graduation project.
"""

import logging
import sqlite3

import config
import storage

from .compute_lp import optimize_ec2, optimize_rds
from .rules import (
    check_dynamodb_tables,
    check_ebs_volumes,
    check_ec2_pricing,
    check_elb_idle,
    check_lambda_memory,
    check_nat_gateways,
    check_rds_pricing,
    check_s3_buckets,
)

logger = logging.getLogger(__name__)

ALL_SERVICES = {"ec2", "rds", "lambda", "s3", "ebs", "dynamodb", "nat_gateway", "elb"}


def optimize(
    conn: sqlite3.Connection,
    user_id: str,
    budget_cap: float | None = None,
    services: list[str] | None = None,
) -> list[dict]:
    """Run all optimization analyzers and store results.

    Clears previous recommendations for this user, runs the LP solver
    for compute services and rule checks for all other services, then
    inserts all recommendations into the DB.

    Args:
        conn: Open database connection.
        user_id: User to optimize.
        budget_cap: Optional total compute budget (passed to LP solver).
            Defaults to config.DEFAULT_BUDGET_CAP.
        services: Optional list of services to optimize. If None, runs all.

    Returns:
        List of all recommendation dicts that were inserted.
    """
    if budget_cap is None:
        budget_cap = config.DEFAULT_BUDGET_CAP

    run = set(services) if services else ALL_SERVICES

    # Clear old recommendations
    conn.execute("DELETE FROM recommendations WHERE user_id = ?", (user_id,))

    recommendations: list[dict] = []

    # LP solver: compute right-sizing
    if "ec2" in run:
        recommendations.extend(optimize_ec2(conn, user_id, budget_cap=budget_cap))
    if "rds" in run:
        recommendations.extend(optimize_rds(conn, user_id, budget_cap=budget_cap))

    # Rule engine: pricing switches
    if "ec2" in run:
        recommendations.extend(check_ec2_pricing(conn, user_id))
    if "rds" in run:
        recommendations.extend(check_rds_pricing(conn, user_id))

    # Rule engine: non-compute
    if "lambda" in run:
        recommendations.extend(check_lambda_memory(conn, user_id))
    if "ebs" in run:
        recommendations.extend(check_ebs_volumes(conn, user_id))
    if "s3" in run:
        recommendations.extend(check_s3_buckets(conn, user_id))
    if "dynamodb" in run:
        recommendations.extend(check_dynamodb_tables(conn, user_id))
    if "nat_gateway" in run:
        recommendations.extend(check_nat_gateways(conn, user_id))
    if "elb" in run:
        recommendations.extend(check_elb_idle(conn, user_id))

    # Deduplicate: one recommendation per (resource_id, recommendation_type)
    # Keep the one with highest savings
    seen: dict[tuple, dict] = {}
    for rec in recommendations:
        key = (rec["resource_id"], rec["recommendation_type"])
        if key not in seen or rec["monthly_savings"] > seen[key]["monthly_savings"]:
            seen[key] = rec
    unique_recs = list(seen.values())

    # Write to DB
    if unique_recs:
        storage.insert_recommendations(conn, user_id, unique_recs)
    conn.commit()

    total_savings = sum(r["monthly_savings"] for r in unique_recs)
    logger.info(
        "optimizer: %d recommendations for %s (est. savings: $%.2f/mo)",
        len(unique_recs), user_id, total_savings,
    )

    return unique_recs
