#!/usr/bin/env python3
"""E1 — localization with degraded GNSS: p50/p95 position error, heading error and NEES per filter and world.

    python3 analyze_e1.py

Reads results/E1/<world>__<variant>__s<seed>/openfield/exp_e1.csv (openfield [Diag] ExperimentCsv: every
filter graded at the ground truth's own stamp). Filters: main (published) and the shadows A (current EKF),
B (receiver sigma + Student-t + latency compensation), C (no GNSS), D (no IMU yaw).
NEES = e' P^-1 e over (x, y, theta); for a consistent filter its mean is 3 (chi-square, 3 dof), and the
95 % band of the MEAN over n independent samples is narrow — but consecutive samples are strongly correlated,
so the band is reported per run and the mean of run means is what the table shows.
"""
from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import chi2  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from analysis_common import fmt, md_table, runs  # noqa: E402

FILTERS = [("A_current", "A: current EKF"), ("B_receiver", "B: receiver σ + Student-t + latency"),
           ("C_no_gnss", "C: no GNSS"), ("D_no_yaw", "D: no IMU yaw")]
SKIP_S = 10.0


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def load(rd: Path) -> pd.DataFrame | None:
    p = rd / "openfield" / "exp_e1.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p).dropna().reset_index(drop=True)   # the last row can be cut by the shutdown
    df = df[df["wall_ms"] - df["wall_ms"].iloc[0] > SKIP_S * 1000].reset_index(drop=True)
    return df if len(df) > 20 else None


def filter_metrics(df: pd.DataFrame, f: str) -> dict:
    ex = df[f"{f}_x"] - df["gt_x"]
    ey = df[f"{f}_y"] - df["gt_y"]
    et = wrap(df[f"{f}_th"] - df["gt_th"])
    epos = np.hypot(ex, ey)
    nees = []
    for i in range(len(df)):
        P = np.array([[df[f"{f}_pxx"][i], df[f"{f}_pxy"][i], df[f"{f}_pxt"][i]],
                      [df[f"{f}_pxy"][i], df[f"{f}_pyy"][i], df[f"{f}_pyt"][i]],
                      [df[f"{f}_pxt"][i], df[f"{f}_pyt"][i], df[f"{f}_ptt"][i]]])
        e = np.array([ex[i], ey[i], et[i]])
        try:
            nees.append(float(e @ np.linalg.solve(P, e)))
        except np.linalg.LinAlgError:
            pass
    return {"p50": float(np.percentile(epos, 50)), "p95": float(np.percentile(epos, 95)),
            "max": float(epos.max()), "th50": math.degrees(float(np.percentile(np.abs(et), 50))),
            "th95": math.degrees(float(np.percentile(np.abs(et), 95))),
            "nees": float(np.mean(nees)) if nees else float("nan"),
            "nees_med": float(np.median(nees)) if nees else float("nan")}


def gnss_stats(df: pd.DataFrame) -> dict:
    ft = df["fix_type"]
    n = max(1, len(ft))
    errs = df.loc[df["fix_valid"] == 1, "fix_err"]
    return {"fixed": 100 * (ft == 4).sum() / n, "float": 100 * (ft == 5).sum() / n,
            "single": 100 * (ft == 1).sum() / n, "no_fix": 100 * ((ft == 0) | (df["fix_valid"] == 0)).sum() / n,
            "err_fix_p95": float(np.percentile(errs, 95)) if len(errs) else float("nan")}


def ellipse(ax, x, y, P2, color):
    w, V = np.linalg.eigh(P2)
    w = np.maximum(w, 1e-12)
    t = np.linspace(0, 2 * np.pi, 60)
    pts = V @ (2.0 * np.sqrt(w)[:, None] * np.vstack([np.cos(t), np.sin(t)]))
    ax.plot(x + pts[0], y + pts[1], "-", c=color, lw=0.7)


def plot_run(rd: Path, df: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 7), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    world = common.world_path(rd.name.split("__")[0])
    for t in common.world_trees(world):
        ax.add_patch(plt.Circle((t["x"], t["y"]), t.get("canopyRadius", 0.4), color="green", alpha=0.12))
    ax.plot(df["gt_x"], df["gt_y"], "-", c="k", lw=1.4, label="ground truth")
    colors = {"A_current": "tab:red", "B_receiver": "tab:blue", "C_no_gnss": "tab:orange", "D_no_yaw": "tab:purple"}
    for f, label in FILTERS:
        ax.plot(df[f"{f}_x"], df[f"{f}_y"], "-", c=colors[f], lw=0.9, label=label)
    for f in ("A_current", "B_receiver"):
        for i in range(0, len(df), 40):
            P2 = np.array([[df[f"{f}_pxx"][i], df[f"{f}_pxy"][i]], [df[f"{f}_pxy"][i], df[f"{f}_pyy"][i]]])
            ellipse(ax, df[f"{f}_x"][i], df[f"{f}_y"][i], P2, colors[f])
    fx = df.drop_duplicates("fix_seq")
    for ft, c, lab in ((4, "limegreen", "RTK fixed fix"), (5, "gold", "RTK float fix"), (1, "orangered", "single fix")):
        sel = fx[(fx["fix_type"] == ft) & (fx["fix_valid"] == 1)]
        if len(sel):
            ax.scatter(sel["fix_x"], sel["fix_y"], s=4, c=c, label=lab, zorder=1)
    ax.set_aspect("equal")
    ax.set_title(f"E1 — {rd.name}\ntrajectories and 2σ ellipses (A red, B blue)", fontsize=9)
    ax.legend(fontsize=7, loc="lower left")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax2 = axes[1]
    t = (df["wall_ms"] - df["wall_ms"].iloc[0]) / 1000.0
    for f, label in FILTERS:
        e = np.hypot(df[f"{f}_x"] - df["gt_x"], df[f"{f}_y"] - df["gt_y"])
        s2 = 2.0 * np.sqrt(0.5 * (df[f"{f}_pxx"] + df[f"{f}_pyy"]))
        ax2.plot(t, e, "-", c=colors[f], lw=0.9, label=f"{label} — error")
        ax2.plot(t, s2, ":", c=colors[f], lw=0.8)
    ft = df["fix_type"].where(df["fix_valid"] == 1, 0)
    ymax = ax2.get_ylim()[1]
    for code, c in ((5, "gold"), (1, "orangered"), (0, "0.6")):
        ax2.fill_between(t, 0, ymax, where=ft == code, color=c, alpha=0.15, step="mid", lw=0)
    ax2.set_ylim(0, ymax)
    ax2.set_xlabel("t (s)")
    ax2.set_ylabel("position error (m) — dotted: estimated 2σ")
    ax2.set_title("background: yellow = RTK float, red = single, grey = no fix", fontsize=8)
    ax2.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def main():
    rows, per = [], {}
    gn = {}
    example = {}
    for rd in runs("E1"):
        df = load(rd)
        if df is None:
            continue
        world, variant, seed = rd.name.split("__")
        g = gnss_stats(df)
        gn.setdefault((world, variant), []).append(g)
        for f, _ in FILTERS:
            if f"{f}_x" not in df:
                continue
            m = filter_metrics(df, f)
            per.setdefault((world, variant, f), []).append(m)
        if (world, variant) not in example or seed == "s1":
            example[(world, variant)] = (rd, df)
    for (world, variant), (rd, df) in example.items():
        plot_run(rd, df, common.IMAGES / f"E1_{world}_{variant}.png")

    def agg(ms, k):
        v = [m[k] for m in ms if m[k] == m[k]]
        return (statistics.mean(v), statistics.pstdev(v)) if v else (float("nan"), float("nan"))

    for (world, variant, f), ms in sorted(per.items()):
        p50, p95, th95, nees = agg(ms, "p50"), agg(ms, "p95"), agg(ms, "th95"), agg(ms, "nees")
        rows.append([world, variant, dict(FILTERS)[f], len(ms), f"{fmt(p50[0], 3)} ± {fmt(p50[1], 3)}",
                     f"{fmt(p95[0], 3)} ± {fmt(p95[1], 3)}", fmt(agg(ms, "th50")[0], 2), fmt(th95[0], 2),
                     f"{fmt(nees[0], 1)} ± {fmt(nees[1], 1)}", fmt(agg(ms, "nees_med")[0], 2)])
    grow = []
    for (world, variant), gs in sorted(gn.items()):
        grow.append([world, variant, len(gs)] + [fmt(statistics.mean(g[k] for g in gs), 1)
                                                for k in ("fixed", "float", "single", "no_fix")]
                    + [fmt(statistics.mean(g["err_fix_p95"] for g in gs), 3)])
    txt = ["# E1 — Localization with degraded GNSS", "",
           "Four EKF configurations run at once on the SAME data (openfield_concept shadow filters); the robot "
           "follows the same route in every run (driver on the simulator's ground truth). Errors are evaluated at the "
           "ground-truth timestamp. NEES over (x, y, θ): consistent ⇔ mean ≈ 3. "
           "95 % interval of the mean of N independent runs: χ²(3N)/N "
           + ", ".join(f"(N = {n}: [{fmt(chi2.ppf(0.025, 3 * n) / n, 2)}, {fmt(chi2.ppf(0.975, 3 * n) / n, 2)}])"
                       for n in sorted({len(ms) for ms in per.values()})) + ".",
           "", "## GNSS state (share of time) and fix error", "",
           md_table(["world", "variant", "n", "RTK fixed %", "RTK float %", "single %", "no fix %",
                     "fix error p95 (m)"], grow), "",
           "Fix error = |delivered fix − Webots GPS reading| at the measurement instant: it measures only the added "
           "degradation; it does not include the simulated GPS's own noise (σ = 2 cm per axis) nor the offset the "
           "latency adds while the robot moves. The filters' errors are measured against the ground truth.", "",
           "## Error and consistency per configuration (mean ± std across runs)", "",
           md_table(["world", "GNSS", "configuration", "n", "error p50 (m)", "error p95 (m)", "heading p50 (°)",
                     "heading p95 (°)", "NEES mean", "NEES median"], rows), ""]
    for (world, variant) in sorted(example):
        txt.append(f"![E1 {world} {variant}](../images/E1_{world}_{variant}.png)")
    (common.RESULTS / "report_E1.md").write_text("\n".join(txt) + "\n")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
