"""
Numerical study for the paper:
  "Cost-Aware Capacity Reservation for Cloud Workloads with Intermittent
   Random Demand Surges: An Integrated Forecasting-Optimization System"

All results are computed from the project's own synthetic-but-realistic
database (data/cloud_optimizer.db, user aws-SYNTHETIC-001). Running this
script regenerates every figure (paper/figures/*.pdf) and the numeric
results file (paper/figures/results.json) cited in the manuscript.

Reproduce with:  python paper/numerical_study.py
"""
import json
import sqlite3
import warnings
import datetime as dt

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

DB = "/home/user/smart-cloud-optimizer/data/cloud_optimizer.db"
USER = "aws-SYNTHETIC-001"
FIGDIR = "/home/user/smart-cloud-optimizer/paper/figures"
RESULTS = {}

plt.rcParams.update({
    "figure.figsize": (6.2, 3.6), "font.size": 10, "axes.grid": True,
    "grid.alpha": 0.3, "axes.spines.top": False,
    "axes.spines.right": False, "savefig.bbox": "tight", "savefig.dpi": 200,
})


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
def load_demand():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT date, total_cost FROM daily_costs WHERE user_id=? ORDER BY date",
        (USER,),
    ).fetchall()
    con.close()
    dates = [dt.date.fromisoformat(r[0]) for r in rows]
    d = np.array([r[1] for r in rows], dtype=float)
    return dates, d


# --------------------------------------------------------------------------
# 1. Demand characterization (base vs. intermittent surge)
# --------------------------------------------------------------------------
def characterize(dates, d):
    n = len(d)
    base = float(np.median(np.sort(d)[: int(0.6 * n)]))   # base-level estimate
    mu, sd = float(d.mean()), float(d.std())
    surge_thr = float(np.median(d) + 2 * sd)
    surge_idx = np.where(d > surge_thr)[0]
    R = {
        "n_days": n,
        "date_start": dates[0].isoformat(), "date_end": dates[-1].isoformat(),
        "total": float(d.sum()), "mean": mu, "median": float(np.median(d)),
        "std": sd, "min": float(d.min()), "max": float(d.max()),
        "base_level": base, "peak_over_median": float(d.max() / np.median(d)),
        "surge_threshold": surge_thr, "n_surge_days": int(surge_idx.size),
        "surge_frac": float(surge_idx.size / n),
        "surge_dates": [dates[i].isoformat() for i in surge_idx],
        "cv": sd / mu,
    }
    # weekly seasonality
    dow = np.array([x.weekday() for x in dates])
    R["weekday_mean"] = float(d[dow < 5].mean())
    R["weekend_mean"] = float(d[dow >= 5].mean())
    RESULTS["demand"] = R

    # Figure 1: demand series with base and surge markers
    fig, ax = plt.subplots()
    ax.plot(dates, d, lw=0.9, color="#2b6cb0", label="Daily demand $D_t$")
    ax.axhline(base, color="#dd6b20", ls="--", lw=1.2,
               label=f"Base level (${base:.0f}/day)")
    ax.scatter([dates[i] for i in surge_idx], d[surge_idx], color="#c53030",
               s=22, zorder=5, label=f"Surge days (n={surge_idx.size})")
    ax.set_xlabel("Date"); ax.set_ylabel("On-demand-equivalent demand ($/day)")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.savefig(f"{FIGDIR}/fig1_demand_series.pdf")
    fig.savefig(f"{FIGDIR}/fig1_demand_series.png")
    plt.close(fig)
    return base, surge_idx


# --------------------------------------------------------------------------
# 2. Newsvendor capacity-reservation model on the real demand distribution
#    Cost of reserving baseline Q (paid every day at (1-delta)) and buying
#    the residual on-demand (price 1):  C(Q) = sum_t [(1-delta) Q + (D_t-Q)^+]
#    Optimal Q* = empirical delta-quantile of demand  (critical ratio = delta)
# --------------------------------------------------------------------------
def annual_cost(d, Q, delta):
    return float(np.sum((1 - delta) * Q + np.maximum(d - Q, 0.0)))

def newsvendor(d):
    T = len(d)
    cost_all_od = float(d.sum())                      # everything on-demand
    tiers = {"RI-1yr": 0.37, "RI-3yr": 0.60}          # real discount tiers
    out = {"cost_all_on_demand": cost_all_od, "horizon_days": T, "tiers": {}}

    for name, delta in tiers.items():
        Qstar = float(np.quantile(d, delta))          # closed-form optimum
        # verify against a fine grid search
        grid = np.linspace(d.min(), d.max(), 4000)
        costs = np.array([annual_cost(d, q, delta) for q in grid])
        Qgrid = float(grid[int(np.argmin(costs))])
        c_star = annual_cost(d, Qstar, delta)
        c_peak = annual_cost(d, d.max(), delta)       # reserve to cover peak
        c_mean = annual_cost(d, d.mean(), delta)      # naive: reserve the mean
        out["tiers"][name] = {
            "delta": delta,
            "Q_star_closed_form": Qstar,
            "Q_star_grid": Qgrid,
            "reserved_quantile": delta,
            "cost_optimal": c_star,
            "cost_reserve_peak": c_peak,
            "cost_reserve_mean": c_mean,
            "save_vs_od_pct": 100 * (cost_all_od - c_star) / cost_all_od,
            "save_vs_peak_pct": 100 * (c_peak - c_star) / c_peak,
            "reserved_cover_frac": float(np.mean(d <= Qstar)),
        }
    RESULTS["newsvendor"] = out

    # Figure 2: empirical CDF with optimal reservation quantiles
    ds = np.sort(d); cdf = np.arange(1, T + 1) / T
    fig, ax = plt.subplots()
    ax.plot(ds, cdf, color="#2b6cb0", lw=1.5)
    for name, delta in tiers.items():
        Q = np.quantile(d, delta)
        ax.axhline(delta, color="#718096", ls=":", lw=0.8)
        ax.axvline(Q, color="#c53030" if delta == 0.37 else "#dd6b20",
                   ls="--", lw=1.1,
                   label=f"{name}: $\\delta$={delta}, $Q^*$=\\${Q:.0f}")
    ax.set_xlabel("Demand $D$ (\\$/day)"); ax.set_ylabel("$F(D)$ (empirical CDF)")
    ax.legend(loc="lower right", fontsize=8)
    fig.savefig(f"{FIGDIR}/fig2_demand_cdf.pdf")
    fig.savefig(f"{FIGDIR}/fig2_demand_cdf.png")
    plt.close(fig)

    # Figure 3: cost curve C(Q) vs Q for the two tiers, optimum marked
    fig, ax = plt.subplots()
    grid = np.linspace(d.min(), d.max(), 600)
    for name, delta in tiers.items():
        costs = [annual_cost(d, q, delta) for q in grid]
        line, = ax.plot(grid, costs, lw=1.4, label=f"{name} ($\\delta$={delta})")
        Qs = np.quantile(d, delta)
        ax.scatter([Qs], [annual_cost(d, Qs, delta)], color=line.get_color(),
                   zorder=5, s=30)
    ax.set_xlabel("Reserved baseline capacity $Q$ (\\$/day)")
    ax.set_ylabel("Annual cost ($)")
    ax.legend(fontsize=8)
    fig.savefig(f"{FIGDIR}/fig3_cost_curve.pdf")
    fig.savefig(f"{FIGDIR}/fig3_cost_curve.png")
    plt.close(fig)

    # Figure 4: sweep optimal reserved quantile & savings vs discount delta
    deltas = np.linspace(0.05, 0.80, 60)
    save = [100 * (cost_all_od - annual_cost(d, np.quantile(d, x), x)) / cost_all_od
            for x in deltas]
    fig, ax1 = plt.subplots()
    ax1.plot(deltas, [np.quantile(d, x) for x in deltas], color="#2b6cb0",
             lw=1.5, label="Optimal reserved level $Q^*$")
    ax1.set_xlabel("Reserved-instance discount $\\delta$")
    ax1.set_ylabel("$Q^*$ (\\$/day)", color="#2b6cb0")
    ax2 = ax1.twinx(); ax2.grid(False)
    ax2.plot(deltas, save, color="#c53030", lw=1.5, ls="--",
             label="Cost saving vs. on-demand")
    ax2.set_ylabel("Saving vs. all-on-demand (%)", color="#c53030")
    for x in (0.37, 0.60):
        ax1.axvline(x, color="#718096", ls=":", lw=0.8)
    fig.savefig(f"{FIGDIR}/fig4_discount_sweep.pdf")
    fig.savefig(f"{FIGDIR}/fig4_discount_sweep.png")
    plt.close(fig)
    return out


# --------------------------------------------------------------------------
# 3. Reservation break-even (alternating-renewal / threshold-policy intuition)
#    An instance run a fraction u of the term should be reserved iff u >= 1-delta
# --------------------------------------------------------------------------
def break_even():
    out = {name: 1 - delta for name, delta in
           {"RI-1yr": 0.37, "RI-3yr": 0.60, "Spot": 0.70}.items()}
    RESULTS["break_even_utilization"] = out
    return out


# --------------------------------------------------------------------------
# 4. Forecasting cross-validation (reproduces ml_engine on the real series)
#    Walk-forward: initial=60, horizon=14, step=7  (project defaults)
# --------------------------------------------------------------------------
def mape(y, f):
    y = np.asarray(y, float); f = np.asarray(f, float)
    m = y != 0
    return float(np.mean(np.abs((y[m] - f[m]) / y[m])) * 100) if m.any() else np.nan

def rmse(y, f):
    return float(np.sqrt(np.mean((np.asarray(y, float) - np.asarray(f, float)) ** 2)))

def mae(y, f):
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(f, float))))

def forecast_models(train, horizon):
    """Return dict model_name -> point forecast array of length `horizon`."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    out = {}
    # Naive
    out["Naive"] = np.repeat(train[-1], horizon)
    # Seasonal naive (m=7)
    m = 7
    out["SeasonalNaive"] = np.array(
        [train[-(m - (i % m))] for i in range(horizon)])
    # ETS (additive trend + additive weekly seasonality)
    try:
        if len(train) >= 2 * m:
            fit = ExponentialSmoothing(train, trend="add", seasonal="add",
                                       seasonal_periods=m).fit(optimized=True)
        else:
            fit = ExponentialSmoothing(train, trend="add").fit(optimized=True)
        out["ETS"] = np.asarray(fit.forecast(horizon), float)
    except Exception:
        out["ETS"] = np.repeat(train[-1], horizon)
    # SARIMAX (1,1,1)(1,0,1,7)
    try:
        fit = SARIMAX(train, order=(1, 1, 1), seasonal_order=(1, 0, 1, m),
                      enforce_stationarity=False,
                      enforce_invertibility=False).fit(disp=False)
        out["SARIMAX"] = np.asarray(fit.forecast(horizon), float)
    except Exception:
        out["SARIMAX"] = np.repeat(train[-1], horizon)
    return out

def forecasting_cv(d, initial=60, horizon=14, step=7):
    names = ["Naive", "SeasonalNaive", "ETS", "SARIMAX"]
    scores = {k: {"mape": [], "rmse": [], "mae": []} for k in names}
    cutoff = initial; n = len(d); n_folds = 0
    while cutoff + horizon <= n:
        train, test = d[:cutoff], d[cutoff:cutoff + horizon]
        fc = forecast_models(train, horizon)
        for k in names:
            scores[k]["mape"].append(mape(test, fc[k]))
            scores[k]["rmse"].append(rmse(test, fc[k]))
            scores[k]["mae"].append(mae(test, fc[k]))
        cutoff += step; n_folds += 1
    table = {}
    for k in names:
        table[k] = {
            "mape_mean": float(np.nanmean(scores[k]["mape"])),
            "mape_std": float(np.nanstd(scores[k]["mape"])),
            "rmse_mean": float(np.nanmean(scores[k]["rmse"])),
            "mae_mean": float(np.nanmean(scores[k]["mae"])),
        }
    best = min(table, key=lambda k: table[k]["mape_mean"])
    RESULTS["forecasting"] = {"n_folds": n_folds, "initial": initial,
                              "horizon": horizon, "step": step,
                              "table": table, "best_model": best}

    # Figure 5: last-fold forecast vs actual for the best model
    cutoff = n - horizon
    train, test = d[:cutoff], d[cutoff:]
    fc = forecast_models(train, horizon)[best]
    fig, ax = plt.subplots()
    hist = 60
    ax.plot(range(cutoff - hist, cutoff), d[cutoff - hist:cutoff],
            color="#2b6cb0", lw=1.0, label="History")
    ax.plot(range(cutoff, n), test, color="#1a202c", lw=1.4, label="Actual")
    ax.plot(range(cutoff, n), fc, color="#c53030", lw=1.4, ls="--",
            label=f"{best} forecast")
    ax.axvline(cutoff, color="#718096", ls=":", lw=0.8)
    ax.set_xlabel("Day index"); ax.set_ylabel("Daily cost ($)")
    ax.legend(fontsize=8)
    fig.savefig(f"{FIGDIR}/fig5_forecast.pdf")
    fig.savefig(f"{FIGDIR}/fig5_forecast.png")
    plt.close(fig)
    return table, best


# --------------------------------------------------------------------------
# 5. System case study: recommendations actually produced by the optimizer
# --------------------------------------------------------------------------
def case_study():
    con = sqlite3.connect(DB)
    recs = con.execute(
        "SELECT recommendation_type, current_monthly_cost, estimated_monthly_cost,"
        " monthly_savings, savings_percent, confidence FROM recommendations"
        " WHERE user_id=?", (USER,)).fetchall()
    by_type = {}
    tot_save = tot_cur = 0.0
    for rt, cur, est, sav, pct, conf in recs:
        e = by_type.setdefault(rt, {"n": 0, "savings": 0.0})
        e["n"] += 1; e["savings"] += (sav or 0.0)
        tot_save += (sav or 0.0); tot_cur += (cur or 0.0)
    n_ai = con.execute("SELECT COUNT(*) FROM ai_recommendations WHERE user_id=?",
                       (USER,)).fetchone()[0]
    fleet = con.execute(
        "SELECT instance_type, COUNT(*), SUM(monthly_cost) FROM ec2_instances"
        " WHERE user_id=? GROUP BY instance_type", (USER,)).fetchall()
    pricing = con.execute(
        "SELECT instance_type, on_demand_monthly, reserved_1yr_monthly,"
        " reserved_3yr_monthly, spot_monthly FROM instance_pricing"
        " WHERE service='EC2' ORDER BY on_demand_monthly LIMIT 6").fetchall()
    con.close()
    RESULTS["case_study"] = {
        "n_recommendations": len(recs),
        "n_ai_recommendations": n_ai,
        "total_monthly_savings": tot_save,
        "total_current_monthly_cost": tot_cur,
        "savings_pct_of_optimized_scope": (100 * tot_save / tot_cur) if tot_cur else None,
        "by_type": by_type,
        "fleet": [{"type": t, "count": c, "monthly_cost": s} for t, c, s in fleet],
        "pricing_sample": [
            {"type": t, "on_demand": od, "ri_1yr": r1, "ri_3yr": r3, "spot": sp}
            for t, od, r1, r3, sp in pricing],
    }
    # implied discount tiers from the pricing table
    discs = []
    for t, od, r1, r3, sp in pricing:
        if od and r1 and r3 and sp:
            discs.append({"type": t, "ri1_disc": 1 - r1 / od,
                          "ri3_disc": 1 - r3 / od, "spot_disc": 1 - sp / od})
    RESULTS["case_study"]["implied_discounts"] = discs
    return RESULTS["case_study"]


# --------------------------------------------------------------------------
def main():
    dates, d = load_demand()
    characterize(dates, d)
    newsvendor(d)
    break_even()
    forecasting_cv(d)
    case_study()
    with open(f"{FIGDIR}/results.json", "w") as f:
        json.dump(RESULTS, f, indent=2)
    # console summary
    print("=== DEMAND ===")
    for k in ("n_days", "mean", "median", "std", "max", "base_level",
              "peak_over_median", "n_surge_days", "surge_frac",
              "weekday_mean", "weekend_mean", "cv"):
        print(f"  {k:18s} {RESULTS['demand'][k]}")
    print("\n=== NEWSVENDOR ===  all-on-demand annual = "
          f"${RESULTS['newsvendor']['cost_all_on_demand']:.0f}")
    for name, t in RESULTS["newsvendor"]["tiers"].items():
        print(f"  {name}: delta={t['delta']}  Q*=${t['Q_star_closed_form']:.2f}"
              f" (grid ${t['Q_star_grid']:.2f})  save_vs_od="
              f"{t['save_vs_od_pct']:.1f}%  save_vs_peak={t['save_vs_peak_pct']:.1f}%")
    print("\n=== BREAK-EVEN UTILIZATION (u*=1-delta) ===")
    print("  " + str(RESULTS["break_even_utilization"]))
    print("\n=== FORECASTING (folds="
          f"{RESULTS['forecasting']['n_folds']}, best={RESULTS['forecasting']['best_model']}) ===")
    for k, v in RESULTS["forecasting"]["table"].items():
        print(f"  {k:14s} MAPE={v['mape_mean']:5.2f}%  RMSE=${v['rmse_mean']:6.2f}"
              f"  MAE=${v['mae_mean']:6.2f}")
    cs = RESULTS["case_study"]
    print(f"\n=== CASE STUDY ===  recs={cs['n_recommendations']} ai={cs['n_ai_recommendations']}"
          f"  monthly_savings=${cs['total_monthly_savings']:.2f}")
    for rt, e in cs["by_type"].items():
        print(f"  {rt:24s} n={e['n']:2d}  save=${e['savings']:.2f}")
    print("  implied discounts:", cs["implied_discounts"][:2])
    print("\nWrote", f"{FIGDIR}/results.json", "and 5 figures.")


if __name__ == "__main__":
    main()
