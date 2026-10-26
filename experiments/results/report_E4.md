# E4 — Integrated navigation

Missions: 3. Waypoint success: 100.0 %. Complete missions: 100.0 %.
Mean mission time: 248.7 s. Minimum clearance to trunks: 0.57 m; to people: 0.73 m. Collisions (contacts of the 0.99x0.686 m body with a trunk / with a person's 0.25 m disc): 0 / 0.

Clearance = distance from the body rectangle (Webots ground-truth pose) to the trunk (real radius) or to the person. GNSS not degraded; the published (A) filter drives.

| run | waypoints | time (s) | path (m) | trunk clearance (m) | person clearance (m) | trunk coll. | person coll. | loc. error p50 (m) | loc. error p95 (m) |
|---|---|---|---|---|---|---|---|---|---|
| husky_apple__base__s1 | 9/9 | 278.3 | 154.7 | 0.58 | 1.16 | 0 | 0 | 0.041 | 0.077 |
| husky_apple__base__s2 | 9/9 | 231.2 | 121.6 | 0.57 | 1.09 | 0 | 0 | 0.040 | 0.079 |
| husky_apple__base__s3 | 9/9 | 236.7 | 126.7 | 0.58 | 0.73 | 0 | 0 | 0.041 | 0.081 |
