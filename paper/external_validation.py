#!/usr/bin/env python3
"""External validation on real public cloud traces (Bitbrains GWA-T-12).

Two experiments, mirroring the paper's synthetic-account study on REAL
per-VM telemetry from a managed-hosting provider (Shen, van Beek & Iosup,
CCGrid 2015; data courtesy of Bitbrains IT Services Inc.):

1. Right-sizing (fastStorage, 1,250 VMs; and Rnd, 500 VMs): per VM, compute
   the deployed rule's requirement (p95 utilization x 1.3 headroom applied
   to provisioned cores / memory), solve the system's own MILP
   (optimizer._solve_compute_lp) over a real AWS price catalog
   (paper/aws_catalog.py, snapshot-dated), and compare against a
   like-for-like "lift-and-shift" baseline that provisions the cheapest
   type covering the ORIGINAL capacity.

2. Forecasting (Rnd, 3 months, hourly aggregate CPU demand in MHz): the
   same walk-forward CV protocol as the synthetic study, at the trace's
   native scale (hourly, season = 24), with MAPE/MASE/coverage and a
   Diebold-Mariano test. Also exports the hourly aggregate as CSV for
   policy_sim.py.

Run after paper/fetch_traces.sh:
  venv/bin/python paper/external_validation.py --trace-dir <dir>

Outputs (under paper/): numbers_external.tex, external_mape_tabular.tex,
fig_ext_series.pdf, trace_rnd_hourly.csv, results_external.json.
Deterministic given the trace files.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PAPER = ROOT / "paper"
FIGDIR = PAPER / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PAPER))

warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import paperlib as pl  # noqa: E402
from aws_catalog import CATALOG, SNAPSHOT_DATE  # noqa: E402
from optimizer.compute_lp import _solve_compute_lp  # noqa: E402
from ml_engine import (  # noqa: E402
    NaiveForecaster,
    SeasonalNaiveForecaster,
    ETSForecaster,
    ProphetForecaster,
)

HEADROOM = 1.3
P95 = 95
HOURS_PER_MONTH = 730.0
SEASON = 24                      # hourly data, daily seasonality
CV_INITIAL = 28 * 24             # 4 weeks of hourly history
CV_STEP = 7 * 24                 # one week between folds
HORIZONS = [6, 12, 24, 48]       # hours
DM_HORIZON = 24                  # deployment-relevant horizon for the DM test
DAILY_SEASON = 7                 # daily aggregate, weekly seasonality
DAILY_INITIAL = 42               # 6 weeks
DAILY_STEP = 7
DAILY_HORIZONS = [7, 14]         # days
DAILY_HEADLINE = 7

C = {
    "blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
    "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9",
    "grey": "#7f7f7f", "black": "#222222",
}

plt.rcParams.update({
    "savefig.dpi": 300, "figure.dpi": 150,
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.grid": True, "grid.alpha": 0.30, "grid.linewidth": 0.4,
    "axes.axisbelow": True, "lines.linewidth": 1.1,
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "figure.constrained_layout.use": True,
})

COLW = 3.45
DBLW = 7.16

GWA_COLS = ["ts", "cores", "cpu_cap_mhz", "cpu_use_mhz", "cpu_use_pct",
            "mem_cap_kb", "mem_use_kb"]


# =============================================================================
# Trace parsing
# =============================================================================
def read_gwa_csv(path: Path) -> pd.DataFrame:
    """Read one GWA-T-12 per-VM CSV (';'-separated with stray tabs)."""
    text = path.read_text(errors="replace").replace("\t", "")
    df = pd.read_csv(io.StringIO(text), sep=";", usecols=range(7),
                     names=GWA_COLS, header=0)
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["ts"])
    # timestamps: seconds vs milliseconds since epoch
    if df["ts"].max() > 1e12:
        df["ts"] = df["ts"] / 1000.0
    df["ts"] = pd.to_datetime(df["ts"], unit="s")
    return df


def read_materna_csv(path: Path) -> pd.DataFrame:
    """Read one Materna GWA-T-13 per-VM CSV (quoted ';'-separated fields,
    decimal commas, dd.mm.yyyy timestamps). Only the 7 GWA-T-12-compatible
    columns are kept; Materna's extra columns (mem %, disk size) are dropped."""
    df = pd.read_csv(path, sep=";", quotechar='"', usecols=range(7),
                     names=GWA_COLS, header=0, encoding="latin-1")
    for c in GWA_COLS[1:]:
        df[c] = pd.to_numeric(
            df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    df["ts"] = pd.to_datetime(df["ts"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
    return df.dropna(subset=["ts"])


def vm_files(dataset_dir: Path) -> list[Path]:
    return sorted(dataset_dir.rglob("*.csv"))


def scan_dataset(dataset_dir: Path, reader=None, group_by_stem=False):
    """One pass over a dataset: per-VM sizing summary + hourly aggregate CPU
    demand (MHz).

    Aggregate = sum over VMs of each VM's hourly-mean CPU usage; with the
    trace's synchronized 5-min sampling this equals the hourly mean of total
    cluster demand up to per-VM gaps.

    group_by_stem: Rnd ships the SAME 500 VMs in three monthly directories
    (rnd/2013-7/1.csv, rnd/2013-8/1.csv, ...); grouping by filename merges a
    VM's months so it is sized once, over its full history.
    """
    reader = reader or read_gwa_csv
    summaries = []
    agg = None
    files = vm_files(dataset_dir)
    if group_by_stem:
        by_vm: dict[str, list[Path]] = {}
        for f in files:
            by_vm.setdefault(f.stem, []).append(f)
        items = sorted(by_vm.items())
    else:
        items = [(f.stem, [f]) for f in files]
    for i, (vm_id, fs) in enumerate(items):
        df = pd.concat([reader(f) for f in fs], ignore_index=True).sort_values("ts")
        if df.empty or df["cpu_use_pct"].dropna().empty:
            continue
        cores = float(df["cores"].max())
        mem_gb = float(df["mem_cap_kb"].max()) / (1024.0 ** 2)
        p95_cpu_pct = float(np.percentile(df["cpu_use_pct"].dropna(), P95))
        mem_use = df["mem_use_kb"].dropna()
        p95_mem_gb = float(np.percentile(mem_use, P95)) / (1024.0 ** 2) if len(mem_use) else 0.0
        summaries.append({
            "vm": vm_id, "cores": cores, "mem_gb": mem_gb,
            "p95_cpu_pct": p95_cpu_pct, "p95_mem_gb": p95_mem_gb,
            "rows": int(len(df)),
        })
        s = df.set_index("ts")["cpu_use_mhz"].astype(float)
        hourly = s.groupby(s.index.floor("h")).mean()
        agg = hourly if agg is None else agg.add(hourly, fill_value=0.0)
        if (i + 1) % 250 == 0:
            print(f"    parsed {i + 1}/{len(items)} VMs")
    return pd.DataFrame(summaries), agg.sort_index() if agg is not None else None


# =============================================================================
# Right-sizing on real VMs (the system's MILP over a real price catalog)
# =============================================================================
def catalog_candidates() -> list[dict]:
    return [{"instance_type": t, "vcpus": s["vcpus"], "memory_gb": s["memory_gb"],
             "on_demand_monthly": round(s["od_hourly"] * HOURS_PER_MONTH, 2)}
            for t, s in CATALOG.items()]


def cheapest_covering(cands: list[dict], vcpus: float, mem_gb: float) -> dict | None:
    ok = [c for c in cands if c["vcpus"] >= vcpus and c["memory_gb"] >= mem_gb]
    return min(ok, key=lambda c: c["on_demand_monthly"]) if ok else None


def rightsize_dataset(vms: pd.DataFrame, label: str) -> dict:
    cands = catalog_candidates()
    biggest = max(cands, key=lambda c: (c["vcpus"], c["memory_gb"]))

    instances, requirements, baseline = [], [], {}
    clamped = 0
    for _, vm in vms.iterrows():
        base = cheapest_covering(cands, vm["cores"], vm["mem_gb"])
        if base is None:           # provisioned beyond the largest catalog type
            clamped += 1
            base = biggest
        rid = str(vm["vm"])
        baseline[rid] = base
        req_vcpu = max(vm["cores"] * vm["p95_cpu_pct"] / 100.0 * HEADROOM, 0.05)
        req_mem = max(vm["p95_mem_gb"] * HEADROOM, 0.05)
        instances.append({"resource_id": rid, "current_type": base["instance_type"]})
        requirements.append({"resource_id": rid, "min_vcpus": req_vcpu,
                             "min_memory_gb": req_mem})

    print(f"    MILP: {len(instances)} VMs x {len(cands)} candidate types ...")
    assignments = _solve_compute_lp(instances, requirements, cands, budget_cap=None)
    if not assignments:
        raise RuntimeError(f"MILP returned no assignment for {label}")

    price = {c["instance_type"]: c["on_demand_monthly"] for c in cands}
    base_cost = sum(baseline[i["resource_id"]]["on_demand_monthly"] for i in instances)
    opt_cost = sum(price[assignments[i["resource_id"]]] for i in instances)
    downsized = sum(
        1 for i in instances
        if price[assignments[i["resource_id"]]] < baseline[i["resource_id"]]["on_demand_monthly"] - 1e-9)
    upsized = sum(
        1 for i in instances
        if price[assignments[i["resource_id"]]] > baseline[i["resource_id"]]["on_demand_monthly"] + 1e-9)

    # reserved-switch lever on top of right-sizing (all trace VMs are always-on)
    ri = {t: s["ri1y_hourly"] for t, s in CATALOG.items() if s.get("ri1y_hourly")}
    gamma_real = float(np.mean([ri[t] / CATALOG[t]["od_hourly"] for t in ri]))
    opt_ri_cost = sum(
        (ri.get(assignments[i["resource_id"]], CATALOG[assignments[i["resource_id"]]]["od_hourly"])
         * HOURS_PER_MONTH) for i in instances)

    out = {
        "label": label, "n_vms": len(instances), "clamped": clamped,
        "baseline_monthly": round(base_cost, 2), "optimized_monthly": round(opt_cost, 2),
        "savings_monthly": round(base_cost - opt_cost, 2),
        "savings_pct": round(100.0 * (base_cost - opt_cost) / base_cost, 1),
        "downsized": downsized, "upsized": upsized,
        "gamma_real": round(gamma_real, 2),
        "optimized_ri_monthly": round(opt_ri_cost, 2),
        "savings_pct_with_ri": round(100.0 * (base_cost - opt_ri_cost) / base_cost, 1),
        "prov_vcpus": float(vms["cores"].sum()),
        "req_vcpus": round(float((vms["cores"] * vms["p95_cpu_pct"] / 100.0 * HEADROOM).sum()), 1),
    }
    print(f"    {label}: baseline ${out['baseline_monthly']:,}/mo -> optimized "
          f"${out['optimized_monthly']:,}/mo ({out['savings_pct']}%), "
          f"with 1-yr RI ${out['optimized_ri_monthly']:,}/mo ({out['savings_pct_with_ri']}%)")
    return out


# =============================================================================
# Forecasting CV on the hourly aggregate (Rnd, 3 months)
# =============================================================================
def model_factories(season: int, hourly: bool):
    return {
        "Naive": lambda: NaiveForecaster(),
        "SeasonalNaive": lambda: SeasonalNaiveForecaster(season_length=season),
        "ETS": lambda: ETSForecaster(seasonal_periods=season),
        "Prophet": lambda: ProphetForecaster(yearly_seasonality=False,
                                             weekly_seasonality=True,
                                             daily_seasonality=hourly),
    }


def run_forecast_cv(series: pd.Series, season: int, initial: int, step: int,
                    horizons: list[int], hourly: bool, unit: str):
    df = series.reset_index()
    df.columns = ["date", "value"]
    results = {}
    for name, factory in model_factories(season, hourly).items():
        results[name] = {}
        for h in horizons:
            np.random.seed(2026)  # Prophet interval sampling uses the global RNG
            r = pl.walk_forward(factory, df, initial=initial, horizon=h,
                                step=step, m=season)
            mapes = [f["mape"] for f in r["folds"]]
            results[name][h] = {
                "mape_mean": float(np.nanmean(mapes)),
                "mape_std": float(np.nanstd(mapes)),
                "mase_mean": float(np.nanmean([f["mase"] for f in r["folds"]])),
                "coverage": float(np.nanmean([f["coverage"] for f in r["folds"]])),
                "n_folds": len(r["folds"]),
                "_pooled": r,
            }
            print(f"    {name:14s} h={h:>3}{unit}  MAPE {results[name][h]['mape_mean']:.1f}%"
                  f" +/- {results[name][h]['mape_std']:.1f}  ({results[name][h]['n_folds']} folds)")
    return results


def write_ext_mape_table(cv_hourly: dict, cv_daily: dict):
    """One combined tabular: hourly horizons then daily horizons."""
    order = ["ETS", "SeasonalNaive", "Prophet", "Naive"]
    cols = [(cv_hourly, h, fr"$h{{=}}{h}$\,h") for h in HORIZONS] + \
           [(cv_daily, h, fr"$h{{=}}{h}$\,d") for h in DAILY_HORIZONS]
    best = [min(cv[m][h]["mape_mean"] for m in order) for cv, h, _ in cols]
    out = [r"\setlength{\tabcolsep}{3pt}",
           r"\resizebox{\columnwidth}{!}{%",
           r"\begin{tabular}{@{}l " + "r " * len(cols) + r"@{}}", r"\toprule"]
    out.append("Model & " + " & ".join(lbl for _, _, lbl in cols) + r" \\")
    out.append(r"\midrule")
    for m in order:
        cells = []
        for j, (cv, h, _) in enumerate(cols):
            v = cv[m][h]["mape_mean"]
            s = f"{v:.1f} $\\pm$ {cv[m][h]['mape_std']:.1f}"
            cells.append(f"\\textbf{{{s}}}" if abs(v - best[j]) < 1e-9 else s)
        out.append(f"{m:14s} & " + " & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}}"]
    (PAPER / "external_mape_tabular.tex").write_text("\n".join(out) + "\n")


def fig_ext_series(series: pd.Series, thresh: float, n_surges: int):
    fig, ax = plt.subplots(figsize=(DBLW, 2.2))
    ghz = series / 1000.0
    ax.plot(ghz.index, ghz.values, color=C["blue"], lw=0.6,
            label="hourly aggregate CPU demand")
    ax.axhline(thresh / 1000.0, color=C["red"], lw=0.8, ls=":",
               label=fr"surge threshold $\mu+2\sigma$ ({n_surges} h above)")
    ax.set_ylabel("CPU demand (GHz)")
    ax.set_xlabel("Date (trace time)")
    ax.legend(loc="upper left", frameon=False, ncol=2)
    ax.margins(x=0.01)
    fig.autofmt_xdate(rotation=0)
    fig.savefig(FIGDIR / "fig_ext_series.pdf")
    plt.close(fig)


def latexcmd(name, value):
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


# =============================================================================
# Main
# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace-dir", required=True,
                    help="dir containing gwa-t-12-fastStorage/ and gwa-t-12-rnd/")
    ap.add_argument("--skip-forecast", action="store_true")
    args = ap.parse_args()
    troot = Path(args.trace_dir)

    print("[1/4] parsing fastStorage (1,250 VMs) ...")
    fs_vms, fs_agg = scan_dataset(troot / "gwa-t-12-fastStorage")
    print(f"    {len(fs_vms)} usable VMs, {fs_vms['cores'].sum():.0f} provisioned vCPUs")

    print("[2/4] parsing Rnd (500 VMs, 3 months) ...")
    rnd_vms, rnd_agg = scan_dataset(troot / "gwa-t-12-rnd", group_by_stem=True)
    print(f"    {len(rnd_vms)} usable VMs; aggregate {len(rnd_agg)} hourly points")

    # Materna GWA-T-13 (second provider): its three traces are consecutive
    # months of the same infrastructure, so right-size only the largest one
    # to avoid counting a VM twice.
    mat_root = troot / "gwa-t-13-materna"
    mat_vms = None
    if mat_root.exists():
        mat_dir = max((d for d in mat_root.rglob("Materna-Trace-*") if d.is_dir()),
                      key=lambda d: len(list(d.glob("*.csv"))))
        print(f"[2b/4] parsing Materna ({mat_dir.name}) ...")
        mat_vms, _ = scan_dataset(mat_dir, reader=read_materna_csv)
        print(f"    {len(mat_vms)} usable VMs")

    print("[3/4] right-sizing MILP over the real AWS catalog "
          f"(snapshot {SNAPSHOT_DATE}) ...")
    rs_fs = rightsize_dataset(fs_vms, "fastStorage")
    rs_rnd = rightsize_dataset(rnd_vms, "Rnd")
    rs_mat = rightsize_dataset(mat_vms, "Materna") if mat_vms is not None else None

    # aggregate series bookkeeping (Rnd primary: longest span)
    rnd_agg = rnd_agg.asfreq("h").interpolate(limit=3).dropna()
    mu, sd = float(rnd_agg.mean()), float(rnd_agg.std(ddof=1))
    thresh = mu + 2 * sd
    n_surges = int((rnd_agg > thresh).sum())
    fig_ext_series(rnd_agg, thresh, n_surges)
    rnd_agg.rename("value").rename_axis("date").reset_index().to_csv(
        PAPER / "trace_rnd_hourly.csv", index=False)

    cv = {}
    cv_daily = {}
    dm = wil = dm_psn = dm_pn = None
    if not args.skip_forecast:
        print("[4/4] walk-forward CV on the Rnd hourly aggregate ...")
        cv = run_forecast_cv(rnd_agg, SEASON, CV_INITIAL, CV_STEP, HORIZONS,
                             hourly=True, unit="h")
        def errs(m):
            r = cv[m][DM_HORIZON]["_pooled"]
            return r["y_true"] - r["y_pred"]

        e_ets = cv["ETS"][DM_HORIZON]["_pooled"]
        e_sn = cv["SeasonalNaive"][DM_HORIZON]["_pooled"]
        dm = pl.dm_test(errs("ETS"), errs("SeasonalNaive"), h=DM_HORIZON, power=1)
        # the best hourly model (Prophet) vs both baselines, same horizon
        dm_psn = pl.dm_test(errs("Prophet"), errs("SeasonalNaive"), h=DM_HORIZON, power=1)
        dm_pn = pl.dm_test(errs("Prophet"), errs("Naive"), h=DM_HORIZON, power=1)
        wil = pl.wilcoxon_folds([f["mape"] for f in e_ets["folds"]],
                                [f["mape"] for f in e_sn["folds"]])
        print(f"    DM(ETS vs SeasonalNaive, h={DM_HORIZON}h): stat={dm[0]:.2f} p={dm[1]:.4f}; "
              f"Wilcoxon p={wil[1]:.4f}")
        print(f"    DM(Prophet vs SeasonalNaive): p={dm_psn[1]:.4f}; DM(Prophet vs Naive): p={dm_pn[1]:.4f}")
        print("    ... and on the daily aggregate ...")
        rnd_daily = rnd_agg.resample("D").mean().dropna()
        cv_daily = run_forecast_cv(rnd_daily, DAILY_SEASON, DAILY_INITIAL,
                                   DAILY_STEP, DAILY_HORIZONS, hourly=False, unit="d")
        write_ext_mape_table(cv, cv_daily)

    # ---- macros ----
    L = ["% Auto-generated by paper/external_validation.py -- do not edit by hand.\n"]
    L.append(latexcmd("extSnapshot", SNAPSHOT_DATE))
    L.append(latexcmd("extCatalogSize", f"{len(CATALOG)}"))
    rs_all = [("Fs", rs_fs), ("Rnd", rs_rnd)] + ([("Mat", rs_mat)] if rs_mat else [])
    for tag, rs in rs_all:
        L.append(latexcmd(f"ext{tag}Vms", f"{rs['n_vms']}"))
        L.append(latexcmd(f"ext{tag}Baseline", f"{rs['baseline_monthly']:,.0f}"))
        L.append(latexcmd(f"ext{tag}Optimized", f"{rs['optimized_monthly']:,.0f}"))
        L.append(latexcmd(f"ext{tag}SavingsPct", f"{rs['savings_pct']:.1f}"))
        L.append(latexcmd(f"ext{tag}SavingsPctRi", f"{rs['savings_pct_with_ri']:.1f}"))
        L.append(latexcmd(f"ext{tag}Downsized", f"{rs['downsized']}"))
        L.append(latexcmd(f"ext{tag}Upsized", f"{rs['upsized']}"))
        L.append(latexcmd(f"ext{tag}Clamped", f"{rs['clamped']}"))
    L.append(latexcmd("extGammaReal", f"{rs_fs['gamma_real']:.2f}"))
    L.append(latexcmd("extTotalVms", f"{sum(rs['n_vms'] for _, rs in rs_all):,}"))
    L.append(latexcmd("extRndHours", f"{len(rnd_agg)}"))
    L.append(latexcmd("extRndMeanGhz", f"{mu / 1000.0:.1f}"))
    L.append(latexcmd("extRndSurges", f"{n_surges}"))
    if cv:
        mname = {"Naive": "Naive", "SeasonalNaive": "Snaive", "ETS": "Ets", "Prophet": "Prophet"}
        for m, tag in mname.items():
            c = cv[m][DM_HORIZON]
            L.append(latexcmd(f"extMape{tag}", f"{c['mape_mean']:.1f}"))
            L.append(latexcmd(f"extMapeSd{tag}", f"{c['mape_std']:.1f}"))
            L.append(latexcmd(f"extMase{tag}", f"{c['mase_mean']:.2f}"))
            L.append(latexcmd(f"extCov{tag}", f"{c['coverage']:.0f}"))
        best = min(mname, key=lambda m: cv[m][DM_HORIZON]["mape_mean"])
        L.append(latexcmd("extBestModel", best))
        L.append(latexcmd("extBestMape", f"{cv[best][DM_HORIZON]['mape_mean']:.1f}"))
        L.append(latexcmd("extNFolds", f"{cv[best][DM_HORIZON]['n_folds']}"))
        L.append(latexcmd("extDmStat", f"{dm[0]:.2f}"))
        L.append(latexcmd("extDmP", "<0.001" if dm[1] < 0.001 else f"{dm[1]:.3f}"))
        L.append(latexcmd("extWilcoxonP", "<0.001" if wil[1] < 0.001 else f"{wil[1]:.3f}"))
        L.append(latexcmd("extDmPProphetSnaive", "<0.001" if dm_psn[1] < 0.001 else f"{dm_psn[1]:.3f}"))
        L.append(latexcmd("extDmPProphetNaive", "<0.001" if dm_pn[1] < 0.001 else f"{dm_pn[1]:.3f}"))
        any_best = min(min(cv[m][h]["mape_mean"] for m in cv for h in HORIZONS),
                       min(cv_daily[m][h]["mape_mean"] for m in cv_daily for h in DAILY_HORIZONS))
        L.append(latexcmd("extAnyBestMape", f"{any_best:.1f}"))
        for m, tag in mname.items():
            c = cv_daily[m][DAILY_HEADLINE]
            L.append(latexcmd(f"extDailyMape{tag}", f"{c['mape_mean']:.1f}"))
            L.append(latexcmd(f"extDailyMapeSd{tag}", f"{c['mape_std']:.1f}"))
            L.append(latexcmd(f"extDailyMase{tag}", f"{c['mase_mean']:.2f}"))
        dbest = min(mname, key=lambda m: cv_daily[m][DAILY_HEADLINE]["mape_mean"])
        L.append(latexcmd("extDailyBestModel", dbest))
        L.append(latexcmd("extDailyBestMape", f"{cv_daily[dbest][DAILY_HEADLINE]['mape_mean']:.1f}"))
        L.append(latexcmd("extDailyNFolds", f"{cv_daily[dbest][DAILY_HEADLINE]['n_folds']}"))
    (PAPER / "numbers_external.tex").write_text("".join(L))

    def strip_pooled(cvd):
        return {m: {h: {k: v for k, v in d.items() if k != "_pooled"}
                    for h, d in hs.items()} for m, hs in cvd.items()}

    (PAPER / "results_external.json").write_text(json.dumps({
        "snapshot": SNAPSHOT_DATE,
        "rightsizing": {"fastStorage": rs_fs, "rnd": rs_rnd, "materna": rs_mat},
        "aggregate": {"hours": len(rnd_agg), "mean_mhz": mu, "std_mhz": sd,
                      "surge_thresh_mhz": thresh, "n_surges": n_surges},
        "cv": strip_pooled(cv),
        "cv_daily": strip_pooled(cv_daily),
        "dm_test": dm, "wilcoxon": wil,
        "dm_prophet_snaive": dm_psn if cv else None,
        "dm_prophet_naive": dm_pn if cv else None,
        "cv_config": {"initial": CV_INITIAL, "step": CV_STEP,
                      "horizons": HORIZONS, "season": SEASON,
                      "daily": {"initial": DAILY_INITIAL, "step": DAILY_STEP,
                                "horizons": DAILY_HORIZONS, "season": DAILY_SEASON}},
    }, indent=2))
    print("wrote numbers_external.tex, external_mape_tabular.tex, "
          "fig_ext_series.pdf, trace_rnd_hourly.csv, results_external.json")


if __name__ == "__main__":
    main()
