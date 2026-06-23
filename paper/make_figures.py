#!/usr/bin/env python3
"""Generate all figures for the Smart Cloud Optimizer paper.

Figures are derived directly from the project database
(``data/cloud_optimizer.db``) and from the walk-forward cross-validation
results reported in ``documentation/forecasting_models.md``.  Running this
script regenerates every PDF under ``paper/figures``.

Usage:  python paper/make_figures.py
"""
import os
import sqlite3

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "data", "cloud_optimizer.db")
OUT = os.path.join(HERE, "figures")
USER = "aws-SYNTHETIC-001"

os.makedirs(OUT, exist_ok=True)
plt.rcParams.update(
    {
        "font.size": 9,
        "font.family": "serif",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "figure.dpi": 200,
        "savefig.bbox": "tight",
    }
)


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
def load_daily():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT date, total_cost FROM daily_costs WHERE user_id=? ORDER BY date",
        (USER,),
    ).fetchall()
    con.close()
    dates = np.array([r[0] for r in rows])
    cost = np.array([float(r[1]) for r in rows])
    return dates, cost


def load_service_costs():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT service, SUM(daily_cost) FROM service_costs WHERE user_id=? "
        "GROUP BY service ORDER BY SUM(daily_cost) DESC",
        (USER,),
    ).fetchall()
    con.close()
    return [r[0] for r in rows], [float(r[1]) for r in rows]


def load_savings_by_type():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT service, recommendation_type, SUM(monthly_savings) "
        "FROM recommendations WHERE user_id=? GROUP BY service, recommendation_type "
        "ORDER BY SUM(monthly_savings) DESC",
        (USER,),
    ).fetchall()
    con.close()
    return rows


# --------------------------------------------------------------------------- #
# Anomaly / surge detection (mirrors ml_engine/anomaly.py: rolling z-score)
# --------------------------------------------------------------------------- #
def detect_surges(values, window=30, threshold=3.0):
    s = np.asarray(values, dtype=float)
    flags = np.zeros(len(s), dtype=bool)
    for i in range(len(s)):
        lo = max(0, i - window)
        ref = s[lo : i + 1]
        if len(ref) < 5:
            continue
        mu, sd = ref.mean(), ref.std()
        if sd > 0 and abs(s[i] - mu) > threshold * sd:
            flags[i] = True
    return flags


# --------------------------------------------------------------------------- #
# Lightweight trend + weekly-seasonal forecaster (numpy only)
# --------------------------------------------------------------------------- #
def forecast(train, horizon, season=7):
    n = len(train)
    t = np.arange(n)
    # linear trend
    a, b = np.polyfit(t, train, 1)
    trend = a * t + b
    detr = train - trend
    # weekly seasonal index
    seas = np.array([detr[i::season].mean() for i in range(season)])
    seas -= seas.mean()
    resid = detr - seas[t % season]
    sigma = resid.std()
    # forecast
    ft = np.arange(n, n + horizon)
    fc = a * ft + b + seas[ft % season]
    ci = 1.96 * sigma
    return fc, ci


# --------------------------------------------------------------------------- #
# Figure 1 -- system architecture
# --------------------------------------------------------------------------- #
def fig_architecture():
    fig, ax = plt.subplots(figsize=(7.1, 2.7))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")

    def box(x, y, w, h, text, color):
        ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h,
                boxstyle="round,pad=0.4,rounding_size=1.2",
                linewidth=1.1, edgecolor="#333", facecolor=color,
            )
        )
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(
            FancyArrowPatch(
                (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11,
                linewidth=1.1, color="#444",
            )
        )

    box(1, 14, 17, 13,
        "Data Sources\nAWS Cost Explorer\nCloudWatch / Pricing\nEC2·RDS·S3·Lambda", "#e8f0fe")
    box(22, 14, 15, 13, "Collector\nIAM AssumeRole\n12-month pull", "#fce8e6")
    box(41, 14, 14, 13, "Storage\nSQLite\n30 tables", "#e6f4ea")
    box(59, 24, 17, 11, "Forecasting\n5 models +\nanomaly filter", "#fff3d6")
    box(59, 3, 17, 11, "Optimizer\nMILP + 8 rules\n+ LLM cold-start", "#fff3d6")
    box(81, 14, 16, 13, "Dashboard\nStreamlit\n5 pages", "#ede7f6")

    arrow(18, 20.5, 22, 20.5)
    arrow(37, 20.5, 41, 20.5)
    arrow(55, 22, 59, 27)
    arrow(55, 19, 59, 9)
    arrow(76, 29, 81, 23)
    arrow(76, 8, 81, 18)
    fig.savefig(os.path.join(OUT, "architecture.pdf"))
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Figure 2 -- demand surges in the daily cost signal
# --------------------------------------------------------------------------- #
def fig_surges():
    dates, cost = load_daily()
    flags = detect_surges(cost)
    x = np.arange(len(cost))
    fig, ax = plt.subplots(figsize=(7.1, 2.6))
    ax.plot(x, cost, color="#1a73e8", linewidth=0.9, label="Daily cost")
    ax.scatter(x[flags], cost[flags], color="#d93025", s=22, zorder=5,
               label="Detected surge (rolling 3$\\sigma$)")
    base = np.median(cost)
    ax.axhline(base, color="#5f6368", linestyle="--", linewidth=0.9,
               label=f"Base demand (median ${base:.0f}/day)")
    ax.set_xlabel("Day index (Jul 2024 -- Jun 2025)")
    ax.set_ylabel("Cost (USD/day)")
    ax.set_xlim(0, len(cost))
    ax.legend(loc="upper left", fontsize=7, framealpha=0.9)
    fig.savefig(os.path.join(OUT, "surges.pdf"))
    plt.close(fig)
    return int(flags.sum())


# --------------------------------------------------------------------------- #
# Figure 3 -- 30-day forecast vs. actual (holdout)
# --------------------------------------------------------------------------- #
def fig_forecast():
    dates, cost = load_daily()
    h = 30
    train, test = cost[:-h], cost[-h:]
    fc, ci = forecast(train, h)
    mape = np.mean(np.abs((test - fc) / test)) * 100
    n = len(cost)
    xt = np.arange(n - h)
    xf = np.arange(n - h, n)
    fig, ax = plt.subplots(figsize=(7.1, 2.6))
    ax.plot(xt[-90:], train[-90:], color="#1a73e8", linewidth=0.9, label="History")
    ax.plot(xf, test, color="#188038", linewidth=1.3, label="Actual")
    ax.plot(xf, fc, color="#d93025", linewidth=1.3, linestyle="--", label="Forecast")
    ax.fill_between(xf, fc - ci, fc + ci, color="#d93025", alpha=0.15,
                    label="95% interval")
    ax.set_xlabel("Day index")
    ax.set_ylabel("Cost (USD/day)")
    ax.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.9)
    ax.set_title(f"30-day holdout  (MAPE = {mape:.1f}%)", fontsize=9)
    fig.savefig(os.path.join(OUT, "forecast.pdf"))
    plt.close(fig)
    return mape


# --------------------------------------------------------------------------- #
# Figure 4 -- MAPE vs. horizon (from forecasting_models.md walk-forward CV)
# --------------------------------------------------------------------------- #
def fig_mape():
    horizon = [7, 14, 30, 60, 90, 120, 180, 240, 300]
    data = {
        "Naive":         [40.5, 22.9, 25.7, 25.5, 25.8, 32.0, 43.1, 30.9, 32.2],
        "Seasonal Naive":[16.0, 17.9, 14.6, 14.9, 13.1, 15.7, 16.0, 22.7, 16.8],
        "ETS":           [9.2, 10.5, 10.4, 10.8, 12.0, 13.0, 12.9, 20.6, 24.0],
        "Prophet":       [7.9, 9.8, 9.5, 22.2, 12.4, 34.5, 27.9, 26.8, 34.1],
    }
    styles = {
        "Naive": ("#9aa0a6", "o-"),
        "Seasonal Naive": ("#fbbc04", "s-"),
        "ETS": ("#188038", "^-"),
        "Prophet": ("#1a73e8", "D-"),
    }
    fig, ax = plt.subplots(figsize=(3.45, 2.6))
    for k, v in data.items():
        c, m = styles[k]
        ax.plot(horizon, v, m, color=c, markersize=3.5, linewidth=1.1, label=k)
    ax.set_xlabel("Forecast horizon (days)")
    ax.set_ylabel("MAPE (%)")
    ax.legend(fontsize=6.5, framealpha=0.9)
    fig.savefig(os.path.join(OUT, "mape.pdf"))
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Figure 5 -- savings breakdown
# --------------------------------------------------------------------------- #
def fig_savings():
    rows = load_savings_by_type()
    labels = [f"{s}\n{t.replace('_', ' ')}" for s, t, _ in rows]
    vals = [v for _, _, v in rows]
    colors = plt.cm.viridis(np.linspace(0.15, 0.85, len(vals)))
    fig, ax = plt.subplots(figsize=(3.45, 2.7))
    y = np.arange(len(vals))[::-1]
    ax.barh(y, vals, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6.5)
    for yi, v in zip(y, vals):
        ax.text(v + 5, yi, f"${v:.0f}", va="center", fontsize=6.5)
    ax.set_xlabel("Monthly savings (USD)")
    ax.set_xlim(0, max(vals) * 1.18)
    ax.grid(axis="y", visible=False)
    fig.savefig(os.path.join(OUT, "savings.pdf"))
    plt.close(fig)
    return sum(vals)


if __name__ == "__main__":
    fig_architecture()
    n_surge = fig_surges()
    mape = fig_forecast()
    fig_mape()
    total = fig_savings()
    print(f"surges detected : {n_surge}")
    print(f"holdout MAPE    : {mape:.2f}%")
    print(f"total savings   : ${total:.2f}/mo")
    print(f"figures written to {OUT}")
