## Conclusions

Internal campaign in simulation (Webots R2025a, apple orchard `husky_apple.wbt`), with few repetitions except in E1
(10 seeds).

- **E1 · Localization with degraded GNSS.** Under the canopies the degradation layer produces 20 % RTK fixed, 38 %
  RTK float, 27 % single and 16 % no fix. The current EKF (A) gives a p50 error of 0.47 m and a p95 of 1.68 m, with a
  mean NEES far above the 95 % interval ([1.68, 4.70] for N = 10): its covariance does not reflect the actual error.
  B (receiver σ + Student-t likelihood + latency compensation) lowers the error to p50 0.22 m / p95 0.98 m and the
  NEES to ~130; it improves, but stays outside the interval, because the receiver error is correlated in time and
  multipath does not show in its σ. Without GNSS (C) the p50 error over the route (~2.5 min) is ~0.7 m. Without the
  IMU yaw (D) the p95 heading error goes from 0.2° to ~12°. With clean GNSS, A has a p50 error of 2 cm.
- **E2 · People tracking.** ZED + LiDAR fusion against ZED only: MOTA 0.30 vs 0.13; MOTP 0.18 m vs 0.44 m (the LiDAR
  places a person more precisely than stereo depth); identity kept in 6 of 18 occlusions (up to 64 s) vs 0 of 32.
  Fusion produces more false births (17 vs 4), on the tree canopies.
- **E3 · Trunk map.** 60/60 trunks, F1 = 1.00, mean error 6.7 cm, no false trunks and no wrong removals. The two
  ablations do not change the result in this world: there are no false semantic candidates in the trunk band and no
  occlusions long enough. With the semantic model at ¼ rate (11 → 2.5 looks/s) F1 is 0.98: the per-reference-look
  normalisation keeps the map.
- **E4 · Integrated navigation.** 3/3 missions completed (9/9 waypoints), ~250 s per mission, minimum clearance
  0.57 m to trunks and 0.73 m to people, no collisions. GNSS not degraded; localization error p50 4 cm / p95 8 cm.
- **E5 · Performance.** Pose at 50 Hz, residual grid at 10 Hz, controller ~17 Hz, ZED processed at ~14 fps. Pose
  latency in the graph 18 ms (p95 26 ms). Total CPU ~11 % of the machine; `retina` is the most expensive process
  (64 % of one core, 1.6 GB of GPU memory).
