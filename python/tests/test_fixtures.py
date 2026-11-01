"""Fixture integrity: synthetic data, valid checksums and documented shapes."""

from __future__ import annotations

import unittest

import _support  # noqa: F401

from deshiqr.crc import crc16
from fixtures import (
    BAD_CHECKSUM_PAYLOAD,
    BANGLA_BYTE_AMOUNT_100_PAYLOAD,
    BANGLA_BYTE_PAYLOAD,
    BANGLA_CHAR_AMOUNT_100_PAYLOAD,
    BANGLA_CHAR_PAYLOAD,
    DUMMY_REFERENCE,
    DYNAMIC_PAYLOAD,
    GENERIC_PAYLOAD,
    LONG_NAME_PAYLOAD,
    MINIMAL_PAYLOAD,
    PAYLOAD_DEMO_GENERIC_AMOUNT,
    STATIC_PAYLOAD,
    TAG80_VALUE,
    TAG81_VALUE,
    duplicate_payload,
    field_value,
    payload_with,
    payload_with_subfield,
    subfields_of,
    tags_of,
)


class FixtureShapeTests(unittest.TestCase):
    def test_every_valid_fixture_has_a_matching_checksum(self):
        for payload in (
            STATIC_PAYLOAD,
            DYNAMIC_PAYLOAD,
            MINIMAL_PAYLOAD,
            LONG_NAME_PAYLOAD,
            GENERIC_PAYLOAD,
            PAYLOAD_DEMO_GENERIC_AMOUNT,
            BANGLA_BYTE_PAYLOAD,
            BANGLA_CHAR_PAYLOAD,
            BANGLA_BYTE_AMOUNT_100_PAYLOAD,
            BANGLA_CHAR_AMOUNT_100_PAYLOAD,
        ):
            with self.subTest(payload=payload[:20]):
                self.assertEqual(payload[-8:-4], "6304")
                self.assertEqual(crc16(payload[:-4]), payload[-4:])

    def test_static_fixture_has_no_amount(self):
        self.assertEqual(field_value(STATIC_PAYLOAD, "01"), "11")
        self.assertIsNone(field_value(STATIC_PAYLOAD, "54"))

    def test_dynamic_fixture_carries_amount_and_reference(self):
        self.assertEqual(field_value(DYNAMIC_PAYLOAD, "01"), "12")
        self.assertEqual(field_value(DYNAMIC_PAYLOAD, "54"), "500.00")
        reference = subfields_of(DYNAMIC_PAYLOAD, "62")
        self.assertEqual([(f.tag, f.value) for f in reference],
                         [("01", DUMMY_REFERENCE), ("06", "FT")])

    def test_token_templates_are_present_and_opaque(self):
        self.assertEqual(field_value(STATIC_PAYLOAD, "80"), TAG80_VALUE)
        self.assertEqual(field_value(STATIC_PAYLOAD, "81"), TAG81_VALUE)

    def test_generic_fixture_is_not_npsb(self):
        institution = subfields_of(GENERIC_PAYLOAD, "26")[0]
        self.assertEqual((institution.tag, institution.value),
                         ("00", "example.org.generic-qr"))
        self.assertNotIn("bd.org.bb.npsb", GENERIC_PAYLOAD)

    def test_generic_derived_fixture_matches_the_documented_difference(self):
        self.assertEqual(
            [tag for tag in tags_of(PAYLOAD_DEMO_GENERIC_AMOUNT) if tag != "54"],
            tags_of(GENERIC_PAYLOAD),
        )
        self.assertEqual(field_value(PAYLOAD_DEMO_GENERIC_AMOUNT, "54"), "1250.50")
        self.assertEqual(field_value(PAYLOAD_DEMO_GENERIC_AMOUNT, "01"), "12")


class FixtureBuilderTests(unittest.TestCase):
    def test_payload_with_reseals_and_preserves_other_fields(self):
        payload = payload_with("53", "840")
        self.assertEqual(field_value(payload, "53"), "840")
        self.assertEqual(field_value(payload, "59"), "DEMO STORE")
        self.assertEqual(crc16(payload[:-4]), payload[-4:])

    def test_payload_with_subfield_reseals(self):
        payload = payload_with_subfield("62", "01", "BILL123")
        self.assertEqual(
            [(f.tag, f.value) for f in subfields_of(payload, "62")],
            [("01", "BILL123"), ("06", "FT")],
        )
        self.assertEqual(crc16(payload[:-4]), payload[-4:])

    def test_duplicate_payload_is_checksum_valid_but_duplicated(self):
        payload = duplicate_payload()
        self.assertEqual(crc16(payload[:-4]), payload[-4:])
        top_level = tags_of(payload)
        self.assertEqual(top_level.count("59"), 2)
        self.assertEqual(top_level[-1], "63")

    def test_bad_checksum_fixture(self):
        self.assertNotEqual(crc16(BAD_CHECKSUM_PAYLOAD[:-4]), BAD_CHECKSUM_PAYLOAD[-4:])

    def test_fixtures_use_synthetic_merchant_data(self):
        for payload in (STATIC_PAYLOAD, DYNAMIC_PAYLOAD, MINIMAL_PAYLOAD):
            self.assertIn("01000000000", payload)
            self.assertIn("DEMO STORE", payload)
        self.assertIn("GENERIC SHOP", GENERIC_PAYLOAD)
        self.assertIn("example.org.generic-qr", GENERIC_PAYLOAD)

    def test_payload_with_subfield_keeps_sibling_sub_tags(self):
        payload = payload_with_subfield("62", "01", "BILL123")
        self.assertEqual(
            [f.tag for f in subfields_of(payload, "62")], ["01", "06"]
        )


if __name__ == "__main__":
    unittest.main()
