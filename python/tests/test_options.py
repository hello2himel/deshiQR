"""Options plumbing for both public functions."""

from __future__ import annotations

import unittest
import warnings

import _support  # noqa: F401

from deshiqr import (
    DeshiQrIssue,
    DeshiQrWarning,
    UpdateOptions,
    ValidateOptions,
    update,
    validate,
)
from fixtures import GENERIC_PAYLOAD, STATIC_PAYLOAD, payload_with_subfield


def codes(issues):
    return [issue.code for issue in issues]


class UpdateOptionsTests(unittest.TestCase):
    def test_dataclass_options_with_callback(self):
        seen = []
        options = UpdateOptions(on_warning=seen.append)
        update(STATIC_PAYLOAD, {"name": "X"}, options)
        self.assertEqual(codes(seen), ["RISKY_EDIT"])
        self.assertIsInstance(seen[0], DeshiQrIssue)

    def test_dict_options_camel_case_key(self):
        seen = []
        update(STATIC_PAYLOAD, {"name": "X"}, {"onWarning": seen.append})
        self.assertEqual(codes(seen), ["RISKY_EDIT"])

    def test_dict_options_snake_case_key(self):
        seen = []
        update(STATIC_PAYLOAD, {"name": "X"}, {"on_warning": seen.append})
        self.assertEqual(codes(seen), ["RISKY_EDIT"])

    def test_dataclass_suppression_list(self):
        seen = []
        update(
            STATIC_PAYLOAD,
            {"name": "X"},
            UpdateOptions(warnings=["59"], on_warning=seen.append),
        )
        self.assertEqual(seen, [])

    def test_dict_suppression_list_keeps_other_warnings(self):
        seen = []
        update(
            GENERIC_PAYLOAD,
            {"name": "A"},
            {"warnings": ["59"], "onWarning": seen.append},
        )
        self.assertEqual(codes(seen), ["UNKNOWN_INSTITUTION"])

    def test_warnings_false_suppresses_everything(self):
        seen = []
        update(STATIC_PAYLOAD, {"name": "X"}, {"warnings": False, "onWarning": seen.append})
        self.assertEqual(seen, [])

    def test_default_sink_uses_the_stdlib_warnings_module(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            update(STATIC_PAYLOAD, {"name": "X"})
        self.assertEqual(len(caught), 1)
        self.assertIs(caught[0].category, DeshiQrWarning)
        self.assertIn("mislead payers", str(caught[0].message))

    def test_validate_options_are_not_accepted_by_update(self):
        with self.assertRaises(TypeError):
            update(STATIC_PAYLOAD, {}, ValidateOptions())

    def test_invalid_options_type(self):
        with self.assertRaises(TypeError):
            update(STATIC_PAYLOAD, {}, "loud")

    def test_invalid_warnings_type(self):
        with self.assertRaises(TypeError):
            update(STATIC_PAYLOAD, {}, {"warnings": "59"})
        with self.assertRaises(TypeError):
            validate(STATIC_PAYLOAD, {"warnings": 3})

    def test_non_callable_on_warning(self):
        with self.assertRaises(TypeError):
            update(STATIC_PAYLOAD, {}, {"onWarning": "print"})

    def test_callback_receives_each_visible_warning_in_order(self):
        seen = []
        update(
            GENERIC_PAYLOAD,
            {"institution": "example.org.generic-qr"},
            {"onWarning": seen.append},
        )
        self.assertEqual([(issue.code, issue.tag) for issue in seen], [
            ("RISKY_EDIT", "26/00"),
            ("UNKNOWN_INSTITUTION", "26/00"),
        ])


class ValidateOptionsTests(unittest.TestCase):
    def test_dataclass_options(self):
        report = validate(GENERIC_PAYLOAD, ValidateOptions(warnings=False))
        self.assertEqual(report.warnings, [])
        self.assertEqual(report.errors, [])

    def test_dataclass_suppression_list(self):
        report = validate(GENERIC_PAYLOAD, ValidateOptions(warnings=["26/00"]))
        self.assertEqual(report.warnings, [])

    def test_mapping_options(self):
        self.assertEqual(validate(GENERIC_PAYLOAD, {"warnings": False}).warnings, [])
        self.assertEqual(
            [w.code for w in validate(GENERIC_PAYLOAD, {"warnings": True}).warnings],
            ["UNKNOWN_INSTITUTION"],
        )

    def test_update_options_are_not_accepted_by_validate(self):
        with self.assertRaises(TypeError):
            validate(GENERIC_PAYLOAD, UpdateOptions())

    def test_suppression_applies_to_nested_paths_exactly(self):
        payload = payload_with_subfield("62", "01", "A" * 33)
        self.assertEqual(
            [w.code for w in validate(payload, {"warnings": ["62"]}).warnings],
            ["FIELD_TOO_LONG"],
        )
        self.assertEqual(validate(payload, {"warnings": ["62/01"]}).warnings, [])

    def test_validate_does_not_emit_python_warnings(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            validate(GENERIC_PAYLOAD)
        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()
