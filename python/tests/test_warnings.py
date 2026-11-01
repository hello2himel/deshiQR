"""Every documented warning code, warning order and warning suppression."""

from __future__ import annotations

import unittest

import _support  # noqa: F401

from deshiqr import update, validate
from deshiqr.tlv import Field, encode_fields
from fixtures import (
    DYNAMIC_PAYLOAD,
    GENERIC_PAYLOAD,
    MINIMAL_PAYLOAD,
    STATIC_PAYLOAD,
    payload_with,
    payload_with_many,
    payload_with_subfield,
    payload_without,
)


def codes(issues):
    return [issue.code for issue in issues]


def tags(issues):
    return [issue.tag for issue in issues]


def warning_codes(payload):
    return codes(validate(payload).warnings)


class MissingTagTests(unittest.TestCase):
    def test_three_recommended_tags_in_canonical_order(self):
        report = validate(payload_without("00", "01", "59"))
        self.assertEqual(codes(report.warnings), ["MISSING_TAG"] * 3)
        self.assertEqual(tags(report.warnings), ["00", "01", "59"])
        self.assertEqual(report.warnings[0].message, "Missing recommended tag 00.")

    def test_single_missing_name(self):
        report = validate(payload_without("59"))
        self.assertEqual(codes(report.warnings), ["MISSING_TAG"])
        self.assertEqual(report.warnings[0].tag, "59")


class UnknownTagTests(unittest.TestCase):
    def test_unknown_top_level_tag(self):
        payload = payload_with_many(
            lambda fields: fields.append(Field("77", "X"))
        )
        report = validate(payload)
        self.assertIn("UNKNOWN_TAG", codes(report.warnings))
        issue = [w for w in report.warnings if w.code == "UNKNOWN_TAG"][0]
        self.assertEqual(issue.tag, "77")
        self.assertEqual(issue.message, "Unknown tag 77.")

    def test_unknown_account_sub_tag(self):
        payload = payload_with_subfield("26", "04", "X")
        report = validate(payload)
        self.assertEqual(codes(report.warnings), ["UNKNOWN_TAG"])
        self.assertEqual(report.warnings[0].tag, "26/04")

    def test_unknown_additional_data_sub_tag(self):
        payload = payload_with_subfield("62", "02", "X")
        report = validate(payload)
        self.assertEqual(codes(report.warnings), ["UNKNOWN_TAG"])
        self.assertEqual(report.warnings[0].tag, "62/02")


class BadFieldValueTests(unittest.TestCase):
    def _only(self, payload):
        return validate(payload)

    def test_format_indicator(self):
        report = self._only(payload_with("00", "02"))
        self.assertIn("BAD_FIELD_VALUE", codes(report.warnings))
        self.assertEqual(
            [w.tag for w in report.warnings if w.code == "BAD_FIELD_VALUE"], ["00"]
        )

    def test_point_of_initiation(self):
        report = self._only(payload_with("01", "13"))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "01")

    def test_account_version(self):
        report = self._only(payload_with_subfield("26", "01", "2"))
        self.assertIn("BAD_FIELD_VALUE", codes(report.warnings))
        self.assertEqual(
            [w.tag for w in report.warnings if w.code == "BAD_FIELD_VALUE"], ["26/01"]
        )

    def test_account_scheme_variant(self):
        report = self._only(payload_with_subfield("26", "02", "20"))
        self.assertIn("BAD_FIELD_VALUE", codes(report.warnings))
        self.assertEqual(
            [w.tag for w in report.warnings if w.code == "BAD_FIELD_VALUE"], ["26/02"]
        )

    def test_account_identifier_charset_and_length(self):
        report = self._only(payload_with_subfield("26", "03", "abc"))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "26/03")

    def test_mcc(self):
        report = self._only(payload_with("52", "541"))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "52")

    def test_currency(self):
        report = self._only(payload_with("53", "US"))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "53")

    def test_amount_not_two_decimals(self):
        report = validate(payload_with("54", "500"))
        self.assertIn("BAD_FIELD_VALUE", codes(report.warnings))
        self.assertEqual(
            [w.tag for w in report.warnings if w.code == "BAD_FIELD_VALUE"], ["54"]
        )

    def test_country_charset(self):
        report = self._only(payload_with("58", "B1"))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "58")

    def test_empty_merchant_name(self):
        report = self._only(payload_with("59", ""))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "59")

    def test_empty_city(self):
        report = self._only(payload_with("60", ""))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "60")

    def test_empty_reference(self):
        report = self._only(payload_with_subfield("62", "01", ""))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "62/01")

    def test_non_printable_reference(self):
        report = self._only(payload_with_subfield("62", "01", "BILL\n123"))
        self.assertEqual(codes(report.warnings), ["BAD_FIELD_VALUE"])
        self.assertEqual(report.warnings[0].tag, "62/01")


class FieldTooLongTests(unittest.TestCase):
    def test_name(self):
        report = validate(payload_with("59", "A" * 26))
        self.assertEqual(codes(report.warnings), ["FIELD_TOO_LONG"])
        self.assertEqual(report.warnings[0].tag, "59")
        self.assertEqual(
            report.warnings[0].message,
            "Value for tag 59 is longer than 25 characters.",
        )

    def test_city(self):
        report = validate(payload_with("60", "A" * 16))
        self.assertEqual(codes(report.warnings), ["FIELD_TOO_LONG"])
        self.assertEqual(report.warnings[0].tag, "60")

    def test_reference(self):
        report = validate(payload_with_subfield("62", "01", "A" * 33))
        self.assertEqual(codes(report.warnings), ["FIELD_TOO_LONG"])
        self.assertEqual(report.warnings[0].tag, "62/01")

    def test_account_identifier(self):
        report = validate(payload_with_subfield("26", "03", "0" * 35))
        self.assertEqual(codes(report.warnings), ["FIELD_TOO_LONG"])
        self.assertEqual(report.warnings[0].tag, "26/03")


class KnownValueTests(unittest.TestCase):
    def test_unknown_currency(self):
        report = validate(payload_with("53", "999"))
        self.assertEqual(codes(report.warnings), ["UNKNOWN_CURRENCY"])
        self.assertEqual(report.warnings[0].tag, "53")
        self.assertEqual(report.warnings[0].message, 'Unknown currency "999".')

    def test_non_bd_country(self):
        report = validate(payload_with("58", "IN"))
        self.assertEqual(codes(report.warnings), ["NON_BD_COUNTRY"])
        self.assertEqual(report.warnings[0].tag, "58")
        self.assertEqual(report.warnings[0].message, 'Country is "IN", not "BD".')

    def test_lowercase_country_is_non_bd_not_bad_syntax(self):
        report = validate(payload_with("58", "bd"))
        self.assertEqual(codes(report.warnings), ["NON_BD_COUNTRY"])

    def test_unknown_institution(self):
        report = validate(GENERIC_PAYLOAD)
        self.assertEqual(codes(report.warnings), ["UNKNOWN_INSTITUTION"])
        self.assertEqual(report.warnings[0].tag, "26/00")

    def test_missing_institution_is_reported_at_the_end_of_the_account_block(self):
        account_value = encode_fields(
            [
                Field("01", "02"),
                Field("02", "2002"),
                Field("03", "01000000000"),
            ]
        )
        payload = payload_with_many(
            lambda fields: [
                field.__setattr__("value", account_value)
                for field in fields
                if field.tag == "26"
            ]
        )
        report = validate(payload)
        self.assertEqual(codes(report.warnings), ["UNKNOWN_INSTITUTION"])
        self.assertEqual(report.warnings[0].tag, "26/00")
        self.assertEqual(report.warnings[0].message, 'Unverified institution "".')

    def test_unknown_mcc(self):
        report = validate(payload_with("52", "1234"))
        self.assertEqual(codes(report.warnings), ["UNKNOWN_MCC"])
        self.assertEqual(report.warnings[0].tag, "52")


class CouplingWarningTests(unittest.TestCase):
    def test_static_with_amount(self):
        report = validate(DYNAMIC_PAYLOAD.replace("010212", "010211", 1))
        self.assertEqual(codes(report.warnings), ["STATIC_WITH_AMOUNT"])
        self.assertEqual(report.warnings[0].tag, "54")

    def test_dynamic_without_amount(self):
        report = validate(payload_with("01", "12"))
        self.assertEqual(codes(report.warnings), ["DYNAMIC_WITHOUT_AMOUNT"])
        self.assertEqual(report.warnings[0].tag, "54")

    def test_dynamic_without_amount_is_reported_at_tag_01_position(self):
        payload = payload_with_many(
            lambda fields: [
                field.__setattr__("value", "12") for field in fields if field.tag == "01"
            ]
        )
        report = validate(payload)
        self.assertEqual(codes(report.warnings), ["DYNAMIC_WITHOUT_AMOUNT"])


class RiskyEditWarningTests(unittest.TestCase):
    def test_risky_edit_codes_and_tags(self):
        seen = []
        update(STATIC_PAYLOAD, {"name": "X"}, {"onWarning": seen.append})
        self.assertEqual(codes(seen), ["RISKY_EDIT"])
        self.assertEqual(
            seen[0].message,
            "Editing the account/name can mislead payers; only edit what you own.",
        )


class WarningOrderTests(unittest.TestCase):
    def test_document_order_across_fields(self):
        def mutate(fields):
            for field in fields:
                if field.tag == "00":
                    field.value = "02"
                elif field.tag == "01":
                    field.value = "12"
                elif field.tag == "52":
                    field.value = "1234"
                elif field.tag == "53":
                    field.value = "999"
                elif field.tag == "58":
                    field.value = "IN"
                elif field.tag == "59":
                    field.value = "A" * 26
            fields.append(Field("77", "X"))
            fields.remove([field for field in fields if field.tag == "00"][0])

        report = validate(payload_with_many(mutate))
        self.assertEqual(
            codes(report.warnings),
            [
                "MISSING_TAG",
                "DYNAMIC_WITHOUT_AMOUNT",
                "UNKNOWN_MCC",
                "UNKNOWN_CURRENCY",
                "NON_BD_COUNTRY",
                "FIELD_TOO_LONG",
                "UNKNOWN_TAG",
            ],
        )
        self.assertEqual(
            tags(report.warnings),
            ["00", "54", "52", "53", "58", "59", "77"],
        )

    def test_missing_tag_warnings_always_come_first(self):
        report = validate(payload_without("59", "00", "01"))
        self.assertEqual(tags(report.warnings)[:3], ["00", "01", "59"])


class SuppressionTests(unittest.TestCase):
    def test_false_removes_all_warnings(self):
        report = validate(GENERIC_PAYLOAD, {"warnings": False})
        self.assertEqual(report.warnings, [])

    def test_true_shows_all_warnings(self):
        report = validate(
            payload_without("00"), {"warnings": True}
        )
        self.assertEqual(codes(report.warnings), ["MISSING_TAG"])

    def test_exact_tag_suppression(self):
        report = validate(GENERIC_PAYLOAD, {"warnings": ["26/00"]})
        self.assertEqual(report.warnings, [])

    def test_parent_path_does_not_suppress_children(self):
        report = validate(GENERIC_PAYLOAD, {"warnings": ["26"]})
        self.assertEqual(codes(report.warnings), ["UNKNOWN_INSTITUTION"])

    def test_other_tags_do_not_suppress(self):
        report = validate(payload_with("53", "999"), {"warnings": ["52"]})
        self.assertEqual(codes(report.warnings), ["UNKNOWN_CURRENCY"])

    def test_errors_survive_suppression(self):
        payload = payload_without("00")[:-4] + "0000"
        report = validate(payload, {"warnings": ["00"]})
        self.assertFalse(report.ok)
        self.assertIn("CHECKSUM_MISMATCH", codes(report.errors))


if __name__ == "__main__":
    unittest.main()
