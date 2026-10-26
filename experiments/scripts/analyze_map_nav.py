#!/usr/bin/env python3
"""E3 (trunk map), E4 (integrated navigation) and E5 (performance) from the full-stack runs.

    python3 analyze_map_nav.py              # every run found under results/E3, E4, E5

E3 reads the trunk map of every full-stack run (E4 base is the E3 base: same configuration), E4 the base runs,
E5 the CPU/GPU monitor, the DSR pose rate and the agents' own rate lines, and compares the trunk map with the
semantic model slowed down. Writes results/report_E3.md, report_E4.md, report_E5.md and figures in images/.
"""
from __future__ import annotations

import math
import re
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from analysis_common import (driver_summary, fmt, load_run, match, md_table, rect_dist, runs,  # noqa: E402
                            PERSON_R)

GATE = 0.25
IMG = common.IMAGES
IMG.mkdir(parents=True, exist_ok=True)


# ── E3 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def trunk_metrics(R: dict) -> dict | None:
    if not R["maps"] or R["world"] is None:
        return None
    trees = common.world_trees(R["world"])
    gt = np.array([[t["x"], t["y"]] for t in trees])
    last = R["maps"][-1]
    est = np.array([[t[1], t[2]] for t in last["trunks"]]) if last["trunks"] else np.zeros((0, 2))
    m = match(est, gt, GATE)
    tp = len(m)
    prec = tp / len(est) if len(est) else float("nan")
    # Trees the camera could have judged: within the ZED's 4 m of the robot's path at some instant.
    path = np.array([t["gt"][:2] for t in R["ticks"] if "gt" in t])
    seen = np.zeros(len(gt), bool)
    if len(path):
        for k in range(0, len(path), 5):
            seen |= np.linalg.norm(gt - path[k], axis=1) < 4.0
    rec_all = tp / len(gt)
    rec_seen = sum(1 for _, j, _ in m if seen[j]) / max(1, seen.sum())
    f1 = 2 * prec * rec_all / (prec + rec_all) if prec + rec_all > 0 else float("nan")
    err = float(np.mean([d for _, _, d in m])) if m else float("nan")
    # Over the whole run: every trunk NAME, its last position, and whether it survived to the end.
    lastpos, last_t = {}, {}
    for mp in R["maps"]:
        for t in mp["trunks"]:
            lastpos[t[0]] = (t[1], t[2])
            last_t[t[0]] = mp["t"]
    final_names = {t[0] for t in last["trunks"]}
    hours = max(1e-6, (R["maps"][-1]["t"] - R["maps"][0]["t"]) / 3600.0)
    false_names, wrong_removals = [], []
    for name, (x, y) in lastpos.items():
        d = float(np.min(np.linalg.norm(gt - np.array([x, y]), axis=1)))
        if d >= GATE:
            false_names.append(name)
        elif name not in final_names:
            wrong_removals.append(name)
    return {"n_est": len(est), "n_gt": len(gt), "tp": tp, "precision": prec, "recall": rec_all,
            "recall_seen": rec_seen, "n_seen": int(seen.sum()), "f1": f1, "err_m": err,
            "false_h": len(false_names) / hours, "false_n": len(false_names),
            "wrong_removals_h": len(wrong_removals) / hours, "wrong_removals": len(wrong_removals), "hours": hours,
            "est": est, "gt": gt, "matches": m, "path": path}


def plot_trunks(R, M, title, out):
    fig, ax = plt.subplots(figsize=(5.5, 7))
    ax.scatter(M["gt"][:, 0], M["gt"][:, 1], s=60, facecolors="none", edgecolors="green", label="real tree")
    if len(M["est"]):
        matched = {i for i, _, _ in M["matches"]}
        ok = np.array([M["est"][i] for i in range(len(M["est"])) if i in matched]).reshape(-1, 2)
        bad = np.array([M["est"][i] for i in range(len(M["est"])) if i not in matched]).reshape(-1, 2)
        ax.scatter(ok[:, 0], ok[:, 1], s=14, c="tab:blue", label="published trunk (hit)")
        if len(bad):
            ax.scatter(bad[:, 0], bad[:, 1], s=40, c="red", marker="x", label="false trunk")
    if len(M["path"]):
        ax.plot(M["path"][:, 0], M["path"][:, 1], "-", c="0.6", lw=0.8, label="real trajectory")
    ax.set_aspect("equal")
    ax.set_xlabel("x (m, east)")
    ax.set_ylabel("y (m, north)")
    ax.set_title(title, fontsize=9)
    ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def report_e3():
    rows, per_var = [], {}
    sources = [("E4", "base"), ("E3", "base"), ("E3", "no_lidar_confirm"), ("E3", "no_pvis"),
               ("E5", "slow_semantic")]
    for exp, var in sources:
        for rd in runs(exp, var):
            R = load_run(rd)
            M = trunk_metrics(R)
            if M is None:
                continue
            label = "base" if var == "base" else var
            per_var.setdefault(label, []).append(M)
            rows.append([f"{exp}/{rd.name}", label, M["n_est"], M["tp"], fmt(M["precision"]), fmt(M["recall"]),
                         f"{fmt(M['recall_seen'])} ({M['n_seen']})", fmt(M["f1"]), fmt(M["err_m"], 3),
                         f"{M['false_n']} ({fmt(M['false_h'], 1)}/h)", f"{M['wrong_removals']} ({fmt(M['wrong_removals_h'], 1)}/h)"])
            plot_trunks(R, M, f"E3 {label} — {rd.name}", IMG / f"E3_trunk_map_{label}_{rd.name}.png")
    summ = []
    for label, Ms in per_var.items():
        def mean(k):
            v = [m[k] for m in Ms if m[k] == m[k]]
            return statistics.mean(v) if v else float("nan")
        summ.append([label, len(Ms), fmt(mean("precision")), fmt(mean("recall")), fmt(mean("recall_seen")),
                     fmt(mean("f1")), fmt(mean("err_m"), 3), fmt(mean("false_h"), 1), fmt(mean("wrong_removals_h"), 1)])
    txt = ["# E3 — Trunk map against the world's ground truth", "",
           f"Hungarian matching with a {GATE} m gate against the {per_var and next(iter(per_var.values()))[0]['n_gt']} "
           "tree positions of the .wbt (written by gen_apple_rows.py). 'Recall (seen)' counts only the trees that came "
           "within 4 m of the robot (the ZED's absence range). The base runs are the E4 missions.", "",
           "## Summary per variant (mean over runs)", "",
           md_table(["variant", "n", "precision", "recall", "recall (seen)", "F1", "mean error (m)",
                     "false trunks/h", "wrong removals/h"], summ), "",
           "## Per run", "",
           md_table(["run", "variant", "published", "hits", "precision", "recall",
                     "recall seen (n)", "F1", "error (m)", "false", "wrong removals"], rows)]
    (common.RESULTS / "report_E3.md").write_text("\n".join(txt) + "\n")
    print("\n".join(txt))


# ── E4 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def nav_metrics(R) -> dict:
    trees = common.world_trees(R["world"])
    T = np.array([[t["x"], t["y"], t.get("trunkRadius", 0.04)] for t in trees])
    min_trunk, min_person = float("inf"), float("inf")
    contacts_t, contacts_p = 0, 0
    in_t = in_p = False
    errs, path_len, prev = [], 0.0, None
    for tk in R["ticks"]:
        if "gt" not in tk:
            continue
        x, y, yaw = tk["gt"]
        yaw += math.pi / 2          # Webots yaw -> the body's forward (+Y) axis, i.e. its long side
        if prev is not None:
            path_len += math.hypot(x - prev[0], y - prev[1])
        prev = (x, y)
        near = T[np.abs(T[:, 0] - x) + np.abs(T[:, 1] - y) < 3.0]
        dt = min((rect_dist(a, b, x, y, yaw) - r for a, b, r in near), default=float("inf"))
        dp = min((rect_dist(p[0], p[1], x, y, yaw) - PERSON_R for p in tk.get("hum_gt", {}).values()),
                 default=float("inf"))
        min_trunk, min_person = min(min_trunk, dt), min(min_person, dp)
        contacts_t += (dt <= 0) and not in_t
        contacts_p += (dp <= 0) and not in_p
        in_t, in_p = dt <= 0, dp <= 0
        if "est" in tk:
            errs.append(math.hypot(tk["est"][0] - x, tk["est"][1] - y))
    d = driver_summary(R["driver"])
    return {**d, "trunk_clearance": min_trunk, "person_clearance": min_person, "trunk_collisions": contacts_t,
            "person_collisions": contacts_p, "path_m": path_len,
            "loc_err_p50": float(np.percentile(errs, 50)) if errs else None,
            "loc_err_p95": float(np.percentile(errs, 95)) if errs else None}


def plot_route(R, title, out):
    trees = common.world_trees(R["world"])
    fig, ax = plt.subplots(figsize=(5.5, 7))
    for t in trees:
        ax.add_patch(plt.Circle((t["x"], t["y"]), t.get("canopyRadius", 0.4), color="green", alpha=0.15))
        ax.plot(t["x"], t["y"], ".", c="darkgreen", ms=3)
    gt = np.array([t["gt"][:2] for t in R["ticks"] if "gt" in t])
    est = np.array([t["est"][:2] for t in R["ticks"] if "est" in t])
    if len(gt):
        ax.plot(gt[:, 0], gt[:, 1], "-", c="k", lw=1.2, label="real (Webots)")
    if len(est):
        ax.plot(est[:, 0], est[:, 1], "--", c="tab:blue", lw=0.9, label="estimated (EKF)")
    hum = {}
    for t in R["ticks"]:
        for k, v in t.get("hum_gt", {}).items():
            hum.setdefault(k, []).append(v)
    for k, v in hum.items():
        v = np.array(v)
        ax.plot(v[:, 0], v[:, 1], ":", lw=0.8, label=f"worker {k}")
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def report_e4():
    rows, Ms = [], []
    for rd in runs("E4", "base"):
        R = load_run(rd)
        if not R["ticks"]:
            continue
        M = nav_metrics(R)
        Ms.append(M)
        rows.append([rd.name, f"{M['reached']}/{M['total']}", fmt(M["time_s"], 1), fmt(M["path_m"], 1),
                     fmt(M["trunk_clearance"]), fmt(M["person_clearance"]), M["trunk_collisions"],
                     M["person_collisions"], fmt(M["loc_err_p50"], 3), fmt(M["loc_err_p95"], 3)])
        plot_route(R, f"E4 — {rd.name}", IMG / f"E4_trajectory_{rd.name}.png")
    ok = [M for M in Ms if M["reached"] is not None]
    succ = sum(M["reached"] for M in ok) / max(1, sum(M["total"] for M in ok))
    full = sum(1 for M in ok if M["reached"] == M["total"]) / max(1, len(ok))
    txt = ["# E4 — Integrated navigation", "",
           f"Missions: {len(ok)}. Waypoint success: {fmt(100 * succ, 1)} %. Complete missions: {fmt(100 * full, 1)} %.",
           f"Mean mission time: {fmt(statistics.mean([M['time_s'] for M in ok]) if ok else None, 1)} s. "
           f"Minimum clearance to trunks: {fmt(min([M['trunk_clearance'] for M in ok], default=None))} m; to people: "
           f"{fmt(min([M['person_clearance'] for M in ok], default=None))} m. Collisions (contacts of the "
           f"{0.99}x{0.686} m body with a trunk / with a person's 0.25 m disc): "
           f"{sum(M['trunk_collisions'] for M in ok)} / {sum(M['person_collisions'] for M in ok)}.", "",
           "Clearance = distance from the body rectangle (Webots ground-truth pose) to the trunk (real radius) or to the person. GNSS not degraded; the published (A) filter drives.",
           "", md_table(["run", "waypoints", "time (s)", "path (m)", "trunk clearance (m)",
                          "person clearance (m)", "trunk coll.", "person coll.", "loc. error p50 (m)",
                          "loc. error p95 (m)"], rows)]
    (common.RESULTS / "report_E4.md").write_text("\n".join(txt) + "\n")
    print("\n".join(txt))


# ── E5 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
RATE_PATTERNS = {
    "openfield_concept (pose EKF)": ("openfield_concept", r"Fps = (\d+) \[openfield_concept Compute\]"),
    "residual (residual grid)": ("residual", r"\[perf\] fps=([\d.]+)"),
    "controller (planner)": ("controller", r"\[CTRL\] fps=([\d.]+)"),
    "retina (loop)": ("retina", r"Fps = (\d+) \[Compute\]"),
    "retina: ZED frames processed": ("retina", r"\[ZedSource\] 5s hits=\d+ \(([\d.]+) Hz\)"),
    "trunk_concept": ("trunk_concept", r"Fps = (\d+) \[trunk_concept Compute\]"),
    "vegetation_concept": ("vegetation_concept", r"Fps = (\d+) \[vegetation_concept Compute\]"),
    "human_concept": ("human_concept", r"Fps = (\d+) \[Compute\]"),
    "robot_concept": ("robot_concept", r"Fps = (\d+) Compute"),
    "zed (driver)": ("zed", r"Fps = (\d+) ZED compute"),
    "helios (LiDAR)": ("helios", r"Fps = (\d+) Num points"),
}


def rates_from_logs(rd: Path) -> dict:
    out = {}
    for label, (comp, rx) in RATE_PATTERNS.items():
        p = rd / "logs" / f"{comp}.out"
        if not p.exists():
            continue
        vals = [float(v) for v in re.findall(rx, p.read_text(errors="ignore"))]
        if vals:
            vals = vals[len(vals) // 5:]   # drop the start-up fifth
            out[label] = (statistics.median(vals), min(vals))
    return out


def report_e5():
    base = runs("E4", "base") + runs("E5", "base")
    if not base:
        return
    rd = base[0]
    R = load_run(rd)
    rates = rates_from_logs(rd)
    pose_hz = [r.get("pose_rt_hz") for r in R["rates"] if r.get("pose_rt_hz")]
    procs = {}
    gpu_u, cpu_m = [], []
    for s in R["sysmon"]:
        if s.get("gpu_util") is not None:
            gpu_u.append(s["gpu_util"])
        if s.get("cpu_machine_pct") is not None:
            cpu_m.append(s["cpu_machine_pct"])
        for k, v in s["procs"].items():
            procs.setdefault(k, []).append(v)
    rows = [[k, fmt(statistics.mean(x["cpu"] for x in v), 0), fmt(max(x["cpu"] for x in v), 0),
             fmt(statistics.mean(x["rss_mb"] for x in v), 0),
             fmt(max((x["gpu_mb"] or 0) for x in v), 0) if any(x["gpu_mb"] for x in v) else "—"]
            for k, v in sorted(procs.items(), key=lambda kv: -statistics.mean(x["cpu"] for x in kv[1]))]
    rate_rows = [["pose in the graph (RT ring robot→field)", fmt(statistics.median(pose_hz), 1) if pose_hz else "—",
                  fmt(min(pose_hz), 1) if pose_hz else "—", "≥ 50 Hz"]]
    for k, (med, mn) in rates.items():
        req = "≥ 2 Hz" if k.startswith("residual") else ""
        rate_rows.append([k, fmt(med, 1), fmt(mn, 1), req])
    # Figure: CPU per agent.
    fig, ax = plt.subplots(figsize=(7, 3.6))
    names = [r[0] for r in rows]
    ax.barh(names, [float(r[1]) for r in rows], color="tab:blue")
    ax.set_xlabel("mean CPU (% of one core)")
    ax.invert_yaxis()
    ax.set_title(f"E5 — CPU per agent ({rd.name})", fontsize=9)
    fig.tight_layout()
    fig.savefig(IMG / "E5_cpu_per_agent.png", dpi=130)
    plt.close(fig)
    # E3 with the semantic model slowed down: the per-reference-look normalisation should keep the map the same.
    cmp_rows = []
    for exp, var in (("E4", "base"), ("E5", "slow_semantic")):
        for r2 in runs(exp, var):
            R2 = load_run(r2)
            M = trunk_metrics(R2)
            sem = None
            tl = r2 / "logs" / "trunk_concept.out"
            looks = re.findall(r"\(looks (\d+)\)", tl.read_text(errors="ignore")) if tl.exists() else []
            span = (R2["meta"].get("driver_end", 0) - R2["meta"].get("start", 0)) - 45.0   # minus start-up
            if looks and span > 0:
                sem = int(looks[-1]) / span
            if M:
                cmp_rows.append([f"{exp}/{var}/{r2.name.split('__')[-1]}", fmt(sem, 1), M["n_est"],
                                 fmt(M["precision"]), fmt(M["recall"]), fmt(M["f1"]), fmt(M["err_m"], 3),
                                 fmt(M["false_h"], 1), fmt(M["wrong_removals_h"], 1)])
    # Latencies: age of the pose / person RT samples when the recorder reads them (graph propagation + estimator
    # stamp), and the controller's own command age (scan -> velocity command), over every full-stack run.
    pose_age, pers_age, cmd_age = [], [], []
    for r2 in runs("E4", "base") + runs("E5") + runs("E3"):
        R2 = load_run(r2)
        for r in R2["rates"]:
            if r.get("pose_age_ms") is not None:
                pose_age.append(r["pose_age_ms"])
            pers_age += r.get("person_age_ms", [])
        p = r2 / "logs" / "controller.out"
        if p.exists():
            cmd_age += [float(v) for v in re.findall(r"cmd age max (\d+) ms", p.read_text(errors="ignore"))]
    lat_rows = []
    for name, v in (("robot pose in the graph (age when read)", pose_age),
                    ("people in the graph (age of the last RT sample)", pers_age),
                    ("controller: max age of the velocity command (per report)", cmd_age)):
        if v:
            lat_rows.append([name, len(v), fmt(float(np.median(v)), 0), fmt(float(np.percentile(v, 95)), 0),
                             fmt(float(np.max(v)), 0)])
    txt = ["# E5 — Computational performance", "",
           "PC: AMD Ryzen 9 9950X3D (16 cores / 32 threads), 60 GiB RAM, NVIDIA GeForce RTX 5070 Ti 16 GB "
           "(driver 595.91), Ubuntu 24.04.5, kernel 7.0.", "",
           f"Measured run: {rd.name}. Mean machine CPU {fmt(statistics.mean(cpu_m), 0) if cpu_m else '—'} % "
           f"(of 3200 %), mean GPU {fmt(statistics.mean(gpu_u), 0) if gpu_u else '—'} %.", "",
           "## Rates (median / minimum after start-up)", "",
           md_table(["stream", "median (Hz)", "minimum (Hz)", "requirement"], rate_rows), "",
           "## Latencies (ms)", "",
           md_table(["measure", "n", "median", "p95", "max"], lat_rows) if lat_rows else "(no data)", "",
           "## CPU / memory / GPU per process", "", "![](../images/E5_cpu_per_agent.png)", "",
           md_table(["process", "mean CPU (%)", "max CPU (%)", "RSS (MB)", "GPU memory (MB)"], rows), "",
           "## E3 with the semantic model slowed down (Semantic.decimation = 4)", "",
           "Trunk evidence is weighted per 'reference look' (LookPeriodMs = 530 ms); if the normalisation works, the "
           "map does not depend on how many inferences per second the GPU runs.", "",
           md_table(["run", "semantic looks/s (approx.)", "published", "precision", "recall", "F1",
                     "error (m)", "false/h", "wrong removals/h"], cmp_rows)]
    (common.RESULTS / "report_E5.md").write_text("\n".join(txt) + "\n")
    print("\n".join(txt))


if __name__ == "__main__":
    report_e3()
    print()
    report_e4()
    print()
    report_e5()
