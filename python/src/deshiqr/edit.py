"""``update(payload, edits, options=None) -> str``.

Load a payload, apply tag/alias edits, re-seal the checksum, validate the result
and return the new payload. Warnings are surfaced according to ``options``;
errors are raised as :class:`~deshiqr.errors.DeshiQrError`.

Mirrors ``packages/deshiqr/src/core/edit.ts`` exactly: input-check order, edit
resolution (aliases first, tag paths sorted by depth then lexicographically),
amount formatting, nested-edit rules, warning order and message strings.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable, List, Mapping, Optional, Sequence, Tuple

from .crc import crc16
from .errors import DeshiQrError, DeshiQrIssue, emit_warning
from .fields import (
    ALIASES,
    IDENTITY_PATHS,
    MAX_AMOUNT_DECIMAL,
    MAX_PAYLOAD_LENGTH,
)
from .tlv import (
    CRC_TAG,
    MAX_VALUE_LENGTH,
    Field,
    LengthMode,
    ParsedPayload,
    encode_fields,
    find_field,
    insert_sorted,
    is_hex_checksum,
    is_tag_path,
    normalize,
    parse_subfields,
    parse_with_mode,
    path_components,
    remove_all,
    value_length,
)
from .validate import (
    WarningsOption,
    assert_no_duplicate_tags,
    coerce_warnings,
    collect,
    visible_warnings,
)

__all__ = ["UpdateOptions", "update"]

RISKY_EDIT_MESSAGE = "Editing the account/name can mislead payers; only edit what you own."

AMOUNT_INPUT_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")

_MISSING_AMOUNT_MESSAGE = "Amount must be a number or a numeric string."
_ZERO_AMOUNT_MESSAGE = "Amount must be greater than zero."
_MAX_AMOUNT_MESSAGE = "Amount must not exceed 99999999.99."
_AMOUNT_DECIMALS_MESSAGE = "Amount must have at most two decimal places."
_EDITS_MESSAGE = "Edits must be an object of tag paths/aliases."
_BAD_VALUE_MESSAGE = "Value for tag {} must be a string, a number or null."
_TOO_LONG_MESSAGE = "Value for tag {} is longer than 99 characters."


@dataclass
class UpdateOptions:
    """Options for :func:`update`.

    ``warnings`` mirrors the JavaScript ``UpdateOptions.warnings``: ``True``
    shows every warning, ``False`` hides them, and a list of tag/path strings
    suppresses warnings whose ``tag`` matches exactly.

    ``on_warning`` receives each visible :class:`~deshiqr.errors.DeshiQrIssue`
    (the JavaScript ``onWarning``). When omitted, issues go through the standard
    library ``warnings`` module (like ``console.warn`` in JavaScript).
    """

    warnings: WarningsOption = True
    on_warning: Optional[Callable[[DeshiQrIssue], None]] = None


def _coerce_update_options(options: object) -> UpdateOptions:
    if options is None:
        return UpdateOptions()
    if isinstance(options, UpdateOptions):
        return UpdateOptions(
            warnings=coerce_warnings(options.warnings),
            on_warning=options.on_warning,
        )
    if isinstance(options, Mapping):
        warnings_option = coerce_warnings(options.get("warnings", True))
        callback = options.get("onWarning", options.get("on_warning"))
        if callback is not None and not callable(callback):
            raise TypeError("onWarning must be callable or None")
        return UpdateOptions(warnings=warnings_option, on_warning=callback)
    raise TypeError("options must be an UpdateOptions instance, a dict or None")


def _js_number_string(value: float) -> str:
    """Render a finite Python float roughly the way JavaScript's ``String()`` does."""
    if value.is_integer() and abs(value) < 1e21:
        return str(int(value))
    text = repr(value)
    if "e" in text or "E" in text:
        mantissa, exponent = re.split("[eE]", text)
        sign = exponent[0] if exponent and exponent[0] in "+-" else "+"
        digits = exponent[1:] if exponent and exponent[0] in "+-" else exponent
        digits = digits.lstrip("0") or "0"
        return "{}e{}{}".format(mantissa, sign, digits)
    return text


def _decimal_places(text: str) -> int:
    dot = text.find(".")
    return 0 if dot == -1 else len(text) - dot - 1


def _bad_amount(message: str) -> DeshiQrError:
    return DeshiQrError("BAD_AMOUNT", message, "54")


def _format_amount(raw: object) -> str:
    """``500`` / ``"500"`` / ``"1.5"`` → ``"500.00"`` / ``"500.00"`` / ``"1.50"``."""
    if isinstance(raw, bool):
        raise DeshiQrError("BAD_VALUE", _BAD_VALUE_MESSAGE.format("54"), "54")
    if isinstance(raw, int):
        if raw <= 0:
            raise _bad_amount(_ZERO_AMOUNT_MESSAGE)
        if raw > MAX_AMOUNT_DECIMAL:
            raise _bad_amount(_MAX_AMOUNT_MESSAGE)
        text = str(raw)
    elif isinstance(raw, float):
        if not math.isfinite(raw):
            raise _bad_amount(_MISSING_AMOUNT_MESSAGE)
        if raw <= 0:
            raise _bad_amount(_ZERO_AMOUNT_MESSAGE)
        if raw > MAX_AMOUNT_DECIMAL:
            raise _bad_amount(_MAX_AMOUNT_MESSAGE)
        text = _js_number_string(raw)
    elif isinstance(raw, str):
        text = raw
    else:
        raise DeshiQrError("BAD_VALUE", _BAD_VALUE_MESSAGE.format("54"), "54")

    if AMOUNT_INPUT_RE.fullmatch(text) is None:
        raise _bad_amount(_MISSING_AMOUNT_MESSAGE)
    try:
        numeric = Decimal(text)
    except InvalidOperation:
        raise _bad_amount(_MISSING_AMOUNT_MESSAGE) from None
    if not numeric.is_finite():
        raise _bad_amount(_MISSING_AMOUNT_MESSAGE)
    if numeric <= 0:
        raise _bad_amount(_ZERO_AMOUNT_MESSAGE)
    if numeric > MAX_AMOUNT_DECIMAL:
        raise _bad_amount(_MAX_AMOUNT_MESSAGE)
    if _decimal_places(text) > 2:
        raise _bad_amount(_AMOUNT_DECIMALS_MESSAGE)

    whole_part, _, fraction_part = text.partition(".")
    whole = whole_part.lstrip("0") or "0"
    fraction = (fraction_part + "00")[:2]
    return whole + "." + fraction


def _coerce_value(path: str, raw: object) -> Optional[str]:
    """Turn an edit value into its encoded form; ``None`` means remove."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise DeshiQrError("BAD_VALUE", _BAD_VALUE_MESSAGE.format(path), path)
    if isinstance(raw, int):
        return _format_amount(raw) if path == "54" else str(raw)
    if isinstance(raw, float):
        if not math.isfinite(raw):
            raise DeshiQrError("BAD_VALUE", _BAD_VALUE_MESSAGE.format(path), path)
        return _format_amount(raw) if path == "54" else _js_number_string(raw)
    if isinstance(raw, str):
        return _format_amount(raw) if path == "54" else raw
    raise DeshiQrError("BAD_VALUE", _BAD_VALUE_MESSAGE.format(path), path)


def _bad_tag_invalid(key: str) -> DeshiQrError:
    return DeshiQrError("BAD_TAG", 'Invalid tag path "{}".'.format(key), key)


def _bad_parent(path: str) -> DeshiQrError:
    return DeshiQrError(
        "BAD_TAG",
        "Tag {} has a missing or invalid parent template.".format(path),
        path,
    )


def _too_long(path: str) -> DeshiQrError:
    return DeshiQrError("BAD_VALUE", _TOO_LONG_MESSAGE.format(path), path)


def _depth(path: str) -> int:
    return path.count("/")


def _resolve_edits(edits: object) -> Tuple[List[Tuple[str, Optional[str]]], List[Tuple[str, Optional[str]]]]:
    """Resolve aliases and tag paths; coerce values in insertion order.

    Returns ``(alias_edits, tag_path_edits)``. Alias edits overridden by a tag
    path for the same target are dropped (the tag path wins), and tag-path edits
    are sorted by depth then lexicographically.
    """
    alias_edits: List[Tuple[str, Optional[str]]] = []
    tag_path_edits: List[Tuple[str, Optional[str]]] = []

    if edits is not None:
        if not isinstance(edits, Mapping):
            raise DeshiQrError("BAD_VALUE", _EDITS_MESSAGE)

        for raw_key, raw_value in edits.items():
            if not isinstance(raw_key, str):
                raise _bad_tag_invalid(str(raw_key))
            key = raw_key
            is_path = is_tag_path(key)
            path = key if is_path else ALIASES.get(key)
            if path is None:
                raise _bad_tag_invalid(key)
            if path == CRC_TAG or path.startswith(CRC_TAG + "/"):
                raise DeshiQrError(
                    "BAD_TAG",
                    "Tag 63 is the checksum and cannot be edited.",
                    CRC_TAG,
                )
            edit = (path, _coerce_value(path, raw_value))
            if is_path:
                tag_path_edits.append(edit)
            else:
                alias_edits.append(edit)

    targets = set(path for path, _ in tag_path_edits)
    alias_edits = [edit for edit in alias_edits if edit[0] not in targets]
    tag_path_edits.sort(key=lambda edit: (_depth(edit[0]), edit[0]))
    return alias_edits, tag_path_edits


def _apply_at(
    fields: List[Field],
    segments: List[str],
    full_path: str,
    value: Optional[str],
    mode: LengthMode,
) -> None:
    """Apply one edit at the first ``segments[0]`` field, mirroring ``applyAt``."""
    head = segments[0]
    rest = segments[1:]
    index = -1
    for position, field in enumerate(fields):
        if field.tag == head:
            index = position
            break

    if len(rest) == 0:
        if value is None:
            if index != -1:
                remove_all(fields, head)
            return
        if value_length(value, mode) > MAX_VALUE_LENGTH:
            raise _too_long(full_path)
        if index != -1:
            fields[index] = Field(head, value)
        else:
            insert_sorted(fields, Field(head, value))
        return

    parent = fields[index] if index != -1 else None
    if parent is None:
        raise _bad_parent(full_path)

    try:
        children = parse_subfields(parent.value, mode)
    except DeshiQrError:
        raise _bad_parent(full_path) from None

    _apply_at(children, rest, full_path, value, mode)

    if len(children) == 0:
        del fields[index]
        return

    encoded = encode_fields(children, mode)
    if value_length(encoded, mode) > MAX_VALUE_LENGTH:
        raise _too_long(full_path)
    fields[index] = Field(head, encoded)


def _check_input(text: str) -> ParsedPayload:
    """Validate the payload before editing, raising the documented input errors.

    Returns the parsed fields together with the detected length unit; the unit
    is reused for every nested parse and for re-encoding the result.
    """
    if len(text) == 0:
        raise DeshiQrError("EMPTY_PAYLOAD", "The payload is empty.")
    if len(text) > MAX_PAYLOAD_LENGTH:
        raise DeshiQrError(
            "UNSUPPORTED", "The payload is longer than 4096 characters."
        )

    parsed = parse_with_mode(text)
    fields = parsed.fields

    last = fields[-1] if fields else None
    if last is None or last.tag != CRC_TAG:
        raise DeshiQrError(
            "MISSING_FIELD",
            "The payload does not end with a checksum (tag 63).",
            CRC_TAG,
        )
    if not is_hex_checksum(last.value):
        raise DeshiQrError(
            "BAD_TLV",
            "The checksum must be four hexadecimal characters.",
            CRC_TAG,
        )
    if crc16(text[:-4]) != last.value.upper():
        raise DeshiQrError("CHECKSUM_MISMATCH", "The checksum does not match.", CRC_TAG)

    assert_no_duplicate_tags(fields, parsed.mode)
    return parsed


def _set_top_level(fields: List[Field], tag: str, value: str) -> None:
    for index, field in enumerate(fields):
        if field.tag == tag:
            fields[index] = Field(tag, value)
            return
    insert_sorted(fields, Field(tag, value))


def _risky_warnings(edited_paths: Sequence[str]) -> List[DeshiQrIssue]:
    """``RISKY_EDIT`` warnings, one per edited identity/account path."""
    return [
        DeshiQrIssue("RISKY_EDIT", RISKY_EDIT_MESSAGE, path)
        for path in sorted(set(edited_paths))
        if path in IDENTITY_PATHS
    ]


def update(
    payload: object,
    edits: object = None,
    options: object = None,
) -> str:
    """Apply ``edits`` to a Bangla QR payload and return the new payload.

    ``edits`` maps named aliases (``amount``, ``name``, …) or numeric tag paths
    (``"54"``, ``"62/01"``, …) to strings, numbers or ``None`` (removal). Aliases
    are applied first so a tag path for the same target wins. Tag 63 is never
    editable: the checksum is dropped and re-sealed automatically.

    Field lengths may be UTF-8 byte counts (the EMVCo/NPSB rule) or legacy
    character counts; the unit is auto-detected and the result is re-encoded in
    the same unit, so non-ASCII (Bangla) payloads round-trip either way.

    Raises :class:`~deshiqr.errors.DeshiQrError` for invalid input, invalid
    edits, or a result that fails validation. Warnings never block the edit;
    they are surfaced according to ``options``.
    """
    resolved = _coerce_update_options(options)

    # ---- input checks (throw, in this order) ------------------------------
    text = normalize(payload)
    parsed = _check_input(text)
    fields = parsed.fields
    mode = parsed.mode

    # ---- apply edits -------------------------------------------------------
    alias_edits, tag_path_edits = _resolve_edits(edits)
    working = [field for field in fields if field.tag != CRC_TAG]

    for path, value in alias_edits:
        _apply_at(working, path_components(path), path, value, mode)
    for path, value in tag_path_edits:
        _apply_at(working, path_components(path), path, value, mode)

    # ---- point of initiation follows the amount ---------------------------
    edited = alias_edits + tag_path_edits
    touched54 = any(path == "54" for path, _ in edited)
    touched01 = any(path == "01" for path, _ in edited)
    if touched54 and not touched01:
        has_amount = find_field(working, "54") is not None
        _set_top_level(working, "01", "12" if has_amount else "11")

    # ---- re-seal (same length unit as the input) --------------------------
    body = encode_fields(working, mode) + "6304"
    result = body + crc16(body)

    # ---- validate the result: errors throw, warnings are surfaced ---------
    report = collect(result)
    if report.errors:
        first = report.errors[0]
        raise DeshiQrError(first.code, first.message, first.tag)

    edited_paths = [path for path, _ in edited]
    warnings = _risky_warnings(edited_paths) + report.warnings

    callback = resolved.on_warning or emit_warning
    for issue in visible_warnings(warnings, resolved.warnings):
        callback(issue)

    return result
