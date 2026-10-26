"""Shared helpers for the experiment campaign (experiments/README.md).

Everything here is plumbing: paths, per-run config overlays, starting/stopping the stack, Ice access to the
bridge (simulator ground truth, driving the base) and the ground truth that lives in the .wbt worlds.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXP = REPO / "experiments"
RESULTS = EXP / "resultados"
IMAGES = EXP / "imagenes"
WORLDS_DIR = REPO / "webots-agri" / "worlds"
EXP_WORLDS = EXP / "worlds"
UTILS = REPO / "active_inference" / "utils"
WEBOTS = os.environ.get("WEBOTS", "/usr/local/bin/webots")
LOGS = Path.home() / ".local" / "logs"

# ── Components: where they live and which config they normally read ───────────────────────────────────────────
# (name used in the launcher TOMLs, cwd relative to the repo, binary, base config relative to cwd, layer)
COMPONENTS = {
    "bridge":             ("webots-bridge", "bin/Webots2Robocomp", "etc/config_husky", "sub"),
    "helios":             ("robocomp-robolab/components/hardware/laser/lidar3d_dds",
                           "env OMP_WAIT_POLICY=PASSIVE bin/lidar3d_dds", "etc/config_helios_husky_webots.toml", "sub"),
    "imu":                ("robocomp-robolab/components/hardware/imu/imu_dds", "bin/imu_dds", "etc/config.toml", "sub"),
    "zed":                ("robocomp-robolab/components/hardware/camera/zed_camera", "bin/zed_camera",
                           "etc/configHuskyWebot.toml", "sub"),
    "robot_concept":      ("active_inference/robot_concept", "bin/robot_concept", "etc/config_husky.toml", "cog"),
    "openfield_concept":  ("active_inference/openfield_concept", "bin/openfield_concept", "etc/config.toml", "cog"),
    "residual":           ("active_inference/residual_concept", "bin/residual_concept", "etc/config_husky.toml", "cog"),
    "controller":         ("active_inference/controller", "bin/controller", "etc/config_husky.toml", "cog"),
    "vegetation_concept": ("active_inference/vegetation_concept", "bin/vegetation_concept", "etc/config.toml", "cog"),
    "trunk_concept":      ("active_inference/trunk_concept", "bin/trunk_concept", "etc/config.toml", "cog"),
    "retina":             ("active_inference/retina", "bin/retina", "etc/config_husky.toml", "cog"),
    "human_concept":      ("active_inference/human_concept", "bin/human_concept", "etc/config.toml", "cog"),
}
ICE_NAMES = {
    "bridge": "Webots2Robocomp:tcp -h localhost -p 10006",
    "helios": "Lidar3D:tcp -h localhost -p 11990",
    "imu": "mediaplanedds:tcp -h localhost -p 11891",
}
# The two stacks the campaign uses. FULL = what apple.bash runs (minus the joystick, which would fight the
# route driver for the base). LOC = only what localization needs: E1 runs it with a ground-truth driver.
FULL_STACK = ["bridge", "helios", "imu", "zed", "robot_concept", "openfield_concept", "residual", "controller",
              "vegetation_concept", "trunk_concept", "retina", "human_concept"]
LOC_STACK = ["bridge", "imu", "robot_concept", "openfield_concept"]


def log(msg: str):
    print(f"[exp {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Config overlays ────────────────────────────────────────────────────────────────────────────────────────────
def _fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    return repr(v)


def override_config(text: str, key: str, value) -> str:
    """Set `Section.Key = value` in a component config, keeping every comment and every other line.

    Works on both styles used here: TOML with [Section] tables (the agents) and flat dotted keys (the bridge's
    etc/config_husky). A key that is absent is added — under its [Section] if the file has it, else as a dotted
    key at the end (valid TOML either way)."""
    sec, _, name = key.rpartition(".")
    val = _fmt(value)
    lines = text.splitlines()
    # 1) Flat dotted key anywhere at top level: `Section.Key = ...`
    pat_flat = re.compile(rf"^(\s*){re.escape(key)}\s*=")
    for i, ln in enumerate(lines):
        if pat_flat.match(ln):
            lines[i] = f"{key} = {val}   # [experiment overlay]"
            return "\n".join(lines) + "\n"
    # 2) [Section] table with `Key = ...`
    if sec:
        cur = None
        sec_line = None
        for i, ln in enumerate(lines):
            m = re.match(r"^\s*\[([^\[\]]+)\]\s*(#.*)?$", ln)
            if m:
                cur = m.group(1).strip().strip('"')
                if cur == sec:
                    sec_line = i
                continue
            if cur == sec and re.match(rf"^\s*{re.escape(name)}\s*=", ln):
                lines[i] = f"{name} = {val}   # [experiment overlay]"
                return "\n".join(lines) + "\n"
        if sec_line is not None:
            lines.insert(sec_line + 1, f"{name} = {val}   # [experiment overlay]")
            return "\n".join(lines) + "\n"
        has_tables = any(re.match(r"^\s*\[[^\[\]]+\]", ln) for ln in lines)
        if has_tables:
            lines += ["", f"[{sec}]", f"{name} = {val}   # [experiment overlay]"]
        else:
            lines.append(f"{key} = {val}   # [experiment overlay]")
        return "\n".join(lines) + "\n"
    lines.append(f"{key} = {val}   # [experiment overlay]")
    return "\n".join(lines) + "\n"


def write_overlay(component: str, overrides: dict, out_dir: Path) -> Path:
    """Copy the component's base config into out_dir with the overrides applied; return its absolute path."""
    cwd, _, cfg, _ = COMPONENTS[component]
    src = REPO / cwd / cfg
    text = src.read_text()
    for k, v in overrides.items():
        text = override_config(text, k, v)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{component}__{Path(cfg).name}"
    dst.write_text(text)
    return dst


# ── Launch / stop ─────────────────────────────────────────────────────────────────────────────────────────────
def _launcher_toml(components: list[str], cfg_paths: dict[str, Path], layer: str) -> str:
    out = []
    for c in components:
        cwd, binary, cfg, lay = COMPONENTS[c]
        if lay != layer:
            continue
        cfg_arg = str(cfg_paths.get(c, cfg))
        out.append("[[components]]")
        out.append(f'name = "{c}"')
        out.append(f'cwd = "{REPO / cwd}"')
        out.append(f'cmd = "{binary} {cfg_arg}"')
        if c in ICE_NAMES:
            out.append(f'ice_name = "{ICE_NAMES[c]}"')
        out.append("")
    return "\n".join(out)


def stack_running() -> bool:
    r = subprocess.run(["pgrep", "-f", r"^python3 (sub)?cognitive.py"], capture_output=True)
    return r.returncode == 0 or bool(_pgrep("webots-bin"))


def _pgrep(pattern: str) -> list[int]:
    # Webots by exact process NAME: `pgrep -f webots-bin` also matches any shell whose command line mentions it.
    args = ["pgrep", "-x", pattern] if pattern == "webots-bin" else ["pgrep", "-f", pattern]
    r = subprocess.run(args, capture_output=True, text=True)
    return [int(p) for p in r.stdout.split()]


def _wait_gone(pattern: str, seconds: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < seconds:
        if not _pgrep(pattern):
            return True
        time.sleep(1.0)
    return False


def stop_stack():
    """The graceful order of apple.bash --stop: cognitive layer, sensorimotor layer, then Webots. Never SIGKILL an
    agent (its graph nodes would leak); Webots holds no graph state, so it may be forced."""
    for pat, kids in (("^python3 cognitive.py", r"bin/(robot_concept|openfield_concept|residual_concept|controller|"
                                                 r"retina|human_concept|vegetation_concept|trunk_concept) "),
                      ("^python3 subcognitive.py", r"bin/(Webots2Robocomp|lidar3d_dds|imu_dds|zed_camera) ")):
        for pid in _pgrep(pat):
            os.kill(pid, signal.SIGINT)
        if not _wait_gone(kids, 45):
            log(f"WARNING: still running after 45 s: {kids}; sending SIGINT to them directly")
            for pid in _pgrep(kids):
                os.kill(pid, signal.SIGINT)
            _wait_gone(kids, 20)
    for pid in _pgrep("webots-bin"):
        os.kill(pid, signal.SIGTERM)
    if not _wait_gone("webots-bin", 15):
        for pid in _pgrep("webots-bin"):
            os.kill(pid, signal.SIGKILL)
    _wait_gone("webots-bin", 5)


def start_stack(world: Path, components: list[str], cfg_paths: dict[str, Path], run_dir: Path,
                minimize: bool = False, sub_wait_s: float = 25.0):
    """Webots with `world`, then subcognitive.py and cognitive.py on launcher TOMLs generated for this run."""
    if stack_running():
        raise RuntimeError("a stack is already running — stop it first (./apple.bash --stop)")
    run_dir.mkdir(parents=True, exist_ok=True)
    # The launchers reopen these logs only when they start each component: empty them now, or a readiness check
    # would read the PREVIOUS run's "-> Operating" lines.
    for c in components:
        for ext in ("out", "err"):
            p = LOGS / f"{c}.{ext}"
            if p.exists():
                p.write_text("")
    sub_toml = run_dir / "launch_sub.toml"
    cog_toml = run_dir / "launch_cog.toml"
    sub_toml.write_text(_launcher_toml(components, cfg_paths, "sub"))
    cog_toml.write_text(_launcher_toml(components, cfg_paths, "cog"))

    args = [WEBOTS, "--batch", "--mode=realtime"]
    if minimize:
        args.append("--minimize")
    args.append(str(world))
    subprocess.Popen(args, cwd=str(world.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(30):
        if _pgrep("webots-bin"):
            break
        time.sleep(1)
    time.sleep(8)
    env = dict(os.environ)
    subprocess.Popen(["python3", "subcognitive.py", str(sub_toml), "--no-bw", "--no-battery"], cwd=str(UTILS),
                     stdout=open(run_dir / "launcher_sub.log", "w"), stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True, env=env)
    time.sleep(sub_wait_s)
    if cog_toml.read_text().strip():
        subprocess.Popen(["python3", "cognitive.py", str(cog_toml), "--no-bw", "--no-web"], cwd=str(UTILS),
                         stdout=open(run_dir / "launcher_cog.log", "w"), stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True, env=env)


def collect_logs(components: list[str], run_dir: Path, tail_bytes: int = 4_000_000):
    """Copy the tail of each component's ~/.local/logs/<name>.{out,err} into the run folder."""
    d = run_dir / "logs"
    d.mkdir(parents=True, exist_ok=True)
    for c in components:
        for ext in ("out", "err"):
            src = LOGS / f"{c}.{ext}"
            if not src.exists():
                continue
            with open(src, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - tail_bytes))
                (d / f"{c}.{ext}").write_bytes(f.read())


# ── Ice: the bridge (ground truth + base) ─────────────────────────────────────────────────────────────────────
_ice = None


def ice():
    """(communicator, modules) with the bridge's slices loaded once."""
    global _ice
    if _ice is None:
        import Ice
        gen = REPO / "webots-bridge" / "generated"
        Ice.loadSlice(f"-I{gen} --all {gen / 'Webots2Robocomp.ice'}")
        Ice.loadSlice(f"-I{gen} --all {gen / 'OmniRobot.ice'}")
        Ice.loadSlice(f"-I{gen} --all {gen / 'GPS.ice'}")
        import RoboCompWebots2Robocomp, RoboCompOmniRobot, RoboCompGPS  # noqa: E401
        props = Ice.createProperties()
        props.setProperty("Ice.MessageSizeMax", "20004800")
        props.setProperty("Ice.Warn.Connections", "0")
        data = Ice.InitializationData()
        data.properties = props
        comm = Ice.initialize(data)
        _ice = (comm, RoboCompWebots2Robocomp, RoboCompOmniRobot, RoboCompGPS)
    return _ice


def bridge_proxy():
    comm, W, _, _ = ice()
    return W.Webots2RobocompPrx.uncheckedCast(comm.stringToProxy("webots2robocomp:tcp -h localhost -p 10006"))


def omni_proxy():
    comm, _, O, _ = ice()
    return O.OmniRobotPrx.uncheckedCast(comm.stringToProxy("omnirobot:tcp -h localhost -p 10004"))


def object_pose(prx, DEF: str):
    """(x, y, z, yaw) in metres/radians, world frame, from the supervisor; None if unknown."""
    try:
        p = prx.getObjectPose(DEF)
    except Exception:
        return None
    x, y, z = p.position.x / 1000.0, p.position.y / 1000.0, p.position.z / 1000.0
    q = p.orientation
    yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
    return x, y, z, yaw


def wait_for_bridge(timeout_s: float = 60.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            if object_pose(bridge_proxy(), "husky") is not None:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


# ── Ground truth stored in the worlds ─────────────────────────────────────────────────────────────────────────
def world_trees(world: Path) -> list[dict]:
    """Every tree DEF in a .wbt (AppleTree / YoungPalm): its DEF, (x, y) and, when present, the canopy fields."""
    text = world.read_text()
    out = []
    for m in re.finditer(r"DEF (\S+) (AppleTree|YoungPalm) \{(.*?)\n\}", text, re.S):
        body = m.group(3)
        t = re.search(r"translation\s+(\S+)\s+(\S+)\s+(\S+)", body)
        rec = {"def": m.group(1), "type": m.group(2), "x": float(t.group(1)), "y": float(t.group(2))}
        for f in ("height", "trunkHeight", "trunkRadius", "canopyRadius"):
            fm = re.search(rf"\b{f}\s+(\S+)", body)
            if fm:
                rec[f] = float(fm.group(1))
        out.append(rec)
    return out


def world_humans(world: Path) -> list[str]:
    return re.findall(r"DEF (\S+) Pedestrian \{", world.read_text())


def world_path(name: str) -> Path:
    """`husky_apple` -> the repo world; `exp_*` -> experiments/worlds; or a path."""
    p = Path(name)
    if p.suffix == ".wbt" and p.exists():
        return p.resolve()
    for d in (EXP_WORLDS, WORLDS_DIR):
        if (d / f"{name}.wbt").exists():
            return d / f"{name}.wbt"
    raise FileNotFoundError(name)
