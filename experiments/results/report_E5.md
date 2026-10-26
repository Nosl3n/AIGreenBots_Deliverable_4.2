# E5 — Computational performance

PC: AMD Ryzen 9 9950X3D (16 cores / 32 threads), 60 GiB RAM, NVIDIA GeForce RTX 5070 Ti 16 GB (driver 595.91), Ubuntu 24.04.5, kernel 7.0.

Measured run: husky_apple__base__s1. Mean machine CPU 11 % (of 3200 %), mean GPU 34 %.

## Rates (median / minimum after start-up)

| stream | median (Hz) | minimum (Hz) | requirement |
|---|---|---|---|
| pose in the graph (RT ring robot→field) | 50.0 | 48.7 | ≥ 50 Hz |
| openfield_concept (pose EKF) | 51.0 | 50.0 |  |
| residual (residual grid) | 10.0 | 9.8 | ≥ 2 Hz |
| controller (planner) | 16.8 | 9.4 |  |
| retina (loop) | 40.0 | 40.0 |  |
| retina: ZED frames processed | 14.0 | 11.1 |  |
| trunk_concept | 20.0 | 20.0 |  |
| vegetation_concept | 20.0 | 20.0 |  |
| human_concept | 20.0 | 20.0 |  |
| robot_concept | 10.0 | 10.0 |  |
| zed (driver) | 59.0 | 59.0 |  |
| helios (LiDAR) | 17.0 | 13.0 |  |

## Latencies (ms)

| measure | n | median | p95 | max |
|---|---|---|---|---|
| robot pose in the graph (age when read) | 196 | 18 | 26 | 35 |
| people in the graph (age of the last RT sample) | 345 | 58 | 990 | 2318 |
| controller: max age of the velocity command (per report) | 332 | 43 | 65 | 125 |

## CPU / memory / GPU per process

![](../images/E5_cpu_per_agent.png)

| process | mean CPU (%) | max CPU (%) | RSS (MB) | GPU memory (MB) |
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

## E3 with the semantic model slowed down (Semantic.decimation = 4)

Trunk evidence is weighted per 'reference look' (LookPeriodMs = 530 ms); if the normalisation works, the map does not depend on how many inferences per second the GPU runs.

| run | semantic looks/s (approx.) | published | precision | recall | F1 | error (m) | false/h | wrong removals/h |
|---|---|---|---|---|---|---|---|---|
| E4/base/s1 | 11.0 | 60 | 1.00 | 1.00 | 1.00 | 0.067 | 0.0 | 0.0 |
| E4/base/s2 | 10.8 | 60 | 1.00 | 1.00 | 1.00 | 0.066 | 0.0 | 0.0 |
| E4/base/s3 | 11.0 | 60 | 1.00 | 1.00 | 1.00 | 0.069 | 0.0 | 0.0 |
| E5/slow_semantic/s1 | 2.5 | 60 | 0.98 | 0.98 | 0.98 | 0.061 | 12.8 | 0.0 |
