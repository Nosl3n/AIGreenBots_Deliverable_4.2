# E2 — People tracking

Evaluated region: workers within 10.0 m of the robot (all around it). CLEAR-MOT matching with a 1.0 m gate. 'Occlusion' = a stretch in which the worker is not visible to the camera (outside the ±49° field of view, or a canopy on the line of sight); it counts as kept if the same track follows the worker before and after it. Variants: fusion (ZED + LiDAR) and ZED only (HumanLidar.Enabled = false). The world has 4 workers, so the IDSW denominator is 4 × the run's minutes.

| variant | n | MOTA | MOTP (m) | IDSW/(worker·min) | longest kept occlusion (s) | false births |
|---|---|---|---|---|---|---|
| fusion | 1 | 0.30 | 0.176 | 1.575 | 64.0 | 17.0 |
| zed_only | 1 | 0.13 | 0.436 | 2.145 | 0.0 | 4.0 |

| run | MOTA | MOTP (m) | FN | FP | IDSW | IDSW/(worker·min) | longest occlusion (s) | occlusions kept | false births | tracks | min |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exp_people__fusion__s2 | 0.30 | 0.176 | 3795 | 4176 | 45 | 1.575 | 64.0 | 6/18 | 17 | 47 | 7.1 |
| exp_people__zed_only__s2 | 0.13 | 0.436 | 9159 | 1129 | 61 | 2.145 | 0.0 | 0/32 | 4 | 60 | 7.1 |
