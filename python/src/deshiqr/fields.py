"""Field table, known values and syntax rules for Bangla QR payloads.

Mirrors ``packages/deshiqr/src/core/fields.ts`` exactly: the field table is the
single source of truth for both language implementations, and
:func:`field_warnings` is a line-for-line port of the JavaScript
``fieldWarnings`` so validation output is identical.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Pattern, Tuple

from .errors import DeshiQrIssue

#: Named aliases accepted as ``edits`` keys, mapped to their tag path.
ALIASES: Dict[str, str] = {
    "amount": "54",
    "currency": "53",
    "country": "58",
    "mcc": "52",
    "name": "59",
    "city": "60",
    "reference": "62/01",
    "customerLabel": "62/06",
    "account": "26/03",
    "institution": "26/00",
}

#: Tags whose absence produces a ``MISSING_TAG`` warning, in this order.
RECOMMENDED_TAGS: Tuple[str, ...] = ("00", "01", "59")

#: Templates whose value is itself TLV and is parsed/validated as such.
PARSED_TEMPLATE_TAGS: Tuple[str, ...] = ("26", "62")

#: Opaque token templates: preserved verbatim, never parsed or validated.
OPAQUE_TAGS: Tuple[str, ...] = ("80", "81")

#: Every template tag (parsed and opaque). Used for empty-template cleanup.
ALL_TEMPLATE_TAGS: Tuple[str, ...] = ("26", "62", "80", "81")

#: Editing these fields is risky: the account/name is what payers see.
IDENTITY_PATHS: Tuple[str, ...] = ("26/00", "26/03", "59")

#: Known ISO-4217 numeric currency codes.
KNOWN_CURRENCIES: Tuple[str, ...] = ("050", "356", "764", "840", "978")

#: Known merchant category codes.
KNOWN_MCCS: Tuple[str, ...] = ("5411", "6016", "5999")

#: Known, verified institution AIDs (tag 26/00).
KNOWN_INSTITUTIONS: Tuple[str, ...] = ("bd.org.bb.npsb",)

#: Point-of-initiation values.
STATIC_INITIATION = "11"
DYNAMIC_INITIATION = "12"

#: Payloads longer than this are rejected as ``UNSUPPORTED``.
MAX_PAYLOAD_LENGTH = 4096

#: The largest amount tag 54 may carry.
MAX_AMOUNT = 99_999_999.99
MAX_AMOUNT_TEXT = "99999999.99"
MAX_AMOUNT_DECIMAL = Decimal(MAX_AMOUNT_TEXT)

#: Tag 54 must be a decimal with exactly two decimal places (warning syntax).
AMOUNT_FIELD_RE = re.compile(r"^[0-9]{1,8}\.[0-9]{2}$")

#: Tag path: two digits, optionally nested with ``/`` segments.
TAG_PATH_RE = re.compile(r"^[0-9]{2}(?:/[0-9]{2})*$")


@dataclass(frozen=True)
class FieldSpec:
    """Documented syntax for one tag/path."""

    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[Pattern[str]] = None


#: The documented field table. A path that is not here is an ``UNKNOWN_TAG``
#: warning (the tag is still allowed and preserved).
FIELD_SPECS: Dict[str, FieldSpec] = {
    "00": FieldSpec(pattern=re.compile(r"^01$")),
    "01": FieldSpec(pattern=re.compile(r"^(?:11|12)$")),
    "26": FieldSpec(),
    "26/00": FieldSpec(max_length=32, pattern=re.compile(r"^[\x20-\x7e]*$")),
    "26/01": FieldSpec(pattern=re.compile(r"^[0-9]{2}$")),
    "26/02": FieldSpec(pattern=re.compile(r"^[0-9]{4}$")),
    "26/03": FieldSpec(4, 34, re.compile(r"^[0-9A-Za-z]+$")),
    "52": FieldSpec(pattern=re.compile(r"^[0-9]{4}$")),
    "53": FieldSpec(pattern=re.compile(r"^[0-9]{3}$")),
    "54": FieldSpec(),
    "58": FieldSpec(pattern=re.compile(r"^[A-Za-z]{2}$")),
    "59": FieldSpec(1, 25),
    "60": FieldSpec(1, 15),
    "62": FieldSpec(),
    "62/01": FieldSpec(1, 32, re.compile(r"^[\x20-\x7e]+$")),
    "62/06": FieldSpec(),
    "80": FieldSpec(),
    "80/00": FieldSpec(),
    "80/01": FieldSpec(),
    "81": FieldSpec(),
    "81/00": FieldSpec(),
    "81/01": FieldSpec(),
    "63": FieldSpec(pattern=re.compile(r"^[0-9A-Fa-f]{4}$")),
}

#: Fields where a too-long value is ``FIELD_TOO_LONG`` rather than a syntax
#: error. Fixed-width fields report the shape mismatch as ``BAD_FIELD_VALUE``.
LENGTH_REPORTED_PATHS = frozenset(("26/00", "59", "60", "62/01", "26/03"))


def _issue(code: str, message: str, tag: Optional[str] = None) -> DeshiQrIssue:
    return DeshiQrIssue(code, message, tag)


def _bad_value(path: str, value: str) -> DeshiQrIssue:
    return _issue(
        "BAD_FIELD_VALUE", 'Unexpected value "{}" for tag {}.'.format(value, path), path
    )


def _too_long(path: str, limit: int) -> DeshiQrIssue:
    return _issue(
        "FIELD_TOO_LONG",
        "Value for tag {} is longer than {} characters.".format(path, limit),
        path,
    )


def field_warnings(path: str, value: str) -> List[DeshiQrIssue]:
    """Warning-level checks for one documented field, mirroring the JS port.

    Length problems are reported before shape problems, and "known value"
    warnings are only reported when the syntax itself is fine.
    """
    spec = FIELD_SPECS.get(path)
    if spec is None:
        return [_issue("UNKNOWN_TAG", "Unknown tag {}.".format(path), path)]

    if path == "54":
        if AMOUNT_FIELD_RE.fullmatch(value) is None:
            return [_bad_value(path, value)]
        try:
            amount = Decimal(value)
        except Exception:  # pragma: no cover - regex already guarantees a number
            return [_bad_value(path, value)]
        if amount <= 0 or amount > MAX_AMOUNT_DECIMAL:
            return [_bad_value(path, value)]
        return []

    if (
        path in LENGTH_REPORTED_PATHS
        and spec.max_length is not None
        and len(value) > spec.max_length
    ):
        return [_too_long(path, spec.max_length)]
    if spec.min_length is not None and len(value) < spec.min_length:
        return [_bad_value(path, value)]
    if spec.pattern is not None and spec.pattern.fullmatch(value) is None:
        return [_bad_value(path, value)]

    if path == "53" and value not in KNOWN_CURRENCIES:
        return [_issue("UNKNOWN_CURRENCY", 'Unknown currency "{}".'.format(value), path)]
    if path == "58" and value != "BD":
        return [_issue("NON_BD_COUNTRY", 'Country is "{}", not "BD".'.format(value), path)]
    if path == "52" and value not in KNOWN_MCCS:
        return [
            _issue("UNKNOWN_MCC", 'Unknown merchant category code "{}".'.format(value), path)
        ]
    if path == "26/00" and value not in KNOWN_INSTITUTIONS:
        return [
            _issue("UNKNOWN_INSTITUTION", 'Unverified institution "{}".'.format(value), path)
        ]
    return []
