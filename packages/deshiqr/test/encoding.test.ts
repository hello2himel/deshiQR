/**
 * Length-unit detection and byte/character counted encoding (TLV layer).
 *
 * Real Bangla QR payloads count `LL` in UTF-8 bytes; some producers count
 * characters. The engine auto-detects by re-encoding, prefers bytes, and keeps
 * the detected unit when it writes.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { DeshiQrError } from "../src/core/errors.ts";
import {
  MAX_FIELD_LENGTH,
  detectLengthMode,
  encodeField,
  encodeFields,
  findValue,
  parse,
  parseSubfields,
} from "../src/core/tlv.ts";
import {
  BANGLA_BYTE_PAYLOAD,
  BANGLA_CHAR_PAYLOAD,
  BANGLA_CITY,
  BANGLA_NAME,
  STATIC_PAYLOAD,
} from "./fixtures.ts";

test("all-ASCII payloads detect as bytes (the two units are identical)", () => {
  assert.equal(detectLengthMode(STATIC_PAYLOAD), "bytes");
  assert.deepEqual(parse(STATIC_PAYLOAD, "bytes"), parse(STATIC_PAYLOAD, "chars"));
  assert.equal(encodeFields(parse(STATIC_PAYLOAD), "bytes"), STATIC_PAYLOAD);
  assert.equal(encodeFields(parse(STATIC_PAYLOAD), "chars"), STATIC_PAYLOAD);
});

test("byte-counted Bangla payload detects as bytes", () => {
  assert.equal(detectLengthMode(BANGLA_BYTE_PAYLOAD), "bytes");
  assert.equal(findValue(parse(BANGLA_BYTE_PAYLOAD), "59"), BANGLA_NAME);
  assert.equal(encodeFields(parse(BANGLA_BYTE_PAYLOAD), "bytes"), BANGLA_BYTE_PAYLOAD);
});

test("character-counted Bangla payload is detected as chars", () => {
  assert.equal(detectLengthMode(BANGLA_CHAR_PAYLOAD), "chars");
  assert.equal(findValue(parse(BANGLA_CHAR_PAYLOAD), "59"), BANGLA_NAME);
  assert.equal(encodeFields(parse(BANGLA_CHAR_PAYLOAD), "chars"), BANGLA_CHAR_PAYLOAD);
});

test("parse(payload) with no mode uses the detected unit", () => {
  assert.deepEqual(parse(BANGLA_BYTE_PAYLOAD), parse(BANGLA_BYTE_PAYLOAD, "bytes"));
  assert.deepEqual(parse(BANGLA_CHAR_PAYLOAD), parse(BANGLA_CHAR_PAYLOAD, "chars"));
});

test("parse with an explicit unit uses that unit's lengths", () => {
  assert.equal(findValue(parse(BANGLA_BYTE_PAYLOAD, "bytes"), "59"), BANGLA_NAME);
  assert.equal(findValue(parse(BANGLA_CHAR_PAYLOAD, "chars"), "59"), BANGLA_NAME);
});

test("byte mode counts UTF-8 bytes, char mode counts characters", () => {
  assert.equal(encodeField({ tag: "59", value: BANGLA_NAME }), `5940${BANGLA_NAME}`);
  assert.equal(encodeField({ tag: "59", value: BANGLA_NAME }, "chars"), `5914${BANGLA_NAME}`);
  assert.equal(encodeField({ tag: "60", value: BANGLA_CITY }), `6012${BANGLA_CITY}`);
  assert.equal(encodeField({ tag: "60", value: BANGLA_CITY }, "chars"), `6004${BANGLA_CITY}`);
});

test("byte mode enforces the 99-byte value limit", () => {
  // 34 x U+09E2 = 102 UTF-8 bytes (and only 34 characters).
  const tooManyBytes = "ঢ".repeat(34);
  assert.throws(
    () => encodeField({ tag: "59", value: tooManyBytes }),
    (error: unknown) => DeshiQrError.is(error) && error.code === "BAD_VALUE" && error.tag === "59",
  );
  // 33 characters = exactly 99 bytes: allowed in byte mode.
  const atLimit = "ঢ".repeat(33);
  assert.equal(encodeField({ tag: "59", value: atLimit }), `5999${atLimit}`);
  // In char mode the same 34 characters are under the limit.
  assert.equal(encodeField({ tag: "59", value: tooManyBytes }, "chars"), `5934${tooManyBytes}`);
});

test("parseSubfields keeps a template in the parent mode", () => {
  const byteTemplate = encodeFields([{ tag: "06", value: BANGLA_CITY }], "bytes");
  const charTemplate = encodeFields([{ tag: "06", value: BANGLA_CITY }], "chars");
  assert.equal(byteTemplate, `0612${BANGLA_CITY}`);
  assert.equal(charTemplate, `0604${BANGLA_CITY}`);
  assert.equal(findValue(parseSubfields(byteTemplate, "bytes"), "06"), BANGLA_CITY);
  assert.equal(findValue(parseSubfields(charTemplate, "chars"), "06"), BANGLA_CITY);
});

test("malformed TLV still reports the byte-attempt BAD_TLV error", () => {
  assert.throws(
    () => parse("0005AB"),
    (error: unknown) =>
      DeshiQrError.is(error) &&
      error.code === "BAD_TLV" &&
      error.message === "Malformed payload: tag 00 claims 5 characters but only 2 remain.",
  );
});

test("MAX_FIELD_LENGTH is 99 units", () => {
  assert.equal(MAX_FIELD_LENGTH, 99);
  assert.equal(encodeField({ tag: "59", value: "x".repeat(99) }).slice(2, 4), "99");
});
