# E3 — Trunk map against the world's ground truth

Hungarian matching with a 0.25 m gate against the 60 tree positions of the .wbt (written by gen_apple_rows.py). 'Recall (seen)' counts only the trees that came within 4 m of the robot (the ZED's absence range). The base runs are the E4 missions.

## Summary per variant (mean over runs)

| variant | n | precision | recall | recall (seen) | F1 | mean error (m) | false trunks/h | wrong removals/h |
|---|---|---|---|---|---|---|---|---|
| base | 3 | 1.00 | 1.00 | 1.00 | 1.00 | 0.068 | 0.0 | 0.0 |
| no_lidar_confirm | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0.071 | 0.0 | 0.0 |
| no_pvis | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0.058 | 0.0 | 0.0 |
| slow_semantic | 1 | 0.98 | 0.98 | 0.98 | 0.98 | 0.061 | 12.8 | 0.0 |

## Per run

| run | variant | published | hits | precision | recall | recall seen (n) | F1 | error (m) | false | wrong removals |
|---|---|---|---|---|---|---|---|---|---|---|
| E4/husky_apple__base__s1 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.067 | 0 (0.0/h) | 0 (0.0/h) |
| E4/husky_apple__base__s2 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.066 | 0 (0.0/h) | 0 (0.0/h) |
| E4/husky_apple__base__s3 | base | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.069 | 0 (0.0/h) | 0 (0.0/h) |
| E3/husky_apple__no_lidar_confirm__s1 | no_lidar_confirm | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.071 | 0 (0.0/h) | 0 (0.0/h) |
| E3/husky_apple__no_pvis__s1 | no_pvis | 60 | 60 | 1.00 | 1.00 | 1.00 (60) | 1.00 | 0.058 | 0 (0.0/h) | 0 (0.0/h) |
| E5/husky_apple__slow_semantic__s1 | slow_semantic | 60 | 59 | 0.98 | 0.98 | 0.98 (60) | 0.98 | 0.061 | 1 (12.8/h) | 0 (0.0/h) |
