"""Internal TLV helpers: strict parsing, encoding and path handling.

Mirrors ``packages/deshiqr/src/core/tlv.ts`` exactly. Bangla QR payloads are
EMVCo-style TLV strings: ``TT LL VV…`` with two decimal digits for both tag and
length. Templates carry a nested TLV value. Parsing is strict: malformed input
raises :class:`~deshiqr.errors.DeshiQrError` with code ``BAD_TLV`` instead of
silently truncating.

The standard (EMVCo/NPSB) counts ``LL`` in **UTF-8 bytes**, so a Bangla
character is three units. Some producers count characters instead; the parser
auto-detects which unit a payload uses by parsing and re-encoding it (bytes
first, then characters) and rejects a payload that round-trips in neither.

This module is internal. Only the two public functions are supported API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Literal, Optional

from .errors import DeshiQrError

#: How ``LL`` lengths are counted: ``"bytes"`` is the EMVCo/NPSB rule (and the
#: default); ``"chars"`` is the legacy per-character count. Both are identical
#: for all-ASCII payloads.
LengthMode = Literal["bytes", "chars"]

LENGTH_MODE_BYTES: LengthMode = "bytes"
LENGTH_MODE_CHARS: LengthMode = "chars"

#: Default length unit for encoding: bytes (identical to chars for ASCII).
DEFAULT_LENGTH_MODE: LengthMode = LENGTH_MODE_BYTES

#: The format allows at most 99 units per field value (UTF-8 bytes in
#: ``"bytes"`` mode, characters in ``"chars"`` mode).
MAX_VALUE_LENGTH = 99

#: Tag that always holds the checksum, and is always re-sealed after edits.
CRC_TAG = "63"

_TAG_RE = re.compile(r"^[0-9]{2}$")
_LENGTH_RE = re.compile(r"^[0-9]{2}$")


@dataclass
class Field:
    """A single ``TT LL VV…`` field. ``tag`` is always two digits."""

    tag: str
    value: str


@dataclass
class ParsedPayload:
    """A parsed payload level plus the detected length unit."""

    fields: List[Field]
    mode: LengthMode


def normalize(payload: object) -> str:
    """Trim surrounding whitespace; non-string payloads become ``""``."""
    return payload.strip() if isinstance(payload, str) else ""


def is_tag_path(value: object) -> bool:
    """True when ``value`` is a valid tag path such as ``"54"`` or ``"62/01"``."""
    from .fields import TAG_PATH_RE

    return isinstance(value, str) and TAG_PATH_RE.fullmatch(value) is not None


def path_components(path: str) -> List[str]:
    """Split a validated tag path into its two-digit components."""
    return path.split("/")


def is_hex_checksum(value: object) -> bool:
    """True when ``value`` looks like a four-hex-digit checksum."""
    return isinstance(value, str) and re.fullmatch(r"[0-9A-Fa-f]{4}", value) is not None


def byte_length(value: str) -> int:
    """UTF-8 byte length of a string."""
    return len(value.encode("utf-8"))


def value_length(value: str, mode: LengthMode = DEFAULT_LENGTH_MODE) -> int:
    """Length of a value in ``mode``'s unit (bytes by default)."""
    return byte_length(value) if mode == LENGTH_MODE_BYTES else len(value)


def _parse_in_mode(text: str, mode: LengthMode) -> List[Field]:
    """Walk a non-empty payload level in one length mode."""
    if mode == LENGTH_MODE_BYTES:
        data = text.encode("utf-8")
        total = len(data)

        def unit_slice(start: int, end: int) -> str:
            return data[start:end].decode("utf-8", "replace")

    else:
        total = len(text)

        def unit_slice(start: int, end: int) -> str:
            return text[start:end]

    fields: List[Field] = []
    offset = 0

    while offset < total:
        if offset + 4 > total:
            raise DeshiQrError(
                "BAD_TLV",
                "Malformed payload: truncated field at offset {}.".format(offset),
            )

        tag = unit_slice(offset, offset + 2)
        if _TAG_RE.fullmatch(tag) is None:
            raise DeshiQrError(
                "BAD_TLV",
                'Malformed payload: invalid tag "{}" at offset {}.'.format(tag, offset),
                tag,
            )

        raw_length = unit_slice(offset + 2, offset + 4)
        if _LENGTH_RE.fullmatch(raw_length) is None:
            raise DeshiQrError(
                "BAD_TLV",
                'Malformed payload: invalid length "{}" for tag {} at offset {}.'.format(
                    raw_length, tag, offset
                ),
                tag,
            )

        length = int(raw_length)
        value_start = offset + 4
        value_end = value_start + length
        if value_end > total:
            raise DeshiQrError(
                "BAD_TLV",
                "Malformed payload: tag {} claims {} characters but only {} remain.".format(
                    tag, length, total - value_start
                ),
                tag,
            )

        fields.append(Field(tag, unit_slice(value_start, value_end)))
        offset = value_end

    return fields


def parse_with_mode(payload: object) -> ParsedPayload:
    """Parse a payload and detect how its ``LL`` lengths are counted.

    ``"bytes"`` is tried first (the EMVCo/NPSB rule), then ``"chars"`` for
    legacy character-counted producers; the first unit that makes
    ``encode_fields(fields, mode) == payload`` wins. All-ASCII payloads
    round-trip in both units and therefore detect as ``"bytes"``. If neither
    unit round-trips, the first error (the byte attempt's, when there is one) is
    raised, keeping the historical ``BAD_TLV`` behaviour.
    """
    text = normalize(payload)
    if len(text) == 0:
        raise DeshiQrError("EMPTY_PAYLOAD", "The payload is empty.")

    first_error: Optional[DeshiQrError] = None
    for mode in (LENGTH_MODE_BYTES, LENGTH_MODE_CHARS):
        try:
            fields = _parse_in_mode(text, mode)
            if encode_fields(fields, mode) == text:
                return ParsedPayload(fields, mode)
        except DeshiQrError as error:
            if first_error is None:
                first_error = error

    if first_error is not None:
        raise first_error
    raise DeshiQrError("BAD_TLV", "Malformed payload: unrecognised length encoding.")


def detect_length_mode(payload: object) -> LengthMode:
    """Detect only the length unit of a payload level."""
    return parse_with_mode(payload).mode


def parse(payload: object, mode: Optional[LengthMode] = None) -> List[Field]:
    """Parse a TLV string into fields, preserving order.

    Normalizes (trims) the input like the JavaScript implementation; empty input
    raises ``EMPTY_PAYLOAD`` and malformed input raises ``BAD_TLV``. Without
    ``mode`` the length unit is auto-detected (bytes first, then chars).
    """
    text = normalize(payload)
    if len(text) == 0:
        raise DeshiQrError("EMPTY_PAYLOAD", "The payload is empty.")
    if mode is None:
        return parse_with_mode(text).fields
    return _parse_in_mode(text, mode)


def parse_subfields(value: str, mode: Optional[LengthMode] = None) -> List[Field]:
    """Parse a nested template value; an empty value is an empty (valid) template.

    Pass the parent payload's ``mode`` to keep the template in the same length
    unit; without one the unit is auto-detected.
    """
    if len(value) == 0:
        return []
    return parse(value, mode)


def parse_template(value: str, path: str, mode: Optional[LengthMode] = None) -> List[Field]:
    """Parse a template value, raising ``BAD_TLV`` tagged with ``path`` on failure."""
    try:
        return parse_subfields(value, mode)
    except DeshiQrError:
        raise DeshiQrError(
            "BAD_TLV",
            "Malformed payload: tag {} is not a valid TLV template.".format(path),
            path,
        ) from None


def encode_field(field: Field, mode: LengthMode = DEFAULT_LENGTH_MODE) -> str:
    """Encode one field as ``TTLLVV…``; the length unit defaults to UTF-8 bytes."""
    tag = field.tag
    value = field.value
    if not isinstance(tag, str) or _TAG_RE.fullmatch(tag) is None:
        raise DeshiQrError(
            "BAD_TLV",
            'Malformed payload: invalid tag "{}".'.format(tag),
            str(tag),
        )
    if not isinstance(value, str):
        raise DeshiQrError(
            "BAD_VALUE",
            "Value for tag {} must be a string.".format(tag),
            tag,
        )
    length = value_length(value, mode)
    if length > MAX_VALUE_LENGTH:
        raise DeshiQrError(
            "BAD_VALUE",
            "Value for tag {} is longer than {} characters.".format(tag, MAX_VALUE_LENGTH),
            tag,
        )
    return tag + "{:02d}".format(length) + value


def encode_fields(fields: List[Field], mode: LengthMode = DEFAULT_LENGTH_MODE) -> str:
    """Encode a list of fields back into a TLV string; defaults to UTF-8 bytes."""
    return "".join(encode_field(field, mode) for field in fields)


def find_field(fields: List[Field], tag: str) -> Optional[Field]:
    """First field with ``tag``, or ``None``."""
    for field in fields:
        if field.tag == tag:
            return field
    return None


def find_value(fields: List[Field], tag: str) -> Optional[str]:
    """Value of the first field with ``tag``, or ``None``."""
    field = find_field(fields, tag)
    return field.value if field is not None else None


def remove_all(fields: List[Field], tag: str) -> None:
    """Remove every field with ``tag``, in place."""
    fields[:] = [field for field in fields if field.tag != tag]


def insert_sorted(fields: List[Field], field: Field) -> None:
    """Insert ``field`` in ascending numeric tag order at its level."""
    target = int(field.tag)
    for index, existing in enumerate(fields):
        if int(existing.tag) > target:
            fields.insert(index, field)
            return
    fields.append(field)
