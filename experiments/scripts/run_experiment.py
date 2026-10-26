#!/usr/bin/env python3
"""Run ONE experiment run: config overlays -> stack up -> recorder + sysmon -> driver -> stack down -> logs.

    python3 run_experiment.py E3 --variante base [--mundo husky_apple] [--semilla 1] [--capturas]
    python3 run_experiment.py --lista                 # experiments and variants in configs/experimentos.toml

Every experiment and variant lives in experiments/configs/experimentos.toml (see experiments/README.md): a variant
is only a set of `component -> {"Section.Key" = value}` overrides applied to COPIES of the components' configs
(written into the run folder), so the repo configs are never touched and every run records exactly what it ran.

Output: experiments/resultados/<EXP>/<mundo>__<variante>__s<semilla>/ with
    record.jsonl   recorder.py (poses, ground truth, persons, trunks, obstacles, DSR rates)
    sysmon.jsonl   sysmon.py (CPU / RAM / GPU per component)
    driver.log     the route driver's output
    cfg/           the overlaid configs;  launch_*.toml  the generated launcher files
    logs/          tail of each component's stdout/stderr;  openfield/  the localization CSVs
    run.json       what was run (experiment, variant, world, seed, times, outcome)
"""
from __future__ import annotations

import argparse
import json
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from common import log  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
DEFS = common.EXP / "configs" / "experimentos.toml"


def load_defs() -> dict:
    with open(DEFS, "rb") as f:
        return tomllib.load(f)


def merged_overrides(defs: dict, exp: str, variant: str, seed: int) -> dict[str, dict]:
    """common overrides <- experiment overrides <- variant overrides; '{seed}' in a string value -> the seed."""
    out: dict[str, dict] = {}
    layers = [defs.get("comun", {}).get("overrides", {}), defs[exp].get("overrides", {}),
              defs[exp]["variantes"].get(variant, {})]
    for layer in layers:
        for comp, kv in layer.items():
            if not isinstance(kv, dict):
                continue
            for k, v in kv.items():
                if v == "{seed}":
                    v = seed
                out.setdefault(comp, {})[k] = v
    return out


def wait_operating(run_dir: Path, components: list[str], timeout_s: float) -> bool:
    """Ready = every cognitive agent of the run prints its Operating banner, or the robot pose reaches the graph."""
    t0 = time.time()
    cog = [c for c in components if common.COMPONENTS[c][3] == "cog"]
    while time.time() - t0 < timeout_s:
        ok = True
        for c in cog:
            txt = ""
            for ext in ("out", "err"):
                try:
                    with open(common.LOGS / f"{c}.{ext}", "rb") as f:
                        txt += f.read(3_000_000).decode(errors="ignore")
                except OSError:
                    pass
            if "-> Operating" not in txt and "operating_latched=true" not in txt and '"to":"Operating"' not in txt:
                ok = False
                break
        if ok:
            return True
        time.sleep(2.0)
    return False


def git_state(run_dir: Path) -> dict:
    """Commit the run started from, and the uncommitted changes as a patch next to run.json (none if clean)."""
    def git(*args):
        return subprocess.run(["git", "-C", str(common.REPO), *args], capture_output=True, text=True).stdout
    diff = git("diff", "HEAD")
    if diff:
        (run_dir / "git.diff").write_text(diff)
    return {"commit": git("rev-parse", "HEAD").strip(), "cambios_sin_commit": bool(diff or git("status", "--porcelain"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp", nargs="?")
    ap.add_argument("--variante", default="base")
    ap.add_argument("--mundo", default=None)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--duracion", type=float, default=None, help="override the experiment's duration (s)")
    ap.add_argument("--capturas", action="store_true", help="take window screenshots during the run")
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--etiqueta", default="", help="suffix for the run folder")
    a = ap.parse_args()

    defs = load_defs()
    if a.lista or not a.exp:
        for k, v in defs.items():
            if k == "comun":
                continue
            print(f"{k}: {v.get('descripcion', '')}")
            for var in v.get("variantes", {}):
                print(f"    --variante {var}")
        return

    E = defs[a.exp]
    world_name = a.mundo or E.get("mundo", "husky_apple")
    world = common.world_path(world_name)
    stack = common.FULL_STACK if E.get("pila", "completa") == "completa" else common.LOC_STACK
    stack = [c for c in stack if c not in E.get("excluir", [])]
    duration = a.duracion or float(E.get("duracion_s", 300))
    run_dir = common.RESULTS / a.exp / f"{world.stem}__{a.variante}__s{a.semilla}{a.etiqueta}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    overrides = merged_overrides(defs, a.exp, a.variante, a.semilla)
    cfg_paths = {c: common.write_overlay(c, kv, run_dir / "cfg") for c, kv in overrides.items() if c in stack}
    meta = {"exp": a.exp, "variante": a.variante, "mundo": world.stem, "semilla": a.semilla, "pila": stack,
            "overrides": overrides, "inicio": time.time(), "duracion_s": duration, **git_state(run_dir)}
    log(f"{a.exp} / {a.variante} / {world.stem} / seed {a.semilla} -> {run_dir}")

    common.stop_stack() if common.stack_running() else None
    # openfield's CSVs are per run: move the old ones aside so the run's files are only this run.
    of_tmp = common.REPO / "active_inference/openfield_concept/tmp"
    for f in of_tmp.glob("exp_*.csv"):
        f.unlink()

    procs = []
    outcome = "ok"
    try:
        common.start_stack(world, stack, cfg_paths, run_dir, minimize=bool(E.get("minimizar", False)))
        if not common.wait_for_bridge(90):
            raise RuntimeError("bridge never answered")
        ready = wait_operating(run_dir, stack, float(E.get("espera_operating_s", 150)))
        meta["operating"] = ready
        log("agents Operating" if ready else "WARNING: not every agent printed Operating; going on")
        time.sleep(float(E.get("calentamiento_s", 10)))

        procs.append(subprocess.Popen([sys.executable, str(SCRIPTS / "recorder.py"), str(run_dir / "record.jsonl"),
                                       "--world", str(world), "--rate", str(E.get("rate_hz", 10))],
                                      stdout=open(run_dir / "recorder.log", "w"), stderr=subprocess.STDOUT))
        procs.append(subprocess.Popen([sys.executable, str(SCRIPTS / "sysmon.py"), str(run_dir / "sysmon.jsonl")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(3)

        driver = None
        drv = E.get("conductor", "ruta")
        if drv == "ruta":
            cmd = [sys.executable, str(common.UTILS / "run_route.py"), "--route", E["ruta"],
                   "--timeout", str(E.get("timeout_waypoint_s", 120)), "--tol", str(E.get("tol_m", 0.6))]
            driver = subprocess.Popen(cmd, cwd=str(common.UTILS), stdout=open(run_dir / "driver.log", "w"),
                                      stderr=subprocess.STDOUT)
        elif drv == "gt":
            cmd = [sys.executable, str(SCRIPTS / "gt_driver.py"), "--route", E["ruta"],
                   "--speed", str(E.get("velocidad", 0.6))]
            driver = subprocess.Popen(cmd, stdout=open(run_dir / "driver.log", "w"), stderr=subprocess.STDOUT)

        t0 = time.time()
        meta["t0_driver"] = t0
        shots = [float(s) for s in E.get("capturas_s", [60, 150])] if a.capturas else []
        while time.time() - t0 < duration:
            el = time.time() - t0
            for s in list(shots):
                if el >= s:
                    shots.remove(s)
                    import capturas
                    capturas.open_zed()
                    time.sleep(2)
                    got = capturas.capture(run_dir / "capturas", prefix=f"t{int(s):04d}_")
                    log(f"screenshots t={s:.0f}s: {len(got)}")
            if driver is not None and driver.poll() is not None :
                log("driver finished")
                break
            time.sleep(1.0)
        if driver is not None and driver.poll() is None:
            driver.send_signal(signal.SIGINT)
            try:
                driver.wait(15)
            except subprocess.TimeoutExpired:
                driver.terminate()
        meta["fin_conductor"] = time.time()
    except Exception as e:
        outcome = f"error: {e}"
        log(outcome)
    finally:
        for p in procs:
            p.send_signal(signal.SIGINT)
        for p in procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.terminate()
        common.stop_stack()
        common.collect_logs(stack, run_dir)
        dst = run_dir / "openfield"
        dst.mkdir(exist_ok=True)
        for f in of_tmp.glob("exp_*.csv"):
            shutil.move(str(f), dst / f.name)
        meta["fin"] = time.time()
        meta["resultado"] = outcome
        (run_dir / "run.json").write_text(json.dumps(meta, indent=2, default=str))
        log(f"done ({outcome})")


if __name__ == "__main__":
    main()
