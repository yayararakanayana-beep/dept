# Phase 2G-16A Observation Window / ActionModule Boundary Clarification

## 1. Scope

Phase 2G-16A clarifies the boundary between observation windows and the ActionModule.

Japanese fixed name:

`観測窓口と作用モジュールの境界補足`

This is a **docs-only boundary clarification**.

This addendum supersedes any reading of Phase 2G-16 that could imply that observation-window outputs are runtime inputs to the ActionModule.

In particular, this addendum clarifies the intended reading of:

- `PHASE2G16_V2_INDICATOR_OBSERVATION_WINDOW_DESIGN.md` Section 12.4;
- `PHASE2G16_V2_INDICATOR_OBSERVATION_WINDOW_DESIGN.md` Section 13;
- `PHASE2G16_V2_INDICATOR_OBSERVATION_WINDOW_DESIGN.md` Section 14 item 7.

## 2. Fixed Boundary

Observation windows are external validation and design-adjustment surfaces.

Observation-window outputs must not become runtime inputs to the ActionModule.

The ActionModule receives only prepared system-side information that belongs to the action-translation path.

Japanese fixed rule:

> 観測窓口は、検証者・設計者・後続の調整プロセスが読むための外部観測面である。観測窓口の出力は、作用モジュールの実行時入力ではない。作用モジュールは、あくまで作用翻訳経路に渡された系情報のみを受け取り、その範囲で作用を生成する。

## 3. Reason

Phase 2G-15B fixed that indicators are observation aids, not objectives.

Phase 2G-16 grouped those indicators into observation windows.

If those windows were passed into the ActionModule as direct runtime inputs, the ActionModule could begin to optimize against window status labels or derived scores.

That would violate the established boundary:

- indicators are not objectives;
- windows are not objectives;
- ActionModule must not become a metric optimizer;
- ActionModule must remain a system-side action translator.

Therefore, observation windows must remain outside the ActionModule runtime input path.

## 4. Corrected Interpretation of Phase 2G-16 Section 12.4

The intended rule is not:

> Observation windows command or directly guide runtime action.

The intended rule is:

> Observation-window readings are evidence for external validation and later design adjustment. They do not command action directly, and they are not passed to the runtime ActionModule as action-driving inputs.

Japanese corrected rule:

> 観測窓口の読みは、外部検証と後続の設計調整のための証拠であり、作用を直接命令するものではない。また、実行時の作用モジュールに作用駆動入力として渡すものでもない。

## 5. Corrected Interpretation of Phase 2G-16 Section 13

The phrase `ActionModule Visibility Rule` should be read as an external validation visibility rule, not as runtime visibility by the ActionModule.

Corrected fixed name:

`ActionModule Boundary Rule`

Japanese fixed name:

`作用モジュール境界ルール`

Corrected rule:

> The ActionModule must not consume observation-window outputs as runtime inputs. Observation windows may be used by the validation runner, researcher, or design process to diagnose ActionModule behavior and adjust later implementation choices, but not by the ActionModule itself during action generation.

Japanese corrected rule:

> 作用モジュールは、観測窓口の出力を実行時入力として読んではならない。観測窓口は、検証runner・研究者・設計プロセスが作用モジュールの挙動を診断し、後続の実装方針を調整するために使うものであり、作用生成中の作用モジュール自身が読むものではない。

## 6. Forbidden Runtime Couplings

The following runtime couplings are forbidden:

- ActionModule reads `system_benefit_window_status`;
- ActionModule reads `h11_possibility_distribution_window_status`;
- ActionModule reads `pressure_action_alignment_window_status`;
- ActionModule reads `risk_band_window_status`;
- ActionModule reads `growth_window_status`;
- ActionModule reads `composite_balance_window_status`;
- ActionModule reads window `short_reason` fields;
- ActionModule reads window `warning_flags` as direct action triggers;
- ActionModule reads growth proxies as direct targets;
- ActionModule reads risk-band labels as unconditional action triggers;
- ActionModule changes action strength because a window label is low;
- ActionModule acts without pressure because an observation window is unhealthy.

## 7. Allowed External Uses

The following uses are allowed:

- post-run validation analysis;
- PR review and diagnosis;
- experiment report generation;
- comparison of ActionModule policy modes;
- identification of over-action or under-action patterns;
- identification of missing trace fields;
- offline adjustment of later ActionModule design;
- offline adjustment of thresholds in future experiments;
- deciding which implementation task to run next;
- deciding whether additional probes are needed.

These are design-time or validation-time uses, not runtime ActionModule inputs.

## 8. ActionModule Input Boundary

The ActionModule should receive only system-side action-translation inputs prepared by the pipeline.

The exact implementation-level input contract may be refined later, but the boundary is fixed:

- system information prepared for action translation: allowed;
- observation-window outputs: not allowed as runtime inputs;
- validation summaries: not allowed as runtime inputs;
- window labels: not allowed as runtime inputs;
- window-derived success/failure judgments: not allowed as runtime inputs.

Japanese fixed rule:

> 作用モジュールに渡すのは、作用翻訳のために準備された系情報である。観測窓口の出力、検証summary、window label、成功/失敗判定は、作用モジュールの実行時入力にしてはならない。

## 9. Corrected Phase 2G-17 Entry Condition

Phase 2G-16 Section 14 item 7 should not be read as asking whether the ActionModule may consume window outputs.

Corrected item:

> Confirm that the ActionModule must not consume observation-window outputs at runtime, and decide how external validation will use window outputs for later design adjustment.

Japanese corrected item:

> 作用モジュールが観測窓口出力を実行時に読まないことを確認し、外部検証がそれらの窓口出力を後続の設計調整にどう使うかを決める。

## 10. Implication for Phase 2G-17

Phase 2G-17 should implement or design export/probe behavior under this boundary.

Allowed Phase 2G-17 work:

- export observation-window outputs;
- compute window status labels;
- emit evidence fields;
- emit warning flags;
- emit unresolved flags;
- summarize contradictions among windows;
- report which trace fields were sufficient or missing;
- support external analysis for later ActionModule adjustment.

Forbidden Phase 2G-17 work:

- passing window outputs into the ActionModule;
- changing ActionModule behavior based on window labels;
- using window status as a runtime action trigger;
- using growth proxies as ActionModule objectives;
- using risk-band labels as unconditional action triggers;
- implementing dynamic thresholds inside the ActionModule from window outputs.

## 11. Implication for Later ActionModule Validation

Later ActionModule validation may use observation-window outputs to compare policy modes.

Example:

- run baseline ActionModule;
- export window outputs;
- inspect benefit / possibility / growth / alignment conflicts;
- adjust ActionModule design externally;
- run another controlled validation;
- compare results.

But the ActionModule itself must not read the observation-window outputs during the run.

This preserves the boundary:

```text
system information -> ActionModule -> action
validation traces -> observation windows -> external analysis / design adjustment
```

The second path must not loop directly into the ActionModule at runtime.

## 12. Conclusion

Phase 2G-16A fixes the boundary:

- observation windows are external validation surfaces;
- observation windows are not runtime ActionModule inputs;
- observation windows may be used to adjust later design externally;
- ActionModule remains a system-side action translator;
- ActionModule must not become a window-label optimizer or metric optimizer.

This addendum should be read together with:

- `PHASE2G16_V2_INDICATOR_OBSERVATION_WINDOW_DESIGN.md`;
- `PHASE2G15B_INDICATOR_STATUS_AND_INTERPRETATION_RULE.md`;
- `PHASE2G15_V2_RISK_BAND_BENEFIT_POSSIBILITY_METRIC_FIXATION.md`;
- `PHASE2G15A_V2_GROWTH_COMPOSITE_OBSERVATION_WINDOW.md`;
- `PHASE2G14_RC_FREEZE_HANDOFF_PACK.md`.
