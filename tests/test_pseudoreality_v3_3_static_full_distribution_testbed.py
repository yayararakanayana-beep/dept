from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest

from scripts import pseudoreality_v3_3_static_full_distribution_testbed as t
from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World


def test_distribution_contract_world_mass():
    w, mass = t.run_world(0, (0, 0, 0, 0, 0, 0), 1)
    assert w.config.n_bins == 5
    assert mass.shape == (3125,)
    assert mass.dtype == np.float64
    assert np.isfinite(mass).all()
    assert mass.min() >= -1e-12
    assert abs(float(mass.sum()) - 1.0) <= 1e-8


def test_external_vector_ranges_and_keys():
    assert len(t.EXTERNAL_COLUMNS) == 6
    t.validate_external_values((-1, 1, 0, 0, 0, 0))
    t.validate_external_values((1, -1, 1, 1, 1, 1))
    for bad in [(0,0,-.1,0,0,0),(0,0,0,-.1,0,0),(0,0,0,0,-.1,0),(0,0,0,0,0,-.1),(1.1,0,0,0,0,0),(0,0,1.1,0,0,0)]:
        with pytest.raises(ValueError): t.validate_external_values(bad)
    update=t.all_external_update((0,0,0,0,0,0))
    assert set(update)==set(t.EXTERNAL_COLUMNS)
    assert all(v == 0.0 for v in update.values())


def test_sobol_determinism_and_formal_counts():
    assert np.allclose(t.sobol_points(3, 4, 3101), t.sobol_points(3, 4, 3101))
    assert not np.allclose(t.sobol_points(3, 4, 3101), t.sobol_points(3, 4, 3102))
    fit,_=t.make_sobol_vectors("fit",3101,{"1":4,"2":2,"3":2,"4":1,"5":1,"6":32})
    val,_=t.make_sobol_vectors("validation",3102,{"1":2,"2":1,"3":1,"4":1,"5":1,"6":16})
    assert len(fit)==147
    assert len(val)==84
    hold,_=t.boundary_vectors("holdout",1)
    assert len(hold)==64
    assert len(hold)+16==80
    keys={t.rounded_key(v.values) for v in fit+val+hold+[t.base_vector("fit",999),t.base_vector("validation",999),t.base_vector("holdout",999)]}
    assert len(t.adaptive_candidates(keys))==178


def test_split_and_base_separation():
    fit,_=t.make_sobol_vectors("fit",3101,{"1":1,"2":0,"3":0,"4":0,"5":0,"6":1})
    vecs=fit+[t.base_vector("fit",99),t.base_vector("validation",1),t.base_vector("holdout",1)]
    assert len({v.external_vector_id for v in vecs}) == len(vecs)
    for v in vecs:
        actual=sum(float(x)!=0.0 for x in v.values)
        assert actual == v.active_factor_count
        assert (actual == 0) == v.is_base_vector


def test_terrain_fields_present_and_exclusions_absent():
    w=DistributionTerrainV322World(DistributionTerrainV322Config(seed=0,n_bins=5))
    assert len(t.TERRAIN_FIELDS)==22
    for f in t.TERRAIN_FIELDS:
        arr=np.asarray(getattr(w,f), dtype=np.float32).reshape(-1)
        assert arr.shape == (3125,)
        assert arr.dtype == np.float32
        assert np.isfinite(arr).all()
    assert not any(f in t.TERRAIN_FIELDS for f in t.EXCLUDED_TRANSITION_FIELDS)


def test_smoke_artifacts_and_separation(tmp_path):
    out=t.build("smoke", tmp_path)
    md=pd.read_csv(out/"snapshot_metadata.csv")
    disc=pd.read_csv(out/"discovery_manifest.csv")
    pairs=pd.read_csv(out/"matched_pairs.csv")
    mass=np.load(out/"mass_matrix.npy")
    terr=np.load(out/"terrain_reference.npz")
    assert list(disc.columns)==["matrix_row_index","snapshot_id","dataset_split","analysis_weight"]
    forbidden=set(t.EXTERNAL_COLUMNS+["source_step","seed","distribution_group"]+t.TERRAIN_FIELDS)
    assert forbidden.isdisjoint(disc.columns)
    assert "combined_full" not in set(md["distribution_group"])
    assert mass.shape[0]==len(md)
    assert mass.shape[1]==3125
    assert list(md["matrix_row_index"])==list(range(len(md)))
    for f in t.TERRAIN_FIELDS:
        assert terr[f].shape==(len(md),3125)
        assert terr[f].dtype==np.float32
    assert set(pairs["pair_quality"]) == {"exact"}
    manifest=json.loads((out/"artifact_manifest.json").read_text())
    names={r["relative_path"] for r in manifest}
    required={"external_vectors.csv","snapshot_metadata.csv","discovery_manifest.csv","matched_pairs.csv","cell_coordinates.csv","terrain_field_catalog.csv","mass_matrix.npy","terrain_reference.npz","coverage_summary.csv","coverage_additions.csv","quality_checks.json","results.md"}
    assert required.issubset(names)
    checks=json.loads((out/"quality_checks.json").read_text())
    for key in ["axis_count_is_5","n_bins_is_5","cell_count_is_3125","mass_shape_valid","mass_finite","mass_nonnegative","mass_sum_valid","external_ranges_valid","all_external_keys_present","base_external_separation_valid","discovery_manifest_has_no_forbidden_columns","terrain_fields_present","terrain_shapes_valid","transition_fields_absent","matched_pairs_exact","combined_full_not_stored","split_vector_sets_disjoint","sobol_deterministic","adaptive_count_is_32"]:
        assert key in checks
