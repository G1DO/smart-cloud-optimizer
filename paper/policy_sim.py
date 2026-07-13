#!/usr/bin/env python3
"""Reservation-policy cost-proxy simulation for the paper.

Replays a timestamped empirical proxy series under competing reservation
policies and reports realized out-of-sample mapped cost across
reserved-discount levels (gamma = w_T / w_0). Policies select a commitment
proxy Q on a chronological TRAIN split and are charged on the TEST split --
no policy sees the future.

Policies:
  OD    on-demand only (Q = 0)                         -- the do-nothing baseline
  HEUR  counterfactual Q = q_{0.95}(train) * 1.3       -- reused sizing rule
  NV    newsvendor optimum: Q = (1-gamma) train quantile (closed form)
  SAA   two-stage stochastic program (PuLP/CBC, scenarios = train periods)
        -- external-method baseline in the spirit of Chaisiri et al. (2012)
  LOOK7/30/60
        paper-side recency-window baselines: fit the newsvendor fractile to
        the trailing 7/30/60 days of training
  DUAL  dual-level (Q0, Q1) SAA: base + surge-only supplementary proxy
  LB    perfect-information lower bound: gamma * E[X_test]

The DB-backed arm uses daily account cost X_t in USD/day, so Q is a
committed-spend proxy in USD/day. The restored Rnd arm uses hourly aggregate
CPU demand X_t in MHz, so Q is in MHz. Costs retain the input scale after
normalization by the on-demand rate; percentages of the on-demand-only
baseline are dimensionless. These simulations evaluate relative temporal
policy behavior, not provider billing or physical allocation.

Usage:
  venv/bin/python paper/policy_sim.py                       # synthetic account from the DB
  venv/bin/python paper/policy_sim.py --csv d.csv --prefix ext --gamma-star 0.63

Outputs (under paper/): figures/fig_policy_gamma{suffix}.pdf,
policy_tabular{suffix}.tex, numbers_policy{suffix}.tex,
results_policy{suffix}.json. Deterministic: no randomness anywhere.
"""
from __future__ import annotations

import argparse
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

USER = "aws-SYNTHETIC-001"
TRAIN_FRAC = 0.6
GAMMAS = [round(g, 2) for g in np.arange(0.50, 0.96, 0.05)]
TABLE_GAMMAS = [0.60, 0.70, 0.80, 0.90]
DAYS_PER_MONTH = 365.0 / 12.0
LOOKBACK_DAYS = (7, 30, 60)

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


def load_demand(csv: str | None) -> pd.DataFrame:
    if csv:
        df = pd.read_csv(csv)
        df.columns = ["date", "value"]
    else:
        import storage
        from ml_engine import load_cost_data

        conn = storage.get_connection()
        df = load_cost_data(conn, USER)[["date", "total_cost"]]
        df.columns = ["date", "value"]
        conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def gamma_star_from_db() -> float:
    """Mean reserved-1yr / on-demand ratio in the pricing catalog (as in
    make_figures.py)."""
    import storage

    conn = storage.get_connection()
    rows = conn.execute(
        "SELECT reserved_1yr_monthly, on_demand_monthly FROM instance_pricing "
        "WHERE reserved_1yr_monthly IS NOT NULL AND on_demand_monthly > 0"
    ).fetchall()
    conn.close()
    ratios = [r[0] / r[1] for r in rows if r[1]]
    return round(sum(ratios) / len(ratios), 2)


def periods_per_day(dates: pd.Series) -> int:
    ts = pd.to_datetime(dates).sort_values().drop_duplicates()
    if len(ts) < 2:
        return 1
    step = ts.diff().dropna().median()
    if not isinstance(step, pd.Timedelta) or step <= pd.Timedelta(0):
        return 1
    return max(1, int(round(pd.Timedelta(days=1) / step)))


def lookback_Q(train: np.ndarray, gamma: float, days: int, periods_per_day_: int) -> tuple[float, int]:
    periods = max(1, min(len(train), int(days * periods_per_day_)))
    window = np.asarray(train, dtype=float)[-periods:]
    return pl.newsvendor_K(window, gamma), periods


def evaluate(train: np.ndarray, test: np.ndarray, surge_train: np.ndarray,
             surge_test: np.ndarray, thresh: float, gamma: float,
             periods_per_day_: int) -> dict:
    """Size every policy on train and charge it on test.

    Q and mapped cost retain the empirical input-series units after
    normalization by the on-demand rate. DUAL assumes the surge state is
    observable at execution time (the
    state-modulated information structure of the reference model) and is
    therefore an upper bound; DUALC uses the same (Q0, Q1) proxy commitments but
    activates the supplementary tier causally, on the previous period's
    threshold signal.
    """
    Q_heur = pl.heuristic_K(train)
    Q_nv = pl.newsvendor_K(train, gamma)
    Q_saa = pl.saa_K(train, gamma)
    Q0, Q1 = pl.saa_dual(train, surge_train, gamma)
    lookbacks = {
        days: lookback_Q(train, gamma, days, periods_per_day_)
        for days in LOOKBACK_DAYS
    }
    Q_look = {f"LOOK{days}": q for days, (q, _) in lookbacks.items()}
    cost_look = {
        f"LOOK{days}": pl.policy_cost(test, q, gamma)
        for days, (q, _) in lookbacks.items()
    }
    return {
        "gamma": gamma,
        "Q": {
            "HEUR": Q_heur,
            "NV": Q_nv,
            "SAA": Q_saa,
            **Q_look,
            "DUAL0": Q0,
            "DUAL1": Q1,
        },
        "lookback_periods": {str(days): periods for days, (_, periods) in lookbacks.items()},
        "cost": {
            "OD": float(np.mean(test)),
            "HEUR": pl.policy_cost(test, Q_heur, gamma),
            "NV": pl.policy_cost(test, Q_nv, gamma),
            "SAA": pl.policy_cost(test, Q_saa, gamma),
            **cost_look,
            "DUAL": pl.dual_policy_cost(test, surge_test, Q0, Q1, gamma),
            "DUALC": pl.dual_policy_cost_causal(test, thresh, Q0, Q1, gamma),
            "LB": pl.clairvoyant_lb(test, gamma),
        },
    }


def fig_policy_gamma(results: list[dict], gamma_star: float, suffix: str):
    od = {r["gamma"]: r["cost"]["OD"] for r in results}
    series = {
        "HEUR": (C["red"], "^", "-", "P95 $\\times$ 1.3 counterfactual"),
        "NV": (C["blue"], "o", "-", "newsvendor $1{-}\\gamma$"),
        "DUAL": (C["green"], "s", "-", "dual $(Q_0,Q_1)$, observable state"),
        "DUALC": (C["green"], "d", "--", "dual $(Q_0,Q_1)$, lagged signal"),
        "LB": (C["grey"], None, ":", "perfect-information bound"),
    }
    fig, ax = plt.subplots(figsize=(COLW, 2.4))
    xs = [r["gamma"] for r in results]
    for key, (col, mk, ls, label) in series.items():
        ys = [100.0 * r["cost"][key] / od[r["gamma"]] for r in results]
        ax.plot(xs, ys, color=col, marker=mk, ms=3, ls=ls, label=label)
    # SAA coincides with NV by construction; show it as sparse markers on top.
    ys_saa = [100.0 * r["cost"]["SAA"] / od[r["gamma"]] for r in results]
    ax.plot(xs, ys_saa, color=C["black"], marker="x", ms=4, ls="none",
            label="SAA stochastic program")
    ax.axvline(gamma_star, color=C["grey"], lw=0.8, ls="--")
    ax.text(gamma_star + 0.005, ax.get_ylim()[0] + 2, f"$\\gamma^*{{=}}{gamma_star}$",
            fontsize=6.5, color=C["grey"])
    ax.set_xlabel(r"reserved/on-demand price ratio $\gamma = w_T/w_0$")
    ax.set_ylabel("held-out mapped cost (% of on-demand)")
    ax.legend(frameon=False, fontsize=6.2, handlelength=1.6)
    fig.savefig(FIGDIR / f"fig_policy_gamma{suffix}.pdf")
    plt.close(fig)


def write_policy_table(results: list[dict], suffix: str):
    by_gamma = {r["gamma"]: r for r in results}
    rows = [("HEUR", r"P95 $\times$ 1.3 counterfactual"),
            ("NV", r"newsvendor $1{-}\gamma$"),
            ("SAA", "SAA stochastic program"),
            ("LOOK7", "7-day recency-window replay"),
            ("LOOK30", "30-day recency-window replay"),
            ("LOOK60", "60-day recency-window replay"),
            ("DUAL", r"dual $(Q_0,Q_1)$, obs.\ state"),
            ("DUALC", r"dual $(Q_0,Q_1)$, lagged signal"),
            ("LB", "perfect-information bound")]
    # bold the best policy that needs no contemporaneous surge-state knowledge
    implementable = ("HEUR", "NV", "SAA", "LOOK7", "LOOK30", "LOOK60", "DUALC")
    out = [r"\setlength{\tabcolsep}{4pt}",
           r"\begin{tabular}{@{}l " + "r " * len(TABLE_GAMMAS) + r"@{}}", r"\toprule"]
    out.append("Policy & " + " & ".join(fr"$\gamma{{=}}{g:.2f}$" for g in TABLE_GAMMAS) + r" \\")
    out.append(r"\midrule")
    for key, label in rows:
        cells = []
        for g in TABLE_GAMMAS:
            r = by_gamma[g]
            pct = 100.0 * r["cost"][key] / r["cost"]["OD"]
            best = key in implementable and all(
                r["cost"][key] <= r["cost"][k2] + 1e-12 for k2 in implementable if k2 != key)
            s = f"{pct:.1f}"
            cells.append(f"\\textbf{{{s}}}" if best else s)
        out.append(f"{label} & " + " & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / f"policy_tabular{suffix}.tex").write_text("\n".join(out) + "\n")


def latexcmd(name, value):
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


POLICY_MACRO_SUFFIX = {
    "HEUR": "Heur",
    "NV": "Nv",
    "SAA": "Saa",
    "LOOK7": "LookSeven",
    "LOOK30": "LookThirty",
    "LOOK60": "LookSixty",
    "DUAL": "Dual",
    "DUALC": "Dualc",
    "LB": "Lb",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="timestamped proxy CSV (date,value); default: DB series")
    ap.add_argument("--prefix", default="pol", help="LaTeX macro prefix (letters only)")
    ap.add_argument("--suffix", default="", help="output filename suffix, e.g. _ext")
    ap.add_argument("--gamma-star", type=float, default=None,
                    help="headline gamma; default: DB catalog ratio")
    ap.add_argument("--holds", default="1",
                    help="comma-separated minimum supplementary-contract terms "
                         "(periods) for the DUALC hold sensitivity")
    ap.add_argument("--dollars", action="store_true", default=None,
                    help="series is USD/day; emit $/month macros (default for DB mode)")
    args = ap.parse_args()

    df = load_demand(args.csv)
    gamma_star = args.gamma_star if args.gamma_star is not None else gamma_star_from_db()
    dollars = args.dollars if args.dollars is not None else (args.csv is None)
    if args.csv is None:
        empirical_mapping = {
            "series_notation": "X_t",
            "commitment_notation": "Q",
            "series_role": "daily account-cost demand proxy",
            "input_unit": "USD/day",
            "sampling_period": "day",
            "commitment_unit": "USD/day",
            "mapped_cost_unit": "USD/day proxy units",
            "lower_bound": "gamma * mean(X_test), with period-specific Q_t = X_t",
            "lower_bound_unit": "USD/day proxy units",
            "percentage_unit": "% of the within-arm on-demand-only mapped cost",
            "interpretation": (
                "temporal policy behavior on a cost-proxy series; not provider "
                "billing or physical-capacity allocation"
            ),
        }
    elif Path(args.csv).name == "trace_rnd_hourly.csv":
        empirical_mapping = {
            "series_notation": "X_t",
            "commitment_notation": "Q",
            "series_role": "hourly aggregate CPU-demand proxy",
            "input_unit": "MHz",
            "sampling_period": "hour",
            "commitment_unit": "MHz",
            "mapped_cost_unit": (
                "MHz-equivalent per hourly period, normalized by the on-demand rate"
            ),
            "lower_bound": "gamma * mean(X_test), with period-specific Q_t = X_t",
            "lower_bound_unit": (
                "on-demand-rate-normalized MHz-equivalent units per hourly period"
            ),
            "percentage_unit": "% of the within-arm on-demand-only mapped cost",
            "interpretation": (
                "aggregate trace-policy simulation; not provider billing or "
                "resource-level physical allocation"
            ),
        }
    else:
        empirical_mapping = {
            "series_notation": "X_t",
            "commitment_notation": "Q",
            "series_role": "CSV demand proxy",
            "input_unit": "source-series units",
            "sampling_period": "inferred from timestamps",
            "commitment_unit": "source-series units",
            "mapped_cost_unit": "source-series units normalized by the on-demand rate",
            "lower_bound": "gamma * mean(X_test), with period-specific Q_t = X_t",
            "lower_bound_unit": "source-series units normalized by the on-demand rate",
            "percentage_unit": "% of the within-arm on-demand-only mapped cost",
            "interpretation": "paper-side proxy simulation; not provider billing",
        }

    n = len(df)
    n_train = int(round(n * TRAIN_FRAC))
    train = df["value"].to_numpy(dtype=float)[:n_train]
    test = df["value"].to_numpy(dtype=float)[n_train:]
    ppd = periods_per_day(df["date"])

    thresh = float(train.mean() + 2 * train.std(ddof=1))
    surge_train = train > thresh
    surge_test = test > thresh
    print(f"n={n} train={n_train} test={len(test)} surge_thresh={thresh:.2f} "
          f"(train surges={int(surge_train.sum())}, test surges={int(surge_test.sum())}) "
          f"gamma*={gamma_star}")

    gammas = sorted(set(GAMMAS + [gamma_star]))
    results = [evaluate(train, test, surge_train, surge_test, thresh, g, ppd) for g in gammas]
    star = next(r for r in results if abs(r["gamma"] - gamma_star) < 1e-9)

    # sensitivity: surge-threshold multiplier k and minimum supplementary term
    thresh_sweep = {}
    for k in (1.5, 2.0, 2.5):
        th_k = float(train.mean() + k * train.std(ddof=1))
        Q0k, Q1k = pl.saa_dual(train, train > th_k, gamma_star)
        od_t = float(np.mean(test))
        d = 100.0 * pl.dual_policy_cost(test, test > th_k, Q0k, Q1k, gamma_star) / od_t
        dc = 100.0 * pl.dual_policy_cost_causal(test, th_k, Q0k, Q1k, gamma_star) / od_t
        thresh_sweep[k] = {"dual_pct": d, "dualc_pct": dc}

    # robustness of the headline ordering to the split choice
    robust = []
    vals = df["value"].to_numpy(dtype=float)
    for frac in (0.5, 0.6, 0.7):
        k = int(round(n * frac))
        tr, te = vals[:k], vals[k:]
        th = float(tr.mean() + 2 * tr.std(ddof=1))
        r = evaluate(tr, te, tr > th, te > th, th, gamma_star, ppd)
        od_f = r["cost"]["OD"]
        robust.append({"train_frac": frac,
                       "nv_save": 100.0 - 100.0 * r["cost"]["NV"] / od_f,
                       "poc": 100.0 * (r["cost"]["HEUR"] - r["cost"]["NV"]) / od_f})

    fig_policy_gamma(results, gamma_star, args.suffix)
    write_policy_table(results, args.suffix)

    od = star["cost"]["OD"]
    pct = {k: 100.0 * v / od for k, v in star["cost"].items()}
    # empirical service level the deployed rule implies on this workload
    implied_q = float(np.mean(train <= star["Q"]["HEUR"]) * 100)
    # price of conservatism: deployed heuristic vs newsvendor optimum, on test
    poc_pct = pct["HEUR"] - pct["NV"]
    # gamma at which HEUR crosses break-even (linear interpolation on the sweep)
    breakeven = None
    pcts_heur = [(r["gamma"], 100.0 * r["cost"]["HEUR"] / r["cost"]["OD"]) for r in results]
    for (g1, p1), (g2, p2) in zip(pcts_heur, pcts_heur[1:]):
        if p1 < 100.0 <= p2:
            breakeven = g1 + (g2 - g1) * (100.0 - p1) / (p2 - p1)
            break

    p = args.prefix
    L = [f"% Auto-generated by paper/policy_sim.py -- do not edit by hand.\n"]
    L.append(latexcmd(f"{p}GammaStar", f"{gamma_star:.2f}"))
    L.append(latexcmd(f"{p}TrainPeriods", f"{n_train}"))
    L.append(latexcmd(f"{p}TestPeriods", f"{len(test)}"))
    # Deprecated aliases retained for finalized conference/main consumers.
    # Their values are period counts; for hourly inputs the names do not mean
    # calendar days. New consumers must use the *Periods macros above.
    sampling_period = empirical_mapping["sampling_period"]
    L.append(
        "% Deprecated *Days aliases retained for finalized conference/main "
        "consumers; values count periods "
        f"(sampling period: {sampling_period}). Use *Periods in new prose.\n"
    )
    L.append(latexcmd(f"{p}TrainDays", f"{n_train}"))
    L.append(latexcmd(f"{p}TestDays", f"{len(test)}"))
    for key in ("HEUR", "NV", "SAA", "LOOK7", "LOOK30", "LOOK60", "DUAL", "DUALC", "LB"):
        L.append(latexcmd(f"{p}Pct{POLICY_MACRO_SUFFIX[key]}", f"{pct[key]:.1f}"))
    L.append(latexcmd(f"{p}PoC", f"{poc_pct:.1f}"))
    L.append(latexcmd(f"{p}ImpliedQ", f"{implied_q:.0f}"))
    L.append(latexcmd(f"{p}SurgeTrain", f"{int(surge_train.sum())}"))
    L.append(latexcmd(f"{p}SurgeTest", f"{int(surge_test.sum())}"))
    L.append(latexcmd(f"{p}NvSave", f"{100.0 - pct['NV']:.1f}"))
    L.append(latexcmd(f"{p}DualGain", f"{pct['NV'] - pct['DUAL']:.1f}"))
    L.append(latexcmd(f"{p}DualcGain", f"{pct['NV'] - pct['DUALC']:.1f}"))
    L.append(latexcmd(f"{p}DualGapCapture",
                      f"{100.0 * (pct['NV'] - pct['DUAL']) / (pct['NV'] - pct['LB']):.0f}"))
    L.append(latexcmd(f"{p}DualcGapCapture",
                      f"{100.0 * (pct['NV'] - pct['DUALC']) / (pct['NV'] - pct['LB']):.0f}"))
    if breakeven is not None:
        L.append(latexcmd(f"{p}HeurBreakeven", f"{breakeven:.2f}"))
    # threshold-sweep gains vs NV at gamma*
    dual_gains = [pct["NV"] - v["dual_pct"] for v in thresh_sweep.values()]
    dualc_gains = [pct["NV"] - v["dualc_pct"] for v in thresh_sweep.values()]
    L.append(latexcmd(f"{p}DualGainThreshMin", f"{min(dual_gains):.1f}"))
    L.append(latexcmd(f"{p}DualGainThreshMax", f"{max(dual_gains):.1f}"))
    L.append(latexcmd(f"{p}DualcGainThreshMin", f"{min(dualc_gains):.1f}"))
    L.append(latexcmd(f"{p}DualcGainThreshMax", f"{max(dualc_gains):.1f}"))
    # minimum-hold sensitivity for the causal dual (gains vs NV at gamma*)
    HOLD_NAME = {1: "One", 6: "Six", 7: "SevenD", 24: "Day", 30: "ThirtyD", 168: "Week"}
    hold_gain = {}
    for h in (int(x) for x in args.holds.split(",")):
        c = 100.0 * pl.dual_policy_cost_causal(
            test, thresh, star["Q"]["DUAL0"], star["Q"]["DUAL1"], gamma_star,
            min_hold=h) / od
        hold_gain[h] = pct["NV"] - c
        L.append(latexcmd(f"{p}DualcGainHold{HOLD_NAME.get(h, f'X{h}')}",
                          f"{hold_gain[h]:.1f}"))
    L.append(latexcmd(f"{p}NvSaveMin", f"{min(r['nv_save'] for r in robust):.1f}"))
    L.append(latexcmd(f"{p}NvSaveMax", f"{max(r['nv_save'] for r in robust):.1f}"))
    L.append(latexcmd(f"{p}PoCMin", f"{min(r['poc'] for r in robust):.1f}"))
    L.append(latexcmd(f"{p}PoCMax", f"{max(r['poc'] for r in robust):.1f}"))
    L.append("% Empirical commitment-proxy Q values; units are arm-specific.\n")
    L.append(latexcmd(f"{p}Qheur", f"{star['Q']['HEUR']:.1f}"))
    L.append(latexcmd(f"{p}Qnv", f"{star['Q']['NV']:.1f}"))
    L.append(latexcmd(f"{p}QlookSeven", f"{star['Q']['LOOK7']:.1f}"))
    L.append(latexcmd(f"{p}QlookThirty", f"{star['Q']['LOOK30']:.1f}"))
    L.append(latexcmd(f"{p}QlookSixty", f"{star['Q']['LOOK60']:.1f}"))
    L.append(latexcmd(f"{p}LookSevenPeriods", f"{star['lookback_periods']['7']}"))
    L.append(latexcmd(f"{p}LookThirtyPeriods", f"{star['lookback_periods']['30']}"))
    L.append(latexcmd(f"{p}LookSixtyPeriods", f"{star['lookback_periods']['60']}"))
    L.append(latexcmd(f"{p}Qdualbase", f"{star['Q']['DUAL0']:.1f}"))
    L.append(latexcmd(f"{p}Qdualsurge", f"{star['Q']['DUAL1']:.1f}"))
    # Deprecated K-named aliases retained for finalized conference/main consumers.
    L.append("% Deprecated K-named aliases for finalized conference/main consumers.\n")
    L.append(latexcmd(f"{p}Kheur", f"\\{p}Qheur"))
    L.append(latexcmd(f"{p}Knv", f"\\{p}Qnv"))
    L.append(latexcmd(f"{p}KlookSeven", f"\\{p}QlookSeven"))
    L.append(latexcmd(f"{p}KlookThirty", f"\\{p}QlookThirty"))
    L.append(latexcmd(f"{p}KlookSixty", f"\\{p}QlookSixty"))
    L.append(latexcmd(f"{p}Kdualbase", f"\\{p}Qdualbase"))
    L.append(latexcmd(f"{p}Kdualsurge", f"\\{p}Qdualsurge"))
    # SAA-vs-newsvendor agreement (validates both implementations)
    saa_gap = max(abs(r["Q"]["SAA"] - r["Q"]["NV"]) / max(r["Q"]["NV"], 1e-9)
                  for r in results if r["Q"]["NV"] > 0)
    L.append(latexcmd(f"{p}SaaNvGapPct", f"{100.0 * saa_gap:.2f}"))
    if dollars:
        L.append(latexcmd(f"{p}OdMonthly", f"{od * DAYS_PER_MONTH:,.2f}"))
        L.append(latexcmd(f"{p}HeurMonthly", f"{star['cost']['HEUR'] * DAYS_PER_MONTH:,.2f}"))
        L.append(latexcmd(f"{p}NvMonthly", f"{star['cost']['NV'] * DAYS_PER_MONTH:,.2f}"))
        L.append(latexcmd(f"{p}PoCMonthly", f"{(star['cost']['HEUR'] - star['cost']['NV']) * DAYS_PER_MONTH:,.2f}"))
    (PAPER / f"numbers_policy{args.suffix}.tex").write_text("".join(L))

    (PAPER / f"results_policy{args.suffix}.json").write_text(json.dumps({
        "config": {"train_frac": TRAIN_FRAC, "gamma_star": gamma_star,
                   "surge_thresh": thresh, "n_train": n_train, "n_test": len(test),
                   "csv": args.csv, "periods_per_day": ppd,
                   "lookback_days": list(LOOKBACK_DAYS),
                   "lookback_policy": (
                       "paper-side recency-window baseline; not AWS, Azure, "
                       "or third-party recommender output"
                   ),
                   "result_commitment_field": "Q",
                   "empirical_mapping": empirical_mapping},
        "results": results,
        "star": {"pct_of_od": pct, "implied_q": implied_q, "poc_pct": poc_pct,
                 "heur_breakeven_gamma": breakeven},
        "split_robustness": robust,
        "sensitivity": {"thresh_sweep": {str(k): v for k, v in thresh_sweep.items()},
                        "hold_gain": {str(h): g for h, g in hold_gain.items()}},
    }, indent=2))

    for r in results:
        print(f"  gamma={r['gamma']:.2f}  " + "  ".join(
            f"{k}={100.0 * r['cost'][k] / r['cost']['OD']:.1f}%" for k in
            ("HEUR", "NV", "SAA", "LOOK7", "LOOK30", "LOOK60", "DUAL", "DUALC", "LB")))
    print(f"wrote numbers_policy{args.suffix}.tex, policy_tabular{args.suffix}.tex, "
          f"fig_policy_gamma{args.suffix}.pdf, results_policy{args.suffix}.json")


if __name__ == "__main__":
    main()
