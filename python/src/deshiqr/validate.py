"""Non-throwing validation for Bangla QR payloads.

``validate(payload, options=None)`` is the public entry point: it never raises,
collects every problem, and returns a :class:`ValidationReport` whose ``errors``
make ``ok`` false and whose ``warnings`` are advisory. Warning visibility is
controlled by ``options`` (``True``, ``False`` or a list of tag/path strings to
suppress).

Mirrors ``packages/deshiqr/src/core/validate.ts`` exactly, including error and
warning order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence, Union

from .crc import crc16
from .errors import DeshiQrError, DeshiQrIssue
from .fields import (
    DYNAMIC_INITIATION,
    MAX_PAYLOAD_LENGTH,
    OPAQUE_TAGS,
    PARSED_TEMPLATE_TAGS,
    RECOMMENDED_TAGS,
    STATIC_INITIATION,
    field_warnings,
)
from .tlv import (
    CRC_TAG,
    Field,
    LengthMode,
    find_field,
    find_value,
    is_hex_checksum,
    normalize,
    parse_subfields,
    parse_with_mode,
)

__all__ = [
    "DeshiQrIssue",
    "ValidationReport",
    "ValidateOptions",
    "validate",
]

# Warning suppression: True = all, False = none, sequence = suppress these tags.
WarningsOption = Union[bool, Sequence[str]]


@dataclass
class ValidateOptions:
    """Options for :func:`validate`.

    ``warnings`` mirrors the JavaScript ``ValidateOptions.warnings``: ``True``
    shows every warning, ``False`` hides them, and a list of tag/path strings
    suppresses warnings whose ``tag`` matches exactly. Errors are always kept.
    """

    warnings: WarningsOption = True


@dataclass
class ValidationReport:
    """Result of :func:`validate`.

    ``ok`` is true when ``errors`` is empty; ``warnings`` never affect it.
    """

    ok: bool
    errors: List[DeshiQrIssue]
    warnings: List[DeshiQrIssue]


def coerce_warnings(value: object) -> WarningsOption:
    """Normalize the ``warnings`` option value to ``bool`` or a tuple of strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item) for item in value)
    raise TypeError("warnings must be a boolean or a list of tag paths")


def visible_warnings(
    warnings: Sequence[DeshiQrIssue], option: WarningsOption
) -> List[DeshiQrIssue]:
    """Apply the ``warnings`` option to a list of issues."""
    if option is True:
        return list(warnings)
    if option is False:
        return []
    suppressed = set(option)
    return [issue for issue in warnings if issue.tag not in suppressed]


def _coerce_validate_options(options: object) -> ValidateOptions:
    if options is None:
        return ValidateOptions()
    if isinstance(options, ValidateOptions):
        return options
    if isinstance(options, Mapping):
        return ValidateOptions(warnings=coerce_warnings(options.get("warnings", True)))
    raise TypeError("options must be a ValidateOptions instance, a dict or None")


def _issue(code: str, message: str, tag: Optional[str] = None) -> DeshiQrIssue:
    return DeshiQrIssue(code, message, tag)


def _parse_templates(fields: List[Field], mode: LengthMode = "bytes") -> dict:
    """Parse the documented templates once; ``None`` means invalid TLV."""
    parsed = {}
    for tag in PARSED_TEMPLATE_TAGS:
        field = find_field(fields, tag)
        if field is None:
            continue
        try:
            parsed[tag] = parse_subfields(field.value, mode)
        except DeshiQrError:
            parsed[tag] = None
    return parsed


def _duplicate_issues(fields: List[Field], parsed: dict) -> List[DeshiQrIssue]:
    """``DUPLICATE_TAG`` errors, in canonical order: top level, then 26, then 62."""
    issues: List[DeshiQrIssue] = []
    seen_top = set()
    for field in fields:
        if field.tag in seen_top:
            issues.append(
                _issue(
                    "DUPLICATE_TAG",
                    "Tag {} appears more than once.".format(field.tag),
                    field.tag,
                )
            )
        seen_top.add(field.tag)

    for tag in PARSED_TEMPLATE_TAGS:
        children = parsed.get(tag)
        if children is None:
            continue
        seen_nested = set()
        for child in children:
            path = tag + "/" + child.tag
            if child.tag in seen_nested:
                issues.append(
                    _issue(
                        "DUPLICATE_TAG",
                        "Tag {} appears more than once.".format(path),
                        path,
                    )
                )
            seen_nested.add(child.tag)
    return issues


def assert_no_duplicate_tags(fields: List[Field], mode: LengthMode = "bytes") -> None:
    """Raise the first ``DUPLICATE_TAG`` error, in the same order as ``validate``."""
    issues = _duplicate_issues(fields, _parse_templates(fields, mode))
    if issues:
        first = issues[0]
        raise DeshiQrError(first.code, first.message, first.tag)


def collect(payload: object) -> ValidationReport:
    """Collect an unfiltered report for ``payload`` (internal)."""
    errors: List[DeshiQrIssue] = []
    warnings: List[DeshiQrIssue] = []

    text = normalize(payload)
    if len(text) == 0:
        return ValidationReport(
            False, [_issue("EMPTY_PAYLOAD", "The payload is empty.")], []
        )
    if len(text) > MAX_PAYLOAD_LENGTH:
        return ValidationReport(
            False,
            [_issue("UNSUPPORTED", "The payload is longer than 4096 characters.")],
            [],
        )

    try:
        parsed_payload = parse_with_mode(text)
        fields = parsed_payload.fields
        mode = parsed_payload.mode
    except DeshiQrError as error:
        return ValidationReport(False, [_issue(error.code, error.message, error.tag)], [])

    # ---- checksum ---------------------------------------------------------
    last = fields[-1] if fields else None
    if last is None or last.tag != CRC_TAG:
        errors.append(
            _issue(
                "MISSING_FIELD",
                "The payload does not end with a checksum (tag 63).",
                CRC_TAG,
            )
        )
    elif not is_hex_checksum(last.value):
        errors.append(
            _issue(
                "BAD_TLV",
                "The checksum must be four hexadecimal characters.",
                CRC_TAG,
            )
        )
    elif crc16(text[:-4]) != last.value.upper():
        errors.append(_issue("CHECKSUM_MISMATCH", "The checksum does not match.", CRC_TAG))

    # ---- nested templates (26 and 62 are parsed; 80/81 stay opaque) ------
    parsed = _parse_templates(fields, mode)

    # ---- duplicate tags ---------------------------------------------------
    errors.extend(_duplicate_issues(fields, parsed))
    for tag in PARSED_TEMPLATE_TAGS:
        if tag in parsed and parsed[tag] is None:
            errors.append(
                _issue(
                    "BAD_TLV",
                    "Malformed payload: tag {} is not a valid TLV template.".format(tag),
                    tag,
                )
            )

    # ---- warnings ---------------------------------------------------------
    present = set(field.tag for field in fields)
    for tag in RECOMMENDED_TAGS:
        if tag not in present:
            warnings.append(
                _issue("MISSING_TAG", "Missing recommended tag {}.".format(tag), tag)
            )

    initiation = find_value(fields, "01")
    amount_present = "54" in present

    for field in fields:
        tag = field.tag
        value = field.value
        if tag == CRC_TAG:
            continue

        if tag in PARSED_TEMPLATE_TAGS:
            children = parsed.get(tag)
            if children is None:
                continue
            for child in children:
                warnings.extend(field_warnings(tag + "/" + child.tag, child.value))
            if tag == "26" and find_field(children, "00") is None:
                warnings.append(
                    _issue(
                        "UNKNOWN_INSTITUTION",
                        'Unverified institution "".',
                        "26/00",
                    )
                )
            continue

        if tag in OPAQUE_TAGS:
            # Opaque token templates: never parsed, never warned about.
            continue

        warnings.extend(field_warnings(tag, value))

        if tag == "01" and value == DYNAMIC_INITIATION and not amount_present:
            warnings.append(
                _issue(
                    "DYNAMIC_WITHOUT_AMOUNT",
                    "Dynamic QR has no amount (tag 54).",
                    "54",
                )
            )
        elif tag == "54" and initiation == STATIC_INITIATION:
            warnings.append(
                _issue(
                    "STATIC_WITH_AMOUNT",
                    "Static QR should not carry an amount (tag 54).",
                    "54",
                )
            )

    return ValidationReport(len(errors) == 0, errors, warnings)


def validate(payload: object, options: object = None) -> ValidationReport:
    """Validate a Bangla QR payload without ever raising.

    Returns a :class:`ValidationReport`; ``errors`` always contain every problem
    found, while ``warnings`` are filtered by ``options.warnings`` (or the
    ``warnings`` key of a dict). ``ok`` is true when there are no errors.
    """
    resolved = _coerce_validate_options(options)
    report = collect(payload)
    return ValidationReport(
        ok=report.ok,
        errors=report.errors,
        warnings=visible_warnings(report.warnings, resolved.warnings),
    )
