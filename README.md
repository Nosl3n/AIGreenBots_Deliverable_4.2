# AiGB_UEx_Navigation — robótica agrícola con el Husky A300

Adaptación del stack cognitivo `active_inference` (RoboComp + grafo compartido DSR), que se escribió para el
robot social **Shadow** en interiores, a un **robot agrícola**: un Clearpath **Husky A300** simulado en Webots,
en un campo con hileras de palmeras y trabajadores, que se localiza por **GPS**, navega de forma autónoma por los
pasillos y detecta y sigue a las **personas**.

Estado: localización GPS (~2 cm), navegación autónoma por los pasillos y detección/seguimiento de personas
funcionando en simulación. Reconocimiento de tareas agrícolas: pendiente.

## Qué hay en cada carpeta

```
AiGB_UEx_Navigation/
├── webots-agri/            NUEVO — todo lo agrícola de Webots
│   ├── protos/             HuskyA300 (robot + sensores), YoungPalm (palmera), AppleTree (manzano), FieldTerrain (suelo labrado)
│   ├── worlds/             husky_test.wbt (suelo plano) · husky_field.wbt (camellones, palmeras) · husky_apple.wbt (manzanos)
│   ├── controllers/        husky_selftest (autotest de sensores y conducción)
│   └── tools/              gen_palm_rows.py · gen_apple_rows.py (hileras) · gen_husky_selffilter_stl.py (malla de auto-filtro)
├── webots-bridge/          Puente Webots → RoboComp (añadido: skid-steer, GPS, robot configurable)
├── robocomp-robolab/       Drivers: lidar3d_dds (helios), zed_camera, imu_dds, mando Xbox
└── active_inference/       Agentes cognitivos DSR
    ├── robot_concept/      Cuerpo del robot en el grafo (husky.json)
    ├── openfield_concept/  NUEVO — localización GPS + IMU + ruedas (EKF), sustituye a room_concept
    ├── residual_concept/   Ocupación de lo que ningún concepto explica (palmeras, obstáculos)
    ├── controller/         Planificador y control de la base
    ├── retina/             YOLO (segmentación + pose) sobre la ZED
    ├── human_concept/      Personas: esqueleto + seguimiento con LiDAR
    ├── vegetation_concept/ NUEVO — follaje (ADE20K): nodos plant_*, para saber qué tapa qué
    ├── trunk_concept/      NUEVO — troncos (banda baja de 'tree' en la ZED + LiDAR): discos prohibidos trunk_*
    ├── row_metaconcept/    NUEVO — hileras: troncos alineados -> rectángulo row_* que crece (DESACTIVADO en cognitive_husky.toml)
    ├── common/             Módulos compartidos (world_frame nuevo: `field` fuera, `room` dentro)
    └── utils/              Lanzadores: sub_husky.toml, cognitive_husky.toml, send_goal.py
```

## Requisitos (no incluidos en el repo)

- **RoboComp** en `~/robocomp` (`robocomp_core`, `robocomp_interfaces`, `robocomp_tools`) y **cortex** (librería
  DSR) instalada en `/usr/local`, **con el tipo de nodo `field` registrado** (`REGISTER_NODE_TYPE(field)` en
  `core/include/dsr/core/types/type_checking/dsr_node_type.h`, y reinstalar).
- **Webots R2025a** en `/usr/local/webots`. Necesita red la primera vez (descarga PROTOs de GitHub).
- **Modelos ONNX de retina** en `active_inference/retina/models/yolo26/` (`yolo26x-seg.onnx`,
  `yolo26x-pose.onnx`, `yolo26x-sem-ade20k.onnx`): no se versionan (`*.onnx` está ignorado). Se exportan de
  los pesos oficiales de Ultralytics con
  `yolo export model=yolo26x-pose.pt format=onnx opset=17 simplify=True end2end=False` (igual con
  `yolo26x-seg.pt` y `yolo26x-sem-ade20k.pt`).
- ONNX Runtime 1.30 con CUDA (`/opt/onnxruntime`), Embree/TBB, Qt6, Eigen, FastDDS (los del stack original).
- **TensorRT 10** (opcional, recomendado): retina lo usa si está instalado (FP16, ~4x más rápido que CUDA);
  si no, corre en CUDA. Tiene que ser la versión 10 (la que espera ONNX Runtime 1.30), no la 11:
  `sudo apt install libnvinfer10=10.16.1.11-1+cuda13.2 libnvinfer-plugin10=10.16.1.11-1+cuda13.2 libnvonnxparsers10=10.16.1.11-1+cuda13.2`
  y `sudo apt-mark hold libnvinfer10 libnvinfer-plugin10 libnvonnxparsers10`. El primer arranque construye los
  engines (~1-2 min) en `active_inference/retina/.trt_cache/`; los siguientes cargan en segundos.

El repo debe estar en **`~/robocomp/AiGB_UEx_Navigation`**: los lanzadores usan esa ruta.

## Compilar

Cada componente se compila en su carpeta. **Máximo `-j8`** (la máquina no tiene swap y más hilos agotan la memoria):

```bash
cmake -B build && make -C build -j8
```

Componentes usados: `webots-bridge`, `robocomp-robolab/components/hardware/{laser/lidar3d_dds,camera/zed_camera,imu/imu_dds}`,
`active_inference/{robot_concept,openfield_concept,residual_concept,controller,retina,human_concept}`.

## Lanzar

**Huerto de manzanos, todo de una vez:**

```bash
./apple.bash            # Webots con husky_apple.wbt + capa sensoriomotora + capa cognitiva (una terminal cada una)
./apple.bash --route    # ... y además recorre la ruta fija de prueba (utils/run_route.py)
./apple.bash --stop     # apaga todo en orden: capa cognitiva, capa sensoriomotora y Webots
```

**A mano** (cualquier mundo):

```bash
# 0. IceStorm (rcnode) en el puerto 9999, como en el stack original.
# 1. Webots: abrir webots-agri/worlds/husky_field.wbt (o husky_test.wbt).
cd ~/robocomp/AiGB_UEx_Navigation/active_inference/utils
python3 subcognitive.py sub_husky.toml        # capa sensoriomotora: bridge, helios, IMU, ZED, mando
python3 cognitive.py cognitive_husky.toml     # capa cognitiva (otra terminal)
```

- **Mando Xbox**: avance con el stick izquierdo (eje 1), giro con el derecho (eje 3).
- **Objetivo de navegación**: clic en la vista 2D del controller (pulsar Run), o
  `python3 send_goal.py X Y` (coordenadas del campo, ENU: x este, y norte).
- **Ventana de localización** de `openfield_concept`: mapa, error frente a la verdad de la simulación y
  casillas para apagar el GPS o el yaw de la IMU.

## El robot y el campo

- **Husky A300**: 4 ruedas skid-steer, LiDAR `helios` (50 capas, 110° vertical, 30 m), cámara estéreo **ZED**,
  IMU, brújula y **GPS** (WGS84, referencia cerca del campus de la UEx en Badajoz).
- **Campo**: 5 hileras × 10 palmeras jóvenes, pasillos de 2,5 m. En `husky_field.wbt` cada hilera va sobre un
  camellón de 0,20 m, con suelo de tierra rugoso. Dos trabajadores caminan por el campo.
- **Marco del mundo**: nodo `field` del grafo (ENU), creado por `openfield_concept`. Los agentes buscan `field`
  y, si no existe, `room`: el mismo código sigue sirviendo en interiores.

## Origen

Parte de una instantánea del 18-09-2026 de `robocomp/active_inference` (`main` @ `5dc985e`),
`robocomp/webots-bridge` (`main` @ `486e233`) y `robocomp/robocomp-robolab` (`master` @ `1cc4825`). Solo se
conservan los componentes que usa el Husky; los agentes de interiores, el robot Shadow y su mundo
(`robocomp/webots-shadow`) se han retirado de este repositorio.
