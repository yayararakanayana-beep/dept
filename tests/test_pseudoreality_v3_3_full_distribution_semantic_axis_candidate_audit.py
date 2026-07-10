from pathlib import Path
import pandas as pd

from scripts.pseudoreality_v3_3_full_distribution_semantic_axis_candidate_audit import axis_catalog, summarize

DOCS = Path('docs/task3_1d_full_distribution_semantic_axis_candidate_audit')
REQUIRED_FAMILIES = {'distribution_shape','terrain_semantic','terrain_interaction','temporal_response','external_response','residual_response'}
REQUIRED_FILES = [
 'candidate_axis_catalog.csv','axis_value_summary.csv','axis_redundancy_summary.csv',
 'axis_conditional_separation_summary.csv','axis_external_response_summary.csv',
 'axis_temporal_response_summary.csv','axis_residual_relation_summary.csv',
 'axis_macro_dynamics_preservation_summary.csv','axis_classification_summary.csv','results.md']

def test_axis_catalog_unit_has_reproducible_definitions_and_required_families():
    axes = axis_catalog()
    assert len(axes) > 20
    assert REQUIRED_FAMILIES <= {a.axis_family for a in axes}
    assert all(a.definition and a.source_fields for a in axes)
    assert sum(a.is_interaction_axis for a in axes) >= 6
    assert {a.axis_name for a in axes} != {'resource','information','pressure','exploration','reversibility'}

def test_summarize_unit_columns_with_small_fixture():
    axes = axis_catalog()[:8] + [a for a in axis_catalog() if a.axis_family == 'residual_response']
    rows=[]
    for dataset in ('fit_external','holdout_external'):
        for scenario_id in ('s1','s2'):
            for t in range(4):
                row={'dataset':dataset,'scenario_id':scenario_id,'scenario_group':'g','external_factor_name':'external_shock','external_factor_value':1.0,'seed':0,'t':t,'external_resource_supply':0,'external_demand':0,'external_competition_pressure':0,'external_information_noise':0,'external_shock':float(t==2),'external_constraint_pressure':0}
                for n,a in enumerate(axes): row[a.axis_id]=float((n+1)*(t+1))
                rows.append(row)
    tables=summarize(axes,pd.DataFrame(rows))
    assert {'axis_i','axis_j','global_correlation','redundancy_score'} <= set(tables['axis_redundancy_summary.csv'].columns)
    assert set(tables['axis_conditional_separation_summary.csv']['recommended_pair_action']) <= {'keep_separate','merge_candidate','needs_review'}
    assert {'core_candidate','hold_candidate','audit_only'} & set(tables['axis_classification_summary.csv']['classification'])

def test_committed_docs_are_production_path_audit_artifacts_not_fixture_outputs():
    for name in REQUIRED_FILES:
        assert (DOCS/name).exists(), name
    catalog = pd.read_csv(DOCS/'candidate_axis_catalog.csv')
    assert len(catalog) > 30
    assert REQUIRED_FAMILIES <= set(catalog.axis_family)
    assert catalog.definition.notna().all() and (catalog.definition.str.len() > 0).all()
    assert catalog.source_fields.notna().all() and (catalog.source_fields.str.len() > 0).all()
    assert catalog.uses_distribution_mass.astype(str).str.lower().eq('true').any()
    assert set(catalog.axis_name) != {'resource','information','pressure','exploration','reversibility'}
    assert pd.read_csv(DOCS/'axis_redundancy_summary.csv').shape[0] > len(catalog)
    assert pd.read_csv(DOCS/'axis_conditional_separation_summary.csv').recommended_pair_action.isin(['keep_separate','merge_candidate','needs_review']).all()
    assert not pd.read_csv(DOCS/'axis_external_response_summary.csv').empty
    assert not pd.read_csv(DOCS/'axis_temporal_response_summary.csv').empty
    assert not pd.read_csv(DOCS/'axis_residual_relation_summary.csv').empty
    assert not pd.read_csv(DOCS/'axis_macro_dynamics_preservation_summary.csv').empty
    assert set(pd.read_csv(DOCS/'axis_classification_summary.csv').classification) <= {'core_candidate','merge_candidate','hold_candidate','audit_only','reject_candidate'}
    text=(DOCS/'results.md').read_text()
    for phrase in ['does not select final Core dimensions','does not compress the full distribution into a fixed 5-axis Core','does not use PCA as the primary log basis','Artifact provenance','Full distribution source: yes','PCA used as primary log basis: no','Fixed 5-axis Core selected: no','Final Core dimensions selected: no','Axis classifications are final decisions: no']:
        assert phrase in text
    assert 'production PseudoReality path' in text and 'fixture' not in text.lower()
