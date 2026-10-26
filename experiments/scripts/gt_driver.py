#!/usr/bin/env python3
"""Drive the Husky along a fixed route on the SIMULATOR'S GROUND TRUTH (E1), bypassing the whole navigation stack.

    python3 gt_driver.py --route "1.25,-10.5 1.25,8.5 3.75,8.5" [--speed 0.6]

Why: E1 measures the localizer. If the robot were steered by the estimate being measured, a bad estimate would
change the trajectory and every configuration would drive a different path. On the ground truth the path is the
same in every run and every variant, and no other agent (controller, residual, perception) needs to run.

Pure pursuit (lookahead 1 m) on Webots2Robocomp.getObjectPose("husky"), commands through OmniRobot.setSpeedBase.
It first measures, with two short moves, which body axis is forward and the sign of the rotation command, so it
does not depend on the robot's frame conventions.
"""
from __future__ import annotations

import argparse
import math
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", required=True)
    ap.add_argument("--speed", type=float, default=0.6)
    ap.add_argument("--lookahead", type=float, default=1.0)
    ap.add_argument("--tol", type=float, default=0.35)
    a = ap.parse_args()
    route = [tuple(float(c) for c in wp.split(",")) for wp in a.route.split()]
    W = common.bridge_proxy()
    B = common.omni_proxy()
    stop = []
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))

    def pose():
        p = common.object_pose(W, "husky")
        return None if p is None else (p[0], p[1], p[3])

    def cmd(v, w):
        B.setSpeedBase(0.0, v * 1000.0, w)

    # ── Calibration: which way is forward, which way is +rot ─────────────────────────────────────────────────
    p0 = pose()
    cmd(0.3, 0.0)
    time.sleep(1.5)
    cmd(0.0, 0.0)
    time.sleep(0.5)
    p1 = pose()
    fwd_offset = wrap(math.atan2(p1[1] - p0[1], p1[0] - p0[0]) - p1[2])
    fwd_offset = round(fwd_offset / (math.pi / 2)) * (math.pi / 2)
    cmd(0.0, 0.5)
    time.sleep(1.0)
    cmd(0.0, 0.0)
    time.sleep(0.5)
    p2 = pose()
    rot_sign = 1.0 if wrap(p2[2] - p1[2]) > 0 else -1.0
    print(f"[gt_driver] forward = yaw {math.degrees(fwd_offset):+.0f} deg, rot sign {rot_sign:+.0f}", flush=True)

    t0 = time.time()
    k = 0
    while not stop and k < len(route):
        p = pose()
        if p is None:
            time.sleep(0.05)
            continue
        x, y, yaw = p
        h = wrap(yaw + fwd_offset)
        tx, ty = route[k]
        if math.hypot(tx - x, ty - y) < a.tol:
            print(f"[gt_driver] waypoint {k + 1}/{len(route)} ({tx}, {ty}) reached at {time.time() - t0:.1f} s", flush=True)
            k += 1
            continue
        # Carrot: on the segment from the previous waypoint, lookahead ahead of the projection.
        sx, sy = route[k - 1] if k > 0 else (x, y)
        dx, dy = tx - sx, ty - sy
        L = math.hypot(dx, dy)
        if L > 1e-6:
            s = max(0.0, min(L, ((x - sx) * dx + (y - sy) * dy) / L + a.lookahead))
            cx, cy = sx + dx * s / L, sy + dy * s / L
        else:
            cx, cy = tx, ty
        err = wrap(math.atan2(cy - y, cx - x) - h)
        if abs(err) > math.radians(50):
            v, w = 0.0, 0.8 * math.copysign(1.0, err)
        else:
            v = a.speed * max(0.2, math.cos(err))
            w = max(-1.0, min(1.0, 2.0 * err))
        cmd(v, rot_sign * w)
        time.sleep(0.05)
    cmd(0.0, 0.0)
    cmd(0.0, 0.0)
    B.stopBase()
    print(f"[gt_driver] done: {k}/{len(route)} waypoints in {time.time() - t0:.1f} s", flush=True)


if __name__ == "__main__":
    main()
