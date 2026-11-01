"""Internal TLV parsing/encoding helpers (the contract every public call rests on)."""

from __future__ import annotations

import unittest

import _support  # noqa: F401

from deshiqr.errors import DeshiQrError
from deshiqr.tlv import (
    CRC_TAG,
    Field,
    encode_field,
    encode_fields,
    find_field,
    find_value,
    insert_sorted,
    is_hex_checksum,
    is_tag_path,
    normalize,
    parse,
    parse_subfields,
    parse_template,
    path_components,
    remove_all,
)
from fixtures import STATIC_PAYLOAD, tags_of


class ParseTests(unittest.TestCase):
    def test_parses_every_field_preserving_order(self):
        fields = parse(STATIC_PAYLOAD)
        self.assertEqual(
            [field.tag for field in fields],
            ["00", "01", "26", "52", "53", "58", "59", "60", "62", "80", "81", "63"],
        )
        self.assertEqual(find_value(fields, "59"), "DEMO STORE")
        self.assertEqual(find_value(fields, "00"), "01")

    def test_round_trips(self):
        fields = parse(STATIC_PAYLOAD)
        self.assertEqual(encode_fields(fields), STATIC_PAYLOAD)

    def test_empty_text_is_empty_payload(self):
        with self.assertRaises(DeshiQrError) as caught:
            parse("")
        self.assertEqual(caught.exception.code, "EMPTY_PAYLOAD")
        self.assertEqual(parse_subfields(""), [])

    def test_truncated_header_is_bad_tlv(self):
        with self.assertRaises(DeshiQrError) as caught:
            parse("00")
        self.assertEqual(caught.exception.code, "BAD_TLV")

    def test_bad_tag_is_bad_tlv(self):
        with self.assertRaises(DeshiQrError) as caught:
            parse("XX040000")
        self.assertEqual(caught.exception.code, "BAD_TLV")
        self.assertEqual(caught.exception.tag, "XX")

    def test_bad_length_is_bad_tlv(self):
        with self.assertRaises(DeshiQrError) as caught:
            parse("0004ZZ")
        self.assertEqual(caught.exception.code, "BAD_TLV")
        self.assertEqual(caught.exception.tag, "00")

    def test_overlong_field_is_bad_tlv(self):
        with self.assertRaises(DeshiQrError) as caught:
            parse("0005AB")
        self.assertEqual(caught.exception.code, "BAD_TLV")

    def test_non_string_input_is_bad_tlv(self):
        with self.assertRaises(DeshiQrError):
            parse(None)  # type: ignore[arg-type]


class EncodingTests(unittest.TestCase):
    def test_encodes_header_and_value(self):
        self.assertEqual(encode_field(Field("54", "500.00")), "5406500.00")

    def test_rejects_too_long_values(self):
        with self.assertRaises(DeshiQrError) as caught:
            encode_field(Field("59", "x" * 100))
        self.assertEqual(caught.exception.code, "BAD_VALUE")

    def test_rejects_bad_tag(self):
        with self.assertRaises(DeshiQrError) as caught:
            encode_field(Field("1", "x"))
        self.assertEqual(caught.exception.code, "BAD_TLV")

    def test_inserts_in_ascending_numeric_order(self):
        fields = [Field("00", "01"), Field("52", "6016"), Field("80", "x")]
        insert_sorted(fields, Field("54", "1.00"))
        insert_sorted(fields, Field("01", "12"))
        insert_sorted(fields, Field("81", "y"))
        self.assertEqual([field.tag for field in fields], ["00", "01", "52", "54", "80", "81"])

    def test_remove_all_removes_every_occurrence(self):
        fields = [Field("59", "A"), Field("60", "B"), Field("59", "C")]
        remove_all(fields, "59")
        self.assertEqual([field.tag for field in fields], ["60"])


class PathAndTemplateTests(unittest.TestCase):
    def test_valid_tag_paths(self):
        for path in ("54", "62/01", "26/03", "80/01", "00/01/02"):
            self.assertTrue(is_tag_path(path), path)

    def test_invalid_tag_paths(self):
        for path in ("", "5", "054", "54/", "/54", "54/1", "ab", "54/abc", " 54", 54):
            self.assertFalse(is_tag_path(path), path)

    def test_path_components(self):
        self.assertEqual(path_components("62/01"), ["62", "01"])

    def test_parse_template_reports_the_path(self):
        with self.assertRaises(DeshiQrError) as caught:
            parse_template("abc", "26")
        self.assertEqual(caught.exception.code, "BAD_TLV")
        self.assertEqual(caught.exception.tag, "26")

    def test_parse_template_accepts_an_empty_value(self):
        self.assertEqual(parse_template("", "62"), [])

    def test_checksum_hex_detection(self):
        for value in ("295D", "295d", "0000"):
            self.assertTrue(is_hex_checksum(value))
        for value in ("", "295", "ZZZZ", 295):
            self.assertFalse(is_hex_checksum(value))


class NormalizeTests(unittest.TestCase):
    def test_trims_strings(self):
        self.assertEqual(normalize("  " + STATIC_PAYLOAD + "\n"), STATIC_PAYLOAD)

    def test_non_strings_become_empty(self):
        for value in (None, 1, 1.0, [], {}, object()):
            self.assertEqual(normalize(value), "")


class FindTests(unittest.TestCase):
    def test_find_field_and_value(self):
        fields = parse(STATIC_PAYLOAD)
        self.assertIsInstance(find_field(fields, "59"), Field)
        self.assertIsNone(find_field(fields, "54"))
        self.assertIsNone(find_value(fields, "54"))
        self.assertEqual(find_value(fields, CRC_TAG), "295D")

    def test_tags_of_helper_matches_parse(self):
        self.assertEqual(tags_of(STATIC_PAYLOAD)[0], "00")


if __name__ == "__main__":
    unittest.main()
