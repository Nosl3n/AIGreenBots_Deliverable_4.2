#!/usr/bin/env python3
"""E2 — people tracking: CLEAR-MOT against the Pedestrians' supervisor positions.

    python3 analyze_people.py

MOTA, MOTP, identity switches per worker-minute, the longest camera occlusion survived with the same identity and
false births. Region evaluated: workers within EVAL_R of the robot (all around it — the LiDAR keeps people the
camera cannot see). Writes results/report_E2.md and images/E2_tracks_*.png.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.optimize import linear_sum_assignment  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from analysis_common import fmt, load_run, md_table, runs  # noqa: E402

EVAL_R = 10.0          # m around the robot
MATCH_GATE = 1.0       # m, person hypothesis <-> worker
CAM_HALF_FOV = 0.85    # rad (trunk_concept ZedHalfFovRad); the ZED's horizontal half field of view
CAM_RANGE = 10.0


# ── E2 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def cam_visible(rx, ry, ryaw, px, py, canopies) -> bool:
    """Geometric camera visibility of a worker: in the field of view, in range, no canopy disc on the line."""
    h = ryaw + math.pi / 2          # Webots yaw -> forward (+Y body) heading
    dx, dy = px - rx, py - ry
    d = math.hypot(dx, dy)
    if d > CAM_RANGE or d < 0.3:
        return False
    if abs((math.atan2(dy, dx) - h + math.pi) % (2 * math.pi) - math.pi) > CAM_HALF_FOV:
        return False
    for cx, cy, r in canopies:
        s = max(0.0, min(1.0, ((cx - rx) * dx + (cy - ry) * dy) / (d * d)))
        if 0.0 < s < 1.0 and math.hypot(rx + s * dx - cx, ry + s * dy - cy) < r:
            return False
    return True


def mot(R) -> dict:
    trees = common.world_trees(R["world"])
    canopies = [(t["x"], t["y"], t.get("canopyRadius", 0.45)) for t in trees]
    gt_seen = fn = fp = idsw = 0
    dists = []
    last_match: dict[str, str] = {}       # worker -> track name
    track_life: dict[str, int] = {}
    track_matched: dict[str, int] = {}
    vis_hist: dict[str, list] = {}        # worker -> [(t, visible, matched_track)]
    ticks = [t for t in R["ticks"] if "gt" in t]
    for tk in ticks:
        rx, ry, ryaw = tk["gt"]
        gts = {k: v for k, v in tk.get("hum_gt", {}).items() if math.hypot(v[0] - rx, v[1] - ry) < EVAL_R}
        # Hypotheses outside the evaluated region (plus the gate) are neither hits nor false positives.
        hyps = {p[0]: (p[2], p[3]) for p in tk.get("persons", [])
                if math.hypot(p[2] - rx, p[3] - ry) < EVAL_R + MATCH_GATE}
        for h in hyps:
            track_life[h] = track_life.get(h, 0) + 1
        gk, hk = list(gts), list(hyps)
        pairs = {}
        # Keep last frame's correspondences that are still within the gate (CLEAR-MOT), then Hungarian the rest.
        for g in gk:
            h = last_match.get(g)
            if h in hyps and math.dist(gts[g], hyps[h]) < MATCH_GATE and h not in pairs.values():
                pairs[g] = h
        rg = [g for g in gk if g not in pairs]
        rh = [h for h in hk if h not in pairs.values()]
        if rg and rh:
            D = np.array([[math.dist(gts[g], hyps[h]) for h in rh] for g in rg])
            r, c = linear_sum_assignment(np.where(D < MATCH_GATE, D, 1e6))
            for i, j in zip(r, c):
                if D[i, j] < MATCH_GATE:
                    pairs[rg[i]] = rh[j]
        for g, h in pairs.items():
            if g in last_match and last_match[g] != h:
                idsw += 1
            last_match[g] = h
            dists.append(math.dist(gts[g], hyps[h]))
            track_matched[h] = track_matched.get(h, 0) + 1
        gt_seen += len(gts)
        fn += len(gts) - len(pairs)
        fp += len(hyps) - len(pairs)
        for g, v in gts.items():
            vis_hist.setdefault(g, []).append((tk["t"], cam_visible(rx, ry, ryaw, v[0], v[1], canopies), pairs.get(g)))
    # Longest stretch with the worker NOT visible to the camera, bracketed by the SAME track before and after.
    max_occ, occ_kept, occ_lost = 0.0, 0, 0
    for g, hist in vis_hist.items():
        i = 0
        while i < len(hist):
            if hist[i][1]:
                i += 1
                continue
            j = i
            while j < len(hist) and not hist[j][1]:
                j += 1
            before = next((h[2] for h in reversed(hist[:i]) if h[2]), None)
            after = next((h[2] for h in hist[j:j + 20] if h[2]), None)
            dur = (hist[j - 1][0] - hist[i][0]) if j > i else 0.0
            if dur >= 1.0 and before is not None and j < len(hist):
                if after == before:
                    occ_kept += 1
                    max_occ = max(max_occ, dur)
                else:
                    occ_lost += 1
            i = j
    false_births = sum(1 for h, n in track_life.items() if track_matched.get(h, 0) < 0.2 * n)
    minutes = (ticks[-1]["t"] - ticks[0]["t"]) / 60.0 if len(ticks) > 1 else float("nan")
    n_workers = len(common.world_humans(R["world"]))
    return {"mota": 1.0 - (fn + fp + idsw) / max(1, gt_seen), "motp": statistics.mean(dists) if dists else float("nan"),
            "fn": fn, "fp": fp, "idsw": idsw, "gt": gt_seen, "idsw_wmin": idsw / max(1e-6, n_workers * minutes),
            "max_occ_s": max_occ, "occ_kept": occ_kept, "occ_lost": occ_lost, "false_births": false_births,
            "tracks": len(track_life), "minutes": minutes}


def plot_tracks(R, out):
    fig, ax = plt.subplots(figsize=(5.5, 7))
    for t in common.world_trees(R["world"]):
        ax.add_patch(plt.Circle((t["x"], t["y"]), t.get("canopyRadius", 0.4), color="green", alpha=0.12))
    hum, tr = {}, {}
    for tk in R["ticks"]:
        for k, v in tk.get("hum_gt", {}).items():
            hum.setdefault(k, []).append(v)
        for p in tk.get("persons", []):
            tr.setdefault(p[0], []).append((p[2], p[3]))
    for k, v in hum.items():
        v = np.array(v)
        ax.plot(v[:, 0], v[:, 1], "-", c="0.3", lw=2.5, alpha=0.35)
    cmap = plt.get_cmap("tab20")
    for i, (k, v) in enumerate(tr.items()):
        v = np.array(v)
        ax.plot(v[:, 0], v[:, 1], ".", ms=2, c=cmap(i % 20))
    gt = np.array([t["gt"][:2] for t in R["ticks"] if "gt" in t])
    if len(gt):
        ax.plot(gt[:, 0], gt[:, 1], "-", c="k", lw=0.8)
    ax.set_aspect("equal")
    ax.set_title(f"E2 {R['dir'].name}: real workers (grey) and tracks (colour = identity)", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def report_e2():
    rows, per = [], {}
    for rd in runs("E2"):
        R = load_run(rd)
        if not R["ticks"]:
            continue
        M = mot(R)
        var = rd.name.split("__")[1]
        per.setdefault(var, []).append(M)
        rows.append([rd.name, fmt(M["mota"]), fmt(M["motp"], 3), M["fn"], M["fp"], M["idsw"], fmt(M["idsw_wmin"], 3),
                     fmt(M["max_occ_s"], 1), f"{M['occ_kept']}/{M['occ_kept'] + M['occ_lost']}", M["false_births"],
                     M["tracks"], fmt(M["minutes"], 1)])
        plot_tracks(R, common.IMAGES / f"E2_tracks_{rd.name}.png")
    summ = [[v, len(ms), fmt(statistics.mean(m["mota"] for m in ms)), fmt(statistics.mean(m["motp"] for m in ms), 3),
             fmt(statistics.mean(m["idsw_wmin"] for m in ms), 3), fmt(max(m["max_occ_s"] for m in ms), 1),
             fmt(statistics.mean(m["false_births"] for m in ms), 1)] for v, ms in per.items()]
    txt = ["# E2 — People tracking", "",
           f"Evaluated region: workers within {EVAL_R} m of the robot (all around it). CLEAR-MOT matching with a "
           f"{MATCH_GATE} m gate. 'Occlusion' = a stretch in which the worker is not visible to the camera (outside the "
           "±49° field of view, or a canopy on the line of sight); it counts as kept if the same track follows the worker "
           "before and after it. Variants: fusion (ZED + LiDAR) and ZED only (HumanLidar.Enabled = false). The world has "
           "4 workers, so the IDSW denominator is 4 × the run's minutes.", "",
           md_table(["variant", "n", "MOTA", "MOTP (m)", "IDSW/(worker·min)", "longest kept occlusion (s)",
                     "false births"], summ), "",
           md_table(["run", "MOTA", "MOTP (m)", "FN", "FP", "IDSW", "IDSW/(worker·min)", "longest occlusion (s)",
                     "occlusions kept", "false births", "tracks", "min"], rows)]
    (common.RESULTS / "report_E2.md").write_text("\n".join(txt) + "\n")
    print("\n".join(txt))


if __name__ == "__main__":
    report_e2()
