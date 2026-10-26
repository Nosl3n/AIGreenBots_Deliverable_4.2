#!/usr/bin/env python3
"""Run every analysis and join the reports into results/SUMMARY.md (with the machine and the YOLO models).

    python3 summary.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent

HEADER = """# Experiment campaign — summary

## Machine

AMD Ryzen 9 9950X3D (16 cores / 32 threads) · 60 GiB RAM (no swap) · NVIDIA GeForce RTX 5070 Ti 16 GB (driver 595.91)
· Ubuntu 24.04.5 LTS, kernel 7.0 · Webots R2025a.

## YOLO models in use (all in `retina`: Ultralytics YOLO26 exported to ONNX, TensorRT FP16)

| Model | Block of `retina/etc/config_husky.toml` | Task | Consumer |
|---|---|---|---|
| `yolo26x-seg.onnx` (COCO-80 instance segmentation) | `[Yolo]` | **person** masks (`accepted_labels = ["person"]`) on the ZED image | `human_concept` (and the person exclusion in trunks/vegetation) |
| `yolo26x-pose.onnx` (pose, 17 COCO keypoints → BODY_18) | `[HumanPose]` | 3D **skeletons** of the people (ZED depth) → `skeleton` node | `human_concept` |
| `yolo26x-sem-ade20k.onnx` (ADE20K-150 semantic segmentation) | `[Semantic]` | ADE20K **vegetation** classes (tree, plant, …) → vegetation masks in the `masks` node | `trunk_concept`, `vegetation_concept` |

"""


def main():
    for s in ("analyze_e1.py", "analyze_people.py", "analyze_map_nav.py"):
        subprocess.run([sys.executable, str(HERE / s)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    parts = [HEADER]
    conc = common.RESULTS / "conclusions.md"
    if conc.exists():
        parts.append(conc.read_text())
    for e in ("E1", "E2", "E3", "E4", "E5"):
        p = common.RESULTS / f"report_{e}.md"
        if p.exists():
            t = p.read_text()
            parts.append(("#" + t if t.startswith("# ") else t).replace("\n## ", "\n### "))
    (common.RESULTS / "SUMMARY.md").write_text("\n\n".join(parts))
    print(common.RESULTS / "SUMMARY.md")


if __name__ == "__main__":
    main()
