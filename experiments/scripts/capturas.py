#!/usr/bin/env python3
"""Screenshots of the stack's windows (X11), by window class — no window manager tricks, no focus changes.

    python3 capturas.py OUT_DIR [--prefix 01_] [--zed]

Captures Webots, the controller map, the openfield localization window (trajectories), the DSR graph
(robot_concept) and the retina windows; --zed first presses retina's "ZED" button so its camera view opens.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from pathlib import Path

DISPLAY = os.environ.get("DISPLAY", ":1")
WANTED = {  # file stem -> (WM_CLASS instance, title regex)
    "webots": ("webots-bin", r"\.wbt"),
    "controller_mapa": ("controller", r"^controller"),
    "openfield_trayectorias": ("openfield_concept", r"openfield_concept"),
    "grafo_dsr": ("robot_concept", r"robot_concept"),
    "retina_estado": ("retina", r"^Retina$"),
    "zed_yolo": ("retina", r"^ZED$"),
}


def windows():
    o = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True, text=True,
                       env={**os.environ, "DISPLAY": DISPLAY}).stdout
    out = []
    for ln in o.splitlines():
        m = re.match(r'\s*(0x[0-9a-f]+) "(.*)": \("([^"]*)" "([^"]*)"\)\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)\s+\+(-?\d+)\+(-?\d+)', ln)
        if m:
            out.append({"id": m.group(1), "title": m.group(2), "inst": m.group(3), "w": int(m.group(5)),
                        "h": int(m.group(6)), "ax": int(m.group(9)), "ay": int(m.group(10))})
    return out


def click(x: int, y: int):
    from Xlib import X, display
    from Xlib.ext import xtest
    d = display.Display(DISPLAY)
    xtest.fake_input(d, X.MotionNotify, x=x, y=y)
    d.sync()
    time.sleep(0.15)
    xtest.fake_input(d, X.ButtonPress, 1)
    d.sync()
    time.sleep(0.08)
    xtest.fake_input(d, X.ButtonRelease, 1)
    d.sync()


def activate(win_id: str):
    from Xlib import X, display, protocol
    d = display.Display(DISPLAY)
    root = d.screen().root
    w = d.create_resource_object("window", int(win_id, 16))
    atom = d.intern_atom("_NET_ACTIVE_WINDOW")
    ev = protocol.event.ClientMessage(window=w, client_type=atom, data=(32, [2, X.CurrentTime, 0, 0, 0]))
    root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
    d.sync()


def open_zed():
    ws = windows()
    if any(w["inst"] == "retina" and w["title"] == "ZED" for w in ws):
        return True
    ret = [w for w in ws if w["inst"] == "retina" and w["title"] == "Retina" and w["w"] > 50]
    if not ret:
        return False
    activate(ret[0]["id"])
    time.sleep(0.6)
    click(ret[0]["ax"] + 45, ret[0]["ay"] + 18)   # the "ZED: OFF" toggle, top-left of the Retina window
    for _ in range(10):
        time.sleep(0.5)
        if any(w["inst"] == "retina" and w["title"] == "ZED" for w in windows()):
            return True
    return False


def capture(out_dir: Path, prefix: str = "") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    got = []
    ws = windows()
    for stem, (inst, rx) in WANTED.items():
        cands = [w for w in ws if w["inst"] == inst and re.search(rx, w["title"]) and w["w"] > 100]
        if not cands:
            continue
        w = max(cands, key=lambda c: c["w"] * c["h"])
        dst = out_dir / f"{prefix}{stem}.png"
        r = subprocess.run(["import", "-window", w["id"], str(dst)], env={**os.environ, "DISPLAY": DISPLAY},
                           capture_output=True)
        if r.returncode == 0:
            got.append(dst)
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--zed", action="store_true")
    a = ap.parse_args()
    if a.zed:
        print("ZED window:", "open" if open_zed() else "NOT found")
        time.sleep(2)
    for p in capture(Path(a.out_dir), a.prefix):
        print(p)


if __name__ == "__main__":
    main()
