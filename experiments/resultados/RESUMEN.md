# Resumen de la campaña de experimentos

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



## Conclusiones

Campaña interna en simulación (Webots R2025a, huerto de manzanos `husky_apple.wbt`), con pocas repeticiones salvo
en E1 (10 semillas).

- **E1 · Localización con GNSS degradado.** La capa de degradación produce un 20 % de RTK fijo, 38 % flotante,
  27 % simple y 16 % sin fix bajo las copas. El EKF actual (A) da un error p50 de 0,47 m y p95 de 1,68 m, con un
  NEES medio muy por encima del intervalo del 95 % ([1,68; 4,70] para N = 10): su covarianza no refleja el error
  real. B (σ del receptor + verosimilitud t de Student + compensación de latencia) reduce el error a p50 0,22 m /
  p95 0,98 m y el NEES a ~130; mejora, pero sigue fuera del intervalo, porque el error del receptor está correlado
  en el tiempo y el multitrayecto no aparece en su σ. Sin GNSS (C) el error p50 a lo largo del recorrido (~2,5 min) es ~0,7 m. Sin la
  guiñada de la IMU (D) el rumbo p95 pasa de 0,2° a ~12°. Con GNSS limpio, A tiene un error p50 de 2 cm.
- **E2 · Seguimiento de personas.** Fusión ZED + LiDAR frente a solo ZED: MOTA 0,30 frente a 0,13; MOTP 0,18 m
  frente a 0,44 m (el LiDAR sitúa a la persona con más precisión que la profundidad estéreo); identidad conservada
  en 6 de 18 oclusiones (máx. 64 s) frente a 0 de 32. La fusión genera más nacimientos falsos (17 frente a 4),
  sobre las copas de los árboles.
- **E3 · Mapa de troncos.** 60/60 troncos, F1 = 1,00, error medio 6,7 cm, sin troncos falsos ni eliminaciones
  erróneas. Las dos ablaciones no cambian el resultado en este mundo: no hay candidatos semánticos falsos en la banda
  del tronco ni oclusiones lo bastante largas. Con el modelo semántico a ¼ de frecuencia (11 → 2,5 miradas/s) la F1
  es 0,98: la normalización por mirada de referencia mantiene el mapa.
- **E4 · Navegación integrada.** 3/3 misiones completas (9/9 waypoints), ~250 s por misión, holgura mínima 0,57 m a
  troncos y 0,73 m a personas, sin colisiones. GNSS sin degradar; error de localización p50 4 cm / p95 8 cm.
- **E5 · Rendimiento.** Pose a 50 Hz, rejilla residual a 10 Hz, controller ~17 Hz, ZED procesada a ~14 fps.
  Latencia de la pose en el grafo 18 ms (p95 26 ms). CPU total ~11 % de la máquina; `retina` es el proceso más
  costoso (64 % de un núcleo, 1,6 GB de GPU).


## E1 — Localización con GNSS degradado

Cuatro configuraciones del EKF corren a la vez sobre los MISMOS datos (filtros en sombra de openfield_concept); el robot sigue la misma ruta en todas las ejecuciones (conductor sobre la verdad del simulador). Error evaluado en el instante de la verdad. NEES sobre (x, y, θ): consistente ⇔ media ≈ 3. Intervalo del 95 % de la media de N ejecuciones independientes: χ²(3N)/N (N = 2: [0.62, 7.22]), (N = 10: [1.68, 4.70]).

### Estado del GNSS (porcentaje del tiempo) y error real de los fixes

| mundo | variante | n | RTK fijo % | flotante % | simple % | sin fix % | error fix p95 (m) |
|---|---|---|---|---|---|---|---|
| husky_apple | degradado | 10 | 19.5 | 38.0 | 26.6 | 15.9 | 1.902 |
| husky_apple | limpio | 2 | 100.0 | 0.0 | 0.0 | 0.0 | 0.000 |

Error del fix = |fix entregado − lectura del GPS de Webots| en el instante de medida: mide solo la degradación añadida; no incluye el ruido propio del GPS simulado (σ = 2 cm por eje) ni el desfase que añade la latencia mientras el robot avanza. Los errores de los filtros sí se miden contra la verdad.

### Error y consistencia por configuración (media ± desviación entre ejecuciones)

| mundo | GNSS | configuración | n | error p50 (m) | error p95 (m) | rumbo p50 (°) | rumbo p95 (°) | NEES medio | NEES mediana |
|---|---|---|---|---|---|---|---|---|---|
| husky_apple | degradado | A: EKF actual | 10 | 0.472 ± 0.152 | 1.675 ± 0.474 | 0.08 | 0.24 | 3240.2 ± 1361.3 | 867.00 |
| husky_apple | degradado | B: σ receptor + t-Student + latencia | 10 | 0.222 ± 0.086 | 0.984 ± 0.272 | 0.08 | 0.24 | 126.7 ± 73.4 | 47.55 |
| husky_apple | degradado | C: sin GNSS | 10 | 0.681 ± 0.559 | 0.874 ± 0.599 | 0.08 | 0.24 | 49.4 ± 108.9 | 31.46 |
| husky_apple | degradado | D: sin guiñada IMU | 10 | 0.508 ± 0.155 | 1.868 ± 0.501 | 3.59 | 11.83 | 3397.5 ± 1197.7 | 967.77 |
| husky_apple | limpio | A: EKF actual | 2 | 0.022 ± 0.001 | 0.092 ± 0.000 | 0.08 | 0.24 | 9.4 ± 0.1 | 3.93 |
| husky_apple | limpio | B: σ receptor + t-Student + latencia | 2 | 0.024 ± 0.000 | 0.078 ± 0.000 | 0.08 | 0.24 | 19.9 ± 0.3 | 8.62 |
| husky_apple | limpio | C: sin GNSS | 2 | 0.458 ± 0.016 | 0.654 ± 0.024 | 0.08 | 0.24 | 6.3 ± 0.2 | 5.37 |
| husky_apple | limpio | D: sin guiñada IMU | 2 | 0.023 ± 0.000 | 0.091 ± 0.001 | 0.27 | 1.22 | 9.4 ± 0.1 | 3.91 |

![E1 husky_apple degradado](../imagenes/E1_husky_apple_degradado.png)
![E1 husky_apple limpio](../imagenes/E1_husky_apple_limpio.png)


## E2 — Seguimiento de personas

Región evaluada: trabajadores a menos de 10.0 m del robot (todo alrededor). Emparejamiento CLEAR-MOT con umbral 1.0 m. 'Oclusión' = tramo en que el trabajador no es visible para la cámara (fuera del campo de visión ±49°, o una copa en la línea de visión); se cuenta como conservada si la misma pista lo sigue antes y después. Variantes: fusión (ZED + LiDAR) y solo ZED (HumanLidar.Enabled = false).

| variante | n | MOTA | MOTP (m) | IDSW/(trabajador·min) | oclusión máx. conservada (s) | nacimientos falsos |
|---|---|---|---|---|---|---|
| fusion | 1 | 0.30 | 0.176 | 1.575 | 64.0 | 17.0 |
| solo_zed | 1 | 0.13 | 0.436 | 2.145 | 0.0 | 4.0 |

| ejecución | MOTA | MOTP (m) | FN | FP | IDSW | IDSW/(trab·min) | oclusión máx (s) | oclusiones conservadas | nac. falsos | pistas | min |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exp_personas__fusion__s2 | 0.30 | 0.176 | 3795 | 4176 | 45 | 1.575 | 64.0 | 6/18 | 17 | 47 | 7.1 |
| exp_personas__solo_zed__s2 | 0.13 | 0.436 | 9159 | 1129 | 61 | 2.145 | 0.0 | 0/32 | 4 | 60 | 7.1 |


## E3 — Mapa de troncos frente a la verdad del mundo

Emparejamiento húngaro con umbral 0.25 m contra las 60 posiciones de árbol del .wbt (las que escribió gen_apple_rows.py). 'Exhaustividad (visto)' cuenta solo los árboles que pasaron a menos de 4 m del robot (alcance de ausencia de la ZED).

### Resumen por variante (media de ejecuciones)

| variante | n | precisión | exhaustividad | exhaust. (visto) | F1 | error medio (m) | troncos falsos/h | eliminaciones erróneas/h |
|---|---|---|---|---|---|---|---|---|
| base | 3 | 1.00 | 1.00 | 1.00 | 1.00 | 0.068 | 0.0 | 0.0 |
| sin_confirmacion_lidar | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0.071 | 0.0 | 0.0 |
| sin_pvis | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0.058 | 0.0 | 0.0 |
| semantica_lenta | 1 | 0.98 | 0.98 | 0.98 | 0.98 | 0.061 | 12.8 | 0.0 |

### Por ejecución

| ejecución | variante | publicados | aciertos | precisión | exhaustividad | exhaust. visto (n) | F1 | error (m) | falsos | elim. erróneas |
|---|---|---|---|---|---|---|---|---|---|---|
| E4/husky_apple__base__s1 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.067 | 0 (0.0/h) | 0 (0.0/h) |
| E4/husky_apple__base__s2 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.066 | 0 (0.0/h) | 0 (0.0/h) |
| E4/husky_apple__base__s3 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.069 | 0 (0.0/h) | 0 (0.0/h) |
| E3/husky_apple__sin_confirmacion_lidar__s1 | sin_confirmacion_lidar | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.071 | 0 (0.0/h) | 0 (0.0/h) |
| E3/husky_apple__sin_pvis__s1 | sin_pvis | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.058 | 0 (0.0/h) | 0 (0.0/h) |
| E5/husky_apple__semantica_lenta__s1 | semantica_lenta | 60 | 59 | 0.98 | 0.98 | 0.98 (60) | 0.98 | 0.061 | 1 (12.8/h) | 0 (0.0/h) |


## E4 — Navegación integrada

Misiones: 3. Éxito por waypoint: 100.0 %. Misiones completas: 100.0 %.
Tiempo medio de misión: 248.7 s. Holgura mínima a troncos: 0.57 m; a personas: 0.73 m. Colisiones (contactos del cuerpo 0.99x0.686 m con un tronco / con el disco de 0.25 m de una persona): 0 / 0.

Holgura = distancia del rectángulo del cuerpo (pose real de Webots) al tronco (radio real) o a la persona.

| ejecución | waypoints | tiempo (s) | recorrido (m) | holgura tronco (m) | holgura persona (m) | colis. tronco | colis. persona | error loc p50 (m) | error loc p95 (m) |
|---|---|---|---|---|---|---|---|---|---|
| husky_apple__base__s1 | 9/9 | 278.3 | 154.7 | 0.58 | 1.16 | 0 | 0 | 0.041 | 0.077 |
| husky_apple__base__s2 | 9/9 | 231.2 | 121.6 | 0.57 | 1.09 | 0 | 0 | 0.040 | 0.079 |
| husky_apple__base__s3 | 9/9 | 236.7 | 126.7 | 0.58 | 0.73 | 0 | 0 | 0.041 | 0.081 |


## E5 — Rendimiento computacional

PC: AMD Ryzen 9 9950X3D (16 núcleos / 32 hilos), 60 GiB RAM, NVIDIA GeForce RTX 5070 Ti 16 GB (driver 595.91), Ubuntu 24.04.5, kernel 7.0.

Ejecución medida: husky_apple__base__s1. CPU de la máquina media 11 % (de 3200 %), GPU media 34 %.

### Frecuencias (mediana / mínimo tras el arranque)

| flujo | mediana (Hz) | mínimo (Hz) | requisito |
|---|---|---|---|
| pose en el grafo (anillo RT robot→field) | 50.0 | 48.7 | ≥ 50 Hz |
| openfield_concept (pose EKF) | 51.0 | 50.0 |  |
| residual (rejilla residual) | 10.0 | 9.8 | ≥ 2 Hz |
| controller (planificador) | 16.8 | 9.4 |  |
| retina (bucle) | 40.0 | 40.0 |  |
| retina: fotogramas ZED procesados | 14.0 | 11.1 |  |
| trunk_concept | 20.0 | 20.0 |  |
| vegetation_concept | 20.0 | 20.0 |  |
| human_concept | 20.0 | 20.0 |  |
| robot_concept | 10.0 | 10.0 |  |
| zed (driver) | 59.0 | 59.0 |  |
| helios (LiDAR) | 17.0 | 13.0 |  |

### Latencias (ms)

| medida | n | mediana | p95 | máx |
|---|---|---|---|---|
| pose del robot en el grafo (edad al leerla) | 196 | 18 | 26 | 35 |
| personas en el grafo (edad de la última muestra RT) | 345 | 58 | 990 | 2318 |
| controller: edad máxima del comando de velocidad (por informe) | 332 | 43 | 65 | 125 |

### CPU / memoria / GPU por proceso

![](../imagenes/E5_cpu_por_agente.png)

| proceso | CPU media (%) | CPU máx (%) | RSS (MB) | memoria GPU (MB) |
|---|---|---|---|---|
| retina | 64 | 89 | 2580 | 1562 |
| robot_concept | 43 | 64 | 276 | — |
| controller | 40 | 94 | 176 | — |
| residual | 37 | 46 | 329 | — |
| bridge | 33 | 36 | 68 | — |
| webots | 29 | 39 | 1555 | — |
| openfield_concept | 22 | 33 | 146 | — |
| helios | 14 | 15 | 105 | — |
| human_concept | 11 | 17 | 156 | — |
| zed | 9 | 10 | 162 | — |
| trunk_concept | 7 | 11 | 147 | — |
| vegetation_concept | 5 | 7 | 100 | — |
| imu | 2 | 2 | 72 | — |

### E3 con el modelo semántico más lento (Semantic.decimation = 4)

La evidencia de troncos se pondera por 'mirada de referencia' (LookPeriodMs = 530 ms); si la normalización funciona, el mapa no depende de cuántas inferencias por segundo haga la GPU.

| ejecución | miradas semánticas/s (aprox.) | publicados | precisión | exhaustividad | F1 | error (m) | falsos/h | elim. erróneas/h |
|---|---|---|---|---|---|---|---|---|
| E4/base/s1 | 11.0 | 60 | 1.00 | 1.00 | 1.00 | 0.067 | 0.0 | 0.0 |
| E4/base/s2 | 10.8 | 60 | 1.00 | 1.00 | 1.00 | 0.066 | 0.0 | 0.0 |
| E4/base/s3 | 11.0 | 60 | 1.00 | 1.00 | 1.00 | 0.069 | 0.0 | 0.0 |
| E5/semantica_lenta/s1 | 2.5 | 60 | 0.98 | 0.98 | 0.98 | 0.061 | 12.8 | 0.0 |
