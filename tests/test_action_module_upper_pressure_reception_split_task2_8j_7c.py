from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_7c_relation_to_ot_information_preservation_audit import (
    build_and_validate_relation_to_ot_information_preservation_audit,
    validate_relation_to_ot_information_preservation_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_7c_information_preservation_boundaries():
    relation_trace, coverage_audit, audit_trace, final_summary, errors, summary = (
        build_and_validate_relation_to_ot_information_preservation_audit(_small_tracking_cfg())
    )

    assert errors == []
    assert not relation_trace.empty
    assert not coverage_audit.empty
    assert not audit_trace.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["upper_pressure_route_connected"] is False
    assert summary["actionmodule_called"] is False

    for table in [relation_trace, coverage_audit, audit_trace, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["information_preservation_audit_only"].astype(bool)) == {True}
        assert set(table["coarse_graining_allowed"].astype(bool)) == {True}
        assert set(table["source_evidence_required"].astype(bool)) == {True}
        assert set(table["upper_pressure_route_connected"].astype(bool)) == {False}
        assert set(table["actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_7c_relation_trace_and_compression_are_explicit():
    relation_trace, coverage_audit, audit_trace, final_summary, _errors, summary = (
        build_and_validate_relation_to_ot_information_preservation_audit(_small_tracking_cfg())
    )

    assert int(final_summary["source_changed_relation_count"].iloc[0]) == len(relation_trace)
    assert float(final_summary["changed_relation_coverage_rate"].iloc[0]) == 1.0
    assert float(final_summary["state_phase_coverage_rate"].iloc[0]) == 1.0
    assert float(final_summary["tracking_recovery_coverage_rate"].iloc[0]) == 1.0
    assert float(final_summary["audit_trace_coverage_rate"].iloc[0]) == 1.0
    assert int(final_summary["relation_trace_mismatch_count"].iloc[0]) == 0
    assert int(final_summary["compressed_out_relation_edge_count"].iloc[0]) >= 0
    assert set(relation_trace["relation_information_preservation_status"].astype(str)) == {"preserved_as_traceable_coarse_grained_observation"}
    assert coverage_audit["compression_status"].astype(str).str.contains("compressed|preserved").all()
    assert set(audit_trace["audit_trace_status"].astype(str)) == {"audit_layer_trace_preserved"}
    assert "information_preserved" in summary["information_preservation_decision"]


def test_task2_8j_7c_validator_detects_hidden_truth():
    relation_trace, coverage_audit, audit_trace, final_summary, _errors, _summary = (
        build_and_validate_relation_to_ot_information_preservation_audit(_small_tracking_cfg())
    )
    bad = relation_trace.copy()
    bad.loc[bad.index[0], "hidden_truth_input"] = True
    errors = validate_relation_to_ot_information_preservation_tables(bad, coverage_audit, audit_trace, final_summary)
    assert "task2_8j_7c_forbidden_true:relation_trace:hidden_truth_input" in errors
