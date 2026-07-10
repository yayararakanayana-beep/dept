"""Task 3.1e implementation package."""
from .core import (
    DEFAULT_CONFIG, EXCLUDED_TRANSITION_FIELDS, EXTERNAL_COLUMNS, JS_EPSILON,
    MASS_TOLERANCE, NEGATIVE_TOLERANCE, OUT_SUBDIR, RANGES, TERRAIN_FIELDS,
    AdaptiveCandidate, ExternalVector, SelectedCandidate, all_external_update,
    build_adaptive_pool, build_initial_vectors, load_config, masks_by_count,
    rounded_key, sobol_points, validate_external_values, vector_from_active,
)
from .runtime import capture_run, canonical_mass, js_distances, select_adaptive_candidates, validate_mass
from .generator import build, main

__all__ = [name for name in globals() if not name.startswith("_")]
