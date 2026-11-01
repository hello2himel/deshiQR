/**
 * Synthetic fixtures only. No real merchant data.
 *
 * Fake account `01000000000`, DEMO STORE, dummy base64 tokens. The dynamic
 * payload is exactly what `update(STATIC_PAYLOAD, { amount: 500, reference })`
 * produces — the tests pin that.
 *
 * The Bangla fixtures are the same NPSB-shaped payload written two ways: with
 * `LL` counted as UTF-8 **bytes** (the EMVCo/NPSB rule; tag 59 is 40 bytes for
 * a 14-character name) and with `LL` counted as **characters** (a legacy
 * producer; tag 59 is 14). Both are accepted, and edits preserve the unit.
 */
import { crc16 } from "../src/core/crc.ts";
import { type Field, type LengthMode, encodeFields, parse } from "../src/core/tlv.ts";

export const STATIC_PAYLOAD =
  "00020101021126470014bd.org.bb.npsb010202020420020311010000000005204601653030505802BD5910DEMO STORE6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304295D";

export const DYNAMIC_500_PAYLOAD =
  "00020101021226470014bd.org.bb.npsb010202020420020311010000000005204601653030505406500.005802BD5910DEMO STORE6005Dhaka62350125DEMOQR0VZeK2MfbVRI6w36osd0602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304F835";

export const MINIMAL_PAYLOAD =
  "00020101021126470014bd.org.bb.npsb0102020204200203110100000000053030505802BD5910DEMO STORE6005Dhaka63049C89";

/** Synthetic "other provider" layout: unknown AID, no tokens, no tag 62. */
export const GENERIC_STATIC_PAYLOAD =
  "00020101021126410022example.org.generic-qr0311017000000005204541153030505802BD5912GENERIC SHOP6006Sylhet6304818D";

export const REFERENCE = "DEMOQR0VZeK2MfbVRI6w36osd";

/** Sample Bangla merchant name (14 characters, 40 UTF-8 bytes). */
export const BANGLA_NAME = "রহিম ট্রেডার্স";
/** Sample Bangla city (4 characters, 12 UTF-8 bytes). */
export const BANGLA_CITY = "ঢাকা";

/**
 * The proof payload: real-world NPSB layout where `LL` counts UTF-8 bytes.
 * Tag 59 declares 40 (bytes) for a 14-character Bangla name; tag 60 declares 12
 * (bytes) for a 4-character city. CRC `1551`.
 */
export const BANGLA_BYTE_PAYLOAD =
  "00020101021126330014bd.org.bb.npsb0311017000000005204601653030505802BD5940রহিম ট্রেডার্স6012ঢাকা62060602FT63041551";

/**
 * The same payload with `LL` counted in characters instead of bytes (a legacy
 * producer): tag 59 declares 14, tag 60 declares 4. CRC `E69B`.
 */
export const BANGLA_CHAR_PAYLOAD =
  "00020101021126330014bd.org.bb.npsb0311017000000005204601653030505802BD5914রহিম ট্রেডার্স6004ঢাকা62060602FT6304E69B";

/** `update(BANGLA_BYTE_PAYLOAD, { amount: 100 })` — byte lengths preserved, CRC `7278`. */
export const BANGLA_BYTE_AMOUNT_100_PAYLOAD =
  "00020101021226330014bd.org.bb.npsb0311017000000005204601653030505406100.005802BD5940রহিম ট্রেডার্স6012ঢাকা62060602FT63047278";

/** `update(BANGLA_CHAR_PAYLOAD, { amount: 100 })` — char lengths preserved, CRC `81B2`. */
export const BANGLA_CHAR_AMOUNT_100_PAYLOAD =
  "00020101021226330014bd.org.bb.npsb0311017000000005204601653030505406100.005802BD5914রহিম ট্রেডার্স6004ঢাকা62060602FT630481B2";

/** Re-seal a level with a valid CRC-16 (uppercase). */
export function seal(fields: readonly Field[], mode: LengthMode = "bytes"): string {
  const body = `${encodeFields(fields.filter((field) => field.tag !== "63"), mode)}6304`;
  return body + crc16(body);
}

/** Top-level fields of a payload, without the checksum. */
export function fieldsOf(payload: string): Field[] {
  return parse(payload).filter((field) => field.tag !== "63");
}

/** Rewrite a payload: mutate its fields, then re-seal. */
export function rebuild(
  payload: string,
  mutate: (fields: Field[]) => Field[] | void,
  mode: LengthMode = "bytes",
): string {
  const fields = fieldsOf(payload);
  const mutated = mutate(fields);
  return seal(mutated ?? fields, mode);
}

/** Replace one field value or append it when missing. */
export function setField(fields: Field[], tag: string, value: string): void {
  const index = fields.findIndex((field) => field.tag === tag);
  if (index >= 0) fields[index] = { tag, value };
  else fields.push({ tag, value });
}

/** Remove every field with a tag. */
export function removeField(fields: Field[], tag: string): void {
  for (let i = fields.length - 1; i >= 0; i -= 1) {
    if (fields[i]?.tag === tag) fields.splice(i, 1);
  }
}
