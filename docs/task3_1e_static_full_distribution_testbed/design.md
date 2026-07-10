# Task 3.1e Design

Task 3.1e builds a static full-distribution PseudoReality v3.3 testbed from the real `DistributionTerrainV322World` path with five bins per axis and 3125 cells per distribution.

Raw generation, Jensen–Shannon coverage auditing, and persisted-artifact validation are separate. Smoke and formal use the same logical path; smoke only reduces scale. Each vector/seed source run is persistent across configured capture steps.

External values, seed, and step are audit metadata and remain outside the four-column discovery manifest. Semantic-axis selection, dynamic G_t timing, K_t/O_t, H-DEPT, and Action Module integration are out of scope.
