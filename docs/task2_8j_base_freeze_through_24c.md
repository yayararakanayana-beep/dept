# Task2-8j Base Freeze Through 24c

This branch imports the Task2-8j fixed static_pca_7 / 7-axis G_t base code through Task2-8j-24c.

Included:
- Task2-8j-1 through Task2-8j-24c workflow files
- Task2-8j-1 through Task2-8j-24c action_policies modules
- Task2-8j-1 through Task2-8j-24c tests

Development policy:
- Future Task2-8j development should use fixed static_pca_7 / 7-axis G_t as the main development base.
- Older G_t routes are preserved as references, fallback baselines, and rollback/audit material.
- Do not delete legacy G_t code or historical validation artifacts as a side effect of normal development.
- Updates should remain reversible, additive, and auditable unless a later dedicated archival PR explicitly changes that status.

See also:
- docs/task2_8j_7axis_gt_reversible_development_policy.md

Boundary:
- no real ActionModule runtime execution is introduced
- no canonical writeback is introduced
- no axis execution is introduced
- 24c remains a provisional action-module design lock, not final deployment
