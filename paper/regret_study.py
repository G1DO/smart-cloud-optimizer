"""
Regret study for the forecast-integrated capacity-reservation paper.

Three experiments:
  A. Verify the O(1/n) regret bound (Thm T1/T2) against its exact theoretical
     constant  p*delta*(1-delta) / (2 n f(Q*))  on a KNOWN demand distribution
     (a base+surge mixture), where Q* and f(Q*) are known in closed form.
  B. Forecast the delta-QUANTILE vs. the MEAN (T3): on a skewed (surge) demand,
     a Gaussian mean-plug-in policy has an irreducible regret floor while the
     empirical-quantile policy converges to the optimum.
  C. Real data: run the rolling forecast-quantile reservation policy on the
     Azure LLM inference trace (downloaded + cached) and compare to baselines.

Reproduce:  python paper/regret_study.py
Figures ->  paper/figures/regret_*.pdf|png ;  numbers -> figures/regret_results.json
"""
import json, os, urllib.request

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.join(HERE, "figures")
CACHE = os.path.join(HERE, ".trace_cache")
os.makedirs(CACHE, exist_ok=True)
RES = {}

plt.rcParams.update({
    "figure.figsize": (6.2, 3.6), "font.size": 10, "axes.grid": True,
    "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False,
    "savefig.bbox": "tight", "savefig.dpi": 200, "legend.fontsize": 8,
})


# ==========================================================================
#  Known demand model: mixture of base N(mu_b,sd_b) and surge N(mu_s,sd_s)
# ==========================================================================
class MixtureDemand:
    def __init__(self, mu_b=70., sd_b=12., mu_s=180., sd_s=30., pi=0.05):
        self.mu_b, self.sd_b = mu_b, sd_b
        self.mu_s, self.sd_s = mu_s, sd_s
        self.pi = pi

    def cdf(self, x):
        return ((1 - self.pi) * norm.cdf(x, self.mu_b, self.sd_b)
                + self.pi * norm.cdf(x, self.mu_s, self.sd_s))

    def pdf(self, x):
        return ((1 - self.pi) * norm.pdf(x, self.mu_b, self.sd_b)
                + self.pi * norm.pdf(x, self.mu_s, self.sd_s))

    def quantile(self, delta):
        lo, hi = self.mu_b - 6 * self.sd_b, self.mu_s + 6 * self.sd_s
        return brentq(lambda q: self.cdf(q) - delta, lo, hi)

    @staticmethod
    def _normal_shortfall(mu, sd, Q):           # E[(X-Q)^+], X~N(mu,sd)
        z = (mu - Q) / sd
        return (mu - Q) * norm.cdf(z) + sd * norm.pdf(z)

    def expected_shortfall(self, Q):            # E[(D-Q)^+]
        return ((1 - self.pi) * self._normal_shortfall(self.mu_b, self.sd_b, Q)
                + self.pi * self._normal_shortfall(self.mu_s, self.sd_s, Q))

    def g(self, Q, delta, p=1.0):               # true expected per-period cost
        return (1 - delta) * p * Q + p * self.expected_shortfall(Q)

    def sample(self, n, rng):
        comp = rng.random(n) < self.pi
        x = np.where(comp, rng.normal(self.mu_s, self.sd_s, n),
                     rng.normal(self.mu_b, self.sd_b, n))
        return np.maximum(x, 0.0)

    def mean(self):
        return (1 - self.pi) * self.mu_b + self.pi * self.mu_s

    def std(self):
        m = self.mean()
        ex2 = ((1 - self.pi) * (self.mu_b**2 + self.sd_b**2)
               + self.pi * (self.mu_s**2 + self.sd_s**2))
        return np.sqrt(ex2 - m**2)


# ==========================================================================
#  Experiment A: verify the O(1/n) regret rate and constant
# ==========================================================================
def experiment_A(model, deltas=(0.37, 0.60), reps=600, p=1.0, seed=1):
    rng = np.random.default_rng(seed)
    ns = np.unique(np.round(np.logspace(np.log10(20), np.log10(5000), 14))).astype(int)
    out = {}
    fig1, ax1 = plt.subplots()           # regret vs n + theory
    fig2, ax2 = plt.subplots()           # log-log, slope -1
    colors = {0.37: "#2b6cb0", 0.60: "#c53030"}
    for delta in deltas:
        Qstar = model.quantile(delta)
        gstar = model.g(Qstar, delta, p)
        fQ = model.pdf(Qstar)
        const = p * delta * (1 - delta) / (2 * fQ)      # theoretical n*regret
        measured = []
        for n in ns:
            regs = np.empty(reps)
            for r in range(reps):
                s = model.sample(n, rng)
                Qhat = np.quantile(s, delta)
                regs[r] = model.g(Qhat, delta, p) - gstar
            measured.append(regs.mean())
        measured = np.array(measured)
        theory = const / ns
        out[f"delta={delta}"] = {
            "Q_star": Qstar, "f_Qstar": fQ, "theory_const_n_times_regret": const,
            "n_grid": ns.tolist(), "regret_measured": measured.tolist(),
            "regret_theory": theory.tolist(),
            "n_times_regret_measured": (ns * measured).tolist(),
            "ratio_measured_over_theory_largest_n": float(measured[-1] / theory[-1]),
        }
        c = colors.get(delta, "#444")
        ax1.plot(ns, measured, "o-", color=c, ms=4, label=f"measured ($\\delta$={delta})")
        ax1.plot(ns, theory, "--", color=c, lw=1.2, label=f"theory ($\\delta$={delta})")
        ax2.loglog(ns, measured, "o-", color=c, ms=4, label=f"$\\delta$={delta}")
    ax1.set_xlabel("History length $n$"); ax1.set_ylabel("Expected regret (\\$/period)")
    ax1.set_xscale("log"); ax1.legend()
    fig1.savefig(f"{FIGDIR}/regret_fig1_rate.pdf"); fig1.savefig(f"{FIGDIR}/regret_fig1_rate.png")
    # reference slope -1 line
    ref = out[f"delta={deltas[0]}"]
    n0 = ns[2]; r0 = ref["regret_measured"][2]
    ax2.loglog(ns, r0 * n0 / ns, ":", color="#718096", lw=1.2, label="slope $-1$ ref")
    ax2.set_xlabel("History length $n$ (log)"); ax2.set_ylabel("Expected regret (log)")
    ax2.legend()
    fig2.savefig(f"{FIGDIR}/regret_fig2_loglog.pdf"); fig2.savefig(f"{FIGDIR}/regret_fig2_loglog.png")
    plt.close("all")
    RES["experiment_A"] = {"reps": reps, "results": out}
    return out


# ==========================================================================
#  Experiment B: forecast the quantile, not the mean (T3)
# ==========================================================================
def experiment_B(model, delta=0.60, reps=600, p=1.0, seed=2):
    rng = np.random.default_rng(seed)
    ns = np.unique(np.round(np.logspace(np.log10(20), np.log10(5000), 14))).astype(int)
    Qstar = model.quantile(delta); gstar = model.g(Qstar, delta, p)
    # asymptotic mean-plug-in target uses TRUE mean/std (model misspecification)
    Q_norm_inf = model.mean() + model.std() * norm.ppf(delta)
    floor = model.g(Q_norm_inf, delta, p) - gstar
    reg_q, reg_m = [], []
    for n in ns:
        rq = np.empty(reps); rm = np.empty(reps)
        for r in range(reps):
            s = model.sample(n, rng)
            rq[r] = model.g(np.quantile(s, delta), delta, p) - gstar
            Qn = s.mean() + s.std(ddof=1) * norm.ppf(delta)
            rm[r] = model.g(Qn, delta, p) - gstar
        reg_q.append(rq.mean()); reg_m.append(rm.mean())
    RES["experiment_B"] = {
        "delta": delta, "reps": reps, "n_grid": ns.tolist(),
        "regret_quantile": reg_q, "regret_mean_plugin": reg_m,
        "Q_star": Qstar, "Q_mean_plugin_asymptote": Q_norm_inf,
        "regret_floor_mean_plugin": floor,
    }
    fig, ax = plt.subplots()
    ax.plot(ns, reg_q, "o-", color="#2b6cb0", ms=4, label="forecast $\\delta$-quantile")
    ax.plot(ns, reg_m, "s-", color="#c53030", ms=4, label="forecast mean (Gaussian plug-in)")
    ax.axhline(floor, color="#c53030", ls="--", lw=1.1,
               label=f"mean-plug-in floor (\\${floor:.2f})")
    ax.set_xscale("log"); ax.set_xlabel("History length $n$")
    ax.set_ylabel("Expected regret (\\$/period)"); ax.legend()
    fig.savefig(f"{FIGDIR}/regret_fig3_quantile_vs_mean.pdf")
    fig.savefig(f"{FIGDIR}/regret_fig3_quantile_vs_mean.png"); plt.close(fig)
    return RES["experiment_B"]


# ==========================================================================
#  Experiment C: real Azure LLM inference trace
# ==========================================================================
AZURE = ("https://raw.githubusercontent.com/Azure/AzurePublicDataset/master/"
         "data/AzureLLMInferenceTrace_{}.csv")

def load_azure_llm(which="conv", target_points=2500):
    path = os.path.join(CACHE, f"azure_llm_{which}.csv")
    if not os.path.exists(path):
        urllib.request.urlretrieve(AZURE.format(which), path)
    import pandas as pd
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["TIMESTAMP"])
    secs = (ts - ts.min()).dt.total_seconds().to_numpy()
    load = (df["ContextTokens"].to_numpy() + df["GeneratedTokens"].to_numpy()).astype(float)
    span = secs.max()
    bucket = max(1.0, span / target_points)
    idx = np.floor(secs / bucket).astype(int)
    nb = idx.max() + 1
    demand = np.zeros(nb)
    np.add.at(demand, idx, load)            # tokens per bucket = demand signal
    demand = demand / 1000.0                # scale to "k-tokens/interval"
    return demand, bucket, len(df), str(ts.min()), str(ts.max())

def reserve_cost(D, Q, delta, p=1.0):
    return float(np.sum((1 - delta) * p * Q + p * np.maximum(D - Q, 0.0)))

def experiment_C(delta=0.37, which="conv", p=1.0):
    try:
        D, bucket, nreq, t0, t1 = load_azure_llm(which)
    except Exception as e:
        RES["experiment_C"] = {"error": f"download/parse failed: {e}"}
        print("Experiment C skipped:", e); return None
    n = len(D); split = n // 2
    test = D[split:]
    Qstar = float(np.quantile(test, delta))        # hindsight oracle on test
    oracle = reserve_cost(test, Qstar, delta, p)
    base_od = reserve_cost(test, 0.0, delta, p)     # all on-demand (Q=0)
    peak = reserve_cost(test, D[:split].max(), delta, p)
    mean_pol = reserve_cost(test, D[:split].mean(), delta, p)
    # rolling forecast-quantile policy over several training windows
    windows = [20, 40, 80, 160, 320, 640]
    win_rows = []
    for w in windows:
        if w >= split:  # need history
            continue
        cost = 0.0
        for t in range(split, n):
            hist = D[max(0, t - w):t]
            Qhat = np.quantile(hist, delta)
            cost += (1 - delta) * p * Qhat + p * max(D[t] - Qhat, 0.0)
        win_rows.append({"window": w, "cost": float(cost),
                         "regret_vs_oracle": float(cost - oracle),
                         "save_vs_on_demand_pct": 100 * (base_od - cost) / base_od})
    RES["experiment_C"] = {
        "trace": which, "n_requests": nreq, "t_start": t0, "t_end": t1,
        "bucket_seconds": bucket, "n_buckets": n, "delta": delta,
        "test_oracle_cost": oracle, "all_on_demand_cost": base_od,
        "reserve_peak_cost": peak, "reserve_mean_cost": mean_pol,
        "oracle_save_vs_od_pct": 100 * (base_od - oracle) / base_od,
        "rolling_windows": win_rows,
        "demand_mean": float(D.mean()), "demand_max": float(D.max()),
        "demand_peak_over_median": float(D.max() / np.median(D[D > 0])),
    }
    # Fig C1: real demand series
    fig, ax = plt.subplots()
    ax.plot(np.arange(n), D, lw=0.7, color="#2b6cb0")
    ax.axvline(split, color="#718096", ls=":", lw=1)
    ax.set_xlabel(f"Interval (bucket = {bucket:.0f}s)")
    ax.set_ylabel("Demand (k-tokens/interval)")
    ax.set_title(f"Azure LLM inference trace ('{which}'): real demand", fontsize=9)
    fig.savefig(f"{FIGDIR}/regret_fig4_azure_series.pdf")
    fig.savefig(f"{FIGDIR}/regret_fig4_azure_series.png"); plt.close(fig)
    # Fig C2: realized cost vs training window (adaptivity vs. staleness),
    # with the best-static-reservation (oracle) and all-on-demand references.
    # On NON-STATIONARY real data, short adaptive windows can beat the best
    # static reservation -- a motivation for the non-i.i.d. extension (T5),
    # NOT an instance of the i.i.d. O(1/n) rate (which is Experiment A).
    if win_rows:
        fig, ax = plt.subplots()
        ws = [r["window"] for r in win_rows]
        cost = [r["cost"] for r in win_rows]
        ax.plot(ws, cost, "o-", color="#dd6b20", ms=5,
                label="rolling $\\delta$-quantile policy")
        ax.axhline(oracle, color="#2b6cb0", ls="--", lw=1.1,
                   label="best static reservation (oracle)")
        ax.axhline(base_od, color="#c53030", ls=":", lw=1.2, label="all on-demand")
        ax.set_xscale("log"); ax.set_xlabel("Training window $w$ (intervals)")
        ax.set_ylabel("Realized cost on test set (\\$)")
        ax.set_title("Forecast-quantile reservation on a real Azure trace", fontsize=9)
        ax.legend()
        fig.savefig(f"{FIGDIR}/regret_fig5_azure_cost.pdf")
        fig.savefig(f"{FIGDIR}/regret_fig5_azure_cost.png"); plt.close(fig)
    return RES["experiment_C"]


# ==========================================================================
def main():
    model = MixtureDemand()
    print("Demand model: mean=%.1f std=%.1f  Q*(.37)=%.2f Q*(.60)=%.2f"
          % (model.mean(), model.std(), model.quantile(.37), model.quantile(.60)))
    A = experiment_A(model)
    print("\n=== Exp A: O(1/n) regret verification ===")
    for k, v in A.items():
        print(f"  {k}: Q*={v['Q_star']:.2f}  f(Q*)={v['f_Qstar']:.4f}  "
              f"n*regret theory={v['theory_const_n_times_regret']:.3f}  "
              f"measured/theory @max n={v['ratio_measured_over_theory_largest_n']:.3f}")
    B = experiment_B(model)
    print("\n=== Exp B: quantile vs mean plug-in (delta=%.2f) ===" % B["delta"])
    print(f"  Q*={B['Q_star']:.2f}  mean-plugin asymptote={B['Q_mean_plugin_asymptote']:.2f}"
          f"  mean-plugin regret floor=${B['regret_floor_mean_plugin']:.3f}")
    print(f"  quantile regret @ n={B['n_grid'][-1]}: ${B['regret_quantile'][-1]:.4f}"
          f"  | mean-plugin regret @ same n: ${B['regret_mean_plugin'][-1]:.4f}")
    C = experiment_C()
    if C and "error" not in C:
        print("\n=== Exp C: real Azure LLM trace ===")
        print(f"  {C['n_requests']} requests, {C['n_buckets']} intervals "
              f"({C['bucket_seconds']:.0f}s), peak/median={C['demand_peak_over_median']:.1f}x")
        print(f"  oracle saves {C['oracle_save_vs_od_pct']:.1f}% vs on-demand")
        for r in C["rolling_windows"]:
            print(f"    window={r['window']:4d}  regret_vs_oracle=${r['regret_vs_oracle']:.1f}"
                  f"  save_vs_od={r['save_vs_on_demand_pct']:.1f}%")
    with open(f"{FIGDIR}/regret_results.json", "w") as f:
        json.dump(RES, f, indent=2)
    print("\nWrote", f"{FIGDIR}/regret_results.json", "and regret figures.")


if __name__ == "__main__":
    main()
