import { crc16 } from "./crc.ts";
import { type DeshiQrIssue, DeshiQrError } from "./errors.ts";
import {
  CHECKSUM_TAG,
  MAX_PAYLOAD_LENGTH,
  PARSED_TEMPLATE_TAGS,
  RECOMMENDED_TAGS,
  fieldWarnings,
} from "./fields.ts";
import {
  type Field,
  type ParsedPayload,
  findValue,
  normalize,
  parseSubfields,
  parseWithMode,
} from "./tlv.ts";

export type { DeshiQrIssue } from "./errors.ts";

/** The result of `validate()`: errors block, warnings are advisory. */
export interface ValidationReport {
  /** True when `errors` is empty. Warnings do not make a payload invalid. */
  ok: boolean;
  errors: DeshiQrIssue[];
  warnings: DeshiQrIssue[];
}

/** Options for both `validate()` and the warnings surfaced by `update()`. */
export interface ValidateOptions {
  /**
   * Which warnings to return/show: `true` (default) for all, `false` for none,
   * or an array of tags/paths whose warnings should be suppressed.
   * Suppression matches the issue's `tag` exactly (`"59"`, `"62/01"`, …).
   */
  warnings?: boolean | string[];
}

const HEX4_RE = /^[0-9A-Fa-f]{4}$/;

function issue(code: string, message: string, tag?: string): DeshiQrIssue {
  return tag === undefined ? { code, message } : { code, message, tag };
}

/** Apply the `warnings` option to a list of issues. */
export function filterWarnings(
  warnings: readonly DeshiQrIssue[],
  option: boolean | string[] | undefined,
): DeshiQrIssue[] {
  if (option === false) return [];
  if (Array.isArray(option)) {
    return warnings.filter((warning) => warning.tag === undefined || !option.includes(warning.tag));
  }
  return warnings.slice();
}

/**
 * Non-throwing, thorough validation. Collects every problem instead of stopping
 * at the first one, so a form can show everything that is wrong at once.
 *
 * `ok` is true when there are no errors. Warnings are filtered by the
 * `warnings` option; errors are always returned in full. `validate` never throws.
 */
export function validate(payload: string, options?: ValidateOptions): ValidationReport {
  const warningsOption: boolean | string[] | undefined =
    options !== null && typeof options === "object" ? options.warnings : undefined;
  return validatePayload(payload, warningsOption);
}

function validatePayload(
  payload: string,
  warningsOption: boolean | string[] | undefined,
): ValidationReport {
  const errors: DeshiQrIssue[] = [];
  const warnings: DeshiQrIssue[] = [];

  const report = (): ValidationReport => ({
    ok: errors.length === 0,
    errors,
    warnings: filterWarnings(warnings, warningsOption),
  });

  const text = normalize(payload);
  if (text.length === 0) {
    errors.push(issue("EMPTY_PAYLOAD", "The payload is empty."));
    return report();
  }
  if (text.length > MAX_PAYLOAD_LENGTH) {
    errors.push(issue("UNSUPPORTED", "The payload is longer than 4096 characters."));
    return report();
  }

  let parsed: ParsedPayload;
  try {
    parsed = parseWithMode(text);
  } catch (error) {
    if (DeshiQrError.is(error)) errors.push(issue(error.code, error.message, error.tag));
    else errors.push(issue("BAD_TLV", error instanceof Error ? error.message : "Malformed payload."));
    return report();
  }
  const fields = parsed.fields;
  const mode = parsed.mode;

  // ---- checksum ---------------------------------------------------------
  const last = fields[fields.length - 1];
  if (!last || last.tag !== CHECKSUM_TAG) {
    errors.push(issue("MISSING_FIELD", "The payload does not end with a checksum (tag 63).", CHECKSUM_TAG));
  } else if (!HEX4_RE.test(last.value)) {
    errors.push(issue("BAD_TLV", "The checksum must be four hexadecimal characters.", CHECKSUM_TAG));
  } else if (crc16(text.slice(0, -4)) !== last.value.toUpperCase()) {
    errors.push(issue("CHECKSUM_MISMATCH", "The checksum does not match.", CHECKSUM_TAG));
  }

  // ---- nested templates (26 and 62 are parsed; 80/81 stay opaque) ------
  const parsedTemplates = new Map<string, Field[] | null>();
  for (const tag of PARSED_TEMPLATE_TAGS) {
    const field = fields.find((candidate) => candidate.tag === tag);
    if (!field) continue;
    try {
      parsedTemplates.set(tag, parseSubfields(field.value, mode));
    } catch {
      parsedTemplates.set(tag, null);
    }
  }

  // ---- duplicate tags ---------------------------------------------------
  const seenTopLevel = new Set<string>();
  for (const field of fields) {
    if (seenTopLevel.has(field.tag)) {
      errors.push(issue("DUPLICATE_TAG", `Tag ${field.tag} appears more than once.`, field.tag));
    }
    seenTopLevel.add(field.tag);
  }
  for (const tag of PARSED_TEMPLATE_TAGS) {
    const children = parsedTemplates.get(tag);
    if (!children) continue;
    const seenNested = new Set<string>();
    for (const child of children) {
      const path = `${tag}/${child.tag}`;
      if (seenNested.has(child.tag)) {
        errors.push(issue("DUPLICATE_TAG", `Tag ${path} appears more than once.`, path));
      }
      seenNested.add(child.tag);
    }
  }
  for (const tag of PARSED_TEMPLATE_TAGS) {
    if (parsedTemplates.get(tag) === null) {
      errors.push(issue("BAD_TLV", `Malformed payload: tag ${tag} is not a valid TLV template.`, tag));
    }
  }

  // ---- warnings ---------------------------------------------------------
  const present = new Set(fields.map((field) => field.tag));
  for (const tag of RECOMMENDED_TAGS) {
    if (!present.has(tag)) warnings.push(issue("MISSING_TAG", `Missing recommended tag ${tag}.`, tag));
  }

  const initiation = findValue(fields, "01");
  const amountPresent = present.has("54");

  for (const field of fields) {
    const { tag, value } = field;
    if (tag === CHECKSUM_TAG) continue;

    if (PARSED_TEMPLATE_TAGS.includes(tag)) {
      const children = parsedTemplates.get(tag);
      if (!children) continue;
      for (const child of children) {
        warnings.push(...fieldWarnings(`${tag}/${child.tag}`, child.value));
      }
      if (tag === "26" && !children.some((child) => child.tag === "00")) {
        warnings.push(issue("UNKNOWN_INSTITUTION", 'Unverified institution "".', "26/00"));
      }
      continue;
    }

    // 80/81 are opaque token templates: never parsed, never warned about.
    if (tag === "80" || tag === "81") continue;

    warnings.push(...fieldWarnings(tag, value));

    if (tag === "01" && value === "12" && !amountPresent) {
      warnings.push(issue("DYNAMIC_WITHOUT_AMOUNT", "Dynamic QR has no amount (tag 54).", "54"));
    } else if (tag === "54" && initiation === "11") {
      warnings.push(issue("STATIC_WITH_AMOUNT", "Static QR should not carry an amount (tag 54).", "54"));
    }
  }

  return report();
}
