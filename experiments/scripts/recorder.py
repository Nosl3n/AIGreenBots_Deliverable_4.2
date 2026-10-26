#!/usr/bin/env python3
"""Experiment recorder: a read-only DSR agent (id 97) + the simulator's ground truth, written as JSON lines.

    python3 recorder.py OUT.jsonl --world husky_apple [--duration 300] [--rate 10]

Every 1/rate s one line {"k": "tick", ...}:
    t            wall time (s)
    est          robot pose from the graph: field<-robot (x, y) and heading (rad), what the controller reads
    gt           robot pose from the Webots supervisor (bridge getObjectPose("husky")): x, y, yaw
    hum_gt       each Pedestrian DEF of the world -> (x, y) from the supervisor
    persons      every `person` node: name, person_id, (x, y) in the field frame
Every second one line {"k": "map", ...}: trunks (name, x, y, P(exists)), residual obstacles (name, x, y, w, d),
plants (count). Every 5 s one line {"k": "rates", ...}: DSR update counts per edge/node type since the previous
line (pose publish rate, residual rate, ...).

Read-only: it never writes to the graph, so it can run beside any agent without changing what is measured.
Agent id 97 (run_route.py / send_goal.py use 98).
"""


import argparse
import json
import math
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import numpy as np  # noqa: E402

from pydsr import DSRGraph, inner_api  # noqa: E402

AGENT_ID = 97


def find_world(g):
    for t in ("field", "room"):
        nodes = g.get_nodes_by_type(t)
        if nodes:
            return nodes[0]
    return None


def pos_in(g, world_name: str, node_name: str):
    try:
        v = inner_api(g).transform(world_name, node_name)
        if v is not None and len(v) >= 2 and all(math.isfinite(c) for c in v[:3]):
            return float(v[0]), float(v[1]), float(v[2])
    except Exception:
        pass
    return None


def heading_in(g, world_name: str, node_name: str):
    """Angle of the node's +Y (forward) axis in the world frame, atan2 convention (east = 0, CCW).
    (From the 4x4 matrix: the vector overload of inner_api.transform segfaults in this pydsr build.)"""
    try:
        m = inner_api(g).get_transformation_matrix(world_name, node_name)
        if m is not None:
            return math.atan2(float(m[1][1]), float(m[0][1]))
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--world", default="husky_apple")
    ap.add_argument("--duration", type=float, default=0.0, help="seconds (0 = until SIGINT)")
    ap.add_argument("--rate", type=float, default=10.0)
    a = ap.parse_args()

    humans = common.world_humans(common.world_path(a.world))
    bridge = common.bridge_proxy()

    g = DSRGraph(0, "exp_recorder", AGENT_ID)
    def ring_rate(edge):
        """Publish rate of an RT edge from its own ring of timestamps (rt_timestamps, ms)."""
        try:
            ts = sorted(int(x) for x in edge.attrs["rt_timestamps"].value if int(x) > 0)
        except Exception:
            return None
        if len(ts) < 3 or ts[-1] <= ts[0]:
            return None
        return round(1000.0 * (len(ts) - 1) / (ts[-1] - ts[0]), 2)

    stop = []
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))

    out = open(a.out, "a", buffering=1)
    t0 = time.time()
    next_map = t0
    next_rates = t0 + 5.0
    world = robot = None
    period = 1.0 / a.rate
    while not stop and (a.duration <= 0 or time.time() - t0 < a.duration):
        tick = time.time()
        if world is None or robot is None:
            world = find_world(g)
            robots = g.get_nodes_by_type("robot")
            robot = robots[0] if robots else None
        rec = {"k": "tick", "t": round(tick, 3)}
        if world is not None and robot is not None:
            p = pos_in(g, world.name, robot.name)
            h = heading_in(g, world.name, robot.name)
            if p is not None:
                rec["est"] = [round(p[0], 4), round(p[1], 4), None if h is None else round(h, 5)]
            persons = []
            for n in g.get_nodes_by_type("person"):
                q = pos_in(g, world.name, n.name)
                pid = n.attrs["person_id"].value if "person_id" in n.attrs else None
                if q is not None:
                    persons.append([n.name, pid, round(q[0], 3), round(q[1], 3)])
            rec["persons"] = persons
        gt = common.object_pose(bridge, "husky")
        if gt is not None:
            rec["gt"] = [round(gt[0], 4), round(gt[1], 4), round(gt[3], 5)]
        hg = {}
        for d in humans:
            hp = common.object_pose(bridge, d)
            if hp is not None:
                hg[d] = [round(hp[0], 3), round(hp[1], 3)]
        rec["hum_gt"] = hg
        out.write(json.dumps(rec) + "\n")

        if tick >= next_map and world is not None:
            next_map = tick + 1.0
            trunks, obst = [], []
            plants = 0
            for n in g.get_nodes_by_type("plant"):
                if not n.name.startswith("trunk_"):
                    plants += 1
                    continue
                q = pos_in(g, world.name, n.name)
                pe = n.attrs["obj_exist_prob"].value if "obj_exist_prob" in n.attrs else None
                if q is not None:
                    trunks.append([n.name, round(q[0], 3), round(q[1], 3), None if pe is None else round(pe, 3)])
            for n in g.get_nodes_by_type("obstacle"):
                q = pos_in(g, world.name, n.name)
                w = n.attrs["width_m"].value if "width_m" in n.attrs else None
                dd = n.attrs["depth_m"].value if "depth_m" in n.attrs else None
                hh = n.attrs["height_m"].value if "height_m" in n.attrs else None
                if q is not None:
                    obst.append([n.name, round(q[0], 3), round(q[1], 3), w, dd, hh])
            occ = []
            for n in g.get_nodes_by_type("grid"):
                if "grid_occupied_cells" in n.attrs:
                    v = n.attrs["grid_occupied_cells"].value
                    occ = [[round(float(v[i]), 3), round(float(v[i + 1]), 3), round(float(v[i + 2]), 3)]
                           for i in range(0, len(v) - 2, 3)]
            agents = {}
            for n in g.get_nodes_by_type("agent"):
                st = n.attrs["agent_presence_state"].value if "agent_presence_state" in n.attrs else None
                agents[n.name] = st
            out.write(json.dumps({"k": "map", "t": round(tick, 3), "trunks": trunks, "obstacles": obst,
                                  "plants": plants, "agents": agents, "occ": occ}) + "\n")
        if tick >= next_rates and world is not None and robot is not None:
            next_rates = tick + 5.0
            rates = {}
            try:
                e = g.get_edge(robot.id, world.id, "RT")
                if e is not None:
                    rates["pose_rt_hz"] = ring_rate(e)
                    ts = [int(x) for x in e.attrs["rt_timestamps"].value if int(x) > 0]
                    if ts:
                        rates["pose_age_ms"] = int(time.time() * 1000) - max(ts)
                    cov = e.attrs["rt_covariance"].value if "rt_covariance" in e.attrs else None
                    if cov is not None:
                        rates["pose_cov"] = [round(float(c), 7) for c in cov]
            except Exception:
                pass
            ages, prates = [], []
            for n in g.get_nodes_by_type("person"):
                try:
                    pe = g.get_edge(world.id, n.id, "RT")
                    ts = [int(x) for x in pe.attrs["rt_timestamps"].value if int(x) > 0] if pe is not None else []
                    if ts:
                        ages.append(int(time.time() * 1000) - max(ts))
                        prates.append(ring_rate(pe))
                except Exception:
                    pass
            if ages:
                rates["person_age_ms"] = ages
                rates["person_rt_hz"] = prates
            out.write(json.dumps({"k": "rates", "t": round(tick, 3), **rates}) + "\n")
        time.sleep(max(0.0, period - (time.time() - tick)))
    out.close()


if __name__ == "__main__":
    main()
