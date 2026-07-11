"""Task 3.1f stable-structure extraction implementation."""
from .contract import DEFAULT_CONTRACT, OUTPUT_SUBDIR, load_contract
from .input_freeze import freeze_input
from .models import (
    fit_weighted_frobenius_nmf,
    fit_weighted_kl_nmf,
    fit_weighted_pca,
    match_components,
    normalize_basis_and_activations,
    project_probability_simplex_rows,
    transform_fixed_kl_basis,
)
from .runner import run_smoke
from .stage_bc_run import formal_run_plan, run_plan
from .stage_bc_subsets import grouped_subsets
from .stage_bc_selection_core import representative_runs, select_rank
from .batch import run_stage_bc, run_stage_bc_formal, run_stage_bc_smoke
from .selection_validator import validate_selection
from .validator import validate_smoke

__all__ = [name for name in globals() if not name.startswith("_")]
