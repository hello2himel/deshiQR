import assert from "node:assert/strict";
import { test } from "node:test";
import { DeshiQrError } from "../src/core/errors.ts";
import {
  MAX_FIELD_LENGTH,
  encodeField,
  encodeFields,
  findValue,
  insertFieldSorted,
  parse,
  parseSubfields,
} from "../src/core/tlv.ts";
import { DYNAMIC_500_PAYLOAD, MINIMAL_PAYLOAD, STATIC_PAYLOAD, fieldsOf } from "./fixtures.ts";

function isCode(code: string) {
  return (error: unknown) => DeshiQrError.is(error) && error.code === code;
}

test("parse splits the static fixture into top-level fields", () => {
  const fields = parse(STATIC_PAYLOAD);
  assert.deepEqual(
    fields.map((field) => field.tag),
    ["00", "01", "26", "52", "53", "58", "59", "60", "62", "80", "81", "63"],
  );
  assert.equal(findValue(fields, "59"), "DEMO STORE");
  assert.equal(findValue(fields, "63"), "295D");
});

test("encodeFields(parse(x)) round-trips every fixture exactly", () => {
  for (const payload of [STATIC_PAYLOAD, DYNAMIC_500_PAYLOAD, MINIMAL_PAYLOAD]) {
    assert.equal(encodeFields(parse(payload)), payload);
  }
});

test("nested templates parse into their subtree", () => {
  const fields = parse(DYNAMIC_500_PAYLOAD);
  const account = parseSubfields(findValue(fields, "26") ?? "");
  assert.deepEqual(
    account.map((field) => field.tag),
    ["00", "01", "02", "03"],
  );
  assert.equal(findValue(account, "00"), "bd.org.bb.npsb");

  const additional = parseSubfields(findValue(fields, "62") ?? "");
  assert.deepEqual(
    additional.map((field) => field.tag),
    ["01", "06"],
  );
  assert.equal(findValue(additional, "01")?.length, 25);
});

test("parse trims surrounding whitespace", () => {
  assert.equal(parse(`  ${STATIC_PAYLOAD}\n`).length, 12);
});

test("empty input throws EMPTY_PAYLOAD", () => {
  for (const input of ["", "   ", "\n\t"]) {
    assert.throws(() => parse(input), isCode("EMPTY_PAYLOAD"));
  }
});

test("malformed TLV throws BAD_TLV", () => {
  const cases: Array<[string, string]> = [
    ["00", "truncated header"],
    ["0002", "declares a missing value"],
    ["0005AB", "declares more bytes than present"],
    ["XX0201", "non-numeric tag"],
    ["0002A", "one-character value"],
  ];
  for (const [payload, label] of cases) {
    assert.throws(() => parse(payload), isCode("BAD_TLV"), label);
  }
});

test("encodeField enforces the two-digit tag and 99-character limit", () => {
  assert.equal(encodeField({ tag: "59", value: "DEMO" }), "5904DEMO");
  assert.equal(encodeField({ tag: "62", value: "" }), "6200");
  assert.throws(() => encodeField({ tag: "5", value: "x" }), isCode("BAD_TLV"));
  assert.throws(
    () => encodeField({ tag: "59", value: "x".repeat(MAX_FIELD_LENGTH + 1) }),
    isCode("BAD_VALUE"),
  );
});

test("parseSubfields treats an empty value as an empty (valid) template", () => {
  assert.deepEqual(parseSubfields(""), []);
});

test("insertFieldSorted keeps ascending numeric tag order", () => {
  const fields = fieldsOf(MINIMAL_PAYLOAD);
  insertFieldSorted(fields, { tag: "54", value: "500.00" });
  const tags = fields.map((field) => field.tag);
  assert.ok(tags.indexOf("54") > tags.indexOf("53"));
  assert.ok(tags.indexOf("54") < tags.indexOf("58"));

  insertFieldSorted(fields, { tag: "61", value: "x" });
  assert.ok(fields.map((field) => field.tag).indexOf("61") > tags.indexOf("60"));
});
