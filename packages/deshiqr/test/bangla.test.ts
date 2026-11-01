/**
 * End-to-end Bangla (non-ASCII) payload support.
 *
 * Real EMVCo/NPSB payloads count TLV lengths in UTF-8 bytes, so a Bangla
 * merchant name makes the old character-counted parser fail. These tests pin
 * that such payloads validate, round-trip and edit; that a legacy
 * character-counted payload is accepted and stays character-counted; and that
 * all-ASCII behaviour is byte-identical to before.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { crc16 } from "../src/core/crc.ts";
import { DeshiQrError } from "../src/core/errors.ts";
import { detectLengthMode, encodeFields, findValue, parse, parseSubfields } from "../src/core/tlv.ts";
import { update, validate, type DeshiQrIssue } from "../src/index.ts";
import {
  BANGLA_BYTE_AMOUNT_100_PAYLOAD,
  BANGLA_BYTE_PAYLOAD,
  BANGLA_CHAR_AMOUNT_100_PAYLOAD,
  BANGLA_CHAR_PAYLOAD,
  BANGLA_CITY,
  BANGLA_NAME,
  DYNAMIC_500_PAYLOAD,
  GENERIC_STATIC_PAYLOAD,
  MINIMAL_PAYLOAD,
  REFERENCE,
  STATIC_PAYLOAD,
} from "./fixtures.ts";

type Edits = Parameters<typeof update>[1];

function valueOf(payload: string, tag: string): string | null {
  return findValue(parse(payload), tag);
}

function subfieldsOf(payload: string, tag: string) {
  return parseSubfields(valueOf(payload, tag) ?? "");
}

function errorOf(fn: () => unknown): DeshiQrError {
  try {
    fn();
  } catch (error) {
    assert.ok(DeshiQrError.is(error), `expected a DeshiQrError, got ${String(error)}`);
    return error;
  }
  assert.fail("expected the call to throw");
}

function captured(payload: string, edits: Edits) {
  const warnings: DeshiQrIssue[] = [];
  const result = update(payload, edits, { onWarning: (warning) => warnings.push(warning) });
  return { payload: result, warnings };
}

// ---- byte-counted (the real-world rule) ---------------------------------

test("the byte-counted Bangla payload validates cleanly", () => {
  const report = validate(BANGLA_BYTE_PAYLOAD);
  assert.deepEqual(report, { ok: true, errors: [], warnings: [] });
  assert.equal(detectLengthMode(BANGLA_BYTE_PAYLOAD), "bytes");
  assert.equal(findValue(parse(BANGLA_BYTE_PAYLOAD, "bytes"), "59"), BANGLA_NAME);
  assert.equal(findValue(parse(BANGLA_BYTE_PAYLOAD, "bytes"), "60"), BANGLA_CITY);
  assert.equal(crc16(BANGLA_BYTE_PAYLOAD.slice(0, -4)), BANGLA_BYTE_PAYLOAD.slice(-4));
});

test("update with no edits round-trips the byte-counted payload byte for byte", () => {
  assert.equal(update(BANGLA_BYTE_PAYLOAD, {}), BANGLA_BYTE_PAYLOAD);
  assert.equal(update(BANGLA_BYTE_PAYLOAD), BANGLA_BYTE_PAYLOAD);
  assert.equal(update(BANGLA_BYTE_PAYLOAD, null), BANGLA_BYTE_PAYLOAD);
  assert.equal(detectLengthMode(update(BANGLA_BYTE_PAYLOAD, {})), "bytes");
});

test("adding an amount keeps the payload byte-counted and valid", () => {
  const result = update(BANGLA_BYTE_PAYLOAD, { amount: 100 });
  assert.equal(result, BANGLA_BYTE_AMOUNT_100_PAYLOAD);
  assert.equal(detectLengthMode(result), "bytes");
  assert.equal(valueOf(result, "01"), "12");
  assert.equal(valueOf(result, "54"), "100.00");
  // Tag 59's two length digits are its UTF-8 byte length, not its char count.
  assert.ok(result.includes(`5940${BANGLA_NAME}`), "tag 59 length should be 40 bytes");
  assert.ok(result.includes(`6012${BANGLA_CITY}`), "tag 60 length should be 12 bytes");
  assert.equal(crc16(result.slice(0, -4)), result.slice(-4));
  assert.deepEqual(validate(result), { ok: true, errors: [], warnings: [] });
});

test("a byte-counted value over 99 UTF-8 bytes is rejected", () => {
  // 34 Bangla characters = 102 UTF-8 bytes, but only 34 characters.
  const error = errorOf(() => update(BANGLA_BYTE_PAYLOAD, { name: "ঢ".repeat(34) }));
  assert.equal(error.code, "BAD_VALUE");
  assert.equal(error.tag, "59");
  assert.match(error.message, /longer than 99/);

  // 33 characters = exactly 99 bytes: allowed (with the documented 25-char name warning).
  const atLimit = "ঢ".repeat(33);
  const { payload } = captured(BANGLA_BYTE_PAYLOAD, { name: atLimit });
  assert.ok(payload.includes(`5999${atLimit}`));
  assert.equal(validate(payload).ok, true);
  assert.equal(detectLengthMode(payload), "bytes");
});

test("reference edits (62/01) inside a byte-counted template", () => {
  const { payload, warnings } = captured(BANGLA_BYTE_PAYLOAD, { reference: "BILL123" });
  assert.deepEqual(warnings, []);
  assert.equal(detectLengthMode(payload), "bytes");
  assert.deepEqual(
    subfieldsOf(payload, "62").map((field) => [field.tag, field.value]),
    [
      ["01", "BILL123"],
      ["06", "FT"],
    ],
  );
  assert.ok(payload.includes("62170107BILL1230602FT"));
  assert.equal(validate(payload).ok, true);
  assert.deepEqual(validate(payload), { ok: true, errors: [], warnings: [] });
});

test("a nested template field edited in byte mode is byte-counted", () => {
  const { payload, warnings } = captured(BANGLA_BYTE_PAYLOAD, { customerLabel: BANGLA_CITY });
  assert.deepEqual(warnings, []);
  assert.equal(detectLengthMode(payload), "bytes");
  const encoded = valueOf(payload, "62") ?? "";
  assert.equal(encoded, `0612${BANGLA_CITY}`);
  assert.ok(payload.includes(`6216${encoded}`), "tag 62 length should count bytes");
  assert.deepEqual(
    subfieldsOf(payload, "62").map((field) => [field.tag, field.value]),
    [["06", BANGLA_CITY]],
  );
  assert.equal(validate(payload).ok, true);
});

test("other providers' byte layouts are unaffected", () => {
  // ASCII remains byte-identical; the mode is detected, never rewritten.
  const ascii = [STATIC_PAYLOAD, DYNAMIC_500_PAYLOAD, MINIMAL_PAYLOAD, GENERIC_STATIC_PAYLOAD];
  for (const payload of ascii) {
    assert.equal(detectLengthMode(payload), "bytes", payload.slice(0, 16));
    assert.equal(update(payload, {}), payload);
    assert.equal(encodeFields(parse(payload)), payload);
  }
  assert.equal(update(STATIC_PAYLOAD, { amount: 500, reference: REFERENCE }), DYNAMIC_500_PAYLOAD);
});

// ---- character-counted (legacy producers) -------------------------------

test("the character-counted Bangla payload validates cleanly", () => {
  const report = validate(BANGLA_CHAR_PAYLOAD);
  assert.deepEqual(report, { ok: true, errors: [], warnings: [] });
  assert.equal(detectLengthMode(BANGLA_CHAR_PAYLOAD), "chars");
  assert.equal(findValue(parse(BANGLA_CHAR_PAYLOAD, "chars"), "59"), BANGLA_NAME);
  assert.equal(findValue(parse(BANGLA_CHAR_PAYLOAD, "chars"), "60"), BANGLA_CITY);
  assert.equal(crc16(BANGLA_CHAR_PAYLOAD.slice(0, -4)), BANGLA_CHAR_PAYLOAD.slice(-4));
});

test("char-counted payloads stay char-counted after edits", () => {
  assert.equal(update(BANGLA_CHAR_PAYLOAD, {}), BANGLA_CHAR_PAYLOAD);
  assert.equal(update(BANGLA_CHAR_PAYLOAD), BANGLA_CHAR_PAYLOAD);

  const result = update(BANGLA_CHAR_PAYLOAD, { amount: 100 });
  assert.equal(result, BANGLA_CHAR_AMOUNT_100_PAYLOAD);
  assert.equal(detectLengthMode(result), "chars");
  assert.equal(valueOf(result, "01"), "12");
  assert.equal(valueOf(result, "54"), "100.00");
  // Tag lengths stay character counts: 14 characters, not 40 bytes.
  assert.ok(result.includes(`5914${BANGLA_NAME}`), "tag 59 length should stay 14 characters");
  assert.ok(result.includes(`6004${BANGLA_CITY}`), "tag 60 length should stay 4 characters");
  assert.equal(crc16(result.slice(0, -4)), result.slice(-4));
  assert.deepEqual(validate(result), { ok: true, errors: [], warnings: [] });
});

test("char mode keeps its own 99-character limit", () => {
  // 34 characters = 102 bytes: too long for byte mode but fine for char mode.
  const value = "ঢ".repeat(34);
  const { payload } = captured(BANGLA_CHAR_PAYLOAD, { name: value });
  assert.ok(payload.includes(`5934${value}`));
  assert.equal(detectLengthMode(payload), "chars");
  assert.equal(validate(payload, { warnings: false }).ok, true);
});

test("reference edits inside a char-counted template keep char lengths", () => {
  const { payload } = captured(BANGLA_CHAR_PAYLOAD, { reference: "BILL123" });
  assert.equal(detectLengthMode(payload), "chars");
  assert.ok(payload.includes("62170107BILL1230602FT"));
  assert.deepEqual(
    subfieldsOf(payload, "62").map((field) => [field.tag, field.value]),
    [
      ["01", "BILL123"],
      ["06", "FT"],
    ],
  );
  assert.equal(validate(payload).ok, true);
});
