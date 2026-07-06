from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_7b_ot_audit_layering import (
    OtAuditLayeringConfig,
    build_and_validate_ot_audit_layering,
    validate_ot_audit_layering_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_7b_audit_layering_boundaries():
    audit_layers, reason_summary, final_summary, errors, summary = build_and_validate_ot_audit_layering(
        _small_tracking_cfg(),
        cfg=OtAuditLayeringConfig(),
    )

    assert errors == []
    assert not audit_layers.empty
    assert not reason_summary.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["upper_pressure_route_connected"] is False
    assert summary["actionmodule_called"] is False

    for table in [audit_layers, reason_summary, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["audit_layering_only"].astype(bool)) == {True}
        assert set(table["upper_pressure_route_connected"].astype(bool)) == {False}
        assert set(table["hdept_pressure_generated"].astype(bool)) == {False}
        assert set(table["action_input_converted"].astype(bool)) == {False}
        assert set(table["actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_7b_splits_audit_reasons_and_levels():
    audit_layers, reason_summary, final_summary, _errors, summary = build_and_validate_ot_audit_layering(
        _small_tracking_cfg(),
        cfg=OtAuditLayeringConfig(),
    )

    assert int(final_summary["observation_unit_count"].iloc[0]) == len(audit_layers)
    assert int(final_summary["audit_candidate_count"].iloc[0]) > 0
    assert int(final_summary["reason_summary_count"].iloc[0]) >= 5
    assert int(final_summary["risk_reason_total"].iloc[0]) > 0
    assert int(final_summary["confidence_reason_total"].iloc[0]) > 0
    assert int(final_summary["change_reason_total"].iloc[0]) > 0
    assert int(final_summary["centrality_reason_total"].iloc[0]) > 0
    assert set(audit_layers["audit_level"].astype(str)).issubset({"monitor", "review_before_action", "block_direct_action"})
    assert audit_layers["audit_strength_score"].astype(float).between(0.0, 1.0).all()
    assert "ot_audit" in summary["audit_layering_decision"]
    assert {"resource_pressure_involved", "phase_sensitive_relation"}.issubset(set(reason_summary["audit_reason"].astype(str)))


def test_task2_8j_7b_validator_detects_actionmodule_call():
    audit_layers, reason_summary, final_summary, _errors, _summary = build_and_validate_ot_audit_layering(
        _small_tracking_cfg(),
        cfg=OtAuditLayeringConfig(),
    )
    bad = audit_layers.copy()
    bad.loc[bad.index[0], "actionmodule_called"] = True
    errors = validate_ot_audit_layering_tables(bad, reason_summary, final_summary)
    assert "task2_8j_7b_forbidden_true:audit_layers:actionmodule_called" in errors
