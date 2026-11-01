"""Synthetic fixtures only.

No real merchant or payment data is used anywhere: the account is the
unassignable prefix ``01000000000``, the merchant is ``DEMO STORE`` / ``Dhaka``
and the NPSB tokens literally spell "deshiqr dummy token A/B not real".
See ``docs/demo-payloads.md`` in the repository root.

The Bangla fixtures are the same NPSB-shaped payload written two ways: with
``LL`` counted as UTF-8 **bytes** (the EMVCo/NPSB rule; tag 59 is 40 bytes for
a 14-character name) and with ``LL`` counted as **characters** (a legacy
producer; tag 59 is 14). Both are accepted, and edits preserve the unit.
"""

from __future__ import annotations

import _support  # noqa: F401  (side effect: adds src/ to sys.path)

from deshiqr.crc import crc16
from deshiqr.tlv import Field, encode_fields, parse, parse_subfields

STATIC_PAYLOAD = (
    "00020101021126470014bd.org.bb.npsb010202020420020311010000000005204601653030505802BD5910DEMO STORE6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304295D"
)

DYNAMIC_PAYLOAD = (
    "00020101021226470014bd.org.bb.npsb010202020420020311010000000005204601653030505406500.005802BD5910DEMO STORE6005Dhaka62350125DEMOQR0VZeK2MfbVRI6w36osd0602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304F835"
)

MINIMAL_PAYLOAD = (
    "00020101021126470014bd.org.bb.npsb0102020204200203110100000000053030505802BD5910DEMO STORE6005Dhaka63049C89"
)

LONG_NAME_PAYLOAD = (
    "00020101021126470014bd.org.bb.npsb010202020420020311010000000005204541153030505802BD5919DEMO SUPER SHOP LTD6010Chattogram630494E0"
)

#: Synthetic non-bKash layout (made-up institution AID, no tokens, no tag 62).
GENERIC_PAYLOAD = (
    "00020101021126410022example.org.generic-qr0311017000000005204541153030505802BD5912GENERIC SHOP6006Sylhet6304818D"
)

#: The generic fixture at 1250.50 BDT, exactly as published in docs/demo-payloads.md.
PAYLOAD_DEMO_GENERIC_AMOUNT = (
    "00020101021226410022example.org.generic-qr03110170000000052045411530305054071250.505802BD5912GENERIC SHOP6006Sylhet630480A2"
)

#: Synthetic 25-character bill number (the length real dynamic QRs use).
DUMMY_REFERENCE = "DEMOQR0VZeK2MfbVRI6w36osd"

DUMMY_TOKEN_A = "ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE="
DUMMY_TOKEN_B = "ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE="

TAG80_VALUE = "0014bd.org.bb.npsb0144" + DUMMY_TOKEN_A
TAG81_VALUE = "0014bd.org.bb.npsb0144" + DUMMY_TOKEN_B

#: Corrupted checksum: last four characters replaced.
BAD_CHECKSUM_PAYLOAD = STATIC_PAYLOAD[:-4] + "0000"

#: Truncated TLV: drop the checksum and part of the last field.
TRUNCATED_PAYLOAD = STATIC_PAYLOAD[:-12]

#: TLV that declares more bytes than it has.
OVERLONG_FIELD = "0005AB"

#: Invalid TLV: non-numeric tag.
BAD_TAG_TLV = "XX040000"

#: TLV with a non-numeric length.
BAD_LENGTH_TLV = "0004ZZ"

#: Sample Bangla merchant name (14 characters, 40 UTF-8 bytes).
BANGLA_NAME = "রহিম ট্রেডার্স"
#: Sample Bangla city (4 characters, 12 UTF-8 bytes).
BANGLA_CITY = "ঢাকা"

#: The proof payload: real-world NPSB layout where ``LL`` counts UTF-8 bytes.
#: Tag 59 declares 40 (bytes) for a 14-character Bangla name; tag 60 declares
#: 12 (bytes) for a 4-character city. CRC ``1551``.
BANGLA_BYTE_PAYLOAD = (
    "00020101021126330014bd.org.bb.npsb0311017000000005204601653030505802BD5940রহিম ট্রেডার্স6012ঢাকা62060602FT63041551"
)

#: The same payload with ``LL`` counted in characters (a legacy producer):
#: tag 59 declares 14, tag 60 declares 4. CRC ``E69B``.
BANGLA_CHAR_PAYLOAD = (
    "00020101021126330014bd.org.bb.npsb0311017000000005204601653030505802BD5914রহিম ট্রেডার্স6004ঢাকা62060602FT6304E69B"
)

#: ``update(BANGLA_BYTE_PAYLOAD, {"amount": 100})`` — byte lengths preserved,
#: CRC ``7278``.
BANGLA_BYTE_AMOUNT_100_PAYLOAD = (
    "00020101021226330014bd.org.bb.npsb0311017000000005204601653030505406100.005802BD5940রহিম ট্রেডার্স6012ঢাকা62060602FT63047278"
)

#: ``update(BANGLA_CHAR_PAYLOAD, {"amount": 100})`` — char lengths preserved,
#: CRC ``81B2``.
BANGLA_CHAR_AMOUNT_100_PAYLOAD = (
    "00020101021226330014bd.org.bb.npsb0311017000000005204601653030505406100.005802BD5914রহিম ট্রেডার্স6004ঢাকা62060602FT630481B2"
)


def seal(fields, mode="bytes"):
    """Encode fields and append a valid tag-63 checksum (drops any old tag 63)."""
    body = encode_fields([field for field in fields if field.tag != "63"], mode) + "6304"
    return body + crc16(body)


def rebuild(payload, mutate=None, mode="bytes"):
    """Parse a payload, apply ``mutate(fields)`` in place, then re-seal it."""
    fields = parse(payload)
    if mutate is not None:
        mutate(fields)
    return seal(fields, mode)


def set_field(fields, tag, value):
    """Replace the first field with ``tag`` or insert one sorted."""
    for field in fields:
        if field.tag == tag:
            field.value = value
            return
    fields.append(Field(tag, value))
    fields.sort(key=lambda item: int(item.tag))


def remove_field(fields, tag):
    """Remove every top-level field with ``tag``."""
    fields[:] = [field for field in fields if field.tag != tag]


def fields_of(payload):
    """Parse a payload into its top-level fields."""
    return parse(payload)


def field_value(payload, tag):
    """Value of the first top-level ``tag``, or ``None``."""
    for field in parse(payload):
        if field.tag == tag:
            return field.value
    return None


def tags_of(payload):
    """Top-level tags, in payload order."""
    return [field.tag for field in parse(payload)]


def payload_without(*tags):
    """The static fixture with some top-level tags removed, re-sealed."""
    return rebuild(
        STATIC_PAYLOAD,
        lambda fields: [remove_field(fields, tag) for tag in tags],
    )


def payload_with(tag, value):
    """The static fixture with one top-level tag set, re-sealed."""
    return rebuild(STATIC_PAYLOAD, lambda fields: set_field(fields, tag, value))


def subfields_of(payload, tag):
    """Parse a template field's value into fields."""
    return parse_subfields(field_value(payload, tag) or "")


def duplicate_payload(tag="59", value="DEMO STORE"):
    """The static fixture with a duplicated (checksum-valid) tag."""
    fields = parse(STATIC_PAYLOAD)
    fields.append(Field(tag, value))
    return seal(fields)


def set_subfield(fields, parent_tag, sub_tag, value):
    """Replace a sub-tag inside a template field (parent must already exist)."""
    for field in fields:
        if field.tag == parent_tag:
            children = parse(field.value)
            set_field(children, sub_tag, value)
            field.value = encode_fields(children)
            return
    raise AssertionError("parent tag {} is missing".format(parent_tag))


def payload_with_subfield(parent_tag, sub_tag, value, base=None):
    """A sealed fixture with one template sub-tag replaced."""
    source = base or STATIC_PAYLOAD
    return rebuild(
        source,
        lambda fields: set_subfield(fields, parent_tag, sub_tag, value),
    )


def payload_with_many(mutate):
    """The static fixture with an arbitrary mutation, re-sealed."""
    return rebuild(STATIC_PAYLOAD, mutate)
