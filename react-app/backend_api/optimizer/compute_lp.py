"""Compute right-sizing via linear programming.

Uses PuLP to find the cheapest instance type assignment for EC2 and RDS
instances that still meets CPU and memory requirements derived from
historical metrics (P95 with configurable headroom).

Part of the Smart Cloud Optimizer graduation project.
"""

import logging
import sqlite3
from typing import Optional

import numpy as np
import pandas as pd

import storage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal LP solver
# ---------------------------------------------------------------------------

def _solve_compute_lp(
    instances: list[dict],
    requirements: list[dict],
    candidates: list[dict],
    budget_cap: float | None = None,
) -> dict[str, str]:
    """Solve binary LP: assign each instance to the cheapest candidate type.

    Args:
        instances: Dicts with 'resource_id', 'current_type'.
        requirements: Dicts with 'resource_id', 'min_vcpus', 'min_memory_gb'.
            min_memory_gb may be None (skips memory constraint for that instance).
        candidates: Dicts from instance_pricing with 'instance_type', 'vcpus',
            'memory_gb', 'on_demand_monthly'.
        budget_cap: Optional total monthly budget constraint.

    Returns:
        Dict mapping resource_id -> chosen instance_type.
        Empty dict if LP is infeasible or no instances provided.
    """
    import pulp

    if not instances or not candidates:
        return {}

    # Filter candidates with valid pricing and specs
    valid_candidates = [
        c for c in candidates
        if c.get("on_demand_monthly") and c["on_demand_monthly"] > 0
        and c.get("vcpus") is not None
    ]
    if not valid_candidates:
        logger.warning("No valid candidates with pricing + specs")
        return {}

    req_map = {r["resource_id"]: r for r in requirements}

    prob = pulp.LpProblem("compute_rightsize", pulp.LpMinimize)

    # Decision variables: x[instance_id, candidate_type] = binary
    x = {}
    for inst in instances:
        rid = inst["resource_id"]
        for cand in valid_candidates:
            ctype = cand["instance_type"]
            x[rid, ctype] = pulp.LpVariable(
                f"x_{rid}_{ctype}", cat=pulp.LpBinary,
            )

    # Objective: minimize total monthly cost
    prob += pulp.lpSum(
        cand["on_demand_monthly"] * x[inst["resource_id"], cand["instance_type"]]
        for inst in instances
        for cand in valid_candidates
    )

    # Constraint 1: each instance assigned exactly one type
    for inst in instances:
        rid = inst["resource_id"]
        prob += pulp.lpSum(
            x[rid, cand["instance_type"]] for cand in valid_candidates
        ) == 1

    # Constraint 2: CPU capacity
    for inst in instances:
        rid = inst["resource_id"]
        req = req_map.get(rid)
        if req and req["min_vcpus"] is not None and req["min_vcpus"] > 0:
            prob += pulp.lpSum(
                (cand.get("vcpus") or 0) * x[rid, cand["instance_type"]]
                for cand in valid_candidates
            ) >= req["min_vcpus"]

    # Constraint 3: memory capacity (skip if min_memory_gb is None)
    for inst in instances:
        rid = inst["resource_id"]
        req = req_map.get(rid)
        if req and req.get("min_memory_gb") is not None and req["min_memory_gb"] > 0:
            prob += pulp.lpSum(
                (cand.get("memory_gb") or 0) * x[rid, cand["instance_type"]]
                for cand in valid_candidates
                if cand.get("memory_gb") is not None
            ) >= req["min_memory_gb"]

    # Constraint 4: budget cap
    if budget_cap is not None:
        prob += pulp.lpSum(
            cand["on_demand_monthly"] * x[inst["resource_id"], cand["instance_type"]]
            for inst in instances
            for cand in valid_candidates
        ) <= budget_cap

    # Solve (suppress CBC output)
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if prob.status != pulp.constants.LpStatusOptimal:
        logger.warning("LP infeasible or unbounded (status=%d)", prob.status)
        return {}

    # Extract assignments
    result = {}
    for inst in instances:
        rid = inst["resource_id"]
        for cand in valid_candidates:
            ctype = cand["instance_type"]
            if x[rid, ctype].varValue and x[rid, ctype].varValue > 0.5:
                result[rid] = ctype
                break

    return result


# ---------------------------------------------------------------------------
# EC2 right-sizing
# ---------------------------------------------------------------------------

def optimize_ec2(
    conn: sqlite3.Connection,
    user_id: str,
    headroom: float = 1.3,
    budget_cap: float | None = None,
) -> list[dict]:
    """Find cheapest EC2 instance types meeting CPU/memory constraints via LP.

    Loads EC2 inventory and metrics, computes P95 resource requirements,
    solves a binary LP to find the cheapest assignment from the pricing
    catalog. Only generates recommendations where the optimal type differs
    from the current type AND saves money.

    Args:
        conn: Open database connection.
        user_id: User to optimize.
        headroom: Multiplier on P95 requirements (1.3 = 30% headroom).
        budget_cap: Optional total monthly budget for all EC2 instances.

    Returns:
        List of recommendation dicts ready for insert_recommendations().
    """
    ec2_instances = storage.get_ec2_instances(conn, user_id)
    if not ec2_instances:
        return []

    candidates = storage.get_instance_pricing(conn, service="EC2")
    if not candidates:
        logger.warning("No EC2 pricing data available")
        return []

    # Build instances list and requirements from metrics
    instances = []
    requirements = []
    instance_lookup = {}

    for inst in ec2_instances:
        if inst.get("state") != "running":
            continue

        iid = inst["instance_id"]
        itype = inst["instance_type"]

        metrics = storage.get_ec2_metrics(conn, user_id, instance_id=iid)
        if not metrics:
            continue

        df = pd.DataFrame(metrics)
        p95_cpu = float(np.percentile(df["cpu_utilization"].dropna(), 95))
        current_vcpus = inst.get("vcpus") or 2
        current_memory = inst.get("memory_gb") or 8.0

        min_vcpus = (p95_cpu / 100.0) * current_vcpus * headroom
        min_memory = None
        if "memory_utilization" in df.columns and df["memory_utilization"].notna().any():
            p95_mem = float(np.percentile(df["memory_utilization"].dropna(), 95))
            min_memory = (p95_mem / 100.0) * current_memory * headroom

        instances.append({"resource_id": iid, "current_type": itype})
        requirements.append({
            "resource_id": iid,
            "min_vcpus": min_vcpus,
            "min_memory_gb": min_memory,
        })
        instance_lookup[iid] = inst

    if not instances:
        return []

    # Solve LP
    assignments = _solve_compute_lp(instances, requirements, candidates, budget_cap)

    # Build recommendations (only where type changed AND saves money)
    pricing_map = {c["instance_type"]: c for c in candidates}
    recommendations = []

    for inst_dict in instances:
        iid = inst_dict["resource_id"]
        current_type = inst_dict["current_type"]
        new_type = assignments.get(iid)

        if not new_type or new_type == current_type:
            continue

        inv = instance_lookup[iid]
        current_cost = inv.get("monthly_cost") or 0
        new_pricing = pricing_map.get(new_type, {})
        new_cost = new_pricing.get("on_demand_monthly") or 0

        if new_cost >= current_cost:
            continue

        savings = round(current_cost - new_cost, 2)
        pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0

        # Build reasoning from requirements
        req = next((r for r in requirements if r["resource_id"] == iid), {})
        reasoning = (
            f"P95 CPU requires {req.get('min_vcpus', 0):.1f} vCPUs "
            f"(with {headroom:.0%} headroom). "
        )
        if req.get("min_memory_gb") is not None:
            reasoning += f"P95 memory requires {req['min_memory_gb']:.1f} GB. "
        new_specs = pricing_map.get(new_type, {})
        reasoning += (
            f"{new_type} ({new_specs.get('vcpus', '?')} vCPUs, "
            f"{new_specs.get('memory_gb', '?')} GB) meets requirements "
            f"at {pct}% lower cost."
        )

        recommendations.append({
            "service": "EC2",
            "resource_id": iid,
            "recommendation_type": "rightsize",
            "current_config": f"{current_type}, {inv.get('pricing_model', 'on-demand')}",
            "recommended_config": f"{new_type}, {inv.get('pricing_model', 'on-demand')}",
            "current_monthly_cost": current_cost,
            "estimated_monthly_cost": new_cost,
            "monthly_savings": savings,
            "savings_percent": pct,
            "confidence": "high" if pct > 20 else "medium",
            "reasoning": reasoning,
        })

    return recommendations


# ---------------------------------------------------------------------------
# RDS right-sizing
# ---------------------------------------------------------------------------

def optimize_rds(
    conn: sqlite3.Connection,
    user_id: str,
    headroom: float = 1.3,
    budget_cap: float | None = None,
) -> list[dict]:
    """Find cheapest RDS instance classes meeting CPU constraints via LP.

    Same LP structure as optimize_ec2 but uses RDS pricing catalog.
    Memory constraint is skipped because RDS memory_utilization in the DB
    stores raw FreeableMemory bytes from CloudWatch, not a percentage.

    Args:
        conn: Open database connection.
        user_id: User to optimize.
        headroom: Multiplier on P95 CPU requirement.
        budget_cap: Optional total monthly budget for all RDS instances.

    Returns:
        List of recommendation dicts ready for insert_recommendations().
    """
    rds_instances = storage.get_rds_instances(conn, user_id)
    if not rds_instances:
        return []

    candidates = storage.get_instance_pricing(conn, service="RDS")
    if not candidates:
        logger.warning("No RDS pricing data available")
        return []

    instances = []
    requirements = []
    instance_lookup = {}

    for inst in rds_instances:
        dbid = inst["db_instance_id"]
        db_class = inst.get("db_instance_class", "")

        metrics = storage.get_rds_metrics(conn, user_id, db_instance_id=dbid)
        if not metrics:
            continue

        df = pd.DataFrame(metrics)
        if "cpu_utilization" not in df.columns or df["cpu_utilization"].dropna().empty:
            continue

        p95_cpu = float(np.percentile(df["cpu_utilization"].dropna(), 95))
        # RDS doesn't expose vCPU count in inventory; estimate from pricing
        current_pricing = next(
            (c for c in candidates if c["instance_type"] == db_class), None
        )
        current_vcpus = (current_pricing or {}).get("vcpus") or 2
        min_vcpus = (p95_cpu / 100.0) * current_vcpus * headroom

        instances.append({"resource_id": dbid, "current_type": db_class})
        requirements.append({
            "resource_id": dbid,
            "min_vcpus": min_vcpus,
            "min_memory_gb": None,  # Can't use RDS memory metric reliably
        })
        instance_lookup[dbid] = inst

    if not instances:
        return []

    assignments = _solve_compute_lp(instances, requirements, candidates, budget_cap)

    pricing_map = {c["instance_type"]: c for c in candidates}
    recommendations = []

    for inst_dict in instances:
        dbid = inst_dict["resource_id"]
        current_class = inst_dict["current_type"]
        new_class = assignments.get(dbid)

        if not new_class or new_class == current_class:
            continue

        inv = instance_lookup[dbid]
        current_cost = inv.get("monthly_cost") or 0
        new_pricing = pricing_map.get(new_class, {})
        new_cost = new_pricing.get("on_demand_monthly") or 0

        # Account for multi-AZ (doubles cost)
        if inv.get("multi_az"):
            new_cost = round(new_cost * 2, 2)

        if new_cost >= current_cost:
            continue

        savings = round(current_cost - new_cost, 2)
        pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0

        req = next((r for r in requirements if r["resource_id"] == dbid), {})
        multi_az_note = " (multi-AZ)" if inv.get("multi_az") else ""
        reasoning = (
            f"P95 CPU requires {req.get('min_vcpus', 0):.1f} vCPUs "
            f"(with {headroom:.0%} headroom). "
            f"{new_class}{multi_az_note} meets requirements "
            f"at {pct}% lower cost."
        )

        recommendations.append({
            "service": "RDS",
            "resource_id": dbid,
            "recommendation_type": "rightsize",
            "current_config": f"{current_class}, {inv.get('pricing_model', 'on-demand')}",
            "recommended_config": f"{new_class}, {inv.get('pricing_model', 'on-demand')}",
            "current_monthly_cost": current_cost,
            "estimated_monthly_cost": new_cost,
            "monthly_savings": savings,
            "savings_percent": pct,
            "confidence": "high" if pct > 20 else "medium",
            "reasoning": reasoning,
        })

    return recommendations
