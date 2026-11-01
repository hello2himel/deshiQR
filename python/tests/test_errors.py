"""Every documented ``update`` error code, plus the exception contract."""

from __future__ import annotations

import unittest

import _support  # noqa: F401

from deshiqr import DeshiQrError, update
from deshiqr.tlv import Field, encode_fields, parse
from fixtures import (
    BAD_CHECKSUM_PAYLOAD,
    BAD_LENGTH_TLV,
    BAD_TAG_TLV,
    DYNAMIC_PAYLOAD,
    MINIMAL_PAYLOAD,
    OVERLONG_FIELD,
    STATIC_PAYLOAD,
    TRUNCATED_PAYLOAD,
    duplicate_payload,
    payload_with,
)


class UpdateErrorTests(unittest.TestCase):
    def assertCode(self, code, payload=STATIC_PAYLOAD, edits=None, tag=None):
        with self.assertRaises(DeshiQrError) as caught:
            update(payload, edits)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.name, "DeshiQrError")
        self.assertIsInstance(caught.exception, Exception)
        if tag is not None:
            self.assertEqual(caught.exception.tag, tag)
        return caught.exception

    # ---- input errors -----------------------------------------------------
    def test_empty_payload(self):
        for value in ("", "   ", None, 42, [], {}):
            with self.subTest(value=value):
                error = self.assertCode("EMPTY_PAYLOAD", payload=value)
                self.assertEqual(
                    error.message,
                    "The payload is empty.",
                )

    def test_unsupported_payload(self):
        error = self.assertCode("UNSUPPORTED", payload="0" * 4097)
        self.assertEqual(
            error.message, "The payload is longer than 4096 characters."
        )

    def test_malformed_tlv(self):
        for payload in (
            TRUNCATED_PAYLOAD,
            OVERLONG_FIELD,
            BAD_TAG_TLV,
            BAD_LENGTH_TLV,
        ):
            with self.subTest(payload=payload):
                self.assertCode("BAD_TLV", payload=payload)

    def test_missing_checksum(self):
        self.assertCode("MISSING_FIELD", payload=STATIC_PAYLOAD[:-8], tag="63")
        self.assertCode("MISSING_FIELD", payload=STATIC_PAYLOAD + "0002AB", tag="63")

    def test_checksum_format_is_bad_tlv(self):
        self.assertCode("BAD_TLV", payload=STATIC_PAYLOAD[:-4] + "ZZZZ", tag="63")

    def test_checksum_mismatch(self):
        error = self.assertCode("CHECKSUM_MISMATCH", payload=BAD_CHECKSUM_PAYLOAD, tag="63")
        self.assertEqual(error.message, "The checksum does not match.")

    def test_duplicate_tag_is_rejected_before_editing(self):
        error = self.assertCode("DUPLICATE_TAG", payload=duplicate_payload())
        self.assertEqual(error.tag, "59")
        self.assertEqual(error.message, "Tag 59 appears more than once.")

    def test_duplicate_nested_tag_is_rejected_before_editing(self):
        account = encode_fields(
            [
                Field("00", "bd.org.bb.npsb"),
                Field("03", "01000000000"),
                Field("03", "01000000001"),
            ]
        )
        payload = payload_with("26", account)
        error = self.assertCode("DUPLICATE_TAG", payload=payload)
        self.assertEqual(error.tag, "26/03")

    def test_duplicate_input_cannot_be_repaired_by_editing(self):
        payload = duplicate_payload()
        self.assertCode("DUPLICATE_TAG", payload=payload, edits={"59": "NEW"})

    # ---- edit value errors ------------------------------------------------
    def test_bad_amount(self):
        for value in ("abc", "0", 0, "0.00", -5, 100_000_000, "1.234", 10.996):
            with self.subTest(value=value):
                error = self.assertCode("BAD_AMOUNT", edits={"amount": value}, tag="54")
                self.assertIn("Amount", error.message)

    def test_bad_amount_messages(self):
        self.assertEqual(
            self.assertCode("BAD_AMOUNT", edits={"amount": "abc"}).message,
            "Amount must be a number or a numeric string.",
        )
        self.assertEqual(
            self.assertCode("BAD_AMOUNT", edits={"amount": 0}).message,
            "Amount must be greater than zero.",
        )
        self.assertEqual(
            self.assertCode("BAD_AMOUNT", edits={"amount": 100_000_000}).message,
            "Amount must not exceed 99999999.99.",
        )
        self.assertEqual(
            self.assertCode("BAD_AMOUNT", edits={"amount": "1.234"}).message,
            "Amount must have at most two decimal places.",
        )

    def test_bad_tag_invalid_paths(self):
        for key in ("5", "abc", "5/01", "", "54/", "6 3", 54, None):
            with self.subTest(key=key):
                self.assertCode("BAD_TAG", edits={key: "x"})

    def test_bad_tag_checksum(self):
        for key in ("63", "63/01"):
            with self.subTest(key=key):
                error = self.assertCode("BAD_TAG", edits={key: "x"}, tag="63")
                self.assertEqual(
                    error.message,
                    "Tag 63 is the checksum and cannot be edited.",
                )

    def test_bad_tag_missing_parent(self):
        error = self.assertCode("BAD_TAG", payload=MINIMAL_PAYLOAD, edits={"80/01": "x"})
        self.assertEqual(error.tag, "80/01")
        self.assertEqual(
            error.message,
            "Tag 80/01 has a missing or invalid parent template.",
        )

    def test_bad_tag_invalid_parent(self):
        self.assertCode("BAD_TAG", edits={"26/00/01": "x"})

    def test_bad_value_types(self):
        for value in (True, False, [], {}, object()):
            with self.subTest(value=value):
                error = self.assertCode("BAD_VALUE", edits={"name": value})
                self.assertEqual(
                    error.message,
                    "Value for tag 59 must be a string, a number or null.",
                )
                self.assertEqual(error.tag, "59")
        self.assertCode("BAD_VALUE", edits={"amount": True})
        self.assertCode("BAD_VALUE", edits={"amount": []})

    def test_bad_value_too_long(self):
        error = self.assertCode("BAD_VALUE", edits={"62/06": "x" * 100})
        self.assertEqual(
            error.message,
            "Value for tag 62/06 is longer than 99 characters.",
        )

    def test_bad_value_non_finite_number(self):
        self.assertCode("BAD_VALUE", edits={"mcc": float("nan")})
        self.assertCode("BAD_VALUE", edits={"mcc": float("inf")})

    def test_edits_must_be_an_object(self):
        for edits in ("54", [], 5, True):
            with self.subTest(edits=edits):
                error = self.assertCode("BAD_VALUE", edits=edits)
                self.assertEqual(error.message, "Edits must be an object of tag paths/aliases.")

    # ---- result validation errors ----------------------------------------
    def test_result_invalid_nested_template_is_an_error(self):
        error = self.assertCode("BAD_TLV", edits={"26": "abc"})
        self.assertEqual(error.code, "BAD_TLV")
        self.assertEqual(error.tag, "26")

    def test_error_tag_can_be_omitted(self):
        self.assertIsNone(self.assertCode("EMPTY_PAYLOAD", payload="").tag)


class UpdateSuccessTests(unittest.TestCase):
    def test_dynamic_payload_can_be_edited(self):
        result = update(DYNAMIC_PAYLOAD, {"amount": 99})
        self.assertIsInstance(result, str)
        self.assertTrue(result.endswith(result[-4:]))

    def test_parse_of_result_is_stable(self):
        result = update(STATIC_PAYLOAD, {"amount": 1})
        self.assertEqual(parse(result)[-1].tag, "63")


if __name__ == "__main__":
    unittest.main()


class ScalarPathTests(unittest.TestCase):
    def test_nested_edit_under_a_scalar_tag_is_bad_tag(self):
        for path in ("00/01", "01/01", "52/01", "54/01", "58/01", "59/01", "60/01"):
            with self.subTest(path=path):
                with self.assertRaises(DeshiQrError) as caught:
                    update(STATIC_PAYLOAD, {path: "x"})
                self.assertEqual(caught.exception.code, "BAD_TAG")
                self.assertEqual(caught.exception.tag, path)
