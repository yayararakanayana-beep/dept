# PseudoReality v2 Profile Behavior Report

## 1. Purpose

This document records a docs-only observation pass over the PseudoReality v2 profile behavior emitted by `matrix_v2_probe`.

This report is **not** performance validation. It is **profile behavior observation**. It checks whether the v2 diagnostic traces show the intended directional tendencies for three profiles:

- `pseudo_reality_v2_shrinking_equilibrium`
- `pseudo_reality_v2_trust_collapse`
- `pseudo_reality_v2_public_stability_hidden_decay`

This report is a tendency check for the additional v2 traces. It does **not** claim that the v2 world is superior, and it does **not** formally adopt any H-DEPT diagnostic indicator.

The v2 additional traces remain audit / diagnostic outputs only. They must not be directly mixed into `G_t`, `O_t`, or `K_t`.

## 2. Verification target

- Repository branch used by the working tree: `work` in this local checkout; the requested target branch for the task was `main`.
- Verification commit: `4b3d84a Merge PR #36: Freeze PseudoReality v2 Impl-B handoff`.
- Relevant recent history:
  - `4b3d84a Merge PR #36: Freeze PseudoReality v2 Impl-B handoff`
  - `9f8d510 Freeze PseudoReality v2 Impl-B handoff`
  - `f75739c Merge PR #35: Add PseudoReality v2 diagnostic traces and probe matrix`
  - `1aa9a5f Add PseudoReality v2 diagnostic traces`
  - `d76c912 Merge PR #33: Add Phase 2E-1b projection-zero ActionFrame source audit`

## 3. Executed matrix

Command:

```bash
cd localprep1/dept
python scripts/run_matrix_validation.py \
  --matrix configs/matrices/matrix_v2_probe.json \
  --output-dir validation_runs/v2_profile_behavior
```

Observed matrix result:

- Matrix: `configs/matrices/matrix_v2_probe.json`
- Matrix name: `matrix_v2_probe`
- Run count: 9
- `overall_pass`: `true`
- `boundary_violation_total`: `0`
- `dry_run_write_violation_count`: `0`
- `forbidden_write_count`: `0`

## 4. Runs and traces used

The matrix covered each profile with each action profile:

- `action_default`
- `action_conservative`
- `action_buffered`

The following trace files were analyzed in every run:

- `v2_hidden_trace.csv`
- `v2_game_trace.csv`
- `v2_resource_trace.csv`
- `v2_information_trace.csv`
- `v2_action_effect_trace.csv`
- `entity_trace.csv`
- `relation_trace.csv`

For each metric, `first_mean` is the mean over the first three observed `t` values and `last_mean` is the mean over the last three observed `t` values. `delta = last_mean - first_mean`. Direction is `up`, `down`, or `stable`; small absolute deltas below `0.005` are treated as stable for this report.

## 5. Profile-level judgment table

| Profile | Expected behavior | Observed behavior | Judgment | Notes |
| --- | --- | --- | --- | --- |
| `pseudo_reality_v2_shrinking_equilibrium` | Hidden damage, latent pressure, fatigue, resource pressure, and resource inequality rise; cooperation, exploration, reversibility, information quality, and long-term health fall; short-term payoff is maintained or rises. | Observed directions match the intended pattern: hidden damage `+0.6483`, latent pressure `+0.4213`, fatigue `+0.4866`, cooperation intent `-0.4282`, exploration `-0.1830`, reversibility `-0.1083`, short-term payoff `+0.1360`, long-term health proxy `-0.3041`, resource pressure `+0.0685`, resource inequality `+0.0320`, and information quality mean `-0.5450`. | expected | The short-term / long-term split is visible. Resource inequality rises, but less strongly than in the other two profiles. |
| `pseudo_reality_v2_trust_collapse` | Information quality and information flow fall; distortion, misread probability, coordination lag, hidden damage, latent pressure, and defense rise; cooperation falls. | Observed directions match the trust-collapse pattern: information quality mean `-0.4117`, information distortion `+0.1441`, misread probability `+0.0720`, coordination lag `+0.1104`, information flow `-0.1950`, cooperation intent `-0.4467`, cooperate tendency `-0.3256`, defend tendency `+0.3783`, hidden damage `+0.7044`, and latent pressure `+0.4480`. | expected | Trust / information deterioration is visible. Resource pressure also rises strongly, so the observed run is not purely information-only decay. |
| `pseudo_reality_v2_public_stability_hidden_decay` | Public-facing activity remains stable while hidden damage, latent pressure, and fatigue rise; exploration, reversibility, and long-term health fall; volatility and uncertainty should remain stable or decline. | Hidden decay matches strongly: hidden damage `+0.6725`, latent pressure `+0.4921`, fatigue `+0.5938`, exploration `-0.2073`, reversibility `-0.1373`, and long-term health `-0.3316`. Activity is near-maintained overall at `-0.0156`, but volatility `+0.0888` and uncertainty `+0.1453` rise instead of staying stable or declining. | weak | The internal decay / public activity split is present, but the surface stability claim is only partially supported because volatility and uncertainty increase. |

## 6. Profile summary

### 6.1 `pseudo_reality_v2_shrinking_equilibrium`

The shrinking-equilibrium run family shows a clear internal degradation pattern. Hidden damage, latent pressure, and fatigue rise materially, while cooperation intent, exploration, reversibility, information quality, and long-term health proxy decline. Short-term payoff rises, which supports the intended separation between immediate payoff and long-term health.

The strongest matching evidence is the combination of short-term payoff increasing from `0.4827` to `0.6187` while long-term health proxy declines from `0.5397` to `0.2356`. Hidden damage also rises from `0.2857` to `0.9341`.

The weaker point is not a mismatch, but a scale note: resource inequality rises only from `0.2217` to `0.2537`, a smaller change than trust collapse and public-stability hidden decay.

### 6.2 `pseudo_reality_v2_trust_collapse`

The trust-collapse run family shows the expected information and coordination degradation. Information quality mean falls to `0.0000`, information flow mean falls to `0.0000`, while distortion, misread probability, and coordination lag rise. Cooperation intent and cooperate tendency both decline, and defend tendency rises.

The profile also shows the highest average hidden-damage delta among the three profiles (`+0.7044`) and the highest average resource-pressure delta (`+0.1424`). This means the observed behavior is consistent with trust collapse, but the run also experiences visible resource stress.

### 6.3 `pseudo_reality_v2_public_stability_hidden_decay`

The public-stability hidden-decay profile shows strong hidden decay: hidden damage reaches `1.0000`, latent pressure rises to `0.9622`, fatigue rises to `0.9731`, exploration falls to `0.2006`, reversibility falls to `0.4446`, and long-term health proxy falls to `0.2093`.

The surface-stability expectation is mixed. Activity is mostly maintained at the profile level, moving from `0.5594` to `0.5439`; the `action_default` run is effectively stable at `-0.0018`. However, volatility rises from `0.2223` to `0.3111` and uncertainty rises from `0.3905` to `0.5357`, so this report does not claim that all public-facing stability indicators remained stable.

## 7. Action-profile summary

Across all three world profiles, the three action profiles preserve the main directional behaviors. Differences are mostly in magnitude rather than direction.

| Profile | Action profile | Key observation |
| --- | --- | --- |
| `pseudo_reality_v2_shrinking_equilibrium` | `action_default` | Hidden damage rises `+0.6390`; cooperation intent falls `-0.4243`; exploration falls `-0.1787`; activity rises slightly. |
| `pseudo_reality_v2_shrinking_equilibrium` | `action_conservative` | Same directional pattern; activity falls `-0.0249`; hidden damage rises `+0.6529`. |
| `pseudo_reality_v2_shrinking_equilibrium` | `action_buffered` | Same directional pattern; activity rises `+0.0154`; hidden damage rises `+0.6531`. |
| `pseudo_reality_v2_trust_collapse` | `action_default` | Trust-collapse indicators align: information quality mean falls `-0.4049`; resource pressure rises `+0.1473`. |
| `pseudo_reality_v2_trust_collapse` | `action_conservative` | Same directional pattern; activity is stable at `+0.0016`; hidden damage rises `+0.7054`. |
| `pseudo_reality_v2_trust_collapse` | `action_buffered` | Same directional pattern; information quality mean falls `-0.4000`; hidden damage rises `+0.7086`. |
| `pseudo_reality_v2_public_stability_hidden_decay` | `action_default` | Activity is stable at `-0.0018`, but volatility rises `+0.0910`; hidden damage rises `+0.6720`. |
| `pseudo_reality_v2_public_stability_hidden_decay` | `action_conservative` | Hidden decay is strong, but activity falls `-0.0157` and volatility rises `+0.0902`. |
| `pseudo_reality_v2_public_stability_hidden_decay` | `action_buffered` | Hidden decay is strong, but activity falls `-0.0292` and volatility rises `+0.0853`. |

## 8. Selected numerical aggregation

This table intentionally lists selected key metrics only. It is not a full dump of every trace column.

| profile | action_profile | trace | metric | first_mean | last_mean | delta | direction |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `pseudo_reality_v2_shrinking_equilibrium` | `action_default` | `v2_hidden_trace` | `hidden_damage` | 0.3028 | 0.9418 | 0.6390 | up |
| `pseudo_reality_v2_shrinking_equilibrium` | `action_default` | `v2_game_trace` | `short_term_payoff` | 0.4778 | 0.6176 | 0.1398 | up |
| `pseudo_reality_v2_shrinking_equilibrium` | `action_default` | `v2_game_trace` | `long_term_health_proxy` | 0.5346 | 0.2342 | -0.3004 | down |
| `pseudo_reality_v2_shrinking_equilibrium` | `action_conservative` | `entity_trace` | `exploration` | 0.3850 | 0.2005 | -0.1845 | down |
| `pseudo_reality_v2_shrinking_equilibrium` | `action_buffered` | `entity_trace` | `reversibility` | 0.5691 | 0.4627 | -0.1064 | down |
| `pseudo_reality_v2_trust_collapse` | `action_default` | `v2_information_trace` | `information_quality_mean` | 0.4049 | 0.0000 | -0.4049 | down |
| `pseudo_reality_v2_trust_collapse` | `action_default` | `v2_information_trace` | `information_distortion_mean` | 0.3283 | 0.4700 | 0.1417 | up |
| `pseudo_reality_v2_trust_collapse` | `action_conservative` | `v2_information_trace` | `coordination_lag_mean` | 0.5680 | 0.6773 | 0.1093 | up |
| `pseudo_reality_v2_trust_collapse` | `action_buffered` | `v2_game_trace` | `cooperate_tendency` | 0.4790 | 0.1608 | -0.3182 | down |
| `pseudo_reality_v2_trust_collapse` | `action_buffered` | `v2_hidden_trace` | `hidden_damage` | 0.2866 | 0.9952 | 0.7086 | up |
| `pseudo_reality_v2_public_stability_hidden_decay` | `action_default` | `entity_trace` | `activity` | 0.5612 | 0.5594 | -0.0018 | stable |
| `pseudo_reality_v2_public_stability_hidden_decay` | `action_default` | `entity_trace` | `volatility` | 0.2189 | 0.3099 | 0.0910 | up |
| `pseudo_reality_v2_public_stability_hidden_decay` | `action_conservative` | `v2_hidden_trace` | `hidden_damage` | 0.3273 | 1.0000 | 0.6727 | up |
| `pseudo_reality_v2_public_stability_hidden_decay` | `action_buffered` | `entity_trace` | `exploration` | 0.4202 | 0.2127 | -0.2074 | down |
| `pseudo_reality_v2_public_stability_hidden_decay` | `action_buffered` | `entity_trace` | `reversibility` | 0.5951 | 0.4579 | -0.1372 | down |

## 9. Profile-to-profile differences

### 9.1 Shrinking equilibrium vs. trust collapse

Both profiles show hidden damage, latent pressure, fatigue, cooperation decline, exploration decline, reversibility decline, and long-term health decline. The main observed distinction is that `trust_collapse` starts with worse information conditions and maintains higher distortion, misread probability, and coordination lag. Its resource pressure also rises more strongly than `shrinking_equilibrium` in this probe run.

### 9.2 Shrinking equilibrium vs. public stability hidden decay

Both profiles show the short-term / long-term split and hidden decay. `public_stability_hidden_decay` has stronger fatigue and latent-pressure increase, stronger exploration and reversibility decline, and hidden damage reaches the upper bound. However, the public-stability part is only weakly supported because volatility and uncertainty rise.

### 9.3 Trust collapse vs. public stability hidden decay

`trust_collapse` has the clearest information-collapse signature: higher distortion and misread probability than the other profiles. `public_stability_hidden_decay` shows stronger fatigue and latent pressure and reaches maximum hidden damage, but its volatility and uncertainty rise, making the public-stability interpretation weaker than intended.

## 10. Current interpretation

The v2 diagnostic traces are useful for observing profile tendencies. In this run:

- `shrinking_equilibrium` is consistent with gradual internal degradation under maintained or improved short-term payoff.
- `trust_collapse` is consistent with cooperation failure through information quality loss, distortion, misread probability, and coordination lag.
- `public_stability_hidden_decay` is consistent with hidden decay, but not fully consistent with stable public-facing indicators.

These conclusions are observational. They should be treated as input to v2-RC1 preparation, not as acceptance criteria or runtime control logic.

## 11. What this report must not claim

This report must not claim any of the following:

- That the probe is performance validation.
- That v2 is better than v1 or better than any other world implementation.
- That the observed diagnostic metrics are formally adopted H-DEPT indicators.
- That v2 traces should be connected directly into `G_t`, `O_t`, or `K_t`.
- That the profile behavior is stable across all seeds, step counts, matrices, or future implementations.
- That the public-stability hidden-decay profile fully satisfies every public-stability expectation in this run.
- That any validation gate or acceptance condition has changed.

## 12. Next-phase candidates

Potential next steps for v2-RC1 preparation:

1. Repeat the same docs-only profile observation across more seeds and longer horizons.
2. Add a non-gating analysis notebook or script outside runtime paths, if a later task explicitly requests it.
3. Clarify the intended public-facing stability indicators for `public_stability_hidden_decay`, especially whether volatility and uncertainty should be hard expectations or secondary observations.
4. Compare profile behavior against a small baseline matrix without changing acceptance criteria.
5. Keep all v2 traces as audit / diagnostic outputs unless a later explicit design task proposes and approves a formal integration path.

## 13. Cleanup

After the report was drafted, generated validation outputs were removed with:

```bash
rm -rf validation_runs
find . -type d \( -name "__pycache__" -o -name "pycache" \) -prune -exec rm -rf {} +
```
