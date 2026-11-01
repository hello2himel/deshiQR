"""Length-unit detection and byte/character counted encoding, end to end.

Real Bangla QR payloads count ``LL`` in UTF-8 bytes; some producers count
characters. The engine auto-detects by re-encoding, prefers bytes, and keeps the
detected unit when it writes. These tests mirror the JavaScript
``encoding.test.ts`` / ``bangla.test.ts`` files.
"""

from __future__ import annotations

import unittest

import _support  # noqa: F401

from deshiqr import update, validate
from deshiqr.crc import crc16
from deshiqr.errors import DeshiQrError
from deshiqr.tlv import (
    MAX_VALUE_LENGTH,
    Field,
    detect_length_mode,
    encode_field,
    encode_fields,
    find_value,
    parse,
    parse_subfields,
    value_length,
)
from fixtures import (
    BANGLA_BYTE_AMOUNT_100_PAYLOAD,
    BANGLA_BYTE_PAYLOAD,
    BANGLA_CHAR_AMOUNT_100_PAYLOAD,
    BANGLA_CHAR_PAYLOAD,
    BANGLA_CITY,
    BANGLA_NAME,
    DYNAMIC_PAYLOAD,
    GENERIC_PAYLOAD,
    MINIMAL_PAYLOAD,
    DUMMY_REFERENCE,
    STATIC_PAYLOAD,
)


def field_value(payload, tag):
    """Value of the first top-level ``tag``, or ``None``."""
    return find_value(parse(payload), tag)


def subfields_of(payload, tag):
    """Top-level fields of a template value."""
    return parse_subfields(field_value(payload, tag) or "")


class LengthModeTests(unittest.TestCase):
    def test_all_ascii_payloads_detect_as_bytes(self):
        for payload in (STATIC_PAYLOAD, DYNAMIC_PAYLOAD, MINIMAL_PAYLOAD):
            with self.subTest(payload=payload[:16]):
                self.assertEqual(detect_length_mode(payload), "bytes")
                self.assertEqual(encode_fields(parse(payload), "bytes"), payload)
                self.assertEqual(encode_fields(parse(payload), "chars"), payload)

    def test_byte_counted_bangla_payload_detects_as_bytes(self):
        self.assertEqual(detect_length_mode(BANGLA_BYTE_PAYLOAD), "bytes")
        self.assertEqual(field_value(BANGLA_BYTE_PAYLOAD, "59"), BANGLA_NAME)
        self.assertEqual(
            encode_fields(parse(BANGLA_BYTE_PAYLOAD), "bytes"), BANGLA_BYTE_PAYLOAD
        )

    def test_character_counted_bangla_payload_detects_as_chars(self):
        self.assertEqual(detect_length_mode(BANGLA_CHAR_PAYLOAD), "chars")
        self.assertEqual(field_value(BANGLA_CHAR_PAYLOAD, "59"), BANGLA_NAME)
        self.assertEqual(
            encode_fields(parse(BANGLA_CHAR_PAYLOAD), "chars"), BANGLA_CHAR_PAYLOAD
        )

    def test_parse_without_mode_uses_the_detected_unit(self):
        self.assertEqual(parse(BANGLA_BYTE_PAYLOAD), parse(BANGLA_BYTE_PAYLOAD, "bytes"))
        self.assertEqual(parse(BANGLA_CHAR_PAYLOAD), parse(BANGLA_CHAR_PAYLOAD, "chars"))

    def test_byte_mode_counts_utf8_bytes_char_mode_counts_characters(self):
        self.assertEqual(
            encode_field(Field("59", BANGLA_NAME)), "5940" + BANGLA_NAME
        )
        self.assertEqual(
            encode_field(Field("59", BANGLA_NAME), "chars"), "5914" + BANGLA_NAME
        )
        self.assertEqual(
            encode_field(Field("60", BANGLA_CITY)), "6012" + BANGLA_CITY
        )
        self.assertEqual(
            encode_field(Field("60", BANGLA_CITY), "chars"), "6004" + BANGLA_CITY
        )
        self.assertEqual(value_length(BANGLA_NAME), 40)
        self.assertEqual(value_length(BANGLA_NAME, "chars"), 14)

    def test_byte_mode_enforces_the_99_byte_limit(self):
        too_many_bytes = "ঢ" * 34  # 102 UTF-8 bytes, 34 characters
        with self.assertRaises(DeshiQrError) as caught:
            encode_field(Field("59", too_many_bytes))
        self.assertEqual(caught.exception.code, "BAD_VALUE")
        self.assertEqual(caught.exception.tag, "59")

        at_limit = "ঢ" * 33  # exactly 99 bytes
        self.assertEqual(encode_field(Field("59", at_limit)), "5999" + at_limit)
        self.assertEqual(
            encode_field(Field("59", too_many_bytes), "chars"), "5934" + too_many_bytes
        )

    def test_parse_subfields_keeps_the_parent_mode(self):
        byte_template = encode_fields([Field("06", BANGLA_CITY)], "bytes")
        char_template = encode_fields([Field("06", BANGLA_CITY)], "chars")
        self.assertEqual(byte_template, "0612" + BANGLA_CITY)
        self.assertEqual(char_template, "0604" + BANGLA_CITY)
        self.assertEqual(field_value(byte_template, "06"), BANGLA_CITY)
        self.assertEqual(
            find_value(parse_subfields(byte_template, "bytes"), "06"), BANGLA_CITY
        )
        self.assertEqual(
            find_value(parse_subfields(char_template, "chars"), "06"), BANGLA_CITY
        )

    def test_malformed_tlv_reports_the_byte_attempt_error(self):
        with self.assertRaises(DeshiQrError) as caught:
            parse("0005AB")
        self.assertEqual(caught.exception.code, "BAD_TLV")
        self.assertEqual(
            caught.exception.message,
            "Malformed payload: tag 00 claims 5 characters but only 2 remain.",
        )

    def test_max_value_length_is_99_units(self):
        self.assertEqual(MAX_VALUE_LENGTH, 99)
        self.assertEqual(encode_field(Field("59", "x" * 99))[2:4], "99")


class ByteCountedBanglaTests(unittest.TestCase):
    def test_the_byte_counted_payload_validates_cleanly(self):
        report = validate(BANGLA_BYTE_PAYLOAD)
        self.assertTrue(report.ok)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        self.assertEqual(crc16(BANGLA_BYTE_PAYLOAD[:-4]), BANGLA_BYTE_PAYLOAD[-4:])

    def test_update_with_no_edits_round_trips_byte_for_byte(self):
        self.assertEqual(update(BANGLA_BYTE_PAYLOAD, {}), BANGLA_BYTE_PAYLOAD)
        self.assertEqual(update(BANGLA_BYTE_PAYLOAD), BANGLA_BYTE_PAYLOAD)
        self.assertEqual(update(BANGLA_BYTE_PAYLOAD, None), BANGLA_BYTE_PAYLOAD)
        self.assertEqual(detect_length_mode(update(BANGLA_BYTE_PAYLOAD, {})), "bytes")

    def test_adding_an_amount_keeps_the_payload_byte_counted_and_valid(self):
        result = update(BANGLA_BYTE_PAYLOAD, {"amount": 100})
        self.assertEqual(result, BANGLA_BYTE_AMOUNT_100_PAYLOAD)
        self.assertEqual(detect_length_mode(result), "bytes")
        self.assertEqual(field_value(result, "01"), "12")
        self.assertEqual(field_value(result, "54"), "100.00")
        self.assertIn("5940" + BANGLA_NAME, result)
        self.assertIn("6012" + BANGLA_CITY, result)
        self.assertEqual(crc16(result[:-4]), result[-4:])
        self.assertTrue(validate(result).ok)

    def test_a_value_over_99_utf8_bytes_is_rejected(self):
        with self.assertRaises(DeshiQrError) as caught:
            update(BANGLA_BYTE_PAYLOAD, {"name": "ঢ" * 34})
        self.assertEqual(caught.exception.code, "BAD_VALUE")
        self.assertEqual(caught.exception.tag, "59")
        self.assertIn("longer than 99", caught.exception.message)

        at_limit = "ঢ" * 33  # 99 bytes, allowed
        payload = update(BANGLA_BYTE_PAYLOAD, {"name": at_limit}, {"warnings": False})
        self.assertIn("5999" + at_limit, payload)
        self.assertTrue(validate(payload, {"warnings": False}).ok)
        self.assertEqual(detect_length_mode(payload), "bytes")

    def test_reference_edit_inside_a_byte_counted_template(self):
        payload = update(BANGLA_BYTE_PAYLOAD, {"reference": "BILL123"})
        self.assertEqual(detect_length_mode(payload), "bytes")
        self.assertEqual(
            [(field.tag, field.value) for field in subfields_of(payload, "62")],
            [("01", "BILL123"), ("06", "FT")],
        )
        self.assertIn("62170107BILL1230602FT", payload)
        report = validate(payload)
        self.assertTrue(report.ok)
        self.assertEqual(report.warnings, [])

    def test_a_nested_template_field_edited_in_byte_mode_is_byte_counted(self):
        payload = update(BANGLA_BYTE_PAYLOAD, {"customerLabel": BANGLA_CITY})
        self.assertEqual(detect_length_mode(payload), "bytes")
        encoded = field_value(payload, "62")
        self.assertEqual(encoded, "0612" + BANGLA_CITY)
        self.assertIn("6216" + encoded, payload)
        self.assertEqual(
            [(field.tag, field.value) for field in subfields_of(payload, "62")],
            [("06", BANGLA_CITY)],
        )
        self.assertTrue(validate(payload).ok)

    def test_all_ascii_behaviour_is_unchanged(self):
        for payload in (
            STATIC_PAYLOAD,
            DYNAMIC_PAYLOAD,
            MINIMAL_PAYLOAD,
            GENERIC_PAYLOAD,
        ):
            with self.subTest(payload=payload[:16]):
                self.assertEqual(detect_length_mode(payload), "bytes")
                self.assertEqual(update(payload, {}), payload)
                self.assertEqual(encode_fields(parse(payload)), payload)
        self.assertEqual(
            update(STATIC_PAYLOAD, {"amount": 500, "reference": DUMMY_REFERENCE}),
            DYNAMIC_PAYLOAD,
        )


class CharCountedBanglaTests(unittest.TestCase):
    def test_the_char_counted_payload_validates_cleanly(self):
        report = validate(BANGLA_CHAR_PAYLOAD)
        self.assertTrue(report.ok)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        self.assertEqual(crc16(BANGLA_CHAR_PAYLOAD[:-4]), BANGLA_CHAR_PAYLOAD[-4:])

    def test_char_counted_payloads_stay_char_counted_after_edits(self):
        self.assertEqual(update(BANGLA_CHAR_PAYLOAD, {}), BANGLA_CHAR_PAYLOAD)
        self.assertEqual(update(BANGLA_CHAR_PAYLOAD), BANGLA_CHAR_PAYLOAD)

        result = update(BANGLA_CHAR_PAYLOAD, {"amount": 100})
        self.assertEqual(result, BANGLA_CHAR_AMOUNT_100_PAYLOAD)
        self.assertEqual(detect_length_mode(result), "chars")
        self.assertEqual(field_value(result, "01"), "12")
        self.assertEqual(field_value(result, "54"), "100.00")
        self.assertIn("5914" + BANGLA_NAME, result)
        self.assertIn("6004" + BANGLA_CITY, result)
        self.assertEqual(crc16(result[:-4]), result[-4:])
        self.assertTrue(validate(result).ok)

    def test_char_mode_keeps_its_own_99_character_limit(self):
        value = "ঢ" * 34  # 102 bytes but only 34 characters
        payload = update(BANGLA_CHAR_PAYLOAD, {"name": value}, {"warnings": False})
        self.assertIn("5934" + value, payload)
        self.assertEqual(detect_length_mode(payload), "chars")
        self.assertTrue(validate(payload, {"warnings": False}).ok)

    def test_reference_edits_inside_a_char_counted_template(self):
        payload = update(BANGLA_CHAR_PAYLOAD, {"reference": "BILL123"})
        self.assertEqual(detect_length_mode(payload), "chars")
        self.assertIn("62170107BILL1230602FT", payload)
        self.assertEqual(
            [(field.tag, field.value) for field in subfields_of(payload, "62")],
            [("01", "BILL123"), ("06", "FT")],
        )
        self.assertTrue(validate(payload).ok)


if __name__ == "__main__":
    unittest.main()
