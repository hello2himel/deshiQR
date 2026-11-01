"""``validate`` — reports, checksum/structure errors and the report contract."""

from __future__ import annotations

import unittest

import _support  # noqa: F401

from deshiqr import DeshiQrIssue, ValidationReport, validate
from fixtures import (
    BAD_CHECKSUM_PAYLOAD,
    BAD_LENGTH_TLV,
    BAD_TAG_TLV,
    DYNAMIC_PAYLOAD,
    GENERIC_PAYLOAD,
    LONG_NAME_PAYLOAD,
    MINIMAL_PAYLOAD,
    OVERLONG_FIELD,
    STATIC_PAYLOAD,
    TRUNCATED_PAYLOAD,
    duplicate_payload,
    payload_with,
    payload_without,
)


def codes(issues):
    return [issue.code for issue in issues]


class ReportContractTests(unittest.TestCase):
    def test_every_valid_fixture_validates_cleanly(self):
        for payload in (
            STATIC_PAYLOAD,
            DYNAMIC_PAYLOAD,
            MINIMAL_PAYLOAD,
            LONG_NAME_PAYLOAD,
        ):
            report = validate(payload)
            self.assertIsInstance(report, ValidationReport)
            self.assertTrue(report.ok)
            self.assertEqual(report.errors, [])
            self.assertEqual(report.warnings, [])

    def test_generic_provider_fixture_is_valid_with_a_warning(self):
        report = validate(GENERIC_PAYLOAD)
        self.assertTrue(report.ok)
        self.assertEqual(codes(report.warnings), ["UNKNOWN_INSTITUTION"])
        self.assertEqual(report.warnings[0].tag, "26/00")

    def test_ok_is_errors_empty_not_warnings_empty(self):
        report = validate(payload_with("53", "999"))
        self.assertTrue(report.ok)
        self.assertFalse(report.warnings == [])
        self.assertFalse(
            validate(BAD_CHECKSUM_PAYLOAD).ok,
        )

    def test_issues_are_deshi_qr_issue_values(self):
        report = validate(BAD_CHECKSUM_PAYLOAD)
        self.assertIsInstance(report.errors[0], DeshiQrIssue)
        self.assertEqual(report.errors[0].code, "CHECKSUM_MISMATCH")
        self.assertEqual(report.errors[0].tag, "63")
        self.assertIsInstance(report.errors[0].message, str)

    def test_report_lists_are_independent(self):
        first = validate(STATIC_PAYLOAD)
        second = validate(STATIC_PAYLOAD)
        first.errors.append(DeshiQrIssue("BAD_TLV", "x"))
        self.assertEqual(second.errors, [])


class InputErrorTests(unittest.TestCase):
    def test_empty_payload(self):
        for value in ("", "   ", None, 123, [], {}):
            with self.subTest(value=value):
                report = validate(value)
                self.assertFalse(report.ok)
                self.assertEqual(codes(report.errors), ["EMPTY_PAYLOAD"])
                self.assertEqual(report.errors[0].tag, None)

    def test_unsupported_length(self):
        report = validate("0" * 4097)
        self.assertFalse(report.ok)
        self.assertEqual(codes(report.errors), ["UNSUPPORTED"])

    def test_exactly_4096_characters_is_not_unsupported(self):
        report = validate("0" * 4096)
        self.assertFalse(report.ok)
        self.assertNotIn("UNSUPPORTED", codes(report.errors))

    def test_malformed_tlv(self):
        for payload in (
            TRUNCATED_PAYLOAD,
            OVERLONG_FIELD,
            BAD_TAG_TLV,
            BAD_LENGTH_TLV,
            "00020101",
        ):
            with self.subTest(payload=payload):
                report = validate(payload)
                self.assertFalse(report.ok)
                self.assertEqual(codes(report.errors), ["BAD_TLV"])

    def test_payload_not_ending_with_tag_63(self):
        for payload in (
            STATIC_PAYLOAD[:-8],
            STATIC_PAYLOAD + "0002AB",
            "000201010211",
        ):
            with self.subTest(payload=payload):
                report = validate(payload)
                self.assertFalse(report.ok)
                self.assertIn("MISSING_FIELD", codes(report.errors))
                self.assertEqual(
                    [issue.tag for issue in report.errors if issue.code == "MISSING_FIELD"],
                    ["63"],
                )

    def test_checksum_not_four_hex_characters(self):
        report = validate(STATIC_PAYLOAD[:-4] + "ZZZZ")
        self.assertFalse(report.ok)
        self.assertEqual(codes(report.errors), ["BAD_TLV"])
        self.assertEqual(report.errors[0].tag, "63")

    def test_checksum_mismatch(self):
        report = validate(BAD_CHECKSUM_PAYLOAD)
        self.assertFalse(report.ok)
        self.assertEqual(codes(report.errors), ["CHECKSUM_MISMATCH"])
        self.assertEqual(report.errors[0].tag, "63")

    def test_lowercase_checksum_is_accepted(self):
        report = validate(STATIC_PAYLOAD[:-4] + STATIC_PAYLOAD[-4:].lower())
        self.assertTrue(report.ok)

    def test_duplicate_top_level_tag(self):
        report = validate(duplicate_payload())
        self.assertFalse(report.ok)
        self.assertEqual(codes(report.errors), ["DUPLICATE_TAG"])
        self.assertEqual(report.errors[0].tag, "59")
        self.assertEqual(report.errors[0].message, "Tag 59 appears more than once.")

    def test_duplicate_nested_tag(self):
        payload = payload_with("62", "0102AB0102CD")
        report = validate(payload)
        self.assertFalse(report.ok)
        self.assertIn("DUPLICATE_TAG", codes(report.errors))
        duplicate = [issue for issue in report.errors if issue.code == "DUPLICATE_TAG"][0]
        self.assertEqual(duplicate.tag, "62/01")

    def test_invalid_nested_template(self):
        for tag in ("26", "62"):
            with self.subTest(tag=tag):
                report = validate(payload_with(tag, "abc"))
                self.assertFalse(report.ok)
                self.assertEqual(codes(report.errors), ["BAD_TLV"])
                self.assertEqual(report.errors[0].tag, tag)
                self.assertEqual(
                    report.errors[0].message,
                    "Malformed payload: tag {} is not a valid TLV template.".format(tag),
                )

    def test_opaque_tokens_are_never_parsed(self):
        for tag in ("80", "81"):
            with self.subTest(tag=tag):
                report = validate(payload_with(tag, "not tlv at all !!"))
                self.assertTrue(report.ok)
                self.assertEqual(report.errors, [])

    def test_errors_do_not_hide_warnings(self):
        payload = payload_without("00")
        report = validate(payload[:-4] + "0000")
        self.assertFalse(report.ok)
        self.assertIn("CHECKSUM_MISMATCH", codes(report.errors))
        self.assertIn("MISSING_TAG", codes(report.warnings))

    def test_validate_never_throws_on_junk(self):
        for value in ("x", "00", "0000", "\u0000\u0001", "9999", "6304295D"):
            report = validate(value)
            self.assertIsInstance(report, ValidationReport)
            self.assertIsInstance(report.ok, bool)


class ValidateOptionsIntegrityTests(unittest.TestCase):
    def test_errors_are_kept_when_warnings_are_off(self):
        report = validate(BAD_CHECKSUM_PAYLOAD, {"warnings": False})
        self.assertFalse(report.ok)
        self.assertEqual(report.warnings, [])
        self.assertEqual(len(report.errors), 1)

    def test_options_none_shows_all_warnings(self):
        self.assertTrue(validate(GENERIC_PAYLOAD).warnings)
        self.assertTrue(validate(GENERIC_PAYLOAD, None).warnings)


if __name__ == "__main__":
    unittest.main()
