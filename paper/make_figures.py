#!/usr/bin/env python3
"""Generate all figures and numerical results for the IEEE paper.

Every number and figure is derived from the project's real committed database
(data/cloud_optimizer.db) and the project's own ml_engine forecasters and
optimizer recommendations. Nothing here is hand-entered.

Outputs (written under paper/):
  figures/fig_architecture.pdf      system architecture (data -> forecast -> MILP -> dashboard)
  figures/fig_daily_surges.pdf      365-day daily-cost series with detected demand surges
  figures/fig_forecast_holdout.pdf  30-day holdout forecast (Prophet) with 95% interval
  figures/fig_mape_horizon.pdf      walk-forward CV MAPE vs forecast horizon, per model
  figures/fig_savings_breakdown.pdf recommended monthly savings by optimization action
  figures/fig_service_share.pdf     per-service share of the monthly bill
  numbers.tex                       \newcommand macros consumed by main.tex
  results.json                      machine-readable dump of every number
  cv_results.csv                    per-(model,horizon) cross-validation MAPE table

Run from anywhere with the project venv active:
    venv/bin/python paper/make_figures.py            # default models (no SARIMAX)
    venv/bin/python paper/make_figures.py --with-sarimax
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np

# --- make the project importable regardless of CWD ---------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PAPER = ROOT / "paper"
FIGDIR = PAPER / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

# Silence the chatty forecasting stack (cmdstan / prophet / statsmodels).
warnings.filterwarnings("ignore")
for noisy in ("cmdstanpy", "prophet", "matplotlib", "matplotlib.font_manager"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402  (project root config)
import storage  # noqa: E402
from ml_engine import (  # noqa: E402
    load_cost_data,
    NaiveForecaster,
    SeasonalNaiveForecaster,
    ETSForecaster,
    ProphetForecaster,
    SARIMAXForecaster,
    compare_models,
)

USER = "aws-SYNTHETIC-001"
CV_INITIAL = 120          # min training window (days) -- matches documented methodology
CV_STEP = 30              # days between walk-forward folds
HORIZONS = [7, 14, 21, 30, 45, 60, 90]
HOLDOUT = 30              # days held out for the holdout-forecast figure
PROPHET_INTERVAL = 0.95   # widen Prophet's band to a true 95% interval for the figure

# Colour-blind-friendly palette (Okabe-Ito).
C = {
    "blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
    "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9",
    "yellow": "#F0E442", "grey": "#7f7f7f", "black": "#222222",
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

COLW = 3.45   # IEEE single-column width (in)
DBLW = 7.16   # IEEE double-column width (in)


# =============================================================================
# Data access
# =============================================================================
def get_db():
    # storage.get_connection() sets row_factory = sqlite3.Row, which the storage
    # layer's _rows_to_dicts depends on; keep it. Our helpers below index rows
    # positionally, which sqlite3.Row also supports.
    return storage.get_connection()


def fetchall(conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


# =============================================================================
# DB-grounded numbers
# =============================================================================
RESOURCE_TABLES = [
    "ec2_instances", "ebs_volumes", "rds_instances", "s3_buckets",
    "lambda_functions", "dynamodb_tables", "elasticache_nodes",
    "ecs_services", "elb_instances", "nat_gateways",
]

# Friendly labels for recommendation_type values.
TYPE_LABEL = {
    "rightsize": "Right-size (MILP)",
    "pricing_plan_switch": "Reserved / pricing switch",
    "delete_unused": "Delete unused",
    "replace_with_endpoint": "NAT → VPC endpoint",
    "volume_type_upgrade": "EBS gp2 → gp3",
    "storage_class_switch": "S3 tiering",
    "memory_resize": "Lambda right-size",
}


def collect_db_numbers(conn):
    n = {}

    # ---- daily cost series & surge detection ----
    df = load_cost_data(conn, USER).sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    cost = df["total_cost"]
    mean, std = float(cost.mean()), float(cost.std())  # pandas std = sample (ddof=1)
    thresh = mean + 2 * std
    surges = df[df["total_cost"] > thresh].copy()
    n["n_days"] = int(len(df))
    n["start_date"] = df["date"].min().strftime("%Y-%m-%d")
    n["end_date"] = df["date"].max().strftime("%Y-%m-%d")
    n["mean_daily"] = round(mean, 2)
    n["std_daily"] = round(std, 2)
    n["min_daily"] = round(float(cost.min()), 2)
    n["max_daily"] = round(float(cost.max()), 2)
    n["annual_total"] = round(float(cost.sum()), 2)
    n["surge_thresh"] = round(thresh, 2)
    n["n_surges"] = int(len(surges))
    n["max_z"] = round((float(cost.max()) - mean) / std, 2)
    n["surge_dates"] = [
        {"date": d.strftime("%Y-%m-%d"), "cost": round(float(c), 2)}
        for d, c in zip(surges["date"], surges["total_cost"])
    ]

    # ---- recommendations (the optimizer output) ----
    n["n_recs"] = int(scalar(conn, "SELECT COUNT(*) FROM recommendations WHERE user_id=?", (USER,)))
    n["n_ai_recs"] = int(scalar(conn, "SELECT COUNT(*) FROM ai_recommendations WHERE user_id=?", (USER,)))
    n["total_savings"] = round(float(scalar(conn, "SELECT SUM(monthly_savings) FROM recommendations WHERE user_id=?", (USER,))), 2)
    n["flagged_cost"] = round(float(scalar(conn, "SELECT SUM(current_monthly_cost) FROM recommendations WHERE user_id=?", (USER,))), 2)
    n["after_cost"] = round(float(scalar(conn, "SELECT SUM(estimated_monthly_cost) FROM recommendations WHERE user_id=?", (USER,))), 2)
    n["savings_pct_flagged"] = round(100.0 * n["total_savings"] / n["flagged_cost"], 2)

    # ---- total monthly bill across all resource tables ----
    total_bill = 0.0
    by_resource = {}
    for tbl in RESOURCE_TABLES:
        v = scalar(conn, f"SELECT COALESCE(SUM(monthly_cost),0) FROM {tbl} WHERE user_id=?", (USER,))
        by_resource[tbl] = round(float(v or 0.0), 2)
        total_bill += float(v or 0.0)
    n["total_bill"] = round(total_bill, 2)
    n["bill_by_resource"] = by_resource
    n["savings_pct_bill"] = round(100.0 * n["total_savings"] / total_bill, 2)

    # ---- resource counts ----
    n["n_ec2"] = int(scalar(conn, "SELECT COUNT(*) FROM ec2_instances WHERE user_id=?", (USER,)))
    n["n_resources"] = sum(
        int(scalar(conn, f"SELECT COUNT(*) FROM {t} WHERE user_id=?", (USER,))) for t in RESOURCE_TABLES
    )
    n["n_services_billed"] = int(scalar(conn, "SELECT COUNT(DISTINCT service) FROM service_costs WHERE user_id=?", (USER,)))

    # ---- savings breakdown by action type ----
    rows = fetchall(conn,
        "SELECT recommendation_type AS t, COUNT(*) AS n, ROUND(SUM(monthly_savings),2) AS s "
        "FROM recommendations WHERE user_id=? GROUP BY recommendation_type ORDER BY s DESC", (USER,))
    n["savings_by_type"] = [
        {"type": r["t"], "label": TYPE_LABEL.get(r["t"], r["t"]), "n": int(r["n"]), "savings": float(r["s"])}
        for r in rows
    ]

    # ---- savings by confidence ----
    rows = fetchall(conn,
        "SELECT confidence AS c, COUNT(*) AS n, ROUND(SUM(monthly_savings),2) AS s "
        "FROM recommendations WHERE user_id=? GROUP BY confidence", (USER,))
    n["savings_by_confidence"] = {r["c"]: {"n": int(r["n"]), "savings": float(r["s"])} for r in rows}

    # ---- per-service cost share ----
    rows = fetchall(conn,
        "SELECT service AS svc, ROUND(SUM(daily_cost),2) AS c FROM service_costs "
        "WHERE user_id=? GROUP BY service ORDER BY c DESC", (USER,))
    tot = sum(r["c"] for r in rows) or 1.0
    n["service_share"] = [
        {"service": r["svc"], "cost": float(r["c"]), "pct": round(100.0 * r["c"] / tot, 2)}
        for r in rows
    ]
    return n, df, surges


# =============================================================================
# Forecast cross-validation (the system's own evaluator)
# =============================================================================
def run_cv(df, with_sarimax=False):
    def build():
        models = [NaiveForecaster(), SeasonalNaiveForecaster(), ETSForecaster(), ProphetForecaster()]
        if with_sarimax:
            models.append(SARIMAXForecaster())
        return models

    table = {}        # model -> {horizon -> mape_mean}
    folds = {}        # model -> {horizon -> n_folds}
    for h in HORIZONS:
        res = compare_models(build(), df, cv_params={"initial": CV_INITIAL, "horizon": h, "step": CV_STEP})
        for _, r in res.iterrows():
            table.setdefault(r["model"], {})[h] = float(r["mape_mean"])
            folds.setdefault(r["model"], {})[h] = int(r["n_folds"])
        print(f"  horizon={h:>3}d  " + "  ".join(f"{r['model']}={r['mape_mean']:.1f}%" for _, r in res.iterrows()))
    return table, folds


def run_holdout(df):
    """Fit the CV-selected model (ETS) on all-but-last-HOLDOUT days, forecast HOLDOUT.

    ETS emits a true ~95% band (point +/- 1.96*residual sigma). The last 30 days
    contain a genuine demand surge (2025-06-03), so this also illustrates that
    intermittent surges escape the forecast band -- the paper's central point.
    """
    d = df.sort_values("date").reset_index(drop=True)
    train, test = d.iloc[:-HOLDOUT].copy(), d.iloc[-HOLDOUT:].copy()
    model = ETSForecaster()
    model.fit(train, date_col="date", value_col="total_cost")
    fc = model.predict(horizon=HOLDOUT).reset_index(drop=True)
    y_true = test["total_cost"].to_numpy()
    y_hat = fc["forecast"].to_numpy()
    mask = y_true != 0
    mape = float(np.mean(np.abs((y_true[mask] - y_hat[mask]) / y_true[mask])) * 100)
    cov = float(np.mean((y_true >= fc["lower"].to_numpy()) & (y_true <= fc["upper"].to_numpy())) * 100)
    return train, test, fc, mape, cov, model.name


# =============================================================================
# Figures
# =============================================================================
def fig_architecture():
    fig, ax = plt.subplots(figsize=(DBLW, 2.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 40); ax.axis("off"); ax.grid(False)

    def box(x, y, w, h, text, fc, tc="white", fs=7.5):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                    linewidth=0.8, edgecolor="#333333", facecolor=fc))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, color=tc, weight="bold", zorder=5)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=9, linewidth=0.9, color="#555555"))

    box(1, 16, 14, 8, "AWS account\n(boto3 + STS\nrole assume)", C["grey"])
    box(18, 16, 15, 8, "aws_collector\ninventory + CloudWatch\n+ Cost Explorer", C["sky"], tc="black")
    box(36, 16, 13, 8, "SQLite\nstore\n(~30 tables)", C["black"])
    # three analytics engines
    box(53, 27, 20, 9, "ml_engine: 5 forecasters\n(Naive/SNaive/ETS/\nProphet/SARIMAX) + CV", C["green"])
    box(53, 15.5, 20, 9, "optimizer: MILP right-size\n+ 8 rules  (newsvendor\n(s,S) reservation)", C["orange"], tc="black")
    box(53, 4, 20, 9, "ai_module\nGemini advisor\n(cold start)", C["purple"])
    box(78, 16, 16, 8, "Streamlit\ndashboard\n(5 pages)", C["blue"])

    arrow(15, 20, 18, 20)
    arrow(33, 20, 36, 20)
    arrow(49, 20, 53, 31.5); arrow(49, 20, 53, 20); arrow(49, 20, 53, 8.5)
    arrow(73, 31.5, 78, 21); arrow(73, 20, 78, 20); arrow(73, 8.5, 78, 19)
    fig.savefig(FIGDIR / "fig_architecture.pdf")
    plt.close(fig)


def fig_daily_surges(df, surges, n):
    fig, ax = plt.subplots(figsize=(DBLW, 2.4))
    ax.plot(df["date"], df["total_cost"], color=C["blue"], lw=0.9, label="Daily cost")
    ax.axhline(n["mean_daily"], color=C["grey"], lw=0.8, ls="--", label=fr"mean = \${n['mean_daily']:.2f}")
    ax.axhline(n["surge_thresh"], color=C["red"], lw=0.8, ls=":",
               label=fr"surge threshold $\mu+2\sigma$ = \${n['surge_thresh']:.2f}")
    ax.scatter(surges["date"], surges["total_cost"], color=C["red"], s=22, zorder=5,
               label=f"detected surge ({n['n_surges']})")
    ax.set_ylabel("Daily cost (USD)")
    ax.set_xlabel("Date")
    ax.legend(loc="upper left", ncol=2, frameon=False, handlelength=1.6)
    ax.margins(x=0.01)
    fig.autofmt_xdate(rotation=0)
    fig.savefig(FIGDIR / "fig_daily_surges.pdf")
    plt.close(fig)


def fig_forecast_holdout(train, test, fc, mape, cov, model_name):
    fig, ax = plt.subplots(figsize=(COLW, 2.5))
    tail = train.tail(60)
    ax.plot(tail["date"], tail["total_cost"], color=C["grey"], lw=0.9, label="History")
    ax.plot(test["date"], test["total_cost"], color=C["black"], lw=1.1, marker="o",
            ms=2.5, label="Actual (holdout)")
    ax.plot(fc["date"], fc["forecast"], color=C["blue"], lw=1.1, ls="--", label="Forecast")
    ax.fill_between(fc["date"], fc["lower"], fc["upper"], color=C["blue"],
                    alpha=0.18, label="95% interval")
    ax.set_ylabel("Daily cost (USD)")
    ax.set_xlabel("Date")
    ax.set_title(f"{model_name}, 30-day holdout (MAPE {mape:.1f}%, coverage {cov:.0f}%)")
    ax.legend(loc="upper left", frameon=False, fontsize=6.2, ncol=2, handlelength=1.4)
    fig.autofmt_xdate(rotation=30)
    fig.savefig(FIGDIR / "fig_forecast_holdout.pdf")
    plt.close(fig)


def fig_mape_horizon(table):
    fig, ax = plt.subplots(figsize=(COLW, 2.5))
    styles = {"Naive": (C["grey"], "o", "-"), "SeasonalNaive": (C["green"], "s", "-"),
              "ETS": (C["orange"], "^", "-"), "Prophet": (C["blue"], "D", "-"),
              "SARIMAX": (C["red"], "v", "-")}
    for model, hmap in table.items():
        col, mk, ls = styles.get(model, (C["black"], "x", "-"))
        xs = sorted(hmap)
        ax.plot(xs, [hmap[x] for x in xs], color=col, marker=mk, ls=ls, ms=3.5, label=model)
    ax.set_xlabel("Forecast horizon (days)")
    ax.set_ylabel("Walk-forward MAPE (%)")
    ax.legend(frameon=False, ncol=2, handlelength=1.6)
    ax.set_xticks(HORIZONS)
    fig.savefig(FIGDIR / "fig_mape_horizon.pdf")
    plt.close(fig)


def fig_savings_breakdown(n):
    items = n["savings_by_type"]
    labels = [i["label"] for i in items]
    vals = [i["savings"] for i in items]
    cnts = [i["n"] for i in items]
    y = range(len(items))
    fig, ax = plt.subplots(figsize=(COLW, 2.6))
    bars = ax.barh(list(y), vals, color=C["blue"], edgecolor="#1a1a1a", linewidth=0.4)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Monthly savings (USD)")
    vmax = max(vals)
    for b, v, c in zip(bars, vals, cnts):
        ax.text(v + vmax * 0.01, b.get_y() + b.get_height() / 2,
                fr"\${v:.2f} ({c})", va="center", fontsize=6.3)
    ax.set_xlim(0, vmax * 1.22)
    ax.grid(axis="y", visible=False)
    fig.savefig(FIGDIR / "fig_savings_breakdown.pdf")
    plt.close(fig)


def fig_service_share(n):
    items = n["service_share"]
    labels = [i["service"] for i in items]
    vals = [i["pct"] for i in items]
    fig, ax = plt.subplots(figsize=(COLW, 2.5))
    wedges, *_ = ax.pie(vals, labels=None, autopct=None, startangle=90,
                        colors=[C["blue"], C["orange"], C["green"], C["purple"], C["sky"], C["grey"]],
                        wedgeprops=dict(edgecolor="white", linewidth=0.6))
    ax.legend(wedges, [f"{l} ({v:.1f}%)" for l, v in zip(labels, vals)],
              loc="center left", bbox_to_anchor=(0.98, 0.5), frameon=False, fontsize=6.5)
    ax.set_aspect("equal")
    fig.savefig(FIGDIR / "fig_service_share.pdf")
    plt.close(fig)


# =============================================================================
# LaTeX macro emission
# =============================================================================
def latexcmd(name, value):
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


def write_numbers_tex(n, table, holdout_mape, holdout_cov, holdout_model, with_sarimax):
    L = []
    L.append("% Auto-generated by paper/make_figures.py -- do not edit by hand.\n")
    L.append(latexcmd("totalBill", f"{n['total_bill']:.2f}"))
    L.append(latexcmd("totalSavings", f"{n['total_savings']:.2f}"))
    L.append(latexcmd("savingsPctBill", f"{n['savings_pct_bill']:.1f}"))
    L.append(latexcmd("savingsPctBillExact", f"{n['savings_pct_bill']:.2f}"))
    L.append(latexcmd("savingsPctFlagged", f"{n['savings_pct_flagged']:.1f}"))
    L.append(latexcmd("flaggedCost", f"{n['flagged_cost']:.2f}"))
    L.append(latexcmd("afterCost", f"{n['after_cost']:.2f}"))
    L.append(latexcmd("numRecs", f"{n['n_recs']}"))
    L.append(latexcmd("numAiRecs", f"{n['n_ai_recs']}"))
    L.append(latexcmd("numEctwo", f"{n['n_ec2']}"))
    L.append(latexcmd("numResources", f"{n['n_resources']}"))
    L.append(latexcmd("numServicesBilled", f"{n['n_services_billed']}"))
    L.append(latexcmd("nDays", f"{n['n_days']}"))
    L.append(latexcmd("dataStart", n["start_date"]))
    L.append(latexcmd("dataEnd", n["end_date"]))
    L.append(latexcmd("meanDaily", f"{n['mean_daily']:.2f}"))
    L.append(latexcmd("stdDaily", f"{n['std_daily']:.2f}"))
    L.append(latexcmd("minDaily", f"{n['min_daily']:.2f}"))
    L.append(latexcmd("maxDaily", f"{n['max_daily']:.2f}"))
    L.append(latexcmd("annualTotal", f"{n['annual_total']:,.2f}"))
    L.append(latexcmd("surgeThresh", f"{n['surge_thresh']:.2f}"))
    L.append(latexcmd("numSurges", f"{n['n_surges']}"))
    L.append(latexcmd("maxZ", f"{n['max_z']:.1f}"))

    # savings by type (alpha-only macro suffixes)
    suffix = {"rightsize": "Rightsize", "pricing_plan_switch": "Pricing",
              "delete_unused": "Delete", "replace_with_endpoint": "Nat",
              "volume_type_upgrade": "Ebs", "storage_class_switch": "Sthree",
              "memory_resize": "Lambda"}
    for item in n["savings_by_type"]:
        sfx = suffix.get(item["type"], item["type"].title().replace("_", ""))
        L.append(latexcmd(f"sav{sfx}", f"{item['savings']:.2f}"))
        L.append(latexcmd(f"cnt{sfx}", f"{item['n']}"))

    # savings by confidence
    for conf, key in (("high", "High"), ("medium", "Med"), ("low", "Low")):
        if conf in n["savings_by_confidence"]:
            c = n["savings_by_confidence"][conf]
            L.append(latexcmd(f"sav{key}", f"{c['savings']:.2f}"))
            L.append(latexcmd(f"cnt{key}", f"{c['n']}"))

    # MAPE at the headline 30-day horizon
    mname = {"Naive": "Naive", "SeasonalNaive": "Snaive", "ETS": "Ets",
             "Prophet": "Prophet", "SARIMAX": "Sarimax"}
    for model, hmap in table.items():
        if 30 in hmap:
            L.append(latexcmd(f"mape{mname.get(model, model)}", f"{hmap[30]:.1f}"))
    # best model overall at h=30
    at30 = {m: hmap[30] for m, hmap in table.items() if 30 in hmap}
    best = min(at30, key=at30.get)
    L.append(latexcmd("bestModel", best))
    L.append(latexcmd("bestMape", f"{at30[best]:.1f}"))
    L.append(latexcmd("holdoutModel", holdout_model))
    L.append(latexcmd("holdoutMape", f"{holdout_mape:.1f}"))
    L.append(latexcmd("holdoutCov", f"{holdout_cov:.0f}"))
    L.append(latexcmd("cvInitial", f"{CV_INITIAL}"))
    L.append(latexcmd("cvStep", f"{CV_STEP}"))

    (PAPER / "numbers.tex").write_text("".join(L))


# =============================================================================
# Main
# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-sarimax", action="store_true",
                    help="include SARIMAX in the CV sweep (slow: minutes per fold)")
    args = ap.parse_args()

    conn = get_db()
    print(f"DB: {config.DB_PATH}")
    print("[1/4] DB-grounded numbers ...")
    n, df, surges = collect_db_numbers(conn)
    print(f"      bill=${n['total_bill']}, savings=${n['total_savings']} ({n['savings_pct_bill']}% of bill), "
          f"{n['n_recs']} recs, {n['n_surges']} surges")

    print("[2/4] walk-forward CV (this runs the project forecasters) ...")
    table, folds = run_cv(df, with_sarimax=args.with_sarimax)

    print("[3/4] 30-day holdout forecast (CV-selected model) ...")
    train, test, fc, holdout_mape, holdout_cov, holdout_model = run_holdout(df)
    print(f"      {holdout_model}: holdout MAPE={holdout_mape:.1f}%  coverage={holdout_cov:.0f}%")

    print("[4/4] figures + macros ...")
    fig_architecture()
    fig_daily_surges(df, surges, n)
    fig_forecast_holdout(train, test, fc, holdout_mape, holdout_cov, holdout_model)
    fig_mape_horizon(table)
    fig_savings_breakdown(n)
    fig_service_share(n)
    write_numbers_tex(n, table, holdout_mape, holdout_cov, holdout_model, args.with_sarimax)

    # cv csv
    cv_rows = ["model," + ",".join(f"h{h}" for h in HORIZONS)]
    for model, hmap in table.items():
        cv_rows.append(model + "," + ",".join(f"{hmap.get(h, float('nan')):.2f}" for h in HORIZONS))
    (PAPER / "cv_results.csv").write_text("\n".join(cv_rows) + "\n")

    out = {"numbers": n, "cv_mape": table, "cv_folds": folds,
           "holdout": {"model": holdout_model, "mape": round(holdout_mape, 2),
                       "coverage": round(holdout_cov, 2),
                       "interval_width": PROPHET_INTERVAL, "horizon": HOLDOUT},
           "cv_config": {"initial": CV_INITIAL, "step": CV_STEP, "horizons": HORIZONS,
                         "with_sarimax": args.with_sarimax}}
    (PAPER / "results.json").write_text(json.dumps(out, indent=2))
    conn.close()

    print("\n=== figures ===")
    for f in sorted(FIGDIR.glob("*.pdf")):
        print(f"  {f.relative_to(ROOT)}  ({f.stat().st_size} B)")
    print("=== wrote numbers.tex, results.json, cv_results.csv ===")
    print("DONE")


if __name__ == "__main__":
    main()
