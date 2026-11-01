import { DeshiQrError } from "./errors.ts";

/** A single `TT LL VV…` field. */
export interface Field {
  tag: string;
  value: string;
}

/**
 * How `LL` lengths are counted.
 *
 * `"bytes"` counts UTF-8 bytes — the EMVCo/NPSB rule, so a Bangla character
 * counts as three. `"chars"` counts string characters (the legacy unit some
 * producers write). The two are identical for all-ASCII payloads.
 */
export type LengthMode = "bytes" | "chars";

/** Default length unit for encoding: bytes (identical to chars for ASCII). */
export const DEFAULT_LENGTH_MODE: LengthMode = "bytes";

/**
 * The format allows at most 99 units in a single field value: UTF-8 bytes in
 * `"bytes"` mode, characters in `"chars"` mode.
 */
export const MAX_FIELD_LENGTH = 99;

const TAG_RE = /^\d{2}$/;
const LENGTH_RE = /^\d{2}$/;

const encoder = new TextEncoder();
const decoder = new TextDecoder();

/** Strip surrounding whitespace; anything that is not a string is empty. */
export function normalize(payload: unknown): string {
  return typeof payload === "string" ? payload.trim() : "";
}

/** True for a two-digit tag. */
export function isTag(value: string): boolean {
  return TAG_RE.test(value);
}

/** UTF-8 byte length of a string. */
export function byteLength(value: string): number {
  return encoder.encode(value).length;
}

/** Length of a value in `mode`'s unit (bytes by default). */
export function valueLength(value: string, mode: LengthMode = DEFAULT_LENGTH_MODE): number {
  return mode === "bytes" ? byteLength(value) : value.length;
}

/**
 * Walk a non-empty payload level in one length mode.
 *
 * In `"bytes"` mode the payload is encoded once and walked by byte offsets,
 * decoding each value slice as UTF-8; in `"chars"` mode offsets are string
 * indices. Error messages keep the historical wording; the unit they count is
 * the mode's unit.
 */
function parseInMode(text: string, mode: LengthMode): Field[] {
  const bytes = mode === "bytes" ? encoder.encode(text) : null;
  const total = bytes === null ? text.length : bytes.length;
  const slice = (start: number, end: number): string =>
    bytes === null ? text.slice(start, end) : decoder.decode(bytes.subarray(start, end));

  const fields: Field[] = [];
  let offset = 0;

  while (offset < total) {
    if (offset + 4 > total) {
      throw new DeshiQrError("BAD_TLV", `Malformed payload: truncated field at offset ${offset}.`);
    }

    const tag = slice(offset, offset + 2);
    if (!TAG_RE.test(tag)) {
      throw new DeshiQrError("BAD_TLV", `Malformed payload: invalid tag "${tag}" at offset ${offset}.`, tag);
    }

    const rawLength = slice(offset + 2, offset + 4);
    if (!LENGTH_RE.test(rawLength)) {
      throw new DeshiQrError(
        "BAD_TLV",
        `Malformed payload: invalid length "${rawLength}" for tag ${tag} at offset ${offset}.`,
        tag,
      );
    }

    const length = Number(rawLength);
    const valueStart = offset + 4;
    const valueEnd = valueStart + length;

    if (valueEnd > total) {
      throw new DeshiQrError(
        "BAD_TLV",
        `Malformed payload: tag ${tag} claims ${length} characters but only ${total - valueStart} remain.`,
        tag,
      );
    }

    fields.push({ tag, value: slice(valueStart, valueEnd) });
    offset = valueEnd;
  }

  return fields;
}

/** The fields and the detected length unit of a parsed payload level. */
export interface ParsedPayload {
  fields: Field[];
  /** The length unit that made `encodeFields(fields, mode) === payload`. */
  mode: LengthMode;
}

/**
 * Parse a payload and detect how its `LL` lengths are counted.
 *
 * The EMVCo rule is UTF-8 bytes, so `"bytes"` is tried first; a payload that
 * only round-trips when lengths are counted in characters (a legacy producer)
 * falls back to `"chars"`. All-ASCII payloads round-trip in both modes and
 * therefore detect as `"bytes"` (their encoding is identical either way).
 *
 * The payload must re-encode to itself in the detected mode; if neither mode
 * round-trips, the `"bytes"` attempt's error is thrown (keeping `BAD_TLV`).
 */
export function parseWithMode(payload: string): ParsedPayload {
  const text = normalize(payload);
  if (text.length === 0) {
    throw new DeshiQrError("EMPTY_PAYLOAD", "The payload is empty.");
  }

  let firstError: DeshiQrError | undefined;
  for (const mode of ["bytes", "chars"] as const) {
    try {
      const fields = parseInMode(text, mode);
      if (encodeFields(fields, mode) === text) return { fields, mode };
    } catch (error) {
      if (firstError === undefined) {
        firstError = DeshiQrError.is(error)
          ? error
          : new DeshiQrError("BAD_TLV", error instanceof Error ? error.message : "Malformed payload.");
      }
    }
  }

  if (firstError !== undefined) throw firstError;
  throw new DeshiQrError("BAD_TLV", "Malformed payload: unrecognised length encoding.");
}

/** Detect only the length unit of a payload level. */
export function detectLengthMode(payload: string): LengthMode {
  return parseWithMode(payload).mode;
}

/**
 * Parse a payload level into its `{tag, value}` fields. Strict: a malformed
 * field throws `BAD_TLV` instead of being silently truncated.
 *
 * Without a mode the length unit is auto-detected (bytes first, then chars).
 * Nested templates are plain values here — call `parseSubfields` on them when
 * you need their subtree.
 */
export function parse(payload: string, mode?: LengthMode): Field[] {
  if (mode === undefined) return parseWithMode(payload).fields;

  const text = normalize(payload);
  if (text.length === 0) {
    throw new DeshiQrError("EMPTY_PAYLOAD", "The payload is empty.");
  }
  return parseInMode(text, mode);
}

/** Encode one field as `TTLLVV…`; the length unit defaults to UTF-8 bytes. */
export function encodeField(field: Field, mode: LengthMode = DEFAULT_LENGTH_MODE): string {
  const { tag, value } = field;
  if (!TAG_RE.test(tag)) {
    throw new DeshiQrError("BAD_TLV", `Malformed payload: invalid tag "${tag}".`, tag);
  }
  if (typeof value !== "string") {
    throw new DeshiQrError("BAD_VALUE", `Value for tag ${tag} must be a string.`, tag);
  }
  const length = valueLength(value, mode);
  if (length > MAX_FIELD_LENGTH) {
    throw new DeshiQrError(
      "BAD_VALUE",
      `Value for tag ${tag} is longer than ${MAX_FIELD_LENGTH} characters.`,
      tag,
    );
  }
  return tag + String(length).padStart(2, "0") + value;
}

/** Encode a list of fields back into a payload level; defaults to UTF-8 bytes. */
export function encodeFields(fields: readonly Field[], mode: LengthMode = DEFAULT_LENGTH_MODE): string {
  let out = "";
  for (const field of fields) out += encodeField(field, mode);
  return out;
}

/** First occurrence of a tag, or undefined. */
export function findField(fields: readonly Field[], tag: string): Field | undefined {
  return fields.find((field) => field.tag === tag);
}

/** Value of the first occurrence of a tag, or null. */
export function findValue(fields: readonly Field[], tag: string): string | null {
  const field = findField(fields, tag);
  return field ? field.value : null;
}

/**
 * Parse a nested template value; an empty value is an empty (valid) template.
 * Pass the parent payload's mode to keep a template in the same length unit;
 * without one the unit is auto-detected.
 */
export function parseSubfields(value: string, mode?: LengthMode): Field[] {
  if (value.length === 0) return [];
  return parse(value, mode);
}

/** Insert a field so the level stays in ascending numeric tag order. */
export function insertFieldSorted(fields: Field[], field: Field): void {
  const index = fields.findIndex((existing) => Number(existing.tag) > Number(field.tag));
  if (index === -1) fields.push(field);
  else fields.splice(index, 0, field);
}
