"""Shared evaluation utilities for the paper's numerical studies.

Paper-local helpers (not part of the application): per-fold walk-forward
cross-validation with MAPE/MASE/interval coverage, the Diebold-Mariano
predictive-accuracy test with the Harvey-Leybourne-Newbold small-sample
correction, and newsvendor / reservation-policy cost primitives shared by
make_figures.py, external_validation.py and policy_sim.py.

All functions are deterministic given their inputs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# =============================================================================
# Forecast evaluation
# =============================================================================
def seasonal_naive_insample_mae(y_train: np.ndarray, m: int = 7) -> float:
    """In-sample MAE of the m-period seasonal-naive forecast (MASE denominator,
    Hyndman & Koehler 2006)."""
    y = np.asarray(y_train, dtype=float)
    if len(y) <= m:
        return float("nan")
    return float(np.mean(np.abs(y[m:] - y[:-m])))


def walk_forward(model_factory, df: pd.DataFrame, date_col: str = "date",
                 value_col: str = "value", initial: int = 120, horizon: int = 30,
                 step: int = 30, m: int = 7) -> dict:
    """Walk-forward CV returning per-fold metrics AND pooled per-point errors.

    The fold grid (cutoffs initial, initial+step, ...) is a deterministic
    function of (len(df), initial, horizon, step), so pooled errors from two
    models evaluated with identical parameters are aligned point-by-point --
    the requirement for a paired Diebold-Mariano test.

    Returns dict:
      folds   list of {cutoff, train_size, mape, mase, coverage} per fold
      y_true  pooled test-set actuals across folds
      y_pred  pooled forecasts across folds
      dates   pooled test dates across folds
    """
    data = df[[date_col, value_col]].copy()
    data.columns = ["date", "value"]
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").reset_index(drop=True)
    n = len(data)

    folds, yt_all, yp_all, dt_all = [], [], [], []
    cutoff = initial
    while cutoff + horizon <= n:
        train = data.iloc[:cutoff]
        test = data.iloc[cutoff:cutoff + horizon]
        model = model_factory()
        model.fit(train, date_col="date", value_col="value")
        pred = model.predict(horizon=len(test)).reset_index(drop=True)

        yt = test["value"].to_numpy(dtype=float)
        yp = pred["forecast"].to_numpy(dtype=float)
        lo = pred["lower"].to_numpy(dtype=float)
        hi = pred["upper"].to_numpy(dtype=float)

        mask = yt != 0
        mape = float(np.mean(np.abs((yt[mask] - yp[mask]) / yt[mask])) * 100) if mask.any() else float("nan")
        denom = seasonal_naive_insample_mae(train["value"].to_numpy(dtype=float), m)
        mase = float(np.mean(np.abs(yt - yp)) / denom) if denom and denom > 0 else float("nan")
        coverage = float(np.mean((yt >= lo) & (yt <= hi)) * 100)

        folds.append({"cutoff": int(cutoff), "train_size": int(len(train)),
                      "mape": mape, "mase": mase, "coverage": coverage})
        yt_all.append(yt)
        yp_all.append(yp)
        dt_all.append(test["date"].to_numpy())
        cutoff += step

    return {
        "folds": folds,
        "y_true": np.concatenate(yt_all) if yt_all else np.empty(0),
        "y_pred": np.concatenate(yp_all) if yp_all else np.empty(0),
        "dates": np.concatenate(dt_all) if dt_all else np.empty(0, dtype="datetime64[ns]"),
    }


def dm_test(e1: np.ndarray, e2: np.ndarray, h: int = 1, power: int = 1):
    """Diebold-Mariano (1995) test with the Harvey-Leybourne-Newbold (1997)
    small-sample correction, on aligned forecast errors of two models.

    Args:
        e1, e2: forecast errors (y_true - y_pred) on the SAME targets.
        h: forecast horizon; autocovariances up to lag h-1 enter the
           long-run variance (rectangular/truncated kernel, as in DM 1995).
        power: 1 = absolute-error loss, 2 = squared-error loss.

    Returns (dm_stat, p_two_sided, mean_loss_diff). Negative stat means
    model 1 has the smaller loss.
    """
    from scipy import stats

    e1 = np.asarray(e1, dtype=float)
    e2 = np.asarray(e2, dtype=float)
    if e1.shape != e2.shape or e1.ndim != 1:
        raise ValueError("e1 and e2 must be aligned 1-D arrays")
    d = np.abs(e1) ** power - np.abs(e2) ** power
    n = len(d)
    dbar = float(d.mean())
    gamma = [float(np.mean((d[: n - k] - dbar) * (d[k:] - dbar))) for k in range(min(h, n))]
    var_d = (gamma[0] + 2.0 * sum(gamma[1:])) / n
    if var_d <= 0:
        var_d = gamma[0] / n  # truncated long-run variance can go negative; fall back to lag-0
    dm = dbar / np.sqrt(var_d)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    dm_hln = float(hln * dm)
    p = float(2 * stats.t.sf(abs(dm_hln), df=n - 1))
    return dm_hln, p, dbar


def wilcoxon_folds(a: list, b: list):
    """Paired two-sided Wilcoxon signed-rank test on per-fold metrics."""
    from scipy import stats

    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    res = stats.wilcoxon(a, b)
    return float(res.statistic), float(res.pvalue)


# =============================================================================
# Reservation-policy cost primitives
# =============================================================================
# All costs are expressed in units of the on-demand rate w0 (i.e., gamma is
# the reserved/on-demand price ratio w_T/w_0), so no dollar catalog is needed:
#   static capacity K costs  gamma*K + E[(D - K)^+]  per period.
def policy_cost(demand: np.ndarray, K: float, gamma: float) -> float:
    """Long-run average per-period cost of static reserved capacity K,
    normalized by the on-demand rate."""
    D = np.asarray(demand, dtype=float)
    return float(gamma * K + np.mean(np.maximum(D - K, 0.0)))


def dual_policy_cost(demand: np.ndarray, is_surge: np.ndarray,
                     K0: float, K1: float, gamma: float) -> float:
    """Average per-period cost of base capacity K0 plus surge capacity K1
    (supplementary K1-K0 paid only during surge periods), per Eq. (1)."""
    D = np.asarray(demand, dtype=float)
    s = np.asarray(is_surge, dtype=bool)
    frac_surge = float(np.mean(s))
    cap = np.where(s, K1, K0)
    spill = np.maximum(D - cap, 0.0)
    return float(gamma * K0 + gamma * (K1 - K0) * frac_surge + np.mean(spill))


def dual_policy_cost_causal(demand: np.ndarray, thresh: float,
                            K0: float, K1: float, gamma: float,
                            min_hold: int = 1) -> float:
    """Causal variant of dual_policy_cost: the supplementary tier activates in
    period t iff period t-1 exceeded the surge threshold (one-period
    activation lag; inactive at t=0), and once activated must stay on for at
    least min_hold periods (a minimum contract term). min_hold=1 reduces to
    the pure lagged-signal rule. No contemporaneous state knowledge."""
    D = np.asarray(demand, dtype=float)
    n = len(D)
    act = np.zeros(n, dtype=bool)
    remaining = 0
    for t in range(n):
        if t > 0 and D[t - 1] > thresh:
            remaining = max(remaining, min_hold)
        if remaining > 0:
            act[t] = True
            remaining -= 1
    frac_act = float(np.mean(act))
    cap = np.where(act, K1, K0)
    spill = np.maximum(D - cap, 0.0)
    return float(gamma * K0 + gamma * (K1 - K0) * frac_act + np.mean(spill))


def newsvendor_K(demand: np.ndarray, gamma: float) -> float:
    """Cost-optimal static capacity: the (1-gamma) empirical quantile
    (linear interpolation)."""
    q = min(max(1.0 - gamma, 0.0), 1.0)
    return float(np.quantile(np.asarray(demand, dtype=float), q))


def heuristic_K(demand: np.ndarray, q: float = 0.95, headroom: float = 1.3) -> float:
    """The deployed right-sizing rule: q-th percentile times headroom."""
    return float(np.quantile(np.asarray(demand, dtype=float), q) * headroom)


def saa_K(demand: np.ndarray, gamma: float) -> float:
    """Two-stage sample-average-approximation LP (scenarios = observed
    periods): first stage picks reserved capacity K, second stage buys
    on-demand spillover. Solved with PuLP/CBC -- the same toolchain as the
    system's MILP. Serves as the stochastic-programming baseline in the
    spirit of Chaisiri et al. (2012)."""
    import pulp

    D = np.asarray(demand, dtype=float)
    n = len(D)
    prob = pulp.LpProblem("saa_reserve", pulp.LpMinimize)
    K = pulp.LpVariable("K", lowBound=0)
    s = [pulp.LpVariable(f"s_{i}", lowBound=0) for i in range(n)]
    prob += gamma * K + (1.0 / n) * pulp.lpSum(s)
    for i in range(n):
        prob += s[i] >= D[i] - K
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if prob.status != pulp.constants.LpStatusOptimal:
        return float("nan")
    return float(K.varValue)


def saa_dual(demand: np.ndarray, is_surge: np.ndarray, gamma: float):
    """SAA LP for the dual-capacity (K0, K1) problem of Eq. (1):
    base capacity K0 always reserved, supplementary K1-K0 reserved only in
    surge periods, spillover to on-demand. Returns (K0, K1)."""
    import pulp

    D = np.asarray(demand, dtype=float)
    sg = np.asarray(is_surge, dtype=bool)
    n = len(D)
    frac_surge = float(np.mean(sg))
    prob = pulp.LpProblem("saa_dual_reserve", pulp.LpMinimize)
    K0 = pulp.LpVariable("K0", lowBound=0)
    K1 = pulp.LpVariable("K1", lowBound=0)
    s = [pulp.LpVariable(f"s_{i}", lowBound=0) for i in range(n)]
    prob += gamma * K0 + gamma * frac_surge * (K1 - K0) + (1.0 / n) * pulp.lpSum(s)
    prob += K1 >= K0
    for i in range(n):
        prob += s[i] >= D[i] - (K1 if sg[i] else K0)
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if prob.status != pulp.constants.LpStatusOptimal:
        return float("nan"), float("nan")
    return float(K0.varValue), float(K1.varValue)


def clairvoyant_lb(demand: np.ndarray, gamma: float) -> float:
    """Perfect-information lower bound: reserve exactly D_t every period at
    the reserved rate (ignores commitment inflexibility), i.e. gamma*E[D]."""
    return float(gamma * np.mean(np.asarray(demand, dtype=float)))
