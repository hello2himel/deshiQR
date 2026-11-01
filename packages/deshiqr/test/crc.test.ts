import assert from "node:assert/strict";
import { test } from "node:test";
import { crc16 } from "../src/core/crc.ts";
import {
  DYNAMIC_500_PAYLOAD,
  GENERIC_STATIC_PAYLOAD,
  MINIMAL_PAYLOAD,
  REFERENCE,
  STATIC_PAYLOAD,
  fieldsOf,
  seal,
} from "./fixtures.ts";

test("CRC-16/CCITT-FALSE anchor vector: 123456789 -> 29B1", () => {
  assert.equal(crc16("123456789"), "29B1");
});

test("empty input hashes to FFFF and always renders four uppercase hex chars", () => {
  assert.equal(crc16(""), "FFFF");
  for (const input of ["", "a", "bangla qr", "123456789", REFERENCE]) {
    assert.match(crc16(input), /^[0-9A-F]{4}$/);
  }
});

test("every fixture carries its own valid checksum", () => {
  for (const payload of [STATIC_PAYLOAD, DYNAMIC_500_PAYLOAD, MINIMAL_PAYLOAD, GENERIC_STATIC_PAYLOAD]) {
    assert.equal(payload.slice(-4), crc16(payload.slice(0, -4)), payload.slice(0, 16));
  }
});

test("re-sealing parsed fields reproduces the fixture byte for byte", () => {
  for (const payload of [STATIC_PAYLOAD, DYNAMIC_500_PAYLOAD, MINIMAL_PAYLOAD, GENERIC_STATIC_PAYLOAD]) {
    assert.equal(seal(fieldsOf(payload)), payload);
  }
});
