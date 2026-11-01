"""deshiqr — edit any tag in a Bangla QR payload and get the payload back.

Two functions, no state, no network, no QR rendering:

- :func:`update` — apply named-alias or numeric tag-path edits, re-seal the
  checksum, validate the result and return the new payload.
- :func:`validate` — non-throwing, thorough validation with stable codes.

Zero runtime dependencies, standard library only, Python 3.9+.
"""

from __future__ import annotations

from .edit import UpdateOptions, update
from .errors import DeshiQrError, DeshiQrIssue, DeshiQrWarning
from .validate import ValidateOptions, ValidationReport, validate

__version__ = "0.1.0"

__all__ = [
    "update",
    "validate",
    "DeshiQrError",
    "DeshiQrIssue",
    "DeshiQrWarning",
    "ValidationReport",
    "UpdateOptions",
    "ValidateOptions",
]
