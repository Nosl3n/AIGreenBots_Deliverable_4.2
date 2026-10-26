# utils — cómo lanzar la pila del Husky A300

Hay **dos lanzadores**, uno por capa, y cada uno tiene su TOML. Detalles del monitor web y su
arquitectura: [netmon/README.md](netmon/README.md).

## Arranque

```bash
cd ~/robocomp/AiGB_UEx_Navigation/active_inference/utils

# Terminal 1 — capa sensoriomotora (Webots + bridge + LiDAR + IMU + ZED + mando)
python3 subcognitive.py sub_husky.toml

# Terminal 2 — capa cognitiva (agentes DSR), cuando la tabla de la terminal 1 esté en verde
python3 cognitive.py cognitive_husky.toml
```

- Monitor web: <http://127.0.0.1:8080>
- Webots debe tener abierto **`webots-agri/worlds/husky_apple.wbt`** (`../../apple.bash` lo abre solo).
  El lanzador arranca Webots si no está corriendo, pero abre **el último mundo usado**: compruébalo.
- Se lanza **desde `utils/`**: los dos scripts importan el paquete `netmon/` de esta carpeta.
- Sin argumento, cada lanzador usa su TOML del Husky.
- Objetivo de navegación desde la terminal: `python3 send_goal.py X Y` (metros en el marco del
  campo, ENU: x este, y norte).

## Los dos lanzadores

| Script | Capa | Qué arranca | TOML |
|---|---|---|---|
| `subcognitive.py` | sensoriomotora | Webots (si hace falta), rcnode/icebox, bridge, `lidar3d_dds` (helios), `imu_dds`, `zed_camera`, mando Xbox | `sub_husky.toml` |
| `cognitive.py` | cognitiva | `robot_concept`, `openfield_concept`, `residual_concept`, `controller`, `retina`, `human_concept`, `vegetation_concept`, `trunk_concept` (`row_metaconcept` existe pero está desactivado) | `cognitive_husky.toml` |

Siempre **primero `subcognitive.py`, luego `cognitive.py`**. Los agentes no arrancan Webots y
necesitan los sensores ya publicando. El orden *dentro* de `cognitive_husky.toml` da igual: cada
agente espera a sus `required_agent_names`.

Los dos comparten el monitor web: el primero que arranca lo sirve y el otro solo registra su estado.

> ⚠ **No pases el TOML del otro lanzador.** `subcognitive.py cognitive_husky.toml` arranca igual,
> pero en la capa equivocada. Por ejemplo, `cognitive.py` nunca arranca Webots.

Para comprobar que cada entrada de los TOML tiene su binario y su config:

```bash
python3 - <<'E'
import toml, os, glob
for f in sorted(glob.glob('*.toml')):
    for c in toml.load(f).get('components', []):
        cwd = os.path.expanduser(c.get('cwd', '')); cmd = c.get('cmd', '').split()
        if cmd and cmd[0] == 'env':
            cmd = [x for x in cmd[1:] if '=' not in x]
        miss = [x for x, p in (('bin', cmd[0]), ('cfg', cmd[1] if len(cmd) > 1 else None))
                if p and not os.path.exists(os.path.join(cwd, p))]
        if miss: print(f, c['name'], miss)
E
```

## Logs

Sin `tmux`, cada componente escribe en:

```
~/.local/logs/<name>.out     # stdout
~/.local/logs/<name>.err     # stderr
```

`<name>` es el campo `name` del TOML (`bridge`, `controller`, `robot_concept`…). **Se
sobrescriben en cada arranque**: copia el log **después** de parar el componente y **antes** de
relanzar.

La consola de Webots no va a ningún log (el lanzador la manda a `/dev/null`); se ve en la propia
ventana de Webots.

Con `tmux` instalado, cada componente corre en su propia sesión y el monitor web muestra su
terminal.

## Parar

- **Ctrl+C en cada terminal**: primero `cognitive.py`, luego `subcognitive.py`. El lanzador
  manda SIGTERM a cada componente, los agentes borran sus nodos del grafo DSR y, si alguno no
  termina en 5 s, lo mata con SIGKILL.
- **Nunca `kill -9`** a un agente: sus nodos se quedan colgados en el grafo compartido.
- Relanzar con procesos viejos todavía vivos también los mata con **SIGKILL** (`_remove_existing`).
  Para antes con Ctrl+C y relanza después.
- Webots no se cierra al parar `subcognitive.py`: se reutiliza en el siguiente arranque.

## Flags útiles

| Flag | Script | Efecto |
|---|---|---|
| `--no-webots` | `subcognitive.py` | No arrancar Webots (lo ignora si el TOML tiene `[general] start_webots`) |
| `--no-rcnode` | `subcognitive.py` | No comprobar/arrancar rcnode (icebox) |
| `--no-battery` | `subcognitive.py` | Sin monitor de batería Victron (`/dev/ttyUSB0`) |
| `--no-web` | ambos | No servir el monitor web |
| `--web-port N` | ambos | Puerto web (el mismo en los dos; por defecto 8080) |
| `--no-bw` | ambos | Sin captura de ancho de banda ICE |

## Otras cosas de esta carpeta

| Ruta | Qué es |
|---|---|
| `netmon/` | Paquete común de los dos lanzadores: monitor web, registro en `/tmp/robocomp_netmon/`, puente de estadísticas DDS |
| `dds_preflight/` | Comprueba que el descubrimiento DDS por memoria compartida funciona (dominio 7). Los lanzadores lo ejecutan solos al arrancar. Si falla, casi siempre quedan segmentos viejos: para todo y `rm -f /dev/shm/fastdds_*`. Síntoma sin él: el plano de medios a 0.0 Hz mientras Ice funciona. |
| `send_goal.py` | Manda un objetivo de navegación al controller: `python3 send_goal.py X Y` |
| `run_route.py` | Recorre una ruta fija de objetivos (por defecto, ida y vuelta por tres pasillos del huerto, lejos de los trabajadores) y avanza al siguiente al llegar a 0,6 m: ejecuciones reproducibles para medir. Requiere `Controller.ArmOnStart = true` |
