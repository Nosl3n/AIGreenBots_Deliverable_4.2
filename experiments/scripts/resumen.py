#!/usr/bin/env python3
"""Run every analysis and join the reports into resultados/RESUMEN.md (with the machine and the YOLO models).

    python3 resumen.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent

CABECERA = """# Resumen de la campaña de experimentos

## Equipo

AMD Ryzen 9 9950X3D (16 núcleos / 32 hilos) · 60 GiB RAM (sin swap) · NVIDIA GeForce RTX 5070 Ti 16 GB (driver 595.91)
· Ubuntu 24.04.5 LTS, kernel 7.0 · Webots R2025a.

## Modelos YOLO en funcionamiento (todos en `retina`, YOLO26 de Ultralytics exportado a ONNX, TensorRT FP16)

| Modelo | Bloque de `retina/etc/config_husky.toml` | Proceso | Consumidor |
|---|---|---|---|
| `yolo26x-seg.onnx` (segmentación de instancias COCO-80) | `[Yolo]` | máscaras de **personas** (`accepted_labels = ["person"]`) en la imagen de la ZED | `human_concept` (y la exclusión de personas en troncos/vegetación) |
| `yolo26x-pose.onnx` (pose, 17 puntos COCO → BODY_18) | `[HumanPose]` | **esqueletos 3D** de las personas (profundidad de la ZED) → nodo `skeleton` | `human_concept` |
| `yolo26x-sem-ade20k.onnx` (segmentación semántica ADE20K-150) | `[Semantic]` | clases de **vegetación** de ADE20K (tree, plant, …) → máscaras de vegetación en el nodo `masks` | `trunk_concept`, `vegetation_concept` |

Presentes pero desactivados en el Husky: `yolo26l-seg`, `yolo26l-pose`, `yolo26l-sem-ade20k` (alternativas L), YOLO de la
Ricoh 360 (`[Ricoh360] yolo_enabled = false`), `yolo26l-depth` (`[ZedDepth]`, no hace falta: la ZED mide profundidad),
SAM2 (`[SAM2] enabled = false`) y el especialista de puertas YOLO11s (`[DoorSpecialist]`, interiores).

"""


def main():
    for s in ("analizar_e1.py", "analizar_personas.py", "analizar_mapa_nav.py"):
        subprocess.run([sys.executable, str(HERE / s)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    parts = [CABECERA]
    conc = common.RESULTS / "conclusiones.md"
    if conc.exists():
        parts.append(conc.read_text())
    for e in ("E1", "E2", "E3", "E4", "E5"):
        p = common.RESULTS / f"informe_{e}.md"
        if p.exists():
            t = p.read_text()
            parts.append(("#" + t if t.startswith("# ") else t).replace("\n## ", "\n### "))
    (common.RESULTS / "RESUMEN.md").write_text("\n\n".join(parts))
    print(common.RESULTS / "RESUMEN.md")


if __name__ == "__main__":
    main()
