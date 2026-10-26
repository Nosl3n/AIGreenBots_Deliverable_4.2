#!/usr/bin/env python3
"""CPU / RAM / GPU per component while an experiment runs (E5). JSON lines, one every --period seconds.

    python3 sysmon.py OUT.jsonl [--period 2]

Per process (matched by its binary): cpu % (100 = one core, from /proc/<pid>/stat deltas), RSS MB, GPU memory MB
(nvidia-smi --query-compute-apps). Whole machine: total CPU %, GPU utilisation %, GPU memory used.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time

BINARIES = {
    "webots": "webots-bin", "bridge": "Webots2Robocomp", "helios": "lidar3d_dds", "imu": "imu_dds",
    "zed": "zed_camera", "robot_concept": "robot_concept", "openfield_concept": "openfield_concept",
    "residual": "residual_concept", "controller": "controller", "vegetation_concept": "vegetation_concept",
    "trunk_concept": "trunk_concept", "retina": "retina", "human_concept": "human_concept",
}
CLK = os.sysconf("SC_CLK_TCK")


def pids_by_name() -> dict[str, int]:
    out = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            comm = open(f"/proc/{pid}/comm").read().strip()
        except OSError:
            continue
        for k, b in BINARIES.items():
            if comm == b[:15]:
                out[k] = int(pid)
    return out


def proc_times(pid: int):
    try:
        f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        rss = int(f[21]) * os.sysconf("SC_PAGE_SIZE") / 1e6
        return int(f[11]) + int(f[12]), rss
    except (OSError, IndexError):
        return None, None


def total_cpu():
    v = [int(x) for x in open("/proc/stat").readline().split()[1:]]
    idle = v[3] + v[4]
    return sum(v), idle


def gpu():
    res = {"util": None, "mem_used": None, "per_pid": {}}
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5).stdout.strip().split(",")
        res["util"], res["mem_used"] = float(o[0]), float(o[1])
        o = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5).stdout.strip()
        for ln in o.splitlines():
            p, m = ln.split(",")
            res["per_pid"][int(p)] = float(m)
    except Exception:
        pass
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--period", type=float, default=2.0)
    a = ap.parse_args()
    stop = []
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    out = open(a.out, "a", buffering=1)
    prev = {}
    prev_tot = total_cpu()
    while not stop:
        time.sleep(a.period)
        pids = pids_by_name()
        tot = total_cpu()
        dt_tot = tot[0] - prev_tot[0]
        machine = 100.0 * (1.0 - (tot[1] - prev_tot[1]) / dt_tot) if dt_tot > 0 else None
        prev_tot = tot
        g = gpu()
        rec = {"t": round(time.time(), 3), "cpu_machine_pct": machine, "gpu_util": g["util"],
               "gpu_mem_mb": g["mem_used"], "procs": {}}
        for k, pid in pids.items():
            ticks, rss = proc_times(pid)
            if ticks is None:
                continue
            key = (k, pid)
            if key in prev:
                t_prev, ticks_prev = prev[key]
                cpu = 100.0 * (ticks - ticks_prev) / CLK / (time.time() - t_prev)
                rec["procs"][k] = {"cpu": round(cpu, 1), "rss_mb": round(rss, 1),
                                   "gpu_mb": g["per_pid"].get(pid)}
            prev[key] = (time.time(), ticks)
        out.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
