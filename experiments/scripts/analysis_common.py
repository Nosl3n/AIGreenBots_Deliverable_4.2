"""Loading and geometry shared by the analysis scripts."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

import common

ROBOT_LEN, ROBOT_WID = 0.99, 0.686      # robot_concept/husky.json body depth_m x width_m
PERSON_R = 0.25                         # human_concept HumanLidar.BodyRadiusM


def load_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run.json").read_text()) if (run_dir / "run.json").exists() else {}
    ticks, maps, rates = [], [], []
    rec = run_dir / "record.jsonl"
    if rec.exists():
        for ln in rec.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            {"tick": ticks, "map": maps, "rates": rates}.get(r.get("k"), []).append(r)
    sysmon = []
    if (run_dir / "sysmon.jsonl").exists():
        for ln in (run_dir / "sysmon.jsonl").read_text().splitlines():
            try:
                sysmon.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    drv = (run_dir / "driver.log").read_text(errors="ignore") if (run_dir / "driver.log").exists() else ""
    world = common.world_path(meta.get("world", "husky_apple")) if meta else None
    return {"dir": run_dir, "meta": meta, "ticks": ticks, "maps": maps, "rates": rates, "sysmon": sysmon,
            "driver": drv, "world": world}


def runs(exp: str, variant: str | None = None, world: str | None = None) -> list[Path]:
    d = common.RESULTS / exp
    out = []
    for p in sorted(d.glob("*__*__s*")):
        w, v, _ = p.name.split("__")
        if (variant is None or v == variant) and (world is None or w == world) and (p / "run.json").exists():
            out.append(p)
    return out


def rect_dist(px, py, cx, cy, yaw, length=ROBOT_LEN, width=ROBOT_WID) -> float:
    """Distance from a point to the robot's body rectangle (0 inside). yaw = direction of the LONG axis."""
    dx, dy = px - cx, py - cy
    c, s = math.cos(yaw), math.sin(yaw)
    u = c * dx + s * dy
    v = -s * dx + c * dy
    ex = max(abs(u) - length / 2, 0.0)
    ey = max(abs(v) - width / 2, 0.0)
    return math.hypot(ex, ey)


def match(est: np.ndarray, gt: np.ndarray, gate: float):
    """Hungarian matching of 2-D points under a distance gate. Returns [(i_est, j_gt, d)]."""
    if len(est) == 0 or len(gt) == 0:
        return []
    D = np.linalg.norm(est[:, None, :] - gt[None, :, :], axis=2)
    C = np.where(D < gate, D, 1e6)
    r, c = linear_sum_assignment(C)
    return [(i, j, D[i, j]) for i, j in zip(r, c) if D[i, j] < gate]


def driver_summary(text: str) -> dict:
    m = re.search(r"done: (\d+)/(\d+) waypoints reached in ([\d.]+) s", text)
    out = {"reached": None, "total": None, "time_s": None}
    if m:
        out = {"reached": int(m.group(1)), "total": int(m.group(2)), "time_s": float(m.group(3))}
    out["timeouts"] = len(re.findall(r"waypoint \d+ timeout", text))
    return out


def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)
