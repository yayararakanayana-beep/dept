# PseudoReality v3.3 PCA-G_t Candidate Comparison

Task 3 adds a lightweight, fixed-basis PCA candidate comparison for the
PseudoReality v3.3 full state distribution. Each snapshot is represented as a
3125-cell mass vector over the 5 axes x 5 bins state grid. PCA axes are named
`g1`, `g2`, ... and are treated as geometric distribution axes rather than
semantic aliases for source dimensions.

The pipeline is implemented in
`scripts/pseudoreality_v3_3_pca_gt_candidate_comparison.py` and is runnable with:

```bash
python scripts/pseudoreality_v3_3_pca_gt_candidate_comparison.py
```

By default, outputs are written to
`artifacts/pseudoreality_v3_3_pca_gt_candidate_comparison/`.

## Corpus

The full-envelope corpus includes normal v3.3 snapshots, stress snapshots,
concentrated templates, diffuse templates, multi-peak templates, boundary
templates, convex mixtures, and holdout snapshots. Convex mixtures use
`lambda = 0.25, 0.50, 0.75`. Rows marked `corpus_type == "holdout"` are
excluded from PCA fitting and are projected afterward through the fixed fitted
mean/components for true holdout reconstruction, residual, and envelope metrics.

## Candidate families

The comparison covers:

- `raw_static_pca`
- `sqrt_static_pca`
- `log_static_pca`
- `sqrt_temporal_lag_pca`
- `sqrt_sparse_temporal_lag_pca`

Each family is evaluated at 5, 7, 10, and 12 components. The primary Task 3
candidate is `sqrt_static_pca_7`; its decision status is derived from
reconstruction error, residual energy, out-of-envelope counts, and comparison
against alternatives rather than being unconditionally selected.

## Outputs

Required CSV outputs include candidate summary, component table, snapshot scores,
reconstruction metrics, envelope audit, and candidate decision tables. Optional
manifest tables for the corpus, extreme templates, mixtures, and holdout
projection metrics are also emitted.

## Scope boundary

This task only audits a fixed PCA-G_t basis. It does not implement game-structure
inference, H-DEPT connections, O_t connections, ActionModule connections, macro
relation-field extraction, dynamic PCA basis updates, or canonical parameter
updates.
