# E3 — Mapa de troncos frente a la verdad del mundo

Emparejamiento húngaro con umbral 0.25 m contra las 60 posiciones de árbol del .wbt (las que escribió gen_apple_rows.py). 'Exhaustividad (visto)' cuenta solo los árboles que pasaron a menos de 4 m del robot (alcance de ausencia de la ZED).

## Resumen por variante (media de ejecuciones)

| variante | n | precisión | exhaustividad | exhaust. (visto) | F1 | error medio (m) | troncos falsos/h | eliminaciones erróneas/h |
|---|---|---|---|---|---|---|---|---|
| base | 3 | 1.00 | 1.00 | 1.00 | 1.00 | 0.068 | 0.0 | 0.0 |
| sin_confirmacion_lidar | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0.071 | 0.0 | 0.0 |
| sin_pvis | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0.058 | 0.0 | 0.0 |
| semantica_lenta | 1 | 0.98 | 0.98 | 0.98 | 0.98 | 0.061 | 12.8 | 0.0 |

## Por ejecución

| ejecución | variante | publicados | aciertos | precisión | exhaustividad | exhaust. visto (n) | F1 | error (m) | falsos | elim. erróneas |
|---|---|---|---|---|---|---|---|---|---|---|
| E4/husky_apple__base__s1 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.067 | 0 (0.0/h) | 0 (0.0/h) |
| E4/husky_apple__base__s2 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.066 | 0 (0.0/h) | 0 (0.0/h) |
| E4/husky_apple__base__s3 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.069 | 0 (0.0/h) | 0 (0.0/h) |
| E3/husky_apple__sin_confirmacion_lidar__s1 | sin_confirmacion_lidar | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.071 | 0 (0.0/h) | 0 (0.0/h) |
| E3/husky_apple__sin_pvis__s1 | sin_pvis | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.058 | 0 (0.0/h) | 0 (0.0/h) |
| E5/husky_apple__semantica_lenta__s1 | semantica_lenta | 60 | 59 | 0.98 | 0.98 | 0.98 (60) | 0.98 | 0.061 | 1 (12.8/h) | 0 (0.0/h) |
