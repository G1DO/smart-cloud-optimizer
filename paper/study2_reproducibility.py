#!/usr/bin/env python3
"""Add Study II reproducibility evidence from restored raw GWA traces.

Run after paper/external_validation.py has regenerated the main Study II
outputs:

  venv/bin/python paper/study2_reproducibility.py --trace-dir "$TRACE_DIR"

The script computes bootstrap confidence intervals, a simple real-trace
percentile baseline grid, input checksums/manifests, and trace provenance.
Azure is documented here only if its raw vmtable is absent; the Azure
right-sizing script remains paper/azure_validation.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import external_validation as ev
from aws_catalog import CATALOG, SNAPSHOT_DATE


PAPER = Path(__file__).resolve().parent
HOURS_PER_MONTH = ev.HOURS_PER_MONTH
BOOTSTRAP_SEED = 20260709
BOOTSTRAP_REPS = 2000

POLICIES = [
    ("lift_shift", "Lift-and-shift", None, None, 1.0),
    ("mean", "Mean", "mean_cpu_pct", "mean_mem_gb", 1.0),
    ("median", "Median", "p50_cpu_pct", "p50_mem_gb", 1.0),
    ("p90", "P90", "p90_cpu_pct", "p90_mem_gb", 1.0),
    ("p95", "P95", "p95_cpu_pct", "p95_mem_gb", 1.0),
    ("p99", "P99", "p99_cpu_pct", "p99_mem_gb", 1.0),
    ("max", "Max", "max_cpu_pct", "max_mem_gb", 1.0),
    ("proposed_p95_x_1_3", "P95 x 1.3", "p95_cpu_pct", "p95_mem_gb", ev.HEADROOM),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def manifest_hash(root: Path) -> dict:
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*.csv") if p.is_file())
    for path in files:
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(path.stat().st_size).encode("ascii"))
        h.update(b"\n")
    return {"csv_files": len(files), "manifest_sha256": h.hexdigest()}


def trace_inputs(trace_dir: Path) -> dict:
    expected_zips = [
        "gwa_t_12_fastStorage.zip",
        "gwa_t_12_rnd.zip",
        "gwa_t_13_materna.zip",
    ]
    expected_dirs = [
        "gwa-t-12-fastStorage",
        "gwa-t-12-rnd",
        "gwa-t-13-materna",
    ]
    out = {
        "root": "$TRACE_DIR",
        "root_path_redacted": True,
        "zips": {},
        "directories": {},
    }
    for name in expected_zips:
        path = trace_dir / name
        out["zips"][name] = {
            "present": path.exists(),
            "bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256(path) if path.exists() else None,
        }
    for name in expected_dirs:
        path = trace_dir / name
        info = {"present": path.exists()}
        if path.exists():
            info.update(manifest_hash(path))
        out["directories"][name] = info
    return out


def summarize_vm(paths: list[Path], vm_id: str, reader) -> dict | None:
    df = pd.concat([reader(p) for p in paths], ignore_index=True).sort_values("ts")
    if df.empty or df["cpu_use_pct"].dropna().empty:
        return None
    cpu = df["cpu_use_pct"].dropna().astype(float)
    mem = df["mem_use_kb"].dropna().astype(float) / (1024.0 ** 2)
    if mem.empty:
        mem = pd.Series([0.0])
    return {
        "vm": vm_id,
        "cores": float(df["cores"].max()),
        "mem_gb": float(df["mem_cap_kb"].max()) / (1024.0 ** 2),
        "mean_cpu_pct": float(cpu.mean()),
        "p50_cpu_pct": float(np.percentile(cpu, 50)),
        "p90_cpu_pct": float(np.percentile(cpu, 90)),
        "p95_cpu_pct": float(np.percentile(cpu, 95)),
        "p99_cpu_pct": float(np.percentile(cpu, 99)),
        "max_cpu_pct": float(cpu.max()),
        "mean_mem_gb": float(mem.mean()),
        "p50_mem_gb": float(np.percentile(mem, 50)),
        "p90_mem_gb": float(np.percentile(mem, 90)),
        "p95_mem_gb": float(np.percentile(mem, 95)),
        "p99_mem_gb": float(np.percentile(mem, 99)),
        "max_mem_gb": float(mem.max()),
        "rows": int(len(df)),
    }


def scan_quantiles(dataset_dir: Path, reader=ev.read_gwa_csv, group_by_stem: bool = False) -> pd.DataFrame:
    files = ev.vm_files(dataset_dir)
    if group_by_stem:
        grouped: dict[str, list[Path]] = {}
        for path in files:
            grouped.setdefault(path.stem, []).append(path)
        items = sorted(grouped.items())
    else:
        items = [(path.stem, [path]) for path in files]

    rows = []
    for idx, (vm_id, paths) in enumerate(items, start=1):
        row = summarize_vm(paths, vm_id, reader)
        if row is not None:
            rows.append(row)
        if idx % 250 == 0:
            print(f"    summarized {idx}/{len(items)} VMs")
    return pd.DataFrame(rows)


def catalog_candidates() -> list[dict]:
    return ev.catalog_candidates()


def cheapest_type(cands: list[dict], vcpus: float, mem_gb: float) -> dict | None:
    return ev.cheapest_covering(cands, vcpus, mem_gb)


def bootstrap_ci(base_cost: np.ndarray, opt_cost: np.ndarray) -> dict:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(base_cost)
    stats = np.empty(BOOTSTRAP_REPS, dtype=float)
    for i in range(BOOTSTRAP_REPS):
        idx = rng.integers(0, n, n)
        base = float(base_cost[idx].sum())
        opt = float(opt_cost[idx].sum())
        stats[i] = 100.0 * (base - opt) / base
    low, high = np.percentile(stats, [2.5, 97.5])
    return {"low": round(float(low), 1), "high": round(float(high), 1)}


def evaluate_policy(vms: pd.DataFrame, key: str, name: str, cpu_col: str | None,
                    mem_col: str | None, headroom: float) -> dict:
    cands = catalog_candidates()
    biggest = max(cands, key=lambda c: (c["vcpus"], c["memory_gb"]))
    price = {c["instance_type"]: c["on_demand_monthly"] for c in cands}
    ri_price = {
        t: (spec.get("ri1y_hourly") or spec["od_hourly"]) * HOURS_PER_MONTH
        for t, spec in CATALOG.items()
    }

    base_costs = []
    opt_costs = []
    opt_ri_costs = []
    downsized = 0
    upsized = 0
    clamped = 0
    for _, vm in vms.iterrows():
        base = cheapest_type(cands, float(vm["cores"]), float(vm["mem_gb"]))
        if base is None:
            base = biggest
            clamped += 1
        if key == "lift_shift":
            opt = base
        else:
            req_vcpu = max(float(vm["cores"]) * float(vm[cpu_col]) / 100.0 * headroom, 0.05)
            req_mem = max(float(vm[mem_col]) * headroom, 0.05)
            opt = cheapest_type(cands, req_vcpu, req_mem)
            if opt is None:
                opt = biggest
                clamped += 1
        base_price = float(base["on_demand_monthly"])
        opt_price = float(opt["on_demand_monthly"])
        base_costs.append(base_price)
        opt_costs.append(opt_price)
        opt_ri_costs.append(float(ri_price[opt["instance_type"]]))
        downsized += int(opt_price < base_price - 1e-9)
        upsized += int(opt_price > base_price + 1e-9)

    base_arr = np.array(base_costs, dtype=float)
    opt_arr = np.array(opt_costs, dtype=float)
    ri_arr = np.array(opt_ri_costs, dtype=float)
    base_total = float(base_arr.sum())
    opt_total = float(opt_arr.sum())
    ri_total = float(ri_arr.sum())
    out = {
        "key": key,
        "policy": name,
        "headroom": headroom,
        "baseline_monthly": round(base_total, 2),
        "optimized_monthly": round(opt_total, 2),
        "optimized_ri_monthly": round(ri_total, 2),
        "savings_monthly": round(base_total - opt_total, 2),
        "savings_pct": round(100.0 * (base_total - opt_total) / base_total, 1),
        "savings_pct_with_ri": round(100.0 * (base_total - ri_total) / base_total, 1),
        "savings_pct_ci": bootstrap_ci(base_arr, opt_arr),
        "savings_pct_with_ri_ci": bootstrap_ci(base_arr, ri_arr),
        "downsized": downsized,
        "upsized": upsized,
        "clamped": clamped,
    }
    out["_base_costs"] = base_arr
    out["_opt_costs"] = opt_arr
    out["_ri_costs"] = ri_arr
    return out


def evaluate_dataset(vms: pd.DataFrame) -> dict:
    rows = {}
    for key, name, cpu_col, mem_col, headroom in POLICIES:
        rows[key] = evaluate_policy(vms, key, name, cpu_col, mem_col, headroom)
    return rows


def public_row(row: dict) -> dict:
    return {k: v for k, v in row.items() if not k.startswith("_")}


def write_baseline_table(baseline_grid: dict) -> None:
    lines = [
        r"% Auto-generated by paper/study2_reproducibility.py -- do not edit by hand.",
        r"\begin{tabular}{@{}l l r r@{}}",
        r"\toprule",
        r"Dataset & Policy & Cost (\$/mo) & Saving [95\% CI] \\",
        r"\midrule",
    ]
    labels = {"fastStorage": "fastStorage", "rnd": "Rnd", "materna": "Materna"}
    for dataset, rows in baseline_grid.items():
        for key, _, _, _, _ in POLICIES:
            row = rows[key]
            ci = row["savings_pct_ci"]
            lines.append(
                f"{labels[dataset]} & {row['policy']} & "
                f"{row['optimized_monthly']:,.0f} & "
                f"{row['savings_pct']:.1f} [{ci['low']:.1f}, {ci['high']:.1f}] \\\\"
            )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    (PAPER / "table_external_baselines.tex").write_text("\n".join(lines) + "\n")


def latexcmd(name: str, value: str) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


def update_numbers_external(results: dict) -> None:
    path = PAPER / "numbers_external.tex"
    existing = path.read_text()
    generated = [
        "% Additional Study II reproducibility macros from paper/study2_reproducibility.py.\n"
    ]
    tags = {"fastStorage": "Fs", "rnd": "Rnd", "materna": "Mat"}
    for dataset, tag in tags.items():
        row = results["baseline_grid"][dataset]["proposed_p95_x_1_3"]
        ci = row["savings_pct_ci"]
        ri_ci = row["savings_pct_with_ri_ci"]
        generated.append(latexcmd(f"ext{tag}SavingsCiLow", f"{ci['low']:.1f}"))
        generated.append(latexcmd(f"ext{tag}SavingsCiHigh", f"{ci['high']:.1f}"))
        generated.append(latexcmd(f"ext{tag}SavingsPctRiCiLow", f"{ri_ci['low']:.1f}"))
        generated.append(latexcmd(f"ext{tag}SavingsPctRiCiHigh", f"{ri_ci['high']:.1f}"))
    overall = results["aggregate_bootstrap"]
    ci = overall["savings_pct_ci"]
    ri_ci = overall["savings_pct_with_ri_ci"]
    generated.append(latexcmd("extOverallSavingsPct", f"{overall['savings_pct']:.1f}"))
    generated.append(latexcmd("extOverallSavingsCiLow", f"{ci['low']:.1f}"))
    generated.append(latexcmd("extOverallSavingsCiHigh", f"{ci['high']:.1f}"))
    generated.append(latexcmd("extOverallSavingsPctRi", f"{overall['savings_pct_with_ri']:.1f}"))
    generated.append(latexcmd("extOverallSavingsPctRiCiLow", f"{ri_ci['low']:.1f}"))
    generated.append(latexcmd("extOverallSavingsPctRiCiHigh", f"{ri_ci['high']:.1f}"))

    marker = "% Additional Study II reproducibility macros from paper/study2_reproducibility.py."
    prefix = existing.split(marker)[0].rstrip() + "\n"
    path.write_text(prefix + "".join(generated))


def write_provenance(trace_dir: Path, inputs: dict, timings: dict, outputs: list[str]) -> None:
    lines = [
        "# Study II Trace Provenance",
        "",
        "Generated by `paper/study2_reproducibility.py` after restoring GWA traces.",
        "",
        "## Commands",
        "",
        "```bash",
        "export TRACE_DIR=/path/to/gwa-traces",
        "./paper/fetch_traces.sh \"$TRACE_DIR\"",
        "venv/bin/python paper/external_validation.py --trace-dir \"$TRACE_DIR\"",
        "venv/bin/python paper/study2_reproducibility.py --trace-dir \"$TRACE_DIR\"",
        "venv/bin/python paper/policy_sim.py --csv paper/trace_rnd_hourly.csv --prefix extPol --suffix _ext --gamma-star 0.63",
        "```",
        "",
        "Azure was not rerun in this workspace because `vmtable.csv.gz` is not present and `paper/fetch_traces.sh` does not fetch Azure Public Dataset V2.",
        "",
        "## GWA Inputs",
        "",
        "Trace root during the recorded rerun: local path redacted; use `$TRACE_DIR`.",
        "",
        "| File or directory | Present | Size/count | SHA256 or manifest SHA256 |",
        "| --- | --- | ---: | --- |",
    ]
    for name, info in inputs["zips"].items():
        size = info["bytes"] if info["bytes"] is not None else "missing"
        checksum = info["sha256"] or "missing"
        lines.append(f"| `{name}` | {info['present']} | {size} bytes | `{checksum}` |")
    for name, info in inputs["directories"].items():
        count = f"{info.get('csv_files', 'missing')} CSV files"
        checksum = info.get("manifest_sha256") or "missing"
        lines.append(f"| `{name}/` | {info['present']} | {count} | `{checksum}` |")
    lines.extend([
        "",
        "## Runtime Recorded By This Helper",
        "",
        "| Stage | Seconds |",
        "| --- | ---: |",
    ])
    for key, value in timings.items():
        lines.append(f"| {key} | {value:.2f} |")
    lines.extend([
        "",
        "The external validation and policy simulation commands above were run separately; use terminal logs or rerun with `/usr/bin/time -v` for full process-level resource accounting.",
        "",
        "## Outputs",
        "",
    ])
    for output in outputs:
        lines.append(f"- `{output}`")
    lines.extend([
        "",
        "## Azure Input Status",
        "",
        "- Expected raw file: Azure Public Dataset V2 headerless `vmtable.csv.gz`.",
        "- Present locally: no.",
        "- Checksum: missing until the raw file is restored.",
        "- Rerun command when available: `venv/bin/python paper/azure_validation.py --vmtable /path/to/vmtable.csv.gz`.",
    ])
    (PAPER / "trace_provenance.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace-dir", required=True)
    args = ap.parse_args()
    trace_dir = Path(args.trace_dir)

    timings: dict[str, float] = {}
    start_total = time.perf_counter()

    start = time.perf_counter()
    inputs = trace_inputs(trace_dir)
    timings["input checksum and manifest"] = time.perf_counter() - start

    start = time.perf_counter()
    print("[1/4] summarizing fastStorage quantiles ...")
    fs_vms = scan_quantiles(trace_dir / "gwa-t-12-fastStorage")
    print("[2/4] summarizing Rnd quantiles ...")
    rnd_vms = scan_quantiles(trace_dir / "gwa-t-12-rnd", group_by_stem=True)
    print("[3/4] summarizing Materna quantiles ...")
    mat_root = trace_dir / "gwa-t-13-materna"
    mat_dir = max((d for d in mat_root.rglob("Materna-Trace-*") if d.is_dir()),
                  key=lambda d: len(list(d.glob("*.csv"))))
    mat_vms = scan_quantiles(mat_dir, reader=ev.read_materna_csv)
    timings["raw trace quantile scan"] = time.perf_counter() - start

    start = time.perf_counter()
    print("[4/4] computing bootstrap CIs and baseline grid ...")
    raw_grid = {
        "fastStorage": evaluate_dataset(fs_vms),
        "rnd": evaluate_dataset(rnd_vms),
        "materna": evaluate_dataset(mat_vms),
    }
    timings["baseline grid and bootstrap"] = time.perf_counter() - start

    proposed = [raw_grid[d]["proposed_p95_x_1_3"] for d in ["fastStorage", "rnd", "materna"]]
    base = np.concatenate([r["_base_costs"] for r in proposed])
    opt = np.concatenate([r["_opt_costs"] for r in proposed])
    ri = np.concatenate([r["_ri_costs"] for r in proposed])
    aggregate = {
        "baseline_monthly": round(float(base.sum()), 2),
        "optimized_monthly": round(float(opt.sum()), 2),
        "optimized_ri_monthly": round(float(ri.sum()), 2),
        "savings_pct": round(100.0 * float(base.sum() - opt.sum()) / float(base.sum()), 1),
        "savings_pct_with_ri": round(100.0 * float(base.sum() - ri.sum()) / float(base.sum()), 1),
        "savings_pct_ci": bootstrap_ci(base, opt),
        "savings_pct_with_ri_ci": bootstrap_ci(base, ri),
        "n_vms": int(len(base)),
        "bootstrap": {"reps": BOOTSTRAP_REPS, "seed": BOOTSTRAP_SEED},
    }

    baseline_grid = {
        dataset: {key: public_row(row) for key, row in rows.items()}
        for dataset, rows in raw_grid.items()
    }
    results_path = PAPER / "results_external.json"
    results = json.loads(results_path.read_text())
    results["baseline_grid"] = baseline_grid
    rightsizing_keys = {
        "fastStorage": "fastStorage",
        "rnd": "rnd",
        "materna": "materna",
    }
    for dataset, result_key in rightsizing_keys.items():
        proposed_row = baseline_grid[dataset]["proposed_p95_x_1_3"]
        results["rightsizing"][result_key]["savings_pct_ci"] = proposed_row["savings_pct_ci"]
        results["rightsizing"][result_key]["savings_pct_with_ri_ci"] = proposed_row[
            "savings_pct_with_ri_ci"
        ]
    results["aggregate_bootstrap"] = aggregate
    results["trace_inputs"] = inputs
    results["study2_reproducibility_config"] = {
        "script": "paper/study2_reproducibility.py",
        "snapshot": SNAPSHOT_DATE,
        "bootstrap_reps": BOOTSTRAP_REPS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "policies": [p[0] for p in POLICIES],
    }
    results_path.write_text(json.dumps(results, indent=2))
    write_baseline_table(baseline_grid)
    update_numbers_external(results)

    timings["total helper runtime"] = time.perf_counter() - start_total
    outputs = [
        "paper/results_external.json",
        "paper/numbers_external.tex",
        "paper/table_external_baselines.tex",
        "paper/trace_provenance.md",
    ]
    write_provenance(trace_dir, inputs, timings, outputs)
    print("wrote Study II CIs, baseline grid, and trace_provenance.md")


if __name__ == "__main__":
    main()
