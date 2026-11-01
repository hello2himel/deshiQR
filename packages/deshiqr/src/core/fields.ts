import type { DeshiQrIssue } from "./errors.ts";

/** Tag that carries the CRC-16 checksum. It is always recomputed after edits. */
export const CHECKSUM_TAG = "63";

/** Payloads are a few hundred characters; anything longer is not a Bangla QR payload. */
export const MAX_PAYLOAD_LENGTH = 4096;

/** Largest amount allowed in tag 54 (BDT). */
export const MAX_AMOUNT = 99_999_999.99;

/** A tag path: two-digit tag, optionally nested with `/` segments. */
export const TAG_PATH_RE = /^\d{2}(?:\/\d{2})*$/;

/** Tag 54 must be a decimal with exactly two decimal places. */
export const AMOUNT_FIELD_RE = /^\d{1,8}\.\d{2}$/;

/** Named edit aliases → tag path. */
export const ALIASES: Readonly<Record<string, string>> = {
  amount: "54",
  currency: "53",
  country: "58",
  mcc: "52",
  name: "59",
  city: "60",
  reference: "62/01",
  customerLabel: "62/06",
  account: "26/03",
  institution: "26/00",
};

/** Tags whose absence produces a MISSING_TAG warning, in this order. */
export const RECOMMENDED_TAGS: readonly string[] = ["00", "01", "59"];

/** Tag values that are TLV subtrees. */
export const TEMPLATE_TAGS: readonly string[] = ["26", "62", "80", "81"];

/** Templates whose sub-tags are parsed and validated. 80/81 are opaque. */
export const PARSED_TEMPLATE_TAGS: readonly string[] = ["26", "62"];

/** Editing these fields is risky: the account/name is what payers see. */
export const IDENTITY_PATHS: readonly string[] = ["26/00", "26/03", "59"];

/** Known ISO 4217 numeric currency codes. */
export const KNOWN_CURRENCIES: readonly string[] = ["050", "356", "764", "840", "978"];

/** Known merchant category codes. */
export const KNOWN_MCCS: readonly string[] = ["5411", "6016", "5999"];

/**
 * Known institution AIDs (tag 26/00). The parser is provider-agnostic; only the
 * NPSB Bangla QR AID is verified, every other provider is supported with an
 * UNKNOWN_INSTITUTION warning.
 */
export const VERIFIED_INSTITUTION_AIDS: readonly string[] = ["bd.org.bb.npsb"];

/** Documented syntax for one tag/path. */
export interface FieldSpec {
  /** Shortest allowed value, in characters. */
  minLength?: number;
  /** Longest allowed value, in characters. Exceeding it is FIELD_TOO_LONG. */
  maxLength?: number;
  /** Character-set / shape check. */
  pattern?: RegExp;
}

/**
 * Fields where a too-long value is reported as FIELD_TOO_LONG (rather than as a
 * syntax error). Fixed-width fields report the shape mismatch directly.
 */
const LENGTH_REPORTED_PATHS: ReadonlySet<string> = new Set([
  "26/00",
  "59",
  "60",
  "62/01",
  "26/03",
]);

/**
 * The documented field table. A path that is not in here is an UNKNOWN_TAG
 * warning (the tag is still allowed and preserved).
 */
export const FIELD_SPECS: Readonly<Record<string, FieldSpec>> = {
  "00": { pattern: /^01$/ },
  "01": { pattern: /^(?:11|12)$/ },
  "26": {},
  "26/00": { maxLength: 32, pattern: /^[\x20-\x7E]*$/ },
  "26/01": { pattern: /^\d{2}$/ },
  "26/02": { pattern: /^\d{4}$/ },
  "26/03": { minLength: 4, maxLength: 34, pattern: /^[0-9A-Za-z]+$/ },
  "52": { pattern: /^\d{4}$/ },
  "53": { pattern: /^\d{3}$/ },
  "54": {},
  "58": { pattern: /^[A-Za-z]{2}$/ },
  "59": { minLength: 1, maxLength: 25 },
  "60": { minLength: 1, maxLength: 15 },
  "62": {},
  "62/01": { minLength: 1, maxLength: 32, pattern: /^[\x20-\x7E]+$/ },
  "62/06": {},
  "80": {},
  "80/00": {},
  "80/01": {},
  "81": {},
  "81/00": {},
  "81/01": {},
  "63": { pattern: /^[0-9A-Fa-f]{4}$/ },
};

/** True when a top-level tag holds a TLV subtree. */
export function isTemplateTag(tag: string): boolean {
  return TEMPLATE_TAGS.includes(tag);
}

/** True when a template's sub-tags are parsed/validated (80/81 are opaque). */
export function isParsedTemplateTag(tag: string): boolean {
  return PARSED_TEMPLATE_TAGS.includes(tag);
}

function issue(code: string, message: string, tag?: string): DeshiQrIssue {
  return tag === undefined ? { code, message } : { code, message, tag };
}

function badValue(path: string, value: string): DeshiQrIssue {
  return issue("BAD_FIELD_VALUE", `Unexpected value "${value}" for tag ${path}.`, path);
}

/**
 * Warning-level checks for one documented field. Syntax problems are reported
 * once (length first where the documented limit is about length, then shape);
 * "known value" warnings are only reported when the syntax itself is fine.
 */
export function fieldWarnings(path: string, value: string): DeshiQrIssue[] {
  const spec = FIELD_SPECS[path];
  if (!spec) {
    return [issue("UNKNOWN_TAG", `Unknown tag ${path}.`, path)];
  }

  if (path === "54") {
    if (!AMOUNT_FIELD_RE.test(value)) return [badValue(path, value)];
    const amount = Number(value);
    if (!Number.isFinite(amount) || amount <= 0 || amount > MAX_AMOUNT) return [badValue(path, value)];
    return [];
  }

  if (LENGTH_REPORTED_PATHS.has(path) && spec.maxLength !== undefined && value.length > spec.maxLength) {
    return [issue("FIELD_TOO_LONG", `Value for tag ${path} is longer than ${spec.maxLength} characters.`, path)];
  }
  if (spec.minLength !== undefined && value.length < spec.minLength) {
    return [badValue(path, value)];
  }
  if (spec.pattern && !spec.pattern.test(value)) {
    return [badValue(path, value)];
  }

  switch (path) {
    case "53":
      if (!KNOWN_CURRENCIES.includes(value)) {
        return [issue("UNKNOWN_CURRENCY", `Unknown currency "${value}".`, path)];
      }
      return [];
    case "58":
      if (value !== "BD") {
        return [issue("NON_BD_COUNTRY", `Country is "${value}", not "BD".`, path)];
      }
      return [];
    case "52":
      if (!KNOWN_MCCS.includes(value)) {
        return [issue("UNKNOWN_MCC", `Unknown merchant category code "${value}".`, path)];
      }
      return [];
    case "26/00":
      if (!VERIFIED_INSTITUTION_AIDS.includes(value)) {
        return [issue("UNKNOWN_INSTITUTION", `Unverified institution "${value}".`, path)];
      }
      return [];
    default:
      return [];
  }
}
