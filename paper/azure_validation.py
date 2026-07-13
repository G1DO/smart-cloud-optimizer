#!/usr/bin/env python3
"""Third-provider external validation: right-sizing on the Azure Public
Dataset V2 vmtable (Cortez et al., SOSP 2017; the V2 trace is 2019 Azure
production: 2,695,548 VMs over 30 consecutive days).

Mirrors external_validation.py's right-sizing study (Study II) on a
hyperscaler trace, using Azure's own precomputed per-VM p95 of the 5-minute
max CPU readings (vmtable column p95maxcpu) in place of a percentile computed
from raw series:

- Filter: observed lifetime >= 7 days (vmdeleted - vmcreated; timestamps are
  seconds from trace start, and VMs alive at trace end carry the last trace
  timestamp, so lifetimes are right-censored at 30 days), p95maxcpu in
  (0, 100], and NUMERIC core/memory buckets -- the open-ended '>24' core and
  '>64' GB buckets carry no exact provisioned capacity and are dropped
  (counted). Filters apply in that bucket -> p95 -> lifetime order.
- Baseline (like-for-like lift-and-shift): per VM, the cheapest catalog type
  (paper/aws_catalog.py, snapshot-dated) with vcpus >= core bucket AND
  memory_gb >= memory bucket.
- Optimized: CPU requirement = core bucket x p95maxcpu/100 x HEADROOM
  (floor 0.05 vCPU); memory requirement = the PROVISIONED memory bucket
  unchanged -- Azure publishes no per-VM memory-usage series, so memory is
  never downsized (conservative).
- With no budget cap the MILP decomposes into per-VM cheapest-covering, so
  the selection is vectorized (numpy searchsorted over a per-memory-bucket
  price suffix-argmin) and validated against the system's own MILP
  (optimizer._solve_compute_lp) on the first 2,000 filtered VMs sorted by
  vmid, asserting identical assignments (all catalog prices are distinct,
  so the per-VM optimum is unique).

Run:
  venv/bin/python paper/azure_validation.py --vmtable <path>/vmtable.csv.gz

Outputs (under paper/): numbers_azure.tex, results_azure.json.
Deterministic given the trace file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PAPER = ROOT / "paper"
sys.path.insert(0, str(PAPER))

from aws_catalog import CATALOG, SNAPSHOT_DATE  # noqa: E402
from optimizer.compute_lp import _solve_compute_lp  # noqa: E402

HEADROOM = 1.3
HOURS_PER_MONTH = 730.0
MIN_LIFETIME_S = 7 * 86400       # right-sizing needs at least a week of history
CPU_FLOOR_VCPUS = 0.05
TRACE_END_S = 30 * 86400         # 30-day trace; last vmtable timestamp is 2,591,400
MILP_SAMPLE = 2000               # MILP-equivalence subsample size

# vmtable.csv is headerless; column order verified against the dataset's
# schema.csv (release asset) and the official V2 analysis notebook.
VMTABLE_COLS = ["vmid", "subscriptionid", "deploymentid", "vmcreated",
                "vmdeleted", "maxcpu", "avgcpu", "p95maxcpu", "vmcategory",
                "vmcorecountbucket", "vmmemorybucket"]
USECOLS = ["vmid", "vmcreated", "vmdeleted", "p95maxcpu",
           "vmcorecountbucket", "vmmemorybucket"]


# =============================================================================
# Trace parsing and filtering
# =============================================================================
def read_vmtable(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path, header=None, names=VMTABLE_COLS, usecols=USECOLS,
        dtype={"vmid": str, "vmcreated": np.int64, "vmdeleted": np.int64,
               "vmcorecountbucket": str, "vmmemorybucket": str})


def filter_vms(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    total_rows = len(raw)
    if not ((raw["vmcreated"] >= 0) & (raw["vmdeleted"] >= raw["vmcreated"])
            & (raw["vmdeleted"] <= TRACE_END_S)).all():
        raise ValueError("vmtable timestamps violate the documented convention")

    cores = pd.to_numeric(raw["vmcorecountbucket"], errors="coerce")
    mem = pd.to_numeric(raw["vmmemorybucket"], errors="coerce")
    ok_bucket = cores.notna() & mem.notna()   # drops '>24' core / '>64' GB rows
    p95 = pd.to_numeric(raw["p95maxcpu"], errors="coerce")
    ok_p95 = p95.notna() & (p95 > 0) & (p95 <= 100)
    ok_life = (raw["vmdeleted"] - raw["vmcreated"]) >= MIN_LIFETIME_S

    counts = {
        "total_rows": total_rows,
        "dropped_bucket": int((~ok_bucket).sum()),
        "dropped_p95": int((ok_bucket & ~ok_p95).sum()),
        "dropped_short": int((ok_bucket & ok_p95 & ~ok_life).sum()),
        "gt_core_rows": int(cores.isna().sum()),
        "gt_mem_rows": int(mem.isna().sum()),
        "gt_both_rows": int((cores.isna() & mem.isna()).sum()),
    }
    keep = ok_bucket & ok_p95 & ok_life
    vms = pd.DataFrame({
        "vmid": raw.loc[keep, "vmid"],
        "cores": cores[keep].astype(float),
        "mem_gb": mem[keep].astype(float),
        "p95_cpu_pct": p95[keep].astype(float),
    }).reset_index(drop=True)
    counts["n_vms"] = len(vms)
    return vms, counts


# =============================================================================
# Right-sizing: vectorized per-VM cheapest-covering (= the MILP w/o budget cap)
# =============================================================================
def catalog_candidates() -> list[dict]:
    return [{"instance_type": t, "vcpus": s["vcpus"], "memory_gb": s["memory_gb"],
             "on_demand_monthly": round(s["od_hourly"] * HOURS_PER_MONTH, 2)}
            for t, s in CATALOG.items()]


def cheapest_covering_vec(cands: list[dict], req_vcpus: np.ndarray,
                          req_mem: np.ndarray) -> np.ndarray:
    """Index (into cands) of the cheapest type covering each (vcpu, mem)
    requirement. For each memory level, candidates with enough memory are
    sorted by vcpus; a price suffix-argmin then gives the cheapest feasible
    type per CPU requirement via searchsorted."""
    vc = np.array([c["vcpus"] for c in cands], dtype=float)
    mg = np.array([c["memory_gb"] for c in cands], dtype=float)
    pr = np.array([c["on_demand_monthly"] for c in cands], dtype=float)
    out = np.full(len(req_vcpus), -1, dtype=np.int64)
    for m in np.unique(req_mem):
        rows = np.where(req_mem == m)[0]
        feas = np.where(mg >= m)[0]
        if len(feas) == 0:
            raise ValueError(f"no catalog type offers {m} GB")
        order = feas[np.argsort(vc[feas], kind="stable")]
        best = np.empty(len(order), dtype=np.int64)       # price suffix-argmin
        best[-1] = order[-1]
        for i in range(len(order) - 2, -1, -1):
            best[i] = order[i] if pr[order[i]] < pr[best[i + 1]] else best[i + 1]
        idx = np.searchsorted(vc[order], req_vcpus[rows], side="left")
        if (idx >= len(order)).any():
            raise ValueError(f"CPU requirement exceeds the largest {m} GB type")
        out[rows] = best[idx]
    assert (out >= 0).all()
    return out


def validate_against_milp(vms: pd.DataFrame, cands: list[dict],
                          opt_idx: np.ndarray, base_idx: np.ndarray) -> int:
    """Run the system's MILP on the first MILP_SAMPLE filtered VMs sorted by
    vmid and assert it reproduces the vectorized assignment exactly."""
    sub = vms.sort_values("vmid", kind="mergesort").head(MILP_SAMPLE)
    ctypes = np.array([c["instance_type"] for c in cands])
    req_cpu = np.maximum(
        sub["cores"] * sub["p95_cpu_pct"] / 100.0 * HEADROOM, CPU_FLOOR_VCPUS)
    instances, requirements = [], []
    for k, (i, vm) in enumerate(sub.iterrows()):
        rid = f"v{k:04d}"   # positional ids keep PuLP variable names clean
        instances.append({"resource_id": rid,
                          "current_type": ctypes[base_idx[i]]})
        requirements.append({"resource_id": rid, "min_vcpus": float(req_cpu[i]),
                             "min_memory_gb": float(vm["mem_gb"])})
    print(f"    MILP: {len(instances)} VMs x {len(cands)} candidate types ...")
    assignments = _solve_compute_lp(instances, requirements, cands,
                                    budget_cap=None)
    if not assignments:
        raise RuntimeError("MILP returned no assignment")
    mismatches = sum(
        1 for k, (i, _) in enumerate(sub.iterrows())
        if assignments[f"v{k:04d}"] != ctypes[opt_idx[i]])
    assert mismatches == 0, f"MILP disagrees on {mismatches}/{len(sub)} VMs"
    print(f"    MILP equivalence: PASS -- {len(sub)}/{len(sub)} assignments "
          "identical to the vectorized selection")
    return len(sub)


def rightsize(vms: pd.DataFrame) -> dict:
    cands = catalog_candidates()
    pr = np.array([c["on_demand_monthly"] for c in cands], dtype=float)
    assert len(set(pr)) == len(pr), "catalog prices must be distinct"
    ctypes = [c["instance_type"] for c in cands]

    base_idx = cheapest_covering_vec(cands, vms["cores"].to_numpy(),
                                     vms["mem_gb"].to_numpy())
    req_cpu = np.maximum(
        (vms["cores"] * vms["p95_cpu_pct"] / 100.0 * HEADROOM).to_numpy(),
        CPU_FLOOR_VCPUS)
    opt_idx = cheapest_covering_vec(cands, req_cpu, vms["mem_gb"].to_numpy())

    milp_n = validate_against_milp(vms, cands, opt_idx, base_idx)

    base_cost = float(pr[base_idx].sum())
    opt_cost = float(pr[opt_idx].sum())
    downsized = int((pr[opt_idx] < pr[base_idx] - 1e-9).sum())
    upsized = int((pr[opt_idx] > pr[base_idx] + 1e-9).sum())

    # reserved-switch lever on top of right-sizing (lifetime-filtered VMs
    # run for weeks; RI pricing is the always-on bound, as in the Bitbrains study)
    ri = np.array([CATALOG[t].get("ri1y_hourly") or CATALOG[t]["od_hourly"]
                   for t in ctypes], dtype=float)
    gamma_real = float(np.mean([CATALOG[t]["ri1y_hourly"] / CATALOG[t]["od_hourly"]
                                for t in CATALOG if CATALOG[t].get("ri1y_hourly")]))
    opt_ri_cost = float((ri[opt_idx] * HOURS_PER_MONTH).sum())

    out = {
        "n_vms": len(vms), "milp_sample": milp_n, "milp_match": True,
        "baseline_monthly": round(base_cost, 2),
        "optimized_monthly": round(opt_cost, 2),
        "savings_monthly": round(base_cost - opt_cost, 2),
        "savings_pct": round(100.0 * (base_cost - opt_cost) / base_cost, 1),
        "downsized": downsized, "upsized": upsized,
        "gamma_real": round(gamma_real, 2),
        "optimized_ri_monthly": round(opt_ri_cost, 2),
        "savings_pct_with_ri": round(100.0 * (base_cost - opt_ri_cost) / base_cost, 1),
        "prov_vcpus": float(vms["cores"].sum()),
        "req_vcpus": round(float(req_cpu.sum()), 1),
    }
    print(f"    Azure: baseline ${out['baseline_monthly']:,}/mo -> optimized "
          f"${out['optimized_monthly']:,}/mo ({out['savings_pct']}%), "
          f"with 1-yr RI ${out['optimized_ri_monthly']:,}/mo "
          f"({out['savings_pct_with_ri']}%)")
    return out


def latexcmd(name, value):
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


# =============================================================================
# Main
# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vmtable", required=True,
                    help="path to the V2 vmtable.csv[.gz] (headerless)")
    args = ap.parse_args()

    print("[1/3] reading vmtable ...")
    raw = read_vmtable(Path(args.vmtable))
    vms, counts = filter_vms(raw)
    del raw
    print(f"    {counts['total_rows']:,} rows -> {counts['n_vms']:,} VMs "
          f"(dropped: {counts['dropped_bucket']:,} open-ended bucket, "
          f"{counts['dropped_p95']:,} invalid p95, "
          f"{counts['dropped_short']:,} lifetime < 7 d)")

    print("[2/3] right-sizing over the real AWS catalog "
          f"(snapshot {SNAPSHOT_DATE}) ...")
    rs = rightsize(vms)

    print("[3/3] writing outputs ...")
    L = ["% Auto-generated by paper/azure_validation.py -- do not edit by hand.\n"]
    L.append(latexcmd("azVms", f"{rs['n_vms']:,}"))
    L.append(latexcmd("azTotalRows", f"{counts['total_rows']:,}"))
    L.append(latexcmd("azDroppedBucket", f"{counts['dropped_bucket']:,}"))
    L.append(latexcmd("azDroppedShort", f"{counts['dropped_short']:,}"))
    L.append(latexcmd("azBaseline", f"{rs['baseline_monthly']:,.0f}"))
    L.append(latexcmd("azOptimized", f"{rs['optimized_monthly']:,.0f}"))
    L.append(latexcmd("azSavingsPct", f"{rs['savings_pct']:.1f}"))
    L.append(latexcmd("azSavingsPctRi", f"{rs['savings_pct_with_ri']:.1f}"))
    L.append(latexcmd("azDownsized", f"{rs['downsized']:,}"))
    L.append(latexcmd("azUpsized", f"{rs['upsized']:,}"))
    (PAPER / "numbers_azure.tex").write_text("".join(L))

    (PAPER / "results_azure.json").write_text(json.dumps({
        "snapshot": SNAPSHOT_DATE,
        "trace": counts,
        "rightsizing": rs,
        "config": {"headroom": HEADROOM, "hours_per_month": HOURS_PER_MONTH,
                   "min_lifetime_days": MIN_LIFETIME_S // 86400,
                   "cpu_floor_vcpus": CPU_FLOOR_VCPUS,
                   "catalog_size": len(CATALOG), "milp_sample": MILP_SAMPLE,
                   "memory_never_downsized": True},
    }, indent=2))
    print("wrote numbers_azure.tex, results_azure.json")


if __name__ == "__main__":
    main()
