from pathlib import Path
import re

import pandas as pd

from scripts.pseudoreality_v3_3_external_envelope_fixed_pca_audit import FIT_SEEDS, HOLDOUT_SEEDS, STEPS, fit_external_scenarios, holdout_external_scenarios
from scripts.pseudoreality_v3_3_full_distribution_semantic_axis_candidate_audit import axis_catalog, summarize

DOCS = Path('docs/task3_1d_full_distribution_semantic_axis_candidate_audit')
SCRIPT = Path('scripts/pseudoreality_v3_3_full_distribution_semantic_axis_candidate_audit.py')
REQUIRED_FAMILIES = {'distribution_shape','terrain_semantic','terrain_interaction','temporal_response','external_response','residual_response'}
REQUIRED_FILES = [
 'candidate_axis_catalog.csv','axis_value_summary.csv','axis_redundancy_summary.csv',
 'axis_conditional_separation_summary.csv','axis_external_response_summary.csv',
 'axis_temporal_response_summary.csv','axis_residual_relation_summary.csv',
 'axis_macro_dynamics_preservation_summary.csv','axis_classification_summary.csv',
 'artifact_manifest.csv','results.md']

def _truthy(series):
    return series.astype(str).str.lower().isin({'true','1','yes'})

def test_axis_catalog_unit_has_reproducible_definitions_and_required_families():
    axes = axis_catalog()
    assert len(axes) > 20
    assert REQUIRED_FAMILIES <= {a.axis_family for a in axes}
    assert all(a.definition and a.source_fields for a in axes)
    assert sum(a.is_interaction_axis for a in axes) >= 6
    assert {a.axis_name for a in axes} != {'resource','information','pressure','exploration','reversibility'}

def test_summarize_unit_columns_with_small_fixture_and_task3_1c_stub():
    axes = axis_catalog()[:8] + [a for a in axis_catalog() if a.axis_family == 'residual_response']
    rows=[]
    for dataset in ('fit_external','holdout_external'):
        for scenario_id in ('s1','s2'):
            for t in range(4):
                row={'dataset':dataset,'scenario_id':scenario_id,'scenario_group':'g','external_factor_name':'external_shock','external_factor_value':1.0,'seed':0,'t':t,'external_resource_supply':0,'external_demand':0,'external_competition_pressure':0,'external_information_noise':0,'external_shock':float(t==2),'external_constraint_pressure':0}
                for n,a in enumerate(axes): row[a.axis_id]=float((n+1)*(t+1))
                rows.append(row)
    task3 = {
        'residual': pd.DataFrame({'dataset':['fit_external','holdout_external'],'residual_energy_ratio_mean':[.1,.2],'residual_energy_ratio_max':[.3,.4]}),
        'terrain': pd.DataFrame({'dataset':['fit_external','holdout_external'],'top_positive_residual_cells_summary':['cell1:1','cell2:1'],'top_negative_residual_cells_summary':['cell3:-1',''],'residual_concentration_score':[.2,.3]}),
        'flags': pd.DataFrame({'dataset':['fit_external','holdout_external'],'auto_audit_flag_rate':[.1,.2],'residual_exceed_rate':[.2,.3],'mahalanobis_exceed_rate':[.0,.1],'score_range_violation_rate':[.0,.2]}),
    }
    tables, relation_meta = summarize(axes,pd.DataFrame(rows),task3)
    assert {'axis_i','axis_j','global_correlation','redundancy_score'} <= set(tables['axis_redundancy_summary.csv'].columns)
    assert set(tables['axis_conditional_separation_summary.csv']['recommended_pair_action']) <= {'keep_separate','merge_candidate','needs_review'}
    residual_cols = set(tables['axis_residual_relation_summary.csv'].columns)
    assert {'task3_1c_residual_mean_relation','task3_1c_positive_terrain_relation','task3_1c_auto_flag_rate_relation','task3_1c_join_status','task3_1c_join_key'} <= residual_cols
    assert relation_meta['task3_1c_matched_relation_rows'] > 0
    assert {'core_candidate','hold_candidate','audit_only'} & set(tables['axis_classification_summary.csv']['classification'])

def test_committed_docs_are_production_path_audit_artifacts_not_fixture_outputs():
    for name in REQUIRED_FILES:
        assert (DOCS/name).exists(), name
    catalog = pd.read_csv(DOCS/'candidate_axis_catalog.csv')
    assert len(catalog) > 30
    assert REQUIRED_FAMILIES <= set(catalog.axis_family)
    assert catalog.definition.notna().all() and (catalog.definition.str.len() > 0).all()
    assert catalog.source_fields.notna().all() and (catalog.source_fields.str.len() > 0).all()
    assert _truthy(catalog.uses_distribution_mass).any()
    assert set(catalog.axis_name) != {'resource','information','pressure','exploration','reversibility'}
    assert pd.read_csv(DOCS/'axis_redundancy_summary.csv').shape[0] > len(catalog)
    assert pd.read_csv(DOCS/'axis_conditional_separation_summary.csv').recommended_pair_action.isin(['keep_separate','merge_candidate','needs_review']).all()
    for name in ['axis_external_response_summary.csv','axis_temporal_response_summary.csv','axis_residual_relation_summary.csv','axis_macro_dynamics_preservation_summary.csv']:
        assert not pd.read_csv(DOCS/name).empty
    text=(DOCS/'results.md').read_text()
    for phrase in ['does not select final Core dimensions','does not compress the full distribution into a fixed 5-axis Core','does not use PCA as the primary log basis','Artifact provenance','Artifact scale','Task 3.1c linkage','Full distribution source: yes','PCA used as primary log basis: no','Fixed 5-axis Core selected: no','Final Core dimensions selected: no','Axis classifications are final decisions: no']:
        assert phrase in text
    assert 'production PseudoReality path' in text and 'fixture' not in text.lower()

def test_artifact_manifest_rejects_short_run_official_docs():
    manifest = pd.read_csv(DOCS/'artifact_manifest.csv')
    assert not manifest.empty
    assert _truthy(manifest.official_docs_artifact).all()
    assert (~_truthy(manifest.reduced_run)).all()
    assert (~_truthy(manifest.short_run_configuration)).all()
    assert _truthy(manifest.used_full_distribution).all()
    assert _truthy(manifest.used_task3_1c_outputs).all()
    assert (manifest.n_bins != 3).all()
    assert (manifest.steps != 3).all()
    assert (manifest.steps == STEPS).all()
    assert (manifest.used_fit_scenario_count == manifest.available_fit_scenario_count).all()
    assert (manifest.used_holdout_scenario_count == manifest.available_holdout_scenario_count).all()
    assert (manifest.used_fit_seed_count == manifest.available_fit_seed_count).all()
    assert (manifest.used_holdout_seed_count == manifest.available_holdout_seed_count).all()
    assert int(manifest.available_fit_scenario_count.iloc[0]) == len(fit_external_scenarios(STEPS))
    assert int(manifest.available_holdout_scenario_count.iloc[0]) == len(holdout_external_scenarios(STEPS))
    assert int(manifest.available_fit_seed_count.iloc[0]) == len(FIT_SEEDS)
    assert int(manifest.available_holdout_seed_count.iloc[0]) == len(HOLDOUT_SEEDS)
    assert (manifest.snapshot_count > 0).all()
    assert (manifest.task3_1c_residual_rows_loaded > 0).all()
    assert (manifest.task3_1c_terrain_rows_loaded > 0).all()
    assert (manifest.task3_1c_flag_reason_rows_loaded > 0).all()
    for col in ['task3_1c_residual_decomposition_path','task3_1c_residual_terrain_path','task3_1c_auto_audit_flag_reason_path']:
        assert manifest[col].str.startswith('docs/task3_1c_external_envelope_residual_decomposition/').all()

def test_task3_1c_relation_columns_are_present_and_not_all_unmatched():
    residual = pd.read_csv(DOCS/'axis_residual_relation_summary.csv')
    required = {'task3_1c_residual_mean_relation','task3_1c_residual_max_relation','task3_1c_positive_terrain_relation','task3_1c_negative_terrain_relation','task3_1c_auto_flag_rate_relation','task3_1c_residual_exceed_relation','task3_1c_mahalanobis_exceed_relation','task3_1c_score_range_violation_relation','task3_1c_join_status','task3_1c_join_key'}
    assert required <= set(residual.columns)
    assert (residual.task3_1c_join_status == 'matched').any()
    assert not (residual.task3_1c_join_status == 'unmatched').all()

def test_classification_reasons_are_measured_and_not_uniform():
    cls = pd.read_csv(DOCS/'axis_classification_summary.csv')
    required = {'classification_reason_detail','top_external_response_factor','top_external_response_score','strongest_residual_relation_source','strongest_residual_relation_score','strongest_macro_dynamics_signal','strongest_macro_dynamics_score','highest_redundancy_partner','highest_redundancy_score','conditional_separation_evidence'}
    assert required <= set(cls.columns)
    assert cls.classification_reason_detail.notna().all()
    assert cls.classification_reason_detail.nunique() >= max(1, int(len(cls) * 0.30))
    assert cls.reason.nunique() > 1
    assert cls.top_external_response_factor.replace('', pd.NA).notna().any()
    assert cls.strongest_residual_relation_source.replace('', pd.NA).notna().any()
    assert cls.strongest_macro_dynamics_signal.replace('', pd.NA).notna().any()
    assert cls.highest_redundancy_partner.replace('', pd.NA).notna().any()

def test_script_default_path_does_not_bake_in_short_run_settings():
    text = SCRIPT.read_text()
    assert 'def build_corpus(steps=3)' not in text
    assert 'fit_external_scenarios(steps)[:10]' not in text
    assert 'holdout_external_scenarios(steps)[:5]' not in text
    assert 'FIT_SEEDS[:2]' not in text
    assert 'HOLDOUT_SEEDS[:1]' not in text
    assert not re.search(r'n_bins\s*=\s*3', text)
    assert '--reduced-run' in text
