"""Error and warning types shared by the two public functions.

The only public surface is ``update(payload, edits, options=None) -> str`` and
``validate(payload, options=None) -> ValidationReport``. Everything a caller needs
to switch on is a stable string code carried by :class:`DeshiQrError` or
:class:`DeshiQrIssue`.
"""

from __future__ import annotations

import warnings as _warnings
from dataclasses import dataclass
from typing import Optional

#: Stable error codes. ``update`` raises them, ``validate`` returns them.
ERROR_CODES = (
    "EMPTY_PAYLOAD",
    "UNSUPPORTED",
    "BAD_TLV",
    "MISSING_FIELD",
    "CHECKSUM_MISMATCH",
    "DUPLICATE_TAG",
    "BAD_AMOUNT",
    "BAD_TAG",
    "BAD_VALUE",
)

#: Stable warning codes. Returned by ``validate`` and surfaced by ``update``.
WARNING_CODES = (
    "MISSING_TAG",
    "UNKNOWN_TAG",
    "BAD_FIELD_VALUE",
    "FIELD_TOO_LONG",
    "UNKNOWN_CURRENCY",
    "NON_BD_COUNTRY",
    "UNKNOWN_INSTITUTION",
    "UNKNOWN_MCC",
    "STATIC_WITH_AMOUNT",
    "DYNAMIC_WITHOUT_AMOUNT",
    "RISKY_EDIT",
)


class DeshiQrError(Exception):
    """Every failure raised by :func:`deshiqr.update`.

    ``code`` is a stable, machine-readable string (see :data:`ERROR_CODES`),
    ``message`` is human-readable and identical to the JavaScript package, and
    ``tag`` is the offending tag or tag path when there is one.
    """

    #: ``"DeshiQrError"``, mirroring the JavaScript class name.
    name = "DeshiQrError"

    code: str
    message: str
    tag: Optional[str]

    def __init__(self, code: str, message: str, tag: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.tag = tag

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "DeshiQrError({!r}, {!r}, tag={!r})".format(self.code, self.message, self.tag)


@dataclass(frozen=False)
class DeshiQrIssue:
    """One validation problem: a stable ``code``, a message and an optional ``tag``.

    ``tag`` is a top-level tag (``"59"``) or a tag path (``"62/01"``) when the
    problem belongs to a specific field. Warning suppression matches it exactly.
    """

    code: str
    message: str
    tag: Optional[str] = None


class DeshiQrWarning(UserWarning):
    """Category used by the default warning sink of :func:`deshiqr.update`."""

    name = "DeshiQrWarning"


def emit_warning(issue: DeshiQrIssue) -> None:
    """Default warning sink: route one issue through the stdlib ``warnings`` module.

    JavaScript's default is ``console.warn``; Python's stdlib equivalent is
    ``warnings.warn`` so callers keep control through warning filters. Pass
    ``onWarning``/``on_warning`` to :func:`deshiqr.update` to redirect.
    """

    _warnings.warn(issue.message, DeshiQrWarning, stacklevel=3)
