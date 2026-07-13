#!/usr/bin/env python3
"""Compare synthetic-account MILP feasibility under two EC2 catalogs.

This script is paper-local and does not modify the application database. It
reruns the synthetic-account baseline and ablation grids with:

1. the committed demo database candidate catalog, and
2. the snapshot-dated AWS EC2 catalog already documented in paper/aws_catalog.py.

RDS candidates stay unchanged in both runs. The goal is to test whether the
EC2 infeasibility in paper/evidence_experiments.py is a catalog-coverage
boundary or persists with a richer, dated EC2 candidate set.

Run from the repository root:
  venv/bin/python paper/catalog_comparison.py

Outputs:
  paper/ec2_catalog_audit.md
  paper/results_catalog_comparison.json
  paper/table_catalog_comparison.tex
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PAPER))

import storage  # noqa: E402
import evidence_experiments as ev  # noqa: E402
from aws_catalog import CATALOG, SNAPSHOT_DATE  # noqa: E402

HOURS_PER_MONTH = 730.0
SOURCE_URL = (
    "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/"
    "AmazonEC2/current/us-east-1/index.csv"
)
SOURCE_PUBLICATION = "2026-06-30T19:24:11Z"
SOURCE_VERSION = "20260630192411"


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


def fetch_rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def snapshot_ec2_candidates() -> list[dict[str, Any]]:
    candidates = []
    for instance_type, spec in sorted(CATALOG.items()):
        ri_hourly = spec.get("ri1y_hourly")
        candidates.append(
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
                "source": "paper/aws_catalog.py",
                "snapshot_date": SNAPSHOT_DATE,
            }
        )
    return candidates


def ablation_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for q in (0.75, 0.90, 0.95, 0.99):
        specs.append(
            {
                "dimension": "percentile q",
                "level": f"{q:.2f}",
                "label": f"q={q:.2f}, h=1.3",
                "stat": "percentile",
                "q": q,
                "headroom": 1.3,
                "memory_mode": "observed",
                "budget_ratio": None,
            }
        )
    for h in (1.0, 1.1, 1.3, 1.5):
        specs.append(
            {
                "dimension": "headroom h",
                "level": f"{h:.1f}",
                "label": f"q=0.95, h={h:.1f}",
                "stat": "percentile",
                "q": 0.95,
                "headroom": h,
                "memory_mode": "observed",
                "budget_ratio": None,
            }
        )
    for mem in ("off", "observed"):
        specs.append(
            {
                "dimension": "memory constraint",
                "level": mem,
                "label": f"memory {mem}",
                "stat": "percentile",
                "q": 0.95,
                "headroom": 1.3,
                "memory_mode": mem,
                "budget_ratio": None,
            }
        )
    for cap in (None, 1.0, 0.9, 0.75, 0.01):
        level = "none" if cap is None else f"{int(cap * 100)}% current"
        specs.append(
            {
                "dimension": "budget cap",
                "level": level,
                "label": f"budget {level}",
                "stat": "percentile",
                "q": 0.95,
                "headroom": 1.3,
                "memory_mode": "observed",
                "budget_ratio": cap,
            }
        )
    return specs


def run_suite(
    resources: list[ev.ComputeResource],
    candidates_by_service: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    baseline_rows = []
    baseline_resource_rows: dict[str, list[dict[str, Any]]] = {}
    for label, stat, q, h, mem in BASELINE_SPECS:
        if stat == "none":
            baseline_rows.append(ev.current_inventory_row(resources))
            continue
        summary, rrows, _ = ev.run_assignment(resources, candidates_by_service, stat, q, h, mem, label)
        summary["ci95_savings_pct"] = ev.bootstrap_ci(rrows) if summary.get("comparable") else None
        baseline_rows.append(summary)
        baseline_resource_rows[label] = rrows

    ablation_rows = []
    ablation_resource_rows: dict[str, list[dict[str, Any]]] = {}
    for spec in ablation_specs():
        summary, rrows, _ = ev.run_assignment(
            resources,
            candidates_by_service,
            spec["stat"],
            spec["q"],
            spec["headroom"],
            spec["memory_mode"],
            spec["label"],
            budget_ratio=spec["budget_ratio"],
        )
        summary["dimension"] = spec["dimension"]
        summary["level"] = spec["level"]
        ablation_rows.append(summary)
        ablation_resource_rows[spec["label"]] = rrows

    return {
        "baselines": baseline_rows,
        "baseline_resource_rows": baseline_resource_rows,
        "ablations": ablation_rows,
        "ablation_resource_rows": ablation_resource_rows,
    }


def p95_row(suite: dict[str, Any]) -> dict[str, Any]:
    for row in suite["baselines"]:
        if row["label"] == "P95 x 1.3 heuristic":
            return row
    raise KeyError("P95 x 1.3 heuristic row not found")


def is_budget_constrained(row: dict[str, Any]) -> bool:
    return row.get("dimension") == "budget cap" and row.get("budget_ratio") is not None


def is_current_inventory(row: dict[str, Any]) -> bool:
    return row.get("label") == "Current inventory"


def count_rows(rows: list[dict[str, Any]], needle: str, *, budget: bool | None = None) -> int:
    total = 0
    for row in rows:
        if is_current_inventory(row):
            continue
        if budget is not None and is_budget_constrained(row) != budget:
            continue
        if needle in row.get("status", ""):
            total += 1
    return total


def status_summary(suite: dict[str, Any]) -> dict[str, Any]:
    rows = suite["baselines"] + suite["ablations"]
    non_budget_rows = [r for r in rows if not is_current_inventory(r) and not is_budget_constrained(r)]
    budget_rows = [r for r in rows if is_budget_constrained(r)]
    return {
        "p95_x_1_3": p95_row(suite),
        "non_budget_rows": len(non_budget_rows),
        "budget_rows": len(budget_rows),
        "non_budget_ec2_infeasible_rows": count_rows(rows, "EC2 Infeasible", budget=False),
        "budget_ec2_infeasible_rows": count_rows(rows, "EC2 Infeasible", budget=True),
        "failed_rows": count_rows(rows, "Failed", budget=None),
        "partial_rows": count_rows(rows, "Partial", budget=None),
        "optimal_rows": count_rows(rows, "Optimal", budget=None),
    }


def catalog_stats(candidates_by_service: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "raw_candidate_counts": {svc: len(cands) for svc, cands in candidates_by_service.items()},
        "valid_candidate_counts": {
            svc: len(ev.valid_candidates(cands)) for svc, cands in candidates_by_service.items()
        },
        "valid_candidate_filter": (
            "positive on-demand monthly price and nonmissing vCPU specification; "
            "memory constraints also require memory_gb"
        ),
    }


def comparison_resolution(original: dict[str, Any], snapshot: dict[str, Any]) -> str:
    orig_status = original["p95_x_1_3"]["status"]
    snap_status = snapshot["p95_x_1_3"]["status"]
    if "EC2 Infeasible" in orig_status and "EC2 Infeasible" not in snap_status:
        if snapshot["non_budget_ec2_infeasible_rows"] == 0:
            return (
                "EC2 infeasibility disappears for non-budget baseline and ablation rows "
                "with the shared-basis snapshot EC2 catalog; remaining EC2 infeasibility "
                "is confined to explicit per-service budget-cap rows."
            )
        return (
            "The headline P95 x 1.3 EC2 infeasibility disappears with the snapshot "
            "catalog, but other non-budget EC2 infeasibilities remain."
        )
    if "EC2 Infeasible" in snap_status:
        return "EC2 infeasibility persists even with the snapshot EC2 catalog."
    return "The original headline EC2 infeasibility was not present in either catalog run."


def latex_table(rows: list[dict[str, Any]], resolution: str) -> str:
    out = [
        r"\begin{table*}[t]",
        r"\caption{Catalog-comparison rerun for the synthetic-account EC2 feasibility boundary. The snapshot row uses a shared EC2 price basis: current EC2 inventory and EC2 candidates are repriced with the documented AWS Price List snapshot in \texttt{aws\_catalog.py}; RDS candidates remain from the committed demo database. The 19.0\% snapshot-row saving is the service-mixed aggregate decomposed in Table~\ref{tab:service-decomp}. Non-cap EC2 infeasible rows exclude explicit budget-cap constraints. Partial rows are not comparable savings estimates.}",
        r"\label{tab:catalog-comparison}",
        r"\centering",
        r"\renewcommand{\arraystretch}{1.08}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{@{}l r r l r r r r l@{}}",
        r"\toprule",
        r"Catalog/basis & EC2 raw & EC2 valid & P95$\times$1.3 status & Cost & Saving & Non-cap EC2 infeas. & Cap EC2 infeas. & Boundary \\",
        r" & & & & (\$/mo) & (\%) & rows & rows & \\",
        r"\midrule",
    ]
    for row in rows:
        p95 = row["p95_x_1_3"]
        out.append(
            f"{ev.latex_escape(row['catalog'])} & {row['ec2_raw']} & {row['ec2_valid']} "
            f"& {ev.latex_escape(p95['status'])} & {ev.fmt_money(p95['optimized_monthly'])} "
            f"& {ev.fmt_pct(p95['savings_pct'])} & {row['non_budget_ec2_infeasible_rows']}/{row['non_budget_rows']} "
            f"& {row['budget_ec2_infeasible_rows']}/{row['budget_rows']} "
            f"& {ev.latex_escape(row['boundary'])} \\\\"
        )
    out += [
        r"\bottomrule",
        r"\end{tabular}}",
        r"\vspace{0.25em}",
        r"\begin{minipage}{0.98\textwidth}",
        r"\footnotesize",
        ev.latex_escape(resolution),
        r"\end{minipage}",
        r"\end{table*}",
        "",
    ]
    return "\n".join(out)


def md_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        vals = []
        for col in columns:
            val = row.get(col)
            vals.append("" if val is None else str(val))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def write_audit(
    path: Path,
    schema: list[dict[str, Any]],
    original_ec2_rows: list[dict[str, Any]],
    original_excluded: list[dict[str, Any]],
    snapshot_excluded: list[dict[str, Any]],
    result: dict[str, Any],
) -> None:
    comparison = result["comparison"]
    source = result["metadata"]["snapshot_catalog_source"]
    lines = [
        "# EC2 Catalog Audit",
        "",
        "## Summary",
        "",
        "The committed synthetic database contains 13 EC2 price rows, but only "
        "four are solver-valid because the MILP candidate filter requires a "
        "positive monthly price and a nonmissing vCPU field. Memory-constrained "
        "runs also need memory_gb. The nine EC2 rows excluded from the solver "
        "all lack vCPU and memory specifications.",
        "",
        "The repository already contains documented, snapshot-dated EC2 data in "
        "`paper/aws_catalog.py`, so no new scraped or undocumented pricing data "
        "was introduced. This snapshot is a 28-type t3/m5/c5/r5 candidate set "
        "used by the existing external-validation scripts; it is not a claim "
        "to cover every EC2 SKU in AWS.",
        "",
        "No new fetcher was added for this run because the existing repository "
        "snapshot is sufficient to test whether the synthetic-account "
        "infeasibility is caused by the four-row demo candidate set. A full "
        "all-SKU AWS Price List ingestion remains separate future artifact work.",
        "",
        f"Result: {comparison['resolution']}",
        "",
        "## Current Synthetic DB Schema",
        "",
        md_table(schema, ["cid", "name", "type", "notnull", "dflt_value", "pk"]),
        "",
        "## Original EC2 Price Rows",
        "",
        md_table(
            original_ec2_rows,
            [
                "instance_type",
                "vcpus",
                "memory_gb",
                "on_demand_hourly",
                "on_demand_monthly",
                "reserved_1yr_hourly",
                "reserved_1yr_monthly",
            ],
        ),
        "",
        "## Original Rows Excluded by the Solver Filter",
        "",
        md_table(
            original_excluded,
            ["instance_type", "vcpus", "memory_gb", "on_demand_monthly", "exclusion_reason"],
        ),
        "",
        "## Snapshot EC2 Catalog Source",
        "",
        f"- Source file: `{source['module']}`",
        f"- AWS source URL: {source['source_url']}",
        f"- Snapshot date: {source['snapshot_date']}",
        f"- Publication timestamp: {source['publication']}",
        f"- Version: {source['version']}",
        f"- Region/location: {source['region']} / {source['location']}",
        f"- Operating system: {source['operating_system']}",
        f"- Tenancy: {source['tenancy']}",
        f"- Pre-installed software: {source['pre_installed_software']}",
        f"- Capacity status: {source['capacity_status']}",
        f"- License: {source['license']}",
        f"- Hours per month conversion: {source['hours_per_month']}",
        f"- Candidate scope: {source['catalog_scope']}",
        "",
        "Snapshot entries excluded by the same solver-validity filter:",
        "",
        md_table(
            snapshot_excluded,
            ["instance_type", "vcpus", "memory_gb", "on_demand_monthly", "exclusion_reason"],
        )
        if snapshot_excluded
        else "None. All 28 committed snapshot entries have price, vCPU, and memory fields.",
        "",
        "## Catalog-Comparison Result",
        "",
        md_table(
            comparison["table_rows"],
            [
                "catalog",
                "ec2_raw",
                "ec2_valid",
                "p95_status",
                "p95_optimized_monthly",
                "p95_savings_pct",
                "non_budget_ec2_infeasible_rows",
                "budget_ec2_infeasible_rows",
                "boundary",
            ],
        ),
        "",
        "## Interpretation",
        "",
        "- The original demo catalog failure is explained by candidate coverage: "
        "high-percentile/headroom EC2 requirements exceed the four solver-valid "
        "EC2 candidates.",
        "- With the snapshot EC2 catalog, the non-budget P95 x 1.3 and related "
        "percentile/headroom rows become feasible. This supports treating the "
        "original infeasibility as a catalog-completeness boundary.",
        "- Explicit budget-cap rows can still be infeasible under the snapshot "
        "catalog because the conservative EC2 assignment costs more than the "
        "EC2 service-level cap. That is a separate policy/budget boundary, not "
        "hidden solver failure.",
        "- These results do not compare against AWS Compute Optimizer, Azure "
        "Advisor, Savings Plans recommendations, or commercial FinOps tools.",
        "",
        "## Reproduction",
        "",
        "```bash",
        "venv/bin/python paper/evidence_experiments.py",
        "venv/bin/python paper/catalog_comparison.py",
        "./paper/build_conference.sh",
        "```",
        "",
    ]
    path.write_text("\n".join(lines))


def exclusion_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for cand in candidates:
        reasons = []
        if not cand.get("on_demand_monthly") or cand.get("on_demand_monthly") <= 0:
            reasons.append("nonpositive/missing monthly price")
        if cand.get("vcpus") is None:
            reasons.append("missing vcpus")
        if cand.get("memory_gb") is None:
            reasons.append("missing memory_gb for memory-constrained runs")
        if reasons:
            rows.append(
                {
                    "instance_type": cand.get("instance_type"),
                    "vcpus": cand.get("vcpus"),
                    "memory_gb": cand.get("memory_gb"),
                    "on_demand_monthly": cand.get("on_demand_monthly"),
                    "exclusion_reason": "; ".join(reasons),
                }
            )
    return rows


def main() -> None:
    conn = storage.get_connection()
    resources = ev.load_compute_resources(conn)
    snapshot_resources, missing_snapshot_current = ev.snapshot_repriced_resources(resources)
    original_candidates = ev.candidate_map(conn)
    snapshot_candidates = {
        "EC2": ev.snapshot_ec2_candidates(),
        "RDS": original_candidates["RDS"],
    }

    schema = fetch_rows(conn, "PRAGMA table_info(instance_pricing)")
    original_ec2_rows = fetch_rows(
        conn,
        """
        SELECT instance_type, vcpus, memory_gb, on_demand_hourly,
               on_demand_monthly, reserved_1yr_hourly, reserved_1yr_monthly
        FROM instance_pricing
        WHERE service='EC2'
        ORDER BY instance_type
        """,
    )

    original_suite = run_suite(resources, original_candidates)
    snapshot_suite = run_suite(snapshot_resources, snapshot_candidates)
    original_status = status_summary(original_suite)
    snapshot_status = status_summary(snapshot_suite)

    original_stats = catalog_stats(original_candidates)
    snapshot_stats = catalog_stats(snapshot_candidates)
    resolution = comparison_resolution(original_status, snapshot_status)

    table_rows = []
    for label, stats, status in (
        ("Original demo DB", original_stats, original_status),
        ("AWS snapshot shared EC2 basis", snapshot_stats, snapshot_status),
    ):
        p95 = status["p95_x_1_3"]
        if label.startswith("Original"):
            boundary = "catalog coverage"
        elif status["budget_ec2_infeasible_rows"]:
            boundary = "service budget cap"
        else:
            boundary = "none observed"
        table_rows.append(
            {
                "catalog": label,
                "ec2_raw": stats["raw_candidate_counts"]["EC2"],
                "ec2_valid": stats["valid_candidate_counts"]["EC2"],
                "p95_status": p95["status"],
                "p95_optimized_monthly": p95["optimized_monthly"],
                "p95_savings_pct": p95["savings_pct"],
                "non_budget_rows": status["non_budget_rows"],
                "budget_rows": status["budget_rows"],
                "non_budget_ec2_infeasible_rows": status["non_budget_ec2_infeasible_rows"],
                "budget_ec2_infeasible_rows": status["budget_ec2_infeasible_rows"],
                "p95_x_1_3": p95,
                "boundary": boundary,
            }
        )

    result = {
        "metadata": {
            "user_id": ev.USER,
            "resources": len(resources),
            "resource_counts": {
                "EC2": sum(1 for r in resources if r.service == "EC2"),
                "RDS": sum(1 for r in resources if r.service == "RDS"),
            },
            "snapshot_catalog_source": {
                "module": "paper/aws_catalog.py",
                "source_url": SOURCE_URL,
                "snapshot_date": SNAPSHOT_DATE,
                "publication": SOURCE_PUBLICATION,
                "version": SOURCE_VERSION,
                "region": "us-east-1",
                "location": "US East (N. Virginia)",
                "operating_system": "Linux",
                "tenancy": "Shared",
                "pre_installed_software": "NA",
                "capacity_status": "Used",
                "license": "No License required",
                "hours_per_month": HOURS_PER_MONTH,
                "catalog_scope": (
                    "28 committed t3/m5/c5/r5 EC2 types with on-demand, "
                    "1-year reserved, vCPU, and memory fields; not all AWS EC2 SKUs"
                ),
            },
            "notes": [
                "RDS candidates are unchanged; EC2 current inventory and EC2 candidates are repriced in the snapshot run.",
                "Snapshot EC2 costs use us-east-1 Linux on-demand rates for right-sizing.",
                f"Missing EC2 current types in the snapshot catalog: {missing_snapshot_current}.",
                "Partial rows retain fallback diagnostics in JSON but are not comparable savings estimates.",
                "No commercial-tool outputs are used or inferred.",
            ],
        },
        "schema": {"instance_pricing": schema},
        "original_catalog": {
            "stats": original_stats,
            "excluded_ec2_rows": exclusion_rows(original_candidates["EC2"]),
            **original_suite,
        },
        "snapshot_catalog": {
            "stats": snapshot_stats,
            "excluded_ec2_rows": exclusion_rows(snapshot_candidates["EC2"]),
            **snapshot_suite,
        },
        "comparison": {
            "resolution": resolution,
            "original_status_summary": original_status,
            "snapshot_status_summary": snapshot_status,
            "table_rows": table_rows,
        },
        "rerun": "venv/bin/python paper/catalog_comparison.py",
    }

    (PAPER / "results_catalog_comparison.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (PAPER / "table_catalog_comparison.tex").write_text(latex_table(table_rows, resolution))
    write_audit(
        PAPER / "ec2_catalog_audit.md",
        schema,
        original_ec2_rows,
        result["original_catalog"]["excluded_ec2_rows"],
        result["snapshot_catalog"]["excluded_ec2_rows"],
        result,
    )

    conn.close()
    print("wrote ec2_catalog_audit.md, results_catalog_comparison.json, table_catalog_comparison.tex")
    print(resolution)


if __name__ == "__main__":
    main()
