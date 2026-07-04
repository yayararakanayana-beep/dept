"""Action policy package for FullSpec runner RC1.

This package separates legacy diagnostic/compatibility policies from the
FullSpec primary upper-pressure reception policy introduced by the action
module upper-pressure reception split work.
"""

from .diagnostic_compat_policy import (
    DIAGNOSTIC_COMPAT_POLICY_PROFILE,
    DiagnosticCompatPolicy,
)

__all__ = [
    "DIAGNOSTIC_COMPAT_POLICY_PROFILE",
    "DiagnosticCompatPolicy",
]
