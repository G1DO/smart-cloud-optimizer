#!/usr/bin/env python3
"""Generate minimum baseline, ablation, and runtime evidence tables.

This script is paper-local. It does not modify the application database. It
uses the committed synthetic AWS account and the same MILP constraints as
optimizer.compute_lp._solve_compute_lp, with additional instrumentation for
status, variable counts, and solve time.

Run from the repository root:
  venv/bin/python paper/evidence_experiments.py

Outputs:
  paper/results_baselines.json
  paper/results_ablations.json
  paper/results_runtime.json
  paper/table_baselines.tex
  paper/table_ablations.tex
  paper/table_runtime.tex
"""
from __future__ import annotations

import argparse
import json
import math
import resource
import sqlite3
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
sys.path.insert(0, str(ROOT))

import storage  # noqa: E402
from aws_catalog import CATALOG, SNAPSHOT_DATE  # noqa: E402
from optimizer.compute_lp import _solve_compute_lp, optimize_ec2, optimize_rds  # noqa: E402
from optimizer.rules import (  # noqa: E402
    check_dynamodb_tables,
    check_ebs_volumes,
    check_ec2_pricing,
    check_elb_idle,
    check_lambda_memory,
    check_nat_gateways,
    check_rds_pricing,
    check_s3_buckets,
)

USER = "aws-SYNTHETIC-001"
BOOTSTRAP_REPS = 5000
RNG_SEED = 20260709
HOURS_PER_MONTH = 730.0
SNAPSHOT_SOURCE_URL = (
    "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/"
    "AmazonEC2/current/us-east-1/index.csv"
)
SNAPSHOT_PUBLICATION = "2026-06-30T19:24:11Z"
SNAPSHOT_VERSION = "20260630192411"

BASELINE_SPECS = [
    ("Current inventory", "none", 0.0, 1.0, "observed"),
    ("Mean utilization", "mean", 0.0, 1.0, "observed"),
    ("Median utilization", "median", 0.0, 1.0, "observed"),
    ("P90 sizing", "percentile", 0.90, 1.0, "observed"),
    ("P95 sizing", "percentile", 0.95, 1.0, "observed"),
    ("P95 x 1.3 heuristic", "percentile", 0.95, 1.3, "observed"),
    ("P99 sizing", "percentile", 0.99, 1.0, "observed"),
    ("Max utilization", "max", 0.0, 1.0, "observed"),
]


@dataclass
class ComputeResource:
    resource_id: str
    service: str
    current_type: str
    current_cost: float
    current_vcpus: float
    current_memory_gb: float | None
    cpu_util: np.ndarray
    mem_util: np.ndarray | None
    multiplier: float = 1.0
    pricing_model: str = "on-demand"
    original_current_cost: float | None = None


def now() -> float:
    return time.perf_counter()


def peak_mb() -> float:
    # Linux reports ru_maxrss in KiB.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def fmt_money(x: float | None) -> str:
    if x is None or not math.isfinite(float(x)):
        return "--"
    return f"{float(x):,.0f}"


def fmt_pct(x: float | None) -> str:
    if x is None or not math.isfinite(float(x)):
        return "--"
    return f"{float(x):.1f}"


def fmt_signed_money(x: float | None) -> str:
    if x is None or not math.isfinite(float(x)):
        return "--"
    return f"{float(x):+,.0f}"


def fmt_signed_pct(x: float | None) -> str:
    if x is None or not math.isfinite(float(x)):
        return "--"
    return f"{float(x):+.1f}"


def latex_escape(s: str) -> str:
    return (
        s.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
        .replace("#", r"\#")
    )


def fetch_rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def current_rds_vcpus(conn: sqlite3.Connection, db_class: str) -> float:
    row = conn.execute(
        "SELECT vcpus FROM instance_pricing WHERE service='RDS' AND instance_type=?",
        (db_class,),
    ).fetchone()
    if row and row[0]:
        return float(row[0])
    return 2.0


def load_compute_resources(conn: sqlite3.Connection) -> list[ComputeResource]:
    resources: list[ComputeResource] = []

    for inst in storage.get_ec2_instances(conn, USER):
        if inst.get("state") != "running":
            continue
        metrics = storage.get_ec2_metrics(conn, USER, instance_id=inst["instance_id"])
        if not metrics:
            continue
        df = pd.DataFrame(metrics)
        cpu = df["cpu_utilization"].dropna().to_numpy(dtype=float)
        if cpu.size == 0:
            continue
        mem = None
        if "memory_utilization" in df.columns and df["memory_utilization"].notna().any():
            mem = df["memory_utilization"].dropna().to_numpy(dtype=float)
        resources.append(
            ComputeResource(
                resource_id=inst["instance_id"],
                service="EC2",
                current_type=inst["instance_type"],
                current_cost=float(inst.get("monthly_cost") or 0.0),
                current_vcpus=float(inst.get("vcpus") or 2.0),
                current_memory_gb=float(inst.get("memory_gb") or 0.0),
                cpu_util=cpu,
                mem_util=mem,
                pricing_model=inst.get("pricing_model") or "on-demand",
                original_current_cost=float(inst.get("monthly_cost") or 0.0),
            )
        )

    for inst in storage.get_rds_instances(conn, USER):
        metrics = storage.get_rds_metrics(conn, USER, db_instance_id=inst["db_instance_id"])
        if not metrics:
            continue
        df = pd.DataFrame(metrics)
        cpu = df["cpu_utilization"].dropna().to_numpy(dtype=float)
        if cpu.size == 0:
            continue
        multiplier = 2.0 if inst.get("multi_az") else 1.0
        resources.append(
            ComputeResource(
                resource_id=inst["db_instance_id"],
                service="RDS",
                current_type=inst["db_instance_class"],
                current_cost=float(inst.get("monthly_cost") or 0.0),
                current_vcpus=current_rds_vcpus(conn, inst["db_instance_class"]),
                current_memory_gb=None,
                cpu_util=cpu,
                mem_util=None,
                multiplier=multiplier,
                pricing_model=inst.get("pricing_model") or "on-demand",
                original_current_cost=float(inst.get("monthly_cost") or 0.0),
            )
        )

    return resources


def candidate_map(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    return {
        "EC2": storage.get_instance_pricing(conn, service="EC2"),
        "RDS": storage.get_instance_pricing(conn, service="RDS"),
    }


def snapshot_monthly(instance_type: str, price: str = "od") -> float | None:
    spec = CATALOG.get(instance_type)
    if not spec:
        return None
    key = "od_hourly" if price == "od" else "ri1y_hourly"
    hourly = spec.get(key)
    if hourly is None:
        return None
    return round(float(hourly) * HOURS_PER_MONTH, 6)


def snapshot_ec2_candidates() -> list[dict[str, Any]]:
    rows = []
    for instance_type, spec in sorted(CATALOG.items()):
        ri_hourly = spec.get("ri1y_hourly")
        rows.append(
            {
                "service": "EC2",
                "instance_type": instance_type,
                "vcpus": spec["vcpus"],
                "memory_gb": spec["memory_gb"],
                "category": instance_type.split(".", 1)[0],
                "on_demand_hourly": spec["od_hourly"],
                "reserved_1yr_hourly": ri_hourly,
                "reserved_3yr_hourly": None,
                "spot_hourly": None,
                "on_demand_monthly": round(spec["od_hourly"] * HOURS_PER_MONTH, 6),
                "reserved_1yr_monthly": (
                    round(ri_hourly * HOURS_PER_MONTH, 6) if ri_hourly else None
                ),
                "reserved_3yr_monthly": None,
                "spot_monthly": None,
                "snapshot_date": SNAPSHOT_DATE,
            }
        )
    return rows


def snapshot_repriced_resources(resources: list[ComputeResource]) -> tuple[list[ComputeResource], list[str]]:
    """Use one EC2 snapshot on-demand basis for current and candidate costs.

    RDS resources stay on the committed demo DB basis because this paper-local
    AWS snapshot only covers EC2. This keeps EC2 right-sizing comparisons from
    mixing demo candidate prices with snapshot recommendation prices.
    """
    repriced: list[ComputeResource] = []
    missing: list[str] = []
    for r in resources:
        if r.service != "EC2":
            repriced.append(r)
            continue
        monthly = snapshot_monthly(r.current_type, "od")
        if monthly is None:
            missing.append(r.current_type)
            repriced.append(r)
            continue
        repriced.append(
            replace(
                r,
                current_cost=monthly,
                original_current_cost=r.current_cost,
                pricing_model="snapshot-on-demand",
            )
        )
    return repriced, sorted(set(missing))


def valid_candidates(candidates: list[dict]) -> list[dict]:
    return [
        c
        for c in candidates
        if c.get("on_demand_monthly") and c["on_demand_monthly"] > 0 and c.get("vcpus") is not None
    ]


def stat_value(values: np.ndarray, stat: str, q: float) -> float:
    if stat == "mean":
        return float(np.mean(values))
    if stat == "median":
        return float(np.median(values))
    if stat == "max":
        return float(np.max(values))
    if stat == "percentile":
        return float(np.quantile(values, q))
    raise ValueError(f"unknown stat: {stat}")


def build_requirements(
    resources: list[ComputeResource],
    stat: str,
    q: float,
    headroom: float,
    memory_mode: str,
) -> list[dict]:
    reqs = []
    for r in resources:
        cpu_fraction = stat_value(r.cpu_util / 100.0, stat, q)
        min_vcpus = max(cpu_fraction * r.current_vcpus * headroom, 0.05)
        min_mem = None
        if memory_mode == "observed" and r.mem_util is not None and r.current_memory_gb:
            mem_fraction = stat_value(r.mem_util / 100.0, stat, q)
            min_mem = max(mem_fraction * r.current_memory_gb * headroom, 0.05)
        reqs.append(
            {
                "resource_id": r.resource_id,
                "min_vcpus": min_vcpus,
                "min_memory_gb": min_mem,
            }
        )
    return reqs


def solve_lp_instrumented(
    instances: list[dict],
    requirements: list[dict],
    candidates: list[dict],
    budget_cap: float | None,
    label: str,
    time_limit: int = 60,
) -> tuple[dict[str, str], dict[str, Any]]:
    import pulp

    cands = valid_candidates(candidates)
    meta = {
        "label": label,
        "resources": len(instances),
        "candidates": len(cands),
        "decision_variables": len(instances) * len(cands),
        "budget_cap": budget_cap,
        "status": "not_run",
        "solve_seconds": 0.0,
        "objective": None,
    }
    if not instances or not cands:
        meta["status"] = "empty"
        return {}, meta

    req_map = {r["resource_id"]: r for r in requirements}
    prob = pulp.LpProblem("compute_rightsize_instrumented", pulp.LpMinimize)
    x = {}
    for inst in instances:
        rid = inst["resource_id"]
        for cand in cands:
            ctype = cand["instance_type"]
            x[rid, ctype] = pulp.LpVariable(f"x_{rid}_{ctype}", cat=pulp.LpBinary)

    prob += pulp.lpSum(
        cand["on_demand_monthly"] * x[inst["resource_id"], cand["instance_type"]]
        for inst in instances
        for cand in cands
    )
    for inst in instances:
        rid = inst["resource_id"]
        prob += pulp.lpSum(x[rid, cand["instance_type"]] for cand in cands) == 1
    for inst in instances:
        rid = inst["resource_id"]
        req = req_map.get(rid)
        if req and req["min_vcpus"] is not None and req["min_vcpus"] > 0:
            prob += pulp.lpSum(
                (cand.get("vcpus") or 0) * x[rid, cand["instance_type"]]
                for cand in cands
            ) >= req["min_vcpus"]
    for inst in instances:
        rid = inst["resource_id"]
        req = req_map.get(rid)
        if req and req.get("min_memory_gb") is not None and req["min_memory_gb"] > 0:
            prob += pulp.lpSum(
                (cand.get("memory_gb") or 0) * x[rid, cand["instance_type"]]
                for cand in cands
                if cand.get("memory_gb") is not None
            ) >= req["min_memory_gb"]
    if budget_cap is not None:
        prob += pulp.lpSum(
            cand["on_demand_monthly"] * x[inst["resource_id"], cand["instance_type"]]
            for inst in instances
            for cand in cands
        ) <= budget_cap

    start = now()
    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit)
    prob.solve(solver)
    meta["solve_seconds"] = round(now() - start, 6)
    meta["status"] = pulp.constants.LpStatus.get(prob.status, str(prob.status))
    meta["objective"] = float(pulp.value(prob.objective)) if prob.objective is not None else None
    meta["constraints"] = len(prob.constraints)

    if prob.status != pulp.constants.LpStatusOptimal:
        return {}, meta

    result = {}
    for inst in instances:
        rid = inst["resource_id"]
        for cand in cands:
            ctype = cand["instance_type"]
            if x[rid, ctype].varValue and x[rid, ctype].varValue > 0.5:
                result[rid] = ctype
                break
    return result, meta


def run_assignment(
    resources: list[ComputeResource],
    candidates_by_service: dict[str, list[dict]],
    stat: str,
    q: float,
    headroom: float,
    memory_mode: str,
    label: str,
    budget_ratio: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    requirements = build_requirements(resources, stat, q, headroom, memory_mode)
    req_by_id = {r["resource_id"]: r for r in requirements}
    assignments: dict[str, str] = {}
    solve_meta: list[dict[str, Any]] = []

    for service in ("EC2", "RDS"):
        svc_resources = [r for r in resources if r.service == service]
        if not svc_resources:
            continue
        instances = [{"resource_id": r.resource_id, "current_type": r.current_type} for r in svc_resources]
        reqs = [req_by_id[r.resource_id] for r in svc_resources]
        service_current = sum(r.current_cost for r in svc_resources)
        cap = service_current * budget_ratio if budget_ratio is not None else None
        assn, meta = solve_lp_instrumented(
            instances,
            reqs,
            candidates_by_service[service],
            cap,
            f"{label}:{service}",
        )
        solve_meta.append(meta)
        assignments.update(assn)

    candidate_lookup = {
        service: {c["instance_type"]: c for c in valid_candidates(cands)}
        for service, cands in candidates_by_service.items()
    }

    rows = []
    failed = [m for m in solve_meta if m["status"] != "Optimal"]
    failed_services = {
        m["label"].split(":")[-1]: m["status"]
        for m in failed
        if ":" in m["label"]
    }
    for r in resources:
        new_type = assignments.get(r.resource_id)
        if not new_type:
            cpu_demand = r.cpu_util / 100.0 * r.current_vcpus
            cpu_exceedance = float(np.mean(cpu_demand > r.current_vcpus) * 100.0)
            rows.append(
                {
                    "resource_id": r.resource_id,
                    "service": r.service,
                    "current_cost": r.current_cost,
                    "new_cost": r.current_cost,
                    "savings": 0.0,
                    "cpu_exceedance_pct": cpu_exceedance,
                    "assigned_type": None,
                    "kept_current_due_to_failure": r.service in failed_services,
                }
            )
            continue
        cand = candidate_lookup[r.service][new_type]
        new_cost = float(cand["on_demand_monthly"]) * r.multiplier
        selected_vcpus = float(cand.get("vcpus") or 0)
        cpu_demand = r.cpu_util / 100.0 * r.current_vcpus
        cpu_exceedance = float(np.mean(cpu_demand > selected_vcpus) * 100.0)
        rows.append(
            {
                "resource_id": r.resource_id,
                "service": r.service,
                "current_cost": r.current_cost,
                "new_cost": new_cost,
                "savings": r.current_cost - new_cost,
                "cpu_exceedance_pct": cpu_exceedance,
                "assigned_type": new_type,
                "kept_current_due_to_failure": False,
            }
        )

    if not failed:
        status = "Optimal"
    elif assignments:
        details = ", ".join(f"{svc} {st}" for svc, st in sorted(failed_services.items()))
        status = f"Partial ({details})"
    else:
        details = ", ".join(f"{svc} {st}" for svc, st in sorted(failed_services.items()))
        status = f"Failed ({details})"
    comparable = not failed
    valid_rows = [r for r in rows if math.isfinite(r["new_cost"])]
    current_total = sum(r.current_cost for r in resources)
    new_total = sum(r["new_cost"] for r in valid_rows)
    fallback_breakdown = service_breakdown(rows)
    fallback_savings_pct = 100.0 * (current_total - new_total) / current_total
    downsized = sum(1 for r in valid_rows if r["new_cost"] < r["current_cost"] - 1e-9)
    upsized = sum(1 for r in valid_rows if r["new_cost"] > r["current_cost"] + 1e-9)
    cpu_exceed = float(np.nanmean([r["cpu_exceedance_pct"] for r in valid_rows])) if valid_rows else float("nan")

    summary = {
        "label": label,
        "stat": stat,
        "q": q,
        "headroom": headroom,
        "memory_mode": memory_mode,
        "budget_ratio": budget_ratio,
        "resources": len(resources),
        "current_monthly": round(current_total, 2),
        "optimized_monthly": round(new_total, 2) if comparable and math.isfinite(new_total) else None,
        "savings_monthly": (
            round(current_total - new_total, 2) if comparable and math.isfinite(new_total) else None
        ),
        "savings_pct": (
            round(fallback_savings_pct, 3) if comparable and math.isfinite(fallback_savings_pct) else None
        ),
        "comparable": comparable,
        "fallback_optimized_monthly": round(new_total, 2) if math.isfinite(new_total) else None,
        "fallback_savings_monthly": round(current_total - new_total, 2) if math.isfinite(new_total) else None,
        "fallback_savings_pct": (
            round(fallback_savings_pct, 3) if math.isfinite(fallback_savings_pct) else None
        ),
        "service_breakdown": fallback_breakdown if comparable else None,
        "fallback_service_breakdown": fallback_breakdown,
        "downsized": downsized,
        "upsized": upsized,
        "cpu_exceedance_pct": (
            round(cpu_exceed, 3) if comparable and math.isfinite(cpu_exceed) else None
        ),
        "fallback_cpu_exceedance_pct": round(cpu_exceed, 3) if math.isfinite(cpu_exceed) else None,
        "status": status,
        "failed_services": failed_services,
        "cost_policy": (
            "failed service-level solves are kept at current inventory cost for diagnostics only; "
            "partial/failed rows are not comparable savings estimates"
        ),
        "solve_seconds": round(sum(m["solve_seconds"] for m in solve_meta), 6),
        "decision_variables": sum(m["decision_variables"] for m in solve_meta),
        "solver": "PuLP CBC",
        "solve_meta": solve_meta,
    }
    return summary, rows, solve_meta


def current_inventory_resource_rows(resources: list[ComputeResource]) -> list[dict[str, Any]]:
    rows = []
    for r in resources:
        cpu_demand = r.cpu_util / 100.0 * r.current_vcpus
        rows.append(
            {
                "resource_id": r.resource_id,
                "service": r.service,
                "current_cost": r.current_cost,
                "new_cost": r.current_cost,
                "savings": 0.0,
                "cpu_exceedance_pct": float(np.mean(cpu_demand > r.current_vcpus) * 100.0),
                "assigned_type": r.current_type,
                "kept_current_due_to_failure": False,
            }
        )
    return rows


def service_breakdown(resource_rows: list[dict[str, Any]]) -> dict[str, Any]:
    services: dict[str, dict[str, float | None]] = {}
    for service in sorted({r["service"] for r in resource_rows}):
        svc_rows = [r for r in resource_rows if r["service"] == service]
        current = sum(float(r["current_cost"]) for r in svc_rows)
        optimized = sum(float(r["new_cost"]) for r in svc_rows if math.isfinite(float(r["new_cost"])))
        delta = optimized - current
        pct = 100.0 * delta / current if current else None
        savings = current - optimized
        services[service] = {
            "current_monthly": round(current, 2),
            "optimized_monthly": round(optimized, 2),
            "delta_monthly": round(delta, 2),
            "delta_pct": round(pct, 3) if pct is not None and math.isfinite(pct) else None,
            "savings_monthly": round(savings, 2),
            "savings_pct": (
                round(100.0 * savings / current, 3)
                if current and math.isfinite(100.0 * savings / current)
                else None
            ),
        }
    current_total = sum(v["current_monthly"] for v in services.values())
    optimized_total = sum(v["optimized_monthly"] for v in services.values())
    delta_total = optimized_total - current_total
    pct_total = 100.0 * delta_total / current_total if current_total else None
    return {
        "services": services,
        "aggregate": {
            "current_monthly": round(current_total, 2),
            "optimized_monthly": round(optimized_total, 2),
            "delta_monthly": round(delta_total, 2),
            "delta_pct": round(pct_total, 3) if pct_total is not None and math.isfinite(pct_total) else None,
            "savings_monthly": round(current_total - optimized_total, 2),
            "savings_pct": (
                round(100.0 * (current_total - optimized_total) / current_total, 3)
                if current_total
                else None
            ),
        },
    }


def current_inventory_row(resources: list[ComputeResource]) -> dict[str, Any]:
    current_total = sum(r.current_cost for r in resources)
    exceed = []
    for r in resources:
        cpu_demand = r.cpu_util / 100.0 * r.current_vcpus
        exceed.append(float(np.mean(cpu_demand > r.current_vcpus) * 100.0))
    rows = current_inventory_resource_rows(resources)
    return {
        "label": "Current inventory",
        "stat": "none",
        "q": None,
        "headroom": None,
        "memory_mode": "as provisioned",
        "budget_ratio": None,
        "resources": len(resources),
        "current_monthly": round(current_total, 2),
        "optimized_monthly": round(current_total, 2),
        "savings_monthly": 0.0,
        "savings_pct": 0.0,
        "comparable": True,
        "ci95_savings_pct": [0.0, 0.0],
        "downsized": 0,
        "upsized": 0,
        "cpu_exceedance_pct": round(float(np.mean(exceed)), 3),
        "status": "Baseline",
        "solve_seconds": 0.0,
        "decision_variables": 0,
        "service_breakdown": service_breakdown(rows),
    }


def bootstrap_ci(resource_rows: list[dict[str, Any]], reps: int = BOOTSTRAP_REPS) -> list[float] | None:
    rows = [r for r in resource_rows if math.isfinite(r["new_cost"])]
    if not rows:
        return None
    rng = np.random.default_rng(RNG_SEED)
    current = np.array([r["current_cost"] for r in rows], dtype=float)
    new = np.array([r["new_cost"] for r in rows], dtype=float)
    n = len(rows)
    vals = np.empty(reps, dtype=float)
    for i in range(reps):
        idx = rng.integers(0, n, n)
        c = float(current[idx].sum())
        vals[i] = 100.0 * (c - float(new[idx].sum())) / c if c else float("nan")
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return [round(float(lo), 2), round(float(hi), 2)]


def dedup_recs(recs: list[dict]) -> list[dict]:
    seen: dict[tuple[str, str], dict] = {}
    for rec in recs:
        key = (rec["resource_id"], rec["recommendation_type"])
        if key not in seen or rec["monthly_savings"] > seen[key]["monthly_savings"]:
            seen[key] = rec
    return list(seen.values())


def rule_set_ablation(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], float]:
    start = now()
    milp = optimize_ec2(conn, USER) + optimize_rds(conn, USER)
    pricing = check_ec2_pricing(conn, USER) + check_rds_pricing(conn, USER)
    waste = (
        check_lambda_memory(conn, USER)
        + check_ebs_volumes(conn, USER)
        + check_s3_buckets(conn, USER)
        + check_dynamodb_tables(conn, USER)
        + check_nat_gateways(conn, USER)
        + check_elb_idle(conn, USER)
    )
    all_recs = dedup_recs(milp + pricing + waste)
    elapsed = now() - start

    def row(label: str, recs: list[dict]) -> dict[str, Any]:
        return {
            "dimension": "rule set",
            "level": label,
            "recommendations": len(recs),
            "savings_monthly": round(sum(float(r["monthly_savings"]) for r in recs), 2),
            "status": "computed",
        }

    return [
        row("MILP right-sizing only", milp),
        row("reserved pricing only", pricing),
        row("waste rules only", waste),
        row("all rules, deduplicated", all_recs),
    ], elapsed


def implementation_match_check(
    resources: list[ComputeResource],
    candidates_by_service: dict[str, list[dict]],
) -> dict[str, Any]:
    reqs = build_requirements(resources, "percentile", 0.95, 1.3, "observed")
    req_by_id = {r["resource_id"]: r for r in reqs}
    result = {}
    for service in ("EC2", "RDS"):
        svc = [r for r in resources if r.service == service]
        instances = [{"resource_id": r.resource_id, "current_type": r.current_type} for r in svc]
        service_reqs = [req_by_id[r.resource_id] for r in svc]
        impl = _solve_compute_lp(instances, service_reqs, candidates_by_service[service], budget_cap=None)
        inst, meta = solve_lp_instrumented(
            instances,
            service_reqs,
            candidates_by_service[service],
            None,
            f"implementation_match:{service}",
        )
        result[service] = {
            "matches": impl == inst,
            "implementation_assignments": impl,
            "instrumented_assignments": inst,
            "instrumented_status": meta["status"],
        }
    return result


def load_external_lift_shift() -> dict[str, Any] | None:
    path = PAPER / "results_external.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    rightsizing = data.get("rightsizing", {})
    rows = [v for v in rightsizing.values() if v]
    if not rows:
        return None
    baseline = sum(float(r["baseline_monthly"]) for r in rows)
    optimized = sum(float(r["optimized_monthly"]) for r in rows)
    savings_pct = 100.0 * (baseline - optimized) / baseline
    return {
        "scope": "Bitbrains/Materna",
        "label": "Lift-and-shift to P95 x 1.3",
        "resources": sum(int(r["n_vms"]) for r in rows),
        "current_monthly": round(baseline, 2),
        "optimized_monthly": round(optimized, 2),
        "savings_monthly": round(baseline - optimized, 2),
        "savings_pct": round(savings_pct, 3),
        "ci95_savings_pct": None,
        "downsized": sum(int(r["downsized"]) for r in rows),
        "upsized": sum(int(r["upsized"]) for r in rows),
        "cpu_exceedance_pct": None,
        "status": "existing aggregate; raw per-VM CI not rerun",
    }


def run_baseline_grid(
    resources: list[ComputeResource],
    candidates_by_service: dict[str, list[dict]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    rows = []
    resource_rows = {}
    solve_meta = []
    for label, stat, q, h, mem in BASELINE_SPECS:
        if stat == "none":
            rows.append(current_inventory_row(resources))
            resource_rows[label] = current_inventory_resource_rows(resources)
            continue
        summary, rrows, meta = run_assignment(resources, candidates_by_service, stat, q, h, mem, label)
        summary["ci95_savings_pct"] = bootstrap_ci(rrows) if summary.get("comparable") else None
        rows.append(summary)
        resource_rows[label] = rrows
        solve_meta.extend(meta)
    return rows, resource_rows, solve_meta


def run_ablation_grid(
    resources: list[ComputeResource],
    candidates_by_service: dict[str, list[dict]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    rows = []
    resource_rows = {}
    solve_meta = []
    for q in (0.75, 0.90, 0.95, 0.99):
        label = f"q={q:.2f}, h=1.3"
        summary, rrows, meta = run_assignment(resources, candidates_by_service, "percentile", q, 1.3, "observed", label)
        summary["dimension"] = "percentile q"
        summary["level"] = f"{q:.2f}"
        rows.append(summary)
        resource_rows[label] = rrows
        solve_meta.extend(meta)
    for h in (1.0, 1.1, 1.3, 1.5):
        label = f"q=0.95, h={h:.1f}"
        summary, rrows, meta = run_assignment(resources, candidates_by_service, "percentile", 0.95, h, "observed", label)
        summary["dimension"] = "headroom h"
        summary["level"] = f"{h:.1f}"
        rows.append(summary)
        resource_rows[label] = rrows
        solve_meta.extend(meta)
    for mem in ("off", "observed"):
        label = f"memory {mem}"
        summary, rrows, meta = run_assignment(resources, candidates_by_service, "percentile", 0.95, 1.3, mem, label)
        summary["dimension"] = "memory constraint"
        summary["level"] = mem
        rows.append(summary)
        resource_rows[label] = rrows
        solve_meta.extend(meta)
    for cap in (None, 1.0, 0.9, 0.75, 0.01):
        level = "none" if cap is None else f"{int(cap * 100)}% current"
        label = f"budget {level}"
        summary, rrows, meta = run_assignment(
            resources,
            candidates_by_service,
            "percentile",
            0.95,
            1.3,
            "observed",
            label,
            budget_ratio=cap,
        )
        summary["dimension"] = "budget cap"
        summary["level"] = level
        rows.append(summary)
        resource_rows[label] = rrows
        solve_meta.extend(meta)
    return rows, resource_rows, solve_meta


def usage_hour_ri_replay(
    conn: sqlite3.Connection,
    lookbacks: tuple[int, ...] = (7, 30, 60),
    min_coverage: float = 0.80,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Paper-side usage-hour RI replay over snapshot EC2 prices.

    This implementation-specific baseline is not labeled as AWS Compute
    Optimizer, Cost Explorer, Savings Plans, or third-party recommender output.
    It uses a recent window of observed running hours and recommends a
    commitment when coverage is sufficient and RI pricing is below on-demand.
    """
    instances = storage.get_ec2_instances(conn, USER)
    detail_by_window: dict[str, list[dict[str, Any]]] = {}
    rows = []
    for days in lookbacks:
        details = []
        expected_hours = days * 24
        for inst in instances:
            if inst.get("pricing_model") != "on-demand" or inst.get("state") != "running":
                continue
            itype = inst["instance_type"]
            od = snapshot_monthly(itype, "od")
            ri = snapshot_monthly(itype, "ri1y")
            if od is None or ri is None or ri >= od:
                details.append(
                    {
                        "resource_id": inst["instance_id"],
                        "instance_type": itype,
                        "status": "not_recommended",
                        "reason": "missing snapshot price or no RI saving",
                    }
                )
                continue
            metrics = storage.get_ec2_metrics(conn, USER, instance_id=inst["instance_id"])
            if not metrics:
                continue
            df = pd.DataFrame(metrics)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            end = df["timestamp"].max()
            start = end - pd.Timedelta(hours=expected_hours - 1)
            observed_hours = int(df[df["timestamp"] >= start]["timestamp"].nunique())
            coverage = observed_hours / expected_hours if expected_hours else 0.0
            if coverage < min_coverage:
                details.append(
                    {
                        "resource_id": inst["instance_id"],
                        "instance_type": itype,
                        "status": "not_recommended",
                        "reason": "insufficient observed hours",
                        "observed_hours": observed_hours,
                        "coverage": round(coverage, 3),
                    }
                )
                continue
            details.append(
                {
                    "resource_id": inst["instance_id"],
                    "instance_type": itype,
                    "status": "recommended",
                    "lookback_days": days,
                    "observed_hours": observed_hours,
                    "coverage": round(coverage, 3),
                    "current_monthly": round(od, 2),
                    "estimated_monthly": round(ri, 2),
                    "savings_monthly": round(od - ri, 2),
                    "savings_pct": round(100.0 * (od - ri) / od, 3),
                }
            )
        recs = [d for d in details if d.get("status") == "recommended"]
        current = sum(d["current_monthly"] for d in recs)
        estimated = sum(d["estimated_monthly"] for d in recs)
        savings = current - estimated
        rows.append(
            {
                "baseline": "usage-hour RI replay surrogate",
                "lookback_days": days,
                "min_coverage": min_coverage,
                "eligible_on_demand_instances": sum(
                    1
                    for inst in instances
                    if inst.get("pricing_model") == "on-demand" and inst.get("state") == "running"
                ),
                "recommendations": len(recs),
                "current_monthly": round(current, 2),
                "estimated_monthly": round(estimated, 2),
                "savings_monthly": round(savings, 2),
                "savings_pct": round(100.0 * savings / current, 3) if current else None,
                "status": "surrogate; not AWS/Azure/commercial output",
            }
        )
        detail_by_window[f"{days}d"] = details
    return rows, detail_by_window


def collapse_ri_replay_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    if not rows:
        return [], None
    compare_keys = (
        "eligible_on_demand_instances",
        "recommendations",
        "current_monthly",
        "estimated_monthly",
        "savings_monthly",
        "savings_pct",
    )
    first = rows[0]
    identical = all(all(row.get(k) == first.get(k) for k in compare_keys) for row in rows[1:])
    if not identical:
        return rows, None
    windows = [int(row["lookback_days"]) for row in rows]
    collapsed = first.copy()
    collapsed["lookback_days"] = "/".join(str(w) for w in windows)
    collapsed["lookback_windows"] = windows
    collapsed["collapsed_from_rows"] = len(rows)
    collapsed["collapse_reason"] = (
        "The synthetic account has full observed metric coverage for the same "
        "six eligible on-demand EC2 instances in all replay windows, so the "
        "7-, 30-, and 60-day surrogate recommendations are identical."
    )
    collapsed["status"] = "surrogate; 7/30/60 windows identical"
    return [collapsed], collapsed["collapse_reason"]


def price_delta(demo: float | None, snapshot: float | None) -> tuple[float | None, float | None]:
    if demo is None or snapshot is None:
        return None, None
    delta = float(demo) - float(snapshot)
    pct = 100.0 * delta / float(snapshot) if snapshot else None
    return round(delta, 6), round(pct, 3) if pct is not None else None


def ec2_pricing_audit_rows(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pricing_rows = fetch_rows(
        conn,
        """
        SELECT instance_type, vcpus, memory_gb, on_demand_hourly,
               on_demand_monthly, reserved_1yr_hourly, reserved_1yr_monthly
        FROM instance_pricing
        WHERE service='EC2'
        ORDER BY instance_type
        """,
    )
    audited_pricing = []
    for row in pricing_rows:
        itype = row["instance_type"]
        spec = CATALOG.get(itype)
        od_hour = spec.get("od_hourly") if spec else None
        od_month = snapshot_monthly(itype, "od") if spec else None
        ri_hour = spec.get("ri1y_hourly") if spec else None
        ri_month = snapshot_monthly(itype, "ri1y") if spec else None
        od_delta, od_pct = price_delta(row.get("on_demand_hourly"), od_hour)
        ri_delta, ri_pct = price_delta(row.get("reserved_1yr_hourly"), ri_hour)
        issues = []
        if not spec:
            issues.append("not in snapshot catalog")
        if row.get("vcpus") is None:
            issues.append("missing vcpus")
        if row.get("memory_gb") is None:
            issues.append("missing memory")
        if od_pct is not None and abs(od_pct) > 1.0:
            issues.append("on-demand price mismatch")
        if ri_hour is not None and row.get("reserved_1yr_hourly") is None:
            issues.append("missing RI price")
        elif ri_pct is not None and abs(ri_pct) > 1.0:
            issues.append("reserved price mismatch")
        audited_pricing.append(
            {
                **row,
                "snapshot_od_hourly": od_hour,
                "snapshot_od_monthly": od_month,
                "od_hourly_delta": od_delta,
                "od_hourly_delta_pct": od_pct,
                "snapshot_ri1y_hourly": ri_hour,
                "snapshot_ri1y_monthly": ri_month,
                "ri1y_hourly_delta": ri_delta,
                "ri1y_hourly_delta_pct": ri_pct,
                "issues": "; ".join(issues) if issues else "matches snapshot within tolerance",
            }
        )

    inventory_rows = fetch_rows(
        conn,
        """
        SELECT instance_id, instance_type, pricing_model, monthly_cost
        FROM ec2_instances
        WHERE user_id=?
        ORDER BY instance_id
        """,
        (USER,),
    )
    audited_inventory = []
    for row in inventory_rows:
        price = "ri1y" if row.get("pricing_model") == "reserved-1yr" else "od"
        snapshot = snapshot_monthly(row["instance_type"], price)
        delta, pct = price_delta(row.get("monthly_cost"), snapshot)
        issue = "matches snapshot within tolerance"
        if snapshot is None:
            issue = "not in snapshot catalog"
        elif pct is not None and abs(pct) > 1.0:
            issue = "inventory monthly cost differs from snapshot price"
        audited_inventory.append(
            {
                **row,
                "snapshot_price_basis": price,
                "snapshot_monthly": snapshot,
                "monthly_delta": delta,
                "monthly_delta_pct": pct,
                "issues": issue,
            }
        )
    return audited_pricing, audited_inventory


def md_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        vals = []
        for col in columns:
            val = row.get(col)
            if isinstance(val, float):
                vals.append(f"{val:.6g}")
            elif val is None:
                vals.append("")
            else:
                vals.append(str(val))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def write_pricing_audit(
    conn: sqlite3.Connection,
    pricing_rows: list[dict[str, Any]],
    inventory_rows: list[dict[str, Any]],
    rule_rows: list[dict[str, Any]],
    ri_replay_rows: list[dict[str, Any]],
) -> None:
    stored_count = int(
        conn.execute("SELECT COUNT(*) FROM recommendations WHERE user_id=?", (USER,)).fetchone()[0]
    )
    stored_savings = float(
        conn.execute(
            "SELECT COALESCE(SUM(monthly_savings),0) FROM recommendations WHERE user_id=?",
            (USER,),
        ).fetchone()[0]
    )
    current_all = next((r for r in rule_rows if r["level"] == "all rules, deduplicated"), {})
    lines = [
        "# Pricing Audit",
        "",
        "## Summary",
        "",
        "This audit compares the committed synthetic/demo EC2 prices against the "
        "snapshot-dated AWS EC2 catalog in `paper/aws_catalog.py`. The application "
        "database is not modified.",
        "",
        f"- Snapshot source: {SNAPSHOT_SOURCE_URL}",
        f"- Snapshot date: {SNAPSHOT_DATE}",
        f"- Publication: {SNAPSHOT_PUBLICATION}",
        f"- Version: {SNAPSHOT_VERSION}",
        "- Filters: us-east-1 / US East (N. Virginia), Linux, shared tenancy, "
        "Pre-Installed S/W=NA, CapacityStatus=Used, License=No License required.",
        "",
        "Key finding: the EC2 current-inventory monthly costs mostly match the "
        "snapshot basis, but several `instance_pricing` candidate rows are wrong "
        "or incomplete. The old manuscript-level recommendation count came from "
        "the stored `recommendations` table, which is stale relative to the "
        "current pricing table and recomputed optimizer/rule outputs.",
        "",
        "## EC2 Candidate Price Rows",
        "",
        md_table(
            pricing_rows,
            [
                "instance_type",
                "vcpus",
                "memory_gb",
                "on_demand_hourly",
                "snapshot_od_hourly",
                "od_hourly_delta_pct",
                "reserved_1yr_hourly",
                "snapshot_ri1y_hourly",
                "issues",
            ],
        ),
        "",
        "## EC2 Current Inventory Cost Rows",
        "",
        md_table(
            inventory_rows,
            [
                "instance_id",
                "instance_type",
                "pricing_model",
                "monthly_cost",
                "snapshot_price_basis",
                "snapshot_monthly",
                "monthly_delta_pct",
                "issues",
            ],
        ),
        "",
        "## Recommendation Count Reconciliation",
        "",
        f"- Stored `recommendations` table: {stored_count} rows, ${stored_savings:.2f}/mo.",
        f"- Recomputed current implementation rule-set path: "
        f"{current_all.get('recommendations', 'NA')} rows, "
        f"${current_all.get('savings_monthly', 0.0):.2f}/mo.",
        "- Cause: the stored table includes six EC2 reserved-pricing rows from an "
        "older candidate catalog state; the current committed `instance_pricing` "
        "table only has reserved rates for two of those EC2 types. The paper "
        "therefore should not use the stored 19-row count as an authoritative "
        "fresh optimizer result.",
        "",
        "## Paper-Side Usage-Hour RI Replay",
        "",
        "The surrogate below uses observed EC2 metric coverage over trailing "
        "look-back windows and snapshot EC2 RI prices. It is not AWS Compute "
        "Optimizer, Cost Explorer, Azure Advisor, or a commercial FinOps tool.",
        "",
        "The 7-, 30-, and 60-day rows are identical because the same six "
        "eligible on-demand EC2 instances have complete metric coverage in all "
        "three windows and the snapshot reserved/on-demand prices are static. "
        "The manuscript table collapses these identical rows to avoid padding.",
        "",
        md_table(
            ri_replay_rows,
            [
                "lookback_days",
                "eligible_on_demand_instances",
                "recommendations",
                "current_monthly",
                "estimated_monthly",
                "savings_monthly",
                "savings_pct",
                "status",
            ],
        ),
        "",
        "## Paper Consequence",
        "",
        "- Study I dollar claims based on the stored 19 recommendation rows are "
        "not publication-safe as headline results.",
        "- Snapshot-repriced EC2 right-sizing rows and the paper-side usage-hour "
        "RI replay are the safer synthetic-account evidence generated by "
        "`paper/evidence_experiments.py`.",
        "- Partial or failed MILP rows must be reported as non-comparable; their "
        "fallback costs are diagnostics only.",
        "",
    ]
    (PAPER / "pricing_audit.md").write_text("\n".join(lines))


def stress_milp(
    resources: list[ComputeResource],
    candidates_by_service: dict[str, list[dict]],
    sizes: list[int],
) -> list[dict[str, Any]]:
    ec2 = [r for r in resources if r.service == "EC2"]
    if not ec2:
        return []
    base = ec2[0]
    rows = []
    for n in sizes:
        clones = []
        for i in range(n):
            clones.append(
                ComputeResource(
                    resource_id=f"stress_{i}",
                    service="EC2",
                    current_type=base.current_type,
                    current_cost=base.current_cost,
                    current_vcpus=base.current_vcpus,
                    current_memory_gb=base.current_memory_gb,
                    cpu_util=base.cpu_util,
                    mem_util=base.mem_util,
                )
            )
        summary, _, meta = run_assignment(
            clones,
            candidates_by_service,
            "percentile",
            0.95,
            1.3,
            "observed",
            f"stress EC2 n={n}",
        )
        rows.append(
            {
                "experiment": f"EC2 MILP stress n={n}",
                "resources": n,
                "decision_variables": summary["decision_variables"],
                "solves": len(meta),
                "solve_seconds": summary["solve_seconds"],
                "wall_seconds": summary["solve_seconds"],
                "peak_mb": round(peak_mb(), 1),
                "status": summary["status"],
            }
        )
    return rows


def table_baselines(rows: list[dict[str, Any]], external: dict[str, Any] | None) -> str:
    out = [
        r"\begin{table*}[t]",
        r"\caption{Generated baseline comparison. Synthetic compute rows use a shared price basis: EC2 current inventory and EC2 candidates are repriced with the snapshot-dated AWS catalog in \texttt{paper/aws\_catalog.py}; RDS remains on the committed demo DB basis because the paper snapshot covers EC2 only. Aggregate synthetic savings, including the 19.0\% P95 x 1.3 row, should be read with the EC2/RDS split in Table~\ref{tab:service-decomp}. Partial or failed rows are not comparable savings estimates and are shown as ``--''. The real-trace row uses the restored GWA Study II lift-and-shift aggregate; the full GWA baseline grid is in \texttt{table\_external\_baselines.tex}. Bootstrap intervals are descriptive resource-level 95\% intervals.}",
        r"\label{tab:baselines}",
        r"\centering",
        r"\renewcommand{\arraystretch}{1.08}",
        r"\begin{tabular}{@{}l r r r r r r l@{}}",
        r"\toprule",
        r"Method & Resources & Cost & Saving & 95\% CI & Down & Up & Status \\",
        r" & & (\$/mo) & (\%) & (\%) & & & \\",
        r"\midrule",
    ]
    for row in rows:
        comparable = row.get("comparable", row.get("status") in {"Optimal", "Baseline"})
        ci = row.get("ci95_savings_pct") if comparable else None
        ci_s = "--" if not ci else f"[{ci[0]:.1f}, {ci[1]:.1f}]"
        down = row["downsized"] if comparable else "--"
        up = row["upsized"] if comparable else "--"
        out.append(
            f"{latex_escape(row['label'])} & {row['resources']} "
            f"& {fmt_money(row.get('optimized_monthly') if comparable else None)} "
            f"& {fmt_pct(row.get('savings_pct') if comparable else None)} "
            f"& {ci_s} & {down} & {up} "
            f"& {latex_escape(row['status'])} \\\\"
        )
    if external:
        out.append(r"\midrule")
        out.append(
            f"{latex_escape(external['label'])} & {external['resources']} & {fmt_money(external['optimized_monthly'])} "
            f"& {fmt_pct(external['savings_pct'])} & -- & {external['downsized']} & {external['upsized']} "
            f"& {latex_escape(external['status'])} \\\\"
        )
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
    return "\n".join(out)


def table_service_decomposition(p95: dict[str, Any]) -> str:
    breakdown = p95.get("service_breakdown") or {}
    services = breakdown.get("services", {})
    aggregate = breakdown.get("aggregate", {})
    rows = []
    for service in ("EC2", "RDS"):
        if service in services:
            rows.append((service, services[service]))
    rows.append(("Aggregate", aggregate))
    out = [
        r"\begin{table}[t]",
        r"\caption{Study I service-level decomposition for the generated $q_{0.95}\times1.3$ row. EC2 current inventory and candidates use the shared snapshot on-demand basis; RDS remains on the committed demo DB basis. Positive deltas indicate cost increases.}",
        r"\label{tab:service-decomp}",
        r"\centering",
        r"\renewcommand{\arraystretch}{1.06}",
        r"\begin{tabular}{@{}l r r r r@{}}",
        r"\toprule",
        r"Scope & Current & Optimized & Delta & Delta \\",
        r" & (\$/mo) & (\$/mo) & (\$/mo) & (\%) \\",
        r"\midrule",
    ]
    for label, row in rows:
        out.append(
            f"{latex_escape(label)} & {fmt_money(row.get('current_monthly'))} "
            f"& {fmt_money(row.get('optimized_monthly'))} "
            f"& {fmt_signed_money(row.get('delta_monthly'))} "
            f"& {fmt_signed_pct(row.get('delta_pct'))} \\\\"
        )
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def table_ablations(rows: list[dict[str, Any]], rule_rows: list[dict[str, Any]]) -> str:
    out = [
        r"\begin{table*}[t]",
        r"\caption{Generated ablation results on the synthetic account with EC2 repriced to the snapshot AWS catalog. Percentile, headroom, memory, and budget rows report assignment cost only for feasible MILP solves; aggregate 19.0\% rows inherit the EC2/RDS split and RDS demo-price caveat in Table~\ref{tab:service-decomp}. Partial or failed rows expose feasibility limits and are not comparable savings estimates. Rule-set rows are a recomputed implementation sanity check on the committed demo DB, not the source of headline paper savings.}",
        r"\label{tab:ablations}",
        r"\centering",
        r"\renewcommand{\arraystretch}{1.06}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{@{}l l r r r r l@{}}",
        r"\toprule",
        r"Dimension & Level & Cost & Saving & CPU exceed & Recs/vars & Status \\",
        r" & & (\$/mo) & (\%) & (\%) & & \\",
        r"\midrule",
    ]
    for row in rows:
        level = row["level"]
        comparable = row.get("comparable", row.get("status") == "Optimal")
        out.append(
            f"{latex_escape(row['dimension'])} & {latex_escape(level)} & "
            f"{fmt_money(row.get('optimized_monthly') if comparable else None)} "
            f"& {fmt_pct(row.get('savings_pct') if comparable else None)} "
            f"& {fmt_pct(row.get('cpu_exceedance_pct') if comparable else None)} "
            f"& {row.get('decision_variables', '--')} & {latex_escape(row['status'])} \\\\"
        )
    out.append(r"\midrule")
    for row in rule_rows:
        out.append(
            f"{latex_escape(row['dimension'])} & {latex_escape(row['level'])} & -- "
            f"& -- & -- & {row['recommendations']} & \\${row['savings_monthly']:.2f}/mo \\\\"
        )
    out += [r"\bottomrule", r"\end{tabular}}", r"\end{table*}", ""]
    return "\n".join(out)


def table_ri_replay(rows: list[dict[str, Any]], label: str) -> str:
    legacy_label = label == "tab:commercial-like"
    window_heading = "Lookbacks" if legacy_label else "Recency windows"
    out = [
        r"\begin{table}[t]",
        r"\caption{Paper-side EC2 usage-hour RI replay baseline. The replay uses trailing observed metric coverage and the same snapshot EC2 on-demand/reserved prices; it is not AWS Compute Optimizer, Cost Explorer, Azure Advisor, or third-party recommender output. The 7-, 30-, and 60-day windows collapse to one row because they select the same six fully observed synthetic EC2 instances.}",
    ]
    if legacy_label:
        out.append(
            "% Deprecated commercial-like packaging label retained for the finalized conference source."
        )
    out += [
        rf"\label{{{label}}}",
        r"\centering",
        r"\renewcommand{\arraystretch}{1.06}",
        r"\begin{tabular}{@{}l r r r r l@{}}",
        r"\toprule",
        rf"{window_heading} & Recs & Current & Saving & Saving & Status \\",
        r"(days) & & (\$/mo) & (\$/mo) & (\%) & \\",
        r"\midrule",
    ]
    for row in rows:
        out.append(
            f"{latex_escape(str(row['lookback_days']))} & {row['recommendations']} & {fmt_money(row['current_monthly'])} "
            f"& {fmt_money(row['savings_monthly'])} & {fmt_pct(row['savings_pct'])} "
            f"& paper-side replay \\\\"
        )
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def table_runtime(rows: list[dict[str, Any]]) -> str:
    out = [
        r"\begin{table}[t]",
        r"\caption{Runtime and clone-stress diagnostics for the generated evidence script. GWA Bitbrains/Materna raw-trace parsing runtimes are recorded in \texttt{trace\_provenance.md}; Azure raw parsing runtime was not recorded because the raw \texttt{vmtable.csv.gz} input was not restored. These diagnostics are not a hardware-normalized scalability study.}",
        r"\label{tab:runtime}",
        r"\centering",
        r"\renewcommand{\arraystretch}{1.06}",
        r"\resizebox{\columnwidth}{!}{%",
        r"\begin{tabular}{@{}l r r r r r l@{}}",
        r"\toprule",
        r"Experiment & $n$ & Vars & Solves & Solve s & Peak MB & Status \\",
        r"\midrule",
    ]
    for row in rows:
        out.append(
            f"{latex_escape(row['experiment'])} & {row['resources']} & {row['decision_variables']} "
            f"& {row['solves']} & {row['solve_seconds']:.3f} & {row['peak_mb']:.1f} "
            f"& {latex_escape(row['status'])} \\\\"
        )
    out += [r"\bottomrule", r"\end{tabular}}", r"\end{table}", ""]
    return "\n".join(out)


def latexcmd(name: str, value: str) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}"


def write_evidence_numbers(
    baseline_rows: list[dict[str, Any]],
    ri_replay_rows: list[dict[str, Any]],
    rule_rows: list[dict[str, Any]],
) -> None:
    p95 = next(r for r in baseline_rows if r["label"] == "P95 x 1.3 heuristic")
    current = next(r for r in baseline_rows if r["label"] == "Current inventory")
    commercial = ri_replay_rows[0]
    rules = next(r for r in rule_rows if r["level"] == "all rules, deduplicated")
    breakdown = p95["service_breakdown"]
    ec2 = breakdown["services"]["EC2"]
    rds = breakdown["services"]["RDS"]
    aggregate = breakdown["aggregate"]
    lines = [
        "% Auto-generated by paper/evidence_experiments.py -- do not edit by hand.",
        latexcmd("evidComputeCurrent", f"{current['current_monthly']:.2f}"),
        latexcmd("evidPfiveCost", f"{p95['optimized_monthly']:.2f}"),
        latexcmd("evidPfiveSavingsPct", f"{p95['savings_pct']:.1f}"),
        latexcmd("evidPfiveSavingsPctExact", f"{p95['savings_pct']:.3f}"),
        latexcmd("evidEcTwoCurrent", f"{ec2['current_monthly']:.2f}"),
        latexcmd("evidEcTwoOptimized", f"{ec2['optimized_monthly']:.2f}"),
        latexcmd("evidEcTwoDelta", f"{ec2['delta_monthly']:.2f}"),
        latexcmd("evidEcTwoDeltaPct", f"{ec2['delta_pct']:.1f}"),
        latexcmd("evidRdsCurrent", f"{rds['current_monthly']:.2f}"),
        latexcmd("evidRdsOptimized", f"{rds['optimized_monthly']:.2f}"),
        latexcmd("evidRdsDelta", f"{rds['delta_monthly']:.2f}"),
        latexcmd("evidRdsDeltaPct", f"{rds['delta_pct']:.1f}"),
        latexcmd("evidRdsSavings", f"{rds['savings_monthly']:.2f}"),
        latexcmd("evidRdsSavingsPct", f"{rds['savings_pct']:.1f}"),
        latexcmd("evidAggregateDelta", f"{aggregate['delta_monthly']:.2f}"),
        latexcmd("evidAggregateDeltaPct", f"{aggregate['delta_pct']:.1f}"),
        latexcmd("evidAggregateSavings", f"{aggregate['savings_monthly']:.2f}"),
        r"% Deprecated \evidCommercial* packaging aliases retained for finalized conference/main consumers.",
        latexcmd("evidCommercialLookback", f"{commercial['lookback_days']}"),
        latexcmd("evidCommercialLookbacks", f"{commercial['lookback_days']}"),
        latexcmd("evidCommercialRecs", f"{commercial['recommendations']}"),
        latexcmd("evidCommercialCurrent", f"{commercial['current_monthly']:.2f}"),
        latexcmd("evidCommercialSavings", f"{commercial['savings_monthly']:.2f}"),
        latexcmd("evidCommercialSavingsPct", f"{commercial['savings_pct']:.1f}"),
        latexcmd("evidRiReplayLookback", f"{commercial['lookback_days']}"),
        latexcmd("evidRiReplayLookbacks", f"{commercial['lookback_days']}"),
        latexcmd("evidRiReplayRecs", f"{commercial['recommendations']}"),
        latexcmd("evidRiReplayCurrent", f"{commercial['current_monthly']:.2f}"),
        latexcmd("evidRiReplaySavings", f"{commercial['savings_monthly']:.2f}"),
        latexcmd("evidRiReplaySavingsPct", f"{commercial['savings_pct']:.1f}"),
        latexcmd("evidRuleRecs", f"{rules['recommendations']}"),
        latexcmd("evidRuleSavings", f"{rules['savings_monthly']:.2f}"),
        "",
    ]
    (PAPER / "numbers_evidence.tex").write_text("\n".join(lines))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stress-sizes", default="100,500,1000")
    args = ap.parse_args()
    stress_sizes = [int(x) for x in args.stress_sizes.split(",") if x.strip()]

    script_start = now()
    section_times: dict[str, float] = {}
    runtime_rows: list[dict[str, Any]] = []

    conn = storage.get_connection()
    demo_resources = load_compute_resources(conn)
    demo_candidates = candidate_map(conn)
    snapshot_resources, missing_snapshot_current = snapshot_repriced_resources(demo_resources)
    snapshot_candidates = {
        "EC2": snapshot_ec2_candidates(),
        "RDS": demo_candidates["RDS"],
    }
    raw_candidate_counts = {svc: len(c) for svc, c in snapshot_candidates.items()}
    valid_candidate_counts = {svc: len(valid_candidates(c)) for svc, c in snapshot_candidates.items()}
    original_raw_candidate_counts = {svc: len(c) for svc, c in demo_candidates.items()}
    original_valid_candidate_counts = {svc: len(valid_candidates(c)) for svc, c in demo_candidates.items()}
    impl_match = implementation_match_check(demo_resources, demo_candidates)

    metadata = {
        "user_id": USER,
        "resources": len(snapshot_resources),
        "resource_counts": {
            "EC2": sum(1 for r in snapshot_resources if r.service == "EC2"),
            "RDS": sum(1 for r in snapshot_resources if r.service == "RDS"),
        },
        "price_basis": "EC2 snapshot on-demand current and candidates; RDS committed demo DB current and candidates",
        "snapshot_date": SNAPSHOT_DATE,
        "snapshot_source_url": SNAPSHOT_SOURCE_URL,
        "raw_candidate_counts": raw_candidate_counts,
        "valid_candidate_counts": valid_candidate_counts,
        "original_demo_raw_candidate_counts": original_raw_candidate_counts,
        "original_demo_valid_candidate_counts": original_valid_candidate_counts,
        "missing_snapshot_current_types": missing_snapshot_current,
        "valid_candidate_filter": "positive on-demand monthly price and nonmissing vCPU specification; memory constraints require memory_gb when used",
        "bootstrap_reps": BOOTSTRAP_REPS,
        "bootstrap_seed": RNG_SEED,
        "implementation_match_original_demo_catalog": impl_match,
        "notes": [
            "Synthetic confidence intervals are bootstrap intervals across the 10 compute resources and are descriptive, not population-level inference.",
            "Direct AWS Compute Optimizer, Azure Advisor, Savings Plans, or commercial FinOps outputs are not included because no direct comparable tool output exists in the repository.",
            "Partial and failed MILP rows are retained, but their savings fields are null because fallback costs are diagnostics only.",
            "Original demo-catalog results are preserved under original_demo_* keys; headline synthetic right-sizing rows use the snapshot-repriced EC2 basis.",
        ],
    }

    baseline_start = now()
    original_baseline_rows, original_baseline_resource_rows, original_baseline_solve_meta = run_baseline_grid(
        demo_resources, demo_candidates
    )
    baseline_rows, baseline_resource_rows, baseline_solve_meta = run_baseline_grid(
        snapshot_resources, snapshot_candidates
    )
    section_times["baseline_seconds"] = now() - baseline_start
    external_lift_shift = load_external_lift_shift()

    runtime_rows.append(
        {
            "experiment": "baseline sweep",
            "resources": len(snapshot_resources),
            "decision_variables": sum(r["decision_variables"] for r in baseline_rows),
            "solves": len(baseline_solve_meta),
            "solve_seconds": round(sum(m["solve_seconds"] for m in baseline_solve_meta), 6),
            "peak_mb": round(peak_mb(), 1),
            "status": "computed",
        }
    )

    ablation_start = now()
    original_ablation_rows, original_ablation_resource_rows, original_ablation_solve_meta = run_ablation_grid(
        demo_resources, demo_candidates
    )
    ablation_rows, ablation_resource_rows, ablation_solve_meta = run_ablation_grid(
        snapshot_resources, snapshot_candidates
    )
    rule_rows, rule_elapsed = rule_set_ablation(conn)
    ri_replay_rows, ri_replay_details = usage_hour_ri_replay(conn)
    pricing_rows, inventory_rows = ec2_pricing_audit_rows(conn)
    write_pricing_audit(conn, pricing_rows, inventory_rows, rule_rows, ri_replay_rows)
    ri_replay_table_rows, ri_replay_collapse_note = collapse_ri_replay_rows(ri_replay_rows)
    section_times["ablation_seconds"] = now() - ablation_start

    runtime_rows.append(
        {
            "experiment": "ablation sweep",
            "resources": len(snapshot_resources),
            "decision_variables": sum(r["decision_variables"] for r in ablation_rows),
            "solves": len(ablation_solve_meta),
            "solve_seconds": round(sum(m["solve_seconds"] for m in ablation_solve_meta), 6),
            "peak_mb": round(peak_mb(), 1),
            "status": "computed",
        }
    )
    runtime_rows.append(
        {
            "experiment": "rule-set ablation",
            "resources": len(snapshot_resources),
            "decision_variables": 0,
            "solves": 0,
            "solve_seconds": round(rule_elapsed, 6),
            "peak_mb": round(peak_mb(), 1),
            "status": "computed",
        }
    )

    stress_start = now()
    stress_rows = stress_milp(snapshot_resources, snapshot_candidates, stress_sizes)
    section_times["stress_seconds"] = now() - stress_start
    runtime_rows.extend(stress_rows)

    total_seconds = now() - script_start
    runtime_rows.append(
        {
            "experiment": "evidence script total",
            "resources": len(snapshot_resources),
            "decision_variables": sum(r.get("decision_variables", 0) for r in runtime_rows),
            "solves": sum(r.get("solves", 0) for r in runtime_rows),
            "solve_seconds": round(total_seconds, 6),
            "peak_mb": round(peak_mb(), 1),
            "status": "computed",
        }
    )

    unavailable = [
        {
            "experiment": "Bitbrains/Materna percentile baselines and bootstrap CI",
            "reason": "raw GWA trace CSV files are not present in the workspace; only aggregate results_external.json is available",
        },
        {
            "experiment": "Azure runtime and percentile ablations",
            "reason": "raw Azure vmtable.csv.gz is not present in the workspace; only aggregate results_azure.json is available",
        },
        {
            "experiment": "direct commercial baselines",
            "reason": "no direct AWS Compute Optimizer, Azure Advisor, Savings Plans, or third-party recommender output exists in the repository; a labeled paper-side usage-hour RI replay is generated separately",
        },
    ]

    write_json(
        PAPER / "results_baselines.json",
        {
            "metadata": metadata,
            "baselines": baseline_rows,
            "resource_rows": baseline_resource_rows,
            "original_demo_baselines": original_baseline_rows,
            "original_demo_resource_rows": original_baseline_resource_rows,
            "external_lift_shift": external_lift_shift,
            "unavailable": unavailable,
            "rerun": "venv/bin/python paper/evidence_experiments.py",
        },
    )
    write_json(
        PAPER / "results_ablations.json",
        {
            "metadata": metadata,
            "ablations": ablation_rows,
            "rule_set_ablations": rule_rows,
            "resource_rows": ablation_resource_rows,
            "original_demo_ablations": original_ablation_rows,
            "original_demo_resource_rows": original_ablation_resource_rows,
            "unavailable": unavailable,
            "rerun": "venv/bin/python paper/evidence_experiments.py",
        },
    )
    write_json(
        PAPER / "results_runtime.json",
        {
            "metadata": metadata,
            "runtime": runtime_rows,
            "section_seconds": section_times,
            "solve_events": baseline_solve_meta + ablation_solve_meta,
            "original_demo_solve_events": original_baseline_solve_meta + original_ablation_solve_meta,
            "unavailable": unavailable,
            "rerun": "venv/bin/python paper/evidence_experiments.py",
        },
    )
    ri_replay_payload = {
            "metadata": {
                "baseline": "usage-hour RI replay surrogate",
                "display_label": "paper-side usage-hour RI replay baseline",
                "canonical_artifact_name": "results_ri_replay.json",
                "legacy_artifact_name": "results_commercial_like.json",
                "legacy_artifact_name_deprecated": True,
                "price_basis": "EC2 snapshot on-demand versus one-year reserved",
                "snapshot_date": SNAPSHOT_DATE,
                "min_coverage": 0.80,
                "not_a_commercial_tool": True,
                "collapsed_table_rows": ri_replay_collapse_note is not None,
                "collapse_note": ri_replay_collapse_note,
                "notes": [
                    "This is a paper-side usage-hour RI replay baseline, not AWS Compute Optimizer, Cost Explorer, Azure Advisor, or third-party recommender output.",
                    "It uses observed EC2 metric coverage and snapshot EC2 RI prices for the synthetic account.",
                    "The LaTeX table collapses identical recency-window rows when all reported values match.",
                ],
            },
            "rows": ri_replay_rows,
            "table_rows": ri_replay_table_rows,
            "details": ri_replay_details,
            "rerun": "venv/bin/python paper/evidence_experiments.py",
        }
    write_json(PAPER / "results_ri_replay.json", ri_replay_payload)
    write_json(PAPER / "results_commercial_like.json", ri_replay_payload)

    (PAPER / "table_baselines.tex").write_text(table_baselines(baseline_rows, external_lift_shift))
    p95_row = next(r for r in baseline_rows if r["label"] == "P95 x 1.3 heuristic")
    (PAPER / "table_service_decomposition.tex").write_text(table_service_decomposition(p95_row))
    (PAPER / "table_ablations.tex").write_text(table_ablations(ablation_rows, rule_rows))
    (PAPER / "table_runtime.tex").write_text(table_runtime(runtime_rows))
    # Deprecated packaging names retained only for finalized conference/main
    # consumers: results_commercial_like.json, table_commercial_like.tex,
    # \evidCommercial* macros, and the tab:commercial-like label.
    (PAPER / "table_commercial_like.tex").write_text(
        table_ri_replay(ri_replay_table_rows, "tab:commercial-like")
    )
    (PAPER / "table_ri_replay.tex").write_text(
        table_ri_replay(ri_replay_table_rows, "tab:ri-replay")
    )
    write_evidence_numbers(baseline_rows, ri_replay_table_rows, rule_rows)

    conn.close()
    print("wrote results_baselines.json, results_ablations.json, results_runtime.json")
    print("wrote results_ri_replay.json, results_commercial_like.json, pricing_audit.md")
    print("wrote table_baselines.tex, table_service_decomposition.tex, table_ablations.tex, table_runtime.tex, table_commercial_like.tex, table_ri_replay.tex, numbers_evidence.tex")
    print(f"total runtime: {total_seconds:.3f}s; peak memory: {peak_mb():.1f} MB")


if __name__ == "__main__":
    main()
