"""``update`` — aliases, tag paths, nested edits, removals, ordering, coupling."""

from __future__ import annotations

import unittest
import warnings

import _support  # noqa: F401

from deshiqr import DeshiQrError, update, validate
from deshiqr.crc import crc16
from deshiqr.tlv import parse
from fixtures import (
    DYNAMIC_PAYLOAD,
    GENERIC_PAYLOAD,
    MINIMAL_PAYLOAD,
    STATIC_PAYLOAD,
    PAYLOAD_DEMO_GENERIC_AMOUNT,
    TAG80_VALUE,
    field_value,
    fields_of,
    payload_with,
    subfields_of,
    tags_of,
)


def tags_and_values(payload):
    return [(field.tag, field.value) for field in parse(payload)]


def validate_ok(payload):
    report = validate(payload)
    return report


class EmptyEditsTests(unittest.TestCase):
    def test_no_edits_returns_the_input_byte_identically(self):
        for payload in (STATIC_PAYLOAD, DYNAMIC_PAYLOAD, MINIMAL_PAYLOAD):
            with self.subTest(payload=payload[:16]):
                self.assertEqual(update(payload, {}), payload)
                self.assertEqual(update(payload), payload)
                self.assertEqual(update(payload, None), payload)

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(update("  " + STATIC_PAYLOAD + " \n"), STATIC_PAYLOAD)

    def test_empty_edits_runs_validation_and_surfaces_warnings(self):
        reports = []
        payload = update(GENERIC_PAYLOAD, {}, options={"onWarning": reports.append})
        self.assertEqual(payload, GENERIC_PAYLOAD)
        self.assertEqual([issue.code for issue in reports], ["UNKNOWN_INSTITUTION"])


class AmountTests(unittest.TestCase):
    def test_amount_alias_adds_tag_54_and_makes_the_qr_dynamic(self):
        result = update(STATIC_PAYLOAD, {"amount": 500})
        self.assertEqual(field_value(result, "54"), "500.00")
        self.assertEqual(field_value(result, "01"), "12")
        self.assertTrue(validate(result).ok)
        self.assertEqual(crc16(result[:-4]), result[-4:])

    def test_amount_accepts_numeric_strings_and_two_decimals(self):
        self.assertEqual(
            field_value(update(STATIC_PAYLOAD, {"amount": "1250.5"}), "54"), "1250.50"
        )
        self.assertEqual(
            field_value(update(STATIC_PAYLOAD, {"amount": "0.01"}), "54"), "0.01"
        )
        self.assertEqual(
            field_value(update(STATIC_PAYLOAD, {"amount": "99999999.99"}), "54"),
            "99999999.99",
        )

    def test_amount_tag_path_behaves_like_the_alias(self):
        self.assertEqual(field_value(update(STATIC_PAYLOAD, {"54": 12}), "54"), "12.00")

    def test_amount_replaces_the_existing_value_without_changing_order(self):
        result = update(DYNAMIC_PAYLOAD, {"amount": 1250.5})
        self.assertEqual(field_value(result, "54"), "1250.50")
        self.assertEqual(validate(result).warnings, [])
        before = tags_of(DYNAMIC_PAYLOAD)
        self.assertEqual(tags_of(result), before)

    def test_removing_the_amount_restores_a_static_qr(self):
        result = update(DYNAMIC_PAYLOAD, {"amount": None})
        self.assertIsNone(field_value(result, "54"))
        self.assertEqual(field_value(result, "01"), "11")
        self.assertEqual(validate(result).warnings, [])

    def test_explicit_01_wins_over_coupling(self):
        result = update(STATIC_PAYLOAD, {"amount": 500, "01": "11"})
        self.assertEqual(field_value(result, "01"), "11")
        self.assertEqual(field_value(result, "54"), "500.00")
        self.assertIn("STATIC_WITH_AMOUNT", [w.code for w in validate(result).warnings])

    def test_explicit_01_survives_amount_removal(self):
        result = update(DYNAMIC_PAYLOAD, {"amount": None, "01": "12"})
        self.assertIsNone(field_value(result, "54"))
        self.assertEqual(field_value(result, "01"), "12")
        self.assertIn(
            "DYNAMIC_WITHOUT_AMOUNT", [w.code for w in validate(result).warnings]
        )

    def test_edits_not_touching_54_do_not_couple_01(self):
        result = update(STATIC_PAYLOAD, {"name": "DEMO STORE 2"})
        self.assertEqual(field_value(result, "01"), "11")

    def test_amount_creates_01_when_missing(self):
        result = update(STATIC_PAYLOAD, {"amount": 10})
        self.assertEqual(field_value(result, "01"), "12")
        repaired = update(payload_without_tag(STATIC_PAYLOAD, "01"), {"amount": 10})
        self.assertEqual(field_value(repaired, "01"), "12")
        self.assertTrue(validate(repaired).ok)


def payload_without_tag(payload, tag):
    from fixtures import rebuild, remove_field

    return rebuild(payload, lambda fields: remove_field(fields, tag))


class AliasTests(unittest.TestCase):
    def test_scalar_aliases_map_to_their_tags(self):
        result = update(
            STATIC_PAYLOAD,
            {
                "currency": "840",
                "country": "BD",
                "mcc": "5411",
                "city": "Sylhet",
            },
        )
        self.assertEqual(field_value(result, "53"), "840")
        self.assertEqual(field_value(result, "58"), "BD")
        self.assertEqual(field_value(result, "52"), "5411")
        self.assertEqual(field_value(result, "60"), "Sylhet")
        self.assertEqual(validate(result).warnings, [])

    def test_name_alias(self):
        result = update(STATIC_PAYLOAD, {"name": "NEW NAME"})
        self.assertEqual(field_value(result, "59"), "NEW NAME")
        self.assertEqual(crc16(result[:-4]), result[-4:])

    def test_nested_aliases_reference_and_customer_label(self):
        result = update(
            DYNAMIC_PAYLOAD,
            {"reference": "BILL123", "customerLabel": "FT2"},
        )
        reference = subfields_of(result, "62")
        self.assertEqual([(f.tag, f.value) for f in reference], [("01", "BILL123"), ("06", "FT2")])

    def test_account_and_institution_aliases(self):
        result = update(
            STATIC_PAYLOAD,
            {"account": "01000000009", "institution": "bd.org.bb.npsb"},
        )
        account = subfields_of(result, "26")
        self.assertEqual(field_value_from(account, "03"), "01000000009")
        self.assertEqual(field_value_from(account, "00"), "bd.org.bb.npsb")

    def test_numbers_are_stringified(self):
        result = update(STATIC_PAYLOAD, {"mcc": 5999})
        self.assertEqual(field_value(result, "52"), "5999")
        result = update(STATIC_PAYLOAD, {"59": 42})
        self.assertEqual(field_value(result, "59"), "42")

    def test_tag_path_wins_over_alias_for_the_same_target(self):
        result = update(STATIC_PAYLOAD, {"amount": 100, "54": "200"})
        self.assertEqual(field_value(result, "54"), "200.00")
        result = update(STATIC_PAYLOAD, {"name": "ALIAS", "59": "PATH"})
        self.assertEqual(field_value(result, "59"), "PATH")


def field_value_from(fields, tag):
    for field in fields:
        if field.tag == tag:
            return field.value
    return None


class TagPathTests(unittest.TestCase):
    def test_add_a_new_top_level_tag_in_sorted_position(self):
        result = update(STATIC_PAYLOAD, {"51": "MADEUP"})
        tags = tags_of(result)
        self.assertEqual(tags.index("51"), tags.index("52") - 1)
        self.assertEqual(tags.index("51"), tags.index("26") + 1)

    def test_added_tags_keep_ascending_numeric_order(self):
        result = update(STATIC_PAYLOAD, {"50": "A", "51": "B", "99": "C"})
        body_tags = [tag for tag in tags_of(result) if tag != "63"]
        self.assertEqual(body_tags, sorted(body_tags, key=int))
        self.assertIn("50", body_tags)
        self.assertIn("51", body_tags)
        self.assertIn("99", body_tags)
        self.assertIn("UNKNOWN_TAG", [w.code for w in validate(result).warnings])

    def test_existing_fields_keep_their_order(self):
        result = update(DYNAMIC_PAYLOAD, {"64": "X"})
        before = [tag for tag in tags_of(DYNAMIC_PAYLOAD) if tag != "63"]
        after = [tag for tag in tags_of(result) if tag != "63"]
        self.assertEqual([tag for tag in after if tag != "64"], before)

    def test_nested_insert_is_sorted_within_its_template(self):
        result = update(STATIC_PAYLOAD, {"62/02": "NEW"})
        self.assertEqual(
            [(f.tag, f.value) for f in subfields_of(result, "62")],
            [("02", "NEW"), ("06", "FT")],
        )

    def test_nested_edit_replaces_an_existing_sub_tag(self):
        result = update(STATIC_PAYLOAD, {"62/06": "ZZ"})
        self.assertEqual(
            [(f.tag, f.value) for f in subfields_of(result, "62")],
            [("06", "ZZ")],
        )

    def test_nested_null_removes_only_that_sub_tag(self):
        result = update(DYNAMIC_PAYLOAD, {"62/01": None})
        self.assertEqual(
            [(f.tag, f.value) for f in subfields_of(result, "62")], [("06", "FT")]
        )
        self.assertIsNotNone(field_value(result, "62"))

    def test_removing_everything_drops_the_template(self):
        result = update(DYNAMIC_PAYLOAD, {"62/01": None, "62/06": None})
        self.assertIsNone(field_value(result, "62"))
        self.assertTrue(validate(result).ok)

    def test_setting_a_template_to_an_empty_value_keeps_an_empty_template(self):
        result = update(DYNAMIC_PAYLOAD, {"62": ""})
        self.assertEqual(field_value(result, "62"), "")
        self.assertTrue(validate(result).ok)

    def test_whole_value_template_replacement(self):
        result = update(STATIC_PAYLOAD, {"62": "0104ABCD"})
        self.assertEqual(
            [(f.tag, f.value) for f in subfields_of(result, "62")], [("01", "ABCD")]
        )

    def test_nested_edit_inside_an_opaque_token_template(self):
        result = update(STATIC_PAYLOAD, {"80/01": "dG9rZW4="})
        children = subfields_of(result, "80")
        self.assertEqual(field_value_from(children, "01"), "dG9rZW4=")
        self.assertEqual(field_value_from(children, "00"), "bd.org.bb.npsb")

    def test_removing_everything_from_an_opaque_template_drops_it(self):
        result = update(DYNAMIC_PAYLOAD, {"80/00": None, "80/01": None})
        self.assertIsNone(field_value(result, "80"))
        self.assertTrue(validate(result).ok)

    def test_nested_edit_under_a_missing_parent_is_bad_tag(self):
        with self.assertRaises(DeshiQrError) as caught:
            update(MINIMAL_PAYLOAD, {"80/01": "x"})
        self.assertEqual(caught.exception.code, "BAD_TAG")
        self.assertEqual(caught.exception.tag, "80/01")

    def test_nested_null_under_a_missing_parent_is_bad_tag(self):
        with self.assertRaises(DeshiQrError) as caught:
            update(MINIMAL_PAYLOAD, {"80/01": None})
        self.assertEqual(caught.exception.code, "BAD_TAG")

    def test_nested_edit_under_a_non_tlv_parent_is_bad_tag(self):
        with self.assertRaises(DeshiQrError) as caught:
            update(STATIC_PAYLOAD, {"59/01": "x"})
        self.assertEqual(caught.exception.code, "BAD_TAG")
        self.assertEqual(caught.exception.tag, "59/01")

    def test_top_level_null_of_a_missing_tag_is_a_no_op(self):
        self.assertEqual(update(STATIC_PAYLOAD, {"55": None}), STATIC_PAYLOAD)


class IdempotencyAndInvariantTests(unittest.TestCase):
    def test_same_edits_twice_give_the_same_payload(self):
        edits = {"amount": 500, "customerLabel": "FT", "62/01": "BILL123"}
        once = update(STATIC_PAYLOAD, edits)
        twice = update(once, edits)
        self.assertEqual(once, twice)

    def test_provider_agnostic_invariant_on_the_generic_fixture(self):
        result = update(GENERIC_PAYLOAD, {"amount": 1250.5})
        self.assertEqual(result, PAYLOAD_DEMO_GENERIC_AMOUNT)
        before = tags_and_values(GENERIC_PAYLOAD)
        after = tags_and_values(result)
        changed = {"01", "54", "63"}
        self.assertEqual(
            [(tag, value) for tag, value in after if tag not in changed],
            [(tag, value) for tag, value in before if tag not in changed],
        )
        for tag in ("00", "26", "52", "53", "58", "59", "60"):
            self.assertEqual(field_value(result, tag), field_value(GENERIC_PAYLOAD, tag))

    def test_only_edited_tags_plus_01_and_63_change(self):
        result = update(STATIC_PAYLOAD, {"city": "Sylhet"})
        before = dict(tags_and_values(STATIC_PAYLOAD))
        after = dict(tags_and_values(result))
        changed = {tag for tag in after if before.get(tag) != after[tag]}
        self.assertEqual(changed, {"60", "63"})

    def test_result_always_has_a_valid_checksum(self):
        for edits in (
            {"amount": 1},
            {"name": "X"},
            {"62/01": "REF"},
            {"amount": None},
        ):
            with self.subTest(edits=edits):
                result = update(STATIC_PAYLOAD, edits)
                self.assertEqual(result[-8:-4], "6304")
                self.assertEqual(crc16(result[:-4]), result[-4:])
                self.assertTrue(validate(result).ok)


class UpdateWarningTests(unittest.TestCase):
    def test_risky_edit_for_name(self):
        seen = []
        update(STATIC_PAYLOAD, {"name": "NEW"}, {"onWarning": seen.append})
        self.assertEqual([issue.code for issue in seen], ["RISKY_EDIT"])
        self.assertEqual(seen[0].tag, "59")

    def test_risky_edit_for_account_and_institution_sorted(self):
        seen = []
        update(
            STATIC_PAYLOAD,
            {"account": "01000000009", "institution": "bd.org.bb.npsb"},
            {"onWarning": seen.append},
        )
        self.assertEqual([issue.tag for issue in seen], ["26/00", "26/03"])

    def test_risky_edit_deduped_when_alias_and_path_target_the_same_field(self):
        seen = []
        update(
            STATIC_PAYLOAD,
            {"name": "A", "59": "B"},
            {"onWarning": seen.append},
        )
        self.assertEqual([issue.tag for issue in seen], ["59"])

    def test_validation_warnings_come_after_risky_edit(self):
        seen = []
        update(
            GENERIC_PAYLOAD,
            {"institution": "example.org.generic-qr"},
            {"onWarning": seen.append},
        )
        self.assertEqual([issue.code for issue in seen], ["RISKY_EDIT", "UNKNOWN_INSTITUTION"])

    def test_update_never_emits_warnings_when_disabled(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            update(STATIC_PAYLOAD, {"name": "X"}, {"warnings": False})
        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()
