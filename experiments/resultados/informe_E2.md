# E2 — Seguimiento de personas

Región evaluada: trabajadores a menos de 10.0 m del robot (todo alrededor). Emparejamiento CLEAR-MOT con umbral 1.0 m. 'Oclusión' = tramo en que el trabajador no es visible para la cámara (fuera del campo de visión ±49°, o una copa en la línea de visión); se cuenta como conservada si la misma pista lo sigue antes y después. Variantes: fusión (ZED + LiDAR) y solo ZED (HumanLidar.Enabled = false).

| variante | n | MOTA | MOTP (m) | IDSW/(trabajador·min) | oclusión máx. conservada (s) | nacimientos falsos |
|---|---|---|---|---|---|---|
| fusion | 1 | 0.30 | 0.176 | 1.575 | 64.0 | 17.0 |
| solo_zed | 1 | 0.13 | 0.436 | 2.145 | 0.0 | 4.0 |

| ejecución | MOTA | MOTP (m) | FN | FP | IDSW | IDSW/(trab·min) | oclusión máx (s) | oclusiones conservadas | nac. falsos | pistas | min |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exp_personas__fusion__s2 | 0.30 | 0.176 | 3795 | 4176 | 45 | 1.575 | 64.0 | 6/18 | 17 | 47 | 7.1 |
| exp_personas__solo_zed__s2 | 0.13 | 0.436 | 9159 | 1129 | 61 | 2.145 | 0.0 | 0/32 | 4 | 60 | 7.1 |
