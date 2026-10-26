# Experimentos (E1–E5)

Campaña de experimentos de la pila del Husky A300 en el huerto de manzanos simulado (`husky_apple.wbt`). Todo lo de
esta carpeta es **adicional**: con todos los interruptores en su valor por defecto, la pila funciona igual que con
`./apple.bash`.

| Id | Qué mide | Pila · conductor | Variantes |
|---|---|---|---|
| E1 | Localización con GNSS degradado: error p50/p95, rumbo, NEES (≈ 3 si es consistente) | localización · `gt_driver` | `degradado` (10 semillas), `limpio` |
| E2 | Seguimiento de personas: MOTA, MOTP, cambios de identidad, oclusión máxima con identidad conservada, nacimientos falsos | completa · ruta (mundo `exp_personas`) | `fusion` (ZED + LiDAR), `solo_zed` |
| E3 | Mapa de troncos frente a la verdad del mundo: precisión, exhaustividad, F1 (< 0,25 m), error, troncos falsos y eliminaciones erróneas por hora | completa · ruta | `base` (= E4), `sin_confirmacion_lidar`, `sin_pvis` |
| E4 | Navegación integrada: éxito, tiempo de misión, holgura mínima a troncos y personas, colisiones | completa · ruta (9 waypoints) | `base` |
| E5 | Rendimiento: frecuencias, latencias, CPU/GPU por agente; mapa de troncos con el modelo semántico más lento | completa · ruta | `base` (= E4), `semantica_lenta` |

Resultados: [`resultados/RESUMEN.md`](resultados/RESUMEN.md) (equipo, modelos, conclusiones y los cinco informes) y
`resultados/informe_E*.md`. Figuras y capturas en [`imagenes/`](imagenes/).

```
experiments/
├── configs/experimentos.toml  definición de cada experimento y de sus variantes (qué se activa/desactiva)
├── configs/campana.txt        las ejecuciones que hay detrás de resultados/
├── scripts/                   orquestador, registrador, conductor y análisis
├── worlds/exp_personas.wbt    mundo de E2 (generado por scripts/gen_worlds.py)
├── imagenes/                  capturas de pantalla y figuras de los informes
└── resultados/                informes (.md) + una carpeta por ejecución (no versionada, ver .gitignore)
```

## Uso

```bash
cd ~/robocomp/AiGB_UEx_Navigation/experiments/scripts
python3 run_experiment.py --lista                               # experimentos y variantes disponibles
python3 run_experiment.py E3 --variante sin_pvis --semilla 1     # una ejecución (arranca y para la pila sola)
python3 run_experiment.py E4 --variante base --capturas          # ... con capturas de pantalla de las ventanas
./tanda.sh ../configs/campana.txt > ../resultados/campana.log 2>&1 &   # la campaña completa (~2,5 h), una tras otra

python3 resumen.py      # rehace todos los informes y resultados/RESUMEN.md a partir de las ejecuciones guardadas
```

`run_experiment.py` necesita que no haya otra pila corriendo (si la hay, la para antes en el mismo orden que
`./apple.bash --stop`: capa cognitiva, capa sensoriomotora y Webots, siempre con SIGINT). Cada ejecución dura entre
4 min (E1) y ~6 min (misiones completas), arranque incluido.

## Cómo se activa o desactiva cada caso

Cada caso de degradación, ablación o configuración es **una clave en la config de su componente**, y su valor por
defecto es el comportamiento normal. Se puede usar de dos formas:

1. **Con el orquestador** (lo recomendado): una variante de `configs/experimentos.toml` es solo una lista de claves:

   ```toml
   [E3.variantes.sin_confirmacion_lidar.trunk_concept]
   "Ablation.LidarConfirm" = false
   ```

   El orquestador copia la config del componente en la carpeta de la ejecución, cambia esas claves y lanza el
   componente con la copia. **Las configs del repositorio no se tocan.** Las copias modificadas quedan en `cfg/`
   (solo existen para los componentes con alguna clave cambiada; el resto corre con la config del repo).

2. **A mano, con la pila normal** (`./apple.bash`): se edita la clave en la config del componente y se relanza.

| Componente · fichero | Clave | Por defecto | Efecto si se cambia |
|---|---|---|---|
| bridge · `webots-bridge/etc/config_husky` | `GnssDegradation.Enabled` | `false` | `true`: el fix GPS servido es el degradado (copas, RTK fijo/flotante/simple, multitrayecto, zonas, cortes, latencia) |
| | `GnssDegradation.StatusFile` | `""` | ruta: escribe por cada fix lo que informa el receptor (σ, tipo de fix, satélites, instante de medida) |
| | `GnssDegradation.Seed`, `LatencyMs`, `OutageRatePerMin`, `DeniedZones`, `DegradedZones`, `Satellites`, `FixMinSats`, `SigmaFloatM`, … | ver fichero | parámetros del modelo (documentados en el fichero y en `src/gnss_degradation.h`) |
| openfield_concept · `etc/config.toml` | `Ekf.GpsSigmaSource` | `"fixed"` | `"receiver"`: R = σ² que informa el receptor |
| | `Ekf.GpsLikelihood`, `Ekf.StudentNu` | `"gauss"`, 4 | `"student"`: verosimilitud t de Student (reduce el peso de los saltos de multitrayecto) |
| | `Ekf.LagCompensation` | `false` | `true`: un fix que llega tarde se traslada al instante actual |
| | `Gps.StatusFile` | `""` | lee el informe del receptor (el `StatusFile` del bridge) |
| | `Imu.UseYaw` | `true` | `false`: sin la guiñada absoluta de la IMU |
| | `Experiment.ShadowFilters` | `false` | `true`: corre además los filtros A/B/C/D de E1 sobre los mismos datos (solo se registran) |
| | `Diag.ExperimentCsv` | `""` | ruta: CSV a 10 Hz con cada filtro, su covarianza, la verdad y el estado del receptor |
| trunk_concept · `etc/config.toml` | `Ablation.LidarConfirm` | `true` | `false`: un tronco nace solo con la evidencia semántica de la ZED (sin confirmación LiDAR) |
| | `Ablation.VisibilityModel` | `true` | `false`: la ausencia se carga en toda mirada dentro del campo de visión (sin test de oclusión ni p_vis por distancia) |
| human_concept · `etc/config.toml` | `HumanLidar.Enabled` | `true` | `false`: personas **solo con la ZED** (sin el LiDAR como segunda mirada) |
| retina · `etc/config_husky.toml` | `Semantic.decimation` | `1` | N: el modelo semántico ADE20K corre en uno de cada N fotogramas (E5) |
| robot_concept · `etc/config_husky.toml` | `Media.enable_zed`, `Media.enable_lidar` | `true` | `false` en E1: la pila de localización no retransmite cámara ni LiDAR |

## Detalles de E1

- **Capa de degradación** (bridge, `src/gnss_degradation.{h,cpp}`, C++ puro con autotest): constelación fija de
  satélites sobre la máscara de elevación; en cada época se traza un rayo por satélite desde la antena a través de
  las copas del mundo (cilindros leídos del árbol de escena) y se suma la cuerda de follaje atravesada. Con los
  satélites visibles se decide el estado (RTK fijo / flotante / simple / sin fix) con histéresis de readquisición;
  error Gauss-Markov por estado; saltos de multitrayecto con tasa proporcional al cielo tapado (que el receptor
  **no** refleja en su σ); zonas sin GNSS; cortes aleatorios; latencia con marca de tiempo.
- **Las cuatro configuraciones corren a la vez** sobre los mismos datos (filtros en sombra de openfield): A = EKF
  actual; B = R del receptor + t de Student + compensación de latencia; C = sin GNSS tras inicializar; D = sin
  guiñada IMU. Así la comparación no depende de que dos ejecuciones vean datos distintos.
- **Zona sin GNSS**: el tramo y ∈ [−2, 6] del pasillo x = 3.75 (`DeniedZones`).
- El "error del fix" del informe mide solo la degradación añadida (fix entregado frente a la lectura del GPS de
  Webots); los errores de los filtros se miden contra la verdad del simulador.

## Piezas

| Script | Qué hace |
|---|---|
| `run_experiment.py` | Una ejecución: aplica la variante, arranca Webots + capa sensoriomotora + capa cognitiva, espera a que todos los agentes estén *Operating*, lanza el registrador, el monitor y el conductor, para todo y recoge los logs |
| `recorder.py` | Agente DSR **de solo lectura** (id 97): pose estimada y verdad de Webots a 10 Hz; personas, troncos, obstáculos y celdas ocupadas del residual a 1 Hz; estado de presencia de cada agente; frecuencia y edad de la pose |
| `sysmon.py` | CPU, RAM y memoria GPU por proceso, cada 2 s |
| `gt_driver.py` | Conductor de E1: persecución pura sobre la **verdad del simulador**, de modo que el recorrido es idéntico en todas las ejecuciones y no depende del estimador que se mide |
| `capturas.py` | Capturas de Webots, mapa del controller, trayectorias de openfield, grafo DSR, retina y ventana ZED/YOLO |
| `gen_worlds.py` | Mundo de E2: cuatro trabajadores (cruce, tras la vegetación, detrás del robot) |
| `analizar_e1.py`, `analizar_personas.py`, `analizar_mapa_nav.py` | Métricas, tablas y figuras de E1, E2 y E3–E5 |
| `resumen.py` | Lanza los análisis y une los informes en `resultados/RESUMEN.md` |

Cada ejecución se guarda en `resultados/<EXP>/<mundo>__<variante>__s<semilla>/` (`run.json` con el commit de
partida, `git.diff` con los cambios sin commitear si los hay, `record.jsonl`,
`sysmon.jsonl`, `driver.log`, `cfg/`, `logs/`, `openfield/`, `capturas/`). Los análisis solo leen esas carpetas y
se pueden relanzar cuantas veces se quiera.
