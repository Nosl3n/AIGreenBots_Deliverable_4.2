#!/usr/bin/env python3
"""Generate the E2 world into experiments/worlds/ from webots-agri/worlds/husky_apple.wbt.

    python3 gen_worlds.py

  exp_personas.wbt    (E2) the orchard with four workers instead of two, on purpose-built paths (robot route: the
                      x = -1.25 corridor and the south headland, twice):
                        PERSONA_CRUCE_A / _B  walk the south headland (y -8.4 / -7.9) in OPPOSITE directions: they cross
                                              each other in front of the robot
                        PERSONA_VEG           walks the x = 1.25 corridor: seen from x = -1.25 through the x = 0 row, hidden
                                              by its canopies
                        PERSONA_DETRAS        walks the robot's own corridor (x = -1.7) northwards, behind it

The source world is never modified. PROTO paths are rewritten so the copy works from experiments/worlds/.
Ground truth for the analysis is read back from this file (common.world_trees / world_humans).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SRC = common.WORLDS_DIR / "husky_apple.wbt"


def base_text() -> str:
    t = SRC.read_text()
    t = t.replace('EXTERNPROTO "../protos/', 'EXTERNPROTO "../../webots-agri/protos/')
    return t


def strip_humans(t: str) -> str:
    return re.sub(r"DEF HUMAN_\d+ Pedestrian \{.*?\n\}\n", "", t, flags=re.S)


def pedestrian(DEF: str, start, traj: str, speed: float, shirt: str, name: str) -> str:
    return f"""DEF {DEF} Pedestrian {{
  translation {start[0]} {start[1]} 1.27
  name "{name}"
  controllerArgs [
    "--trajectory={traj}"
    "--speed={speed}"
  ]
  shirtColor {shirt}
}}
"""


def main():
    common.EXP_WORLDS.mkdir(parents=True, exist_ok=True)
    t = strip_humans(base_text())
    marker = "# ---- APPLE_ROWS BEGIN"
    people = (
        "# ---- E2 WORKERS (experiments/scripts/gen_worlds.py) ----\n"
        + pedestrian("PERSONA_CRUCE_A", (-4.0, -8.4), "-4 -8.4, 4 -8.4", 0.5, "0.85 0.45 0.1", "cruce a")
        + pedestrian("PERSONA_CRUCE_B", (4.0, -7.9), "4 -7.9, -4 -7.9", 0.45, "0.1 0.6 0.3", "cruce b")
        + pedestrian("PERSONA_VEG", (1.25, 6.0), "1.25 6, 1.25 -6", 0.45, "0.2 0.35 0.75", "tras vegetacion")
        + pedestrian("PERSONA_DETRAS", (-1.7, -9.0), "-1.7 -9, -1.7 7", 0.35, "0.7 0.1 0.1", "detras")
    )
    out = common.EXP_WORLDS / "exp_personas.wbt"
    out.write_text(t.replace(marker, people + marker, 1))
    print(out)


if __name__ == "__main__":
    main()
