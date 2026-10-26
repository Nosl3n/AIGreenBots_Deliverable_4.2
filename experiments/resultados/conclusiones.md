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
