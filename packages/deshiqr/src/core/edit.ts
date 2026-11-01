import { crc16 } from "./crc.ts";
import { type DeshiQrCode, type DeshiQrIssue, DeshiQrError } from "./errors.ts";
import {
  ALIASES,
  CHECKSUM_TAG,
  IDENTITY_PATHS,
  MAX_AMOUNT,
  MAX_PAYLOAD_LENGTH,
  PARSED_TEMPLATE_TAGS,
  TAG_PATH_RE,
} from "./fields.ts";
import {
  type Field,
  type LengthMode,
  type ParsedPayload,
  encodeFields,
  insertFieldSorted,
  normalize,
  parseSubfields,
  parseWithMode,
  valueLength,
  MAX_FIELD_LENGTH,
} from "./tlv.ts";
import { filterWarnings, validate } from "./validate.ts";

/** A single edit value: a string, a number, or `null` to remove the tag. */
export type EditValue = string | number | null;

/**
 * Everything `update()` accepts as edits. Keys are named aliases (`amount`,
 * `name`, …) or tag paths (`"54"`, `"62/01"`, `"26/03"`, …); when both name the
 * same tag, the tag path wins.
 */
export interface PayloadEdits {
  [aliasOrTagPath: string]: EditValue;
}

/** Options for `update()`. */
export interface UpdateOptions {
  /**
   * Which warnings to surface: `true` (default) for all, `false` for none, or an
   * array of tags/paths whose warnings should be suppressed. Suppression matches
   * the issue's `tag` exactly (`"59"`, `"62/01"`, …).
   */
  warnings?: boolean | string[];
  /** Where warnings go. Defaults to `console.warn`. */
  onWarning?: (issue: DeshiQrIssue) => void;
}

/** Message used for every RISKY_EDIT warning. */
export const RISKY_EDIT_MESSAGE =
  "Editing the account/name can mislead payers; only edit what you own.";

const AMOUNT_INPUT_RE = /^\d+(?:\.\d+)?$/;
const HEX4_RE = /^[0-9A-Fa-f]{4}$/;

function badAmount(message: string): DeshiQrError {
  return new DeshiQrError("BAD_AMOUNT", message, "54");
}

function decimalPlaces(text: string): number {
  const dot = text.indexOf(".");
  return dot === -1 ? 0 : text.length - dot - 1;
}

/** `500` / `"500"` / `"1.5"` → `"500.00"` / `"500.00"` / `"1.50"`. Never rounds. */
function formatAmount(raw: number | string): string {
  let text: string;
  if (typeof raw === "number") {
    if (!Number.isFinite(raw)) throw badAmount("Amount must be a number or a numeric string.");
    if (raw <= 0) throw badAmount("Amount must be greater than zero.");
    if (raw > MAX_AMOUNT) throw badAmount("Amount must not exceed 99999999.99.");
    text = String(raw);
  } else {
    text = raw;
  }

  if (!AMOUNT_INPUT_RE.test(text)) throw badAmount("Amount must be a number or a numeric string.");
  const numeric = Number(text);
  if (!Number.isFinite(numeric)) throw badAmount("Amount must be a number or a numeric string.");
  if (numeric <= 0) throw badAmount("Amount must be greater than zero.");
  if (numeric > MAX_AMOUNT) throw badAmount("Amount must not exceed 99999999.99.");
  if (decimalPlaces(text) > 2) throw badAmount("Amount must have at most two decimal places.");

  const [wholePart, fractionPart = ""] = text.split(".");
  const whole = wholePart.replace(/^0+(?=\d)/, "");
  const fraction = (fractionPart + "00").slice(0, 2);
  return `${whole}.${fraction}`;
}

function coerceValue(path: string, raw: unknown): string | null {
  if (raw === null) return null;
  if (typeof raw === "number") {
    if (path === "54") return formatAmount(raw);
    if (!Number.isFinite(raw)) {
      throw new DeshiQrError(
        "BAD_VALUE",
        `Value for tag ${path} must be a string, a number or null.`,
        path,
      );
    }
    return String(raw);
  }
  if (typeof raw === "string") {
    return path === "54" ? formatAmount(raw) : raw;
  }
  throw new DeshiQrError(
    "BAD_VALUE",
    `Value for tag ${path} must be a string, a number or null.`,
    path,
  );
}

interface ResolvedEdit {
  path: string;
  value: string | null;
}

interface EditPlan {
  aliasEdits: ResolvedEdit[];
  tagPathEdits: ResolvedEdit[];
  touched54: boolean;
  touched01: boolean;
}

function depth(path: string): number {
  let count = 0;
  for (const character of path) if (character === "/") count += 1;
  return count;
}

function comparePaths(a: string, b: string): number {
  const depthDifference = depth(a) - depth(b);
  if (depthDifference !== 0) return depthDifference;
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

function resolveEdits(edits: unknown): EditPlan {
  const aliasEdits: ResolvedEdit[] = [];
  const tagPathEdits: ResolvedEdit[] = [];

  if (edits !== undefined && edits !== null) {
    if (typeof edits !== "object" || Array.isArray(edits)) {
      throw new DeshiQrError("BAD_VALUE", "Edits must be an object of tag paths/aliases.");
    }

    for (const [key, rawValue] of Object.entries(edits)) {
      const isTagPath = TAG_PATH_RE.test(key);
      const isAlias = Object.prototype.hasOwnProperty.call(ALIASES, key);
      const path = isTagPath ? key : isAlias ? (ALIASES[key] as string) : null;

      if (path === null) {
        throw new DeshiQrError("BAD_TAG", `Invalid tag path "${key}".`, key);
      }
      if (path === CHECKSUM_TAG || path.startsWith(`${CHECKSUM_TAG}/`)) {
        throw new DeshiQrError(
          "BAD_TAG",
          "Tag 63 is the checksum and cannot be edited.",
          CHECKSUM_TAG,
        );
      }

      const edit: ResolvedEdit = { path, value: coerceValue(path, rawValue) };
      if (isTagPath) tagPathEdits.push(edit);
      else aliasEdits.push(edit);
    }
  }

  const tagPathTargets = new Set(tagPathEdits.map((edit) => edit.path));
  const keptAliasEdits = aliasEdits.filter((edit) => !tagPathTargets.has(edit.path));
  tagPathEdits.sort((a, b) => comparePaths(a.path, b.path));

  return {
    aliasEdits: keptAliasEdits,
    tagPathEdits,
    touched54: [...keptAliasEdits, ...tagPathEdits].some((edit) => edit.path === "54"),
    touched01: [...keptAliasEdits, ...tagPathEdits].some((edit) => edit.path === "01"),
  };
}

function assertNoDuplicateTags(fields: readonly Field[], mode: LengthMode): void {
  const seenTopLevel = new Set<string>();
  for (const field of fields) {
    if (seenTopLevel.has(field.tag)) {
      throw new DeshiQrError(
        "DUPLICATE_TAG",
        `Tag ${field.tag} appears more than once.`,
        field.tag,
      );
    }
    seenTopLevel.add(field.tag);
  }

  for (const tag of PARSED_TEMPLATE_TAGS) {
    const field = fields.find((candidate) => candidate.tag === tag);
    if (!field) continue;
    let children: Field[];
    try {
      children = parseSubfields(field.value, mode);
    } catch {
      continue; // an unparseable template is reported by validation
    }
    const seenNested = new Set<string>();
    for (const child of children) {
      const path = `${tag}/${child.tag}`;
      if (seenNested.has(child.tag)) {
        throw new DeshiQrError("DUPLICATE_TAG", `Tag ${path} appears more than once.`, path);
      }
      seenNested.add(child.tag);
    }
  }
}

function applyAt(
  fields: Field[],
  segments: string[],
  fullPath: string,
  value: string | null,
  mode: LengthMode,
): void {
  const head = segments[0] as string;
  const rest = segments.slice(1);
  const index = fields.findIndex((field) => field.tag === head);

  if (rest.length === 0) {
    if (value === null) {
      if (index !== -1) {
        for (let i = fields.length - 1; i >= 0; i -= 1) {
          if (fields[i]?.tag === head) fields.splice(i, 1);
        }
      }
      return;
    }
    if (valueLength(value, mode) > MAX_FIELD_LENGTH) {
      throw new DeshiQrError(
        "BAD_VALUE",
        `Value for tag ${fullPath} is longer than ${MAX_FIELD_LENGTH} characters.`,
        fullPath,
      );
    }
    if (index !== -1) fields[index] = { tag: head, value };
    else insertFieldSorted(fields, { tag: head, value });
    return;
  }

  const parent = index === -1 ? undefined : fields[index];
  if (!parent) {
    throw new DeshiQrError(
      "BAD_TAG",
      `Tag ${fullPath} has a missing or invalid parent template.`,
      fullPath,
    );
  }

  let children: Field[];
  try {
    children = parseSubfields(parent.value, mode);
  } catch {
    throw new DeshiQrError(
      "BAD_TAG",
      `Tag ${fullPath} has a missing or invalid parent template.`,
      fullPath,
    );
  }

  applyAt(children, rest, fullPath, value, mode);

  if (children.length === 0) {
    fields.splice(index, 1);
    return;
  }

  const encoded = encodeFields(children, mode);
  if (valueLength(encoded, mode) > MAX_FIELD_LENGTH) {
    throw new DeshiQrError(
      "BAD_VALUE",
      `Value for tag ${fullPath} is longer than ${MAX_FIELD_LENGTH} characters.`,
      fullPath,
    );
  }
  fields[index] = { tag: head, value: encoded };
}

function setTopLevel(fields: Field[], tag: string, value: string): void {
  const index = fields.findIndex((field) => field.tag === tag);
  if (index !== -1) fields[index] = { tag, value };
  else insertFieldSorted(fields, { tag, value });
}

function defaultWarningSink(warning: DeshiQrIssue): void {
  const suffix = warning.tag === undefined ? "" : ` (${warning.tag})`;
  console.warn(`deshiqr: ${warning.code}${suffix}: ${warning.message}`);
}

/**
 * Load a Bangla QR payload, edit any tags, get the new payload back.
 *
 * Accepts named aliases (`amount`, `name`, `reference`, …) and raw tag paths
 * (`"54"`, `"62/01"`, `"26/03"`, …); `null` removes a tag, new tags are inserted
 * in ascending numeric order, and the checksum is always recomputed. The point
 * of initiation (`01`) follows the amount unless it was edited explicitly.
 *
 * Field lengths may be UTF-8 byte counts (the EMVCo/NPSB rule) or legacy
 * character counts; the unit is auto-detected and the result is re-encoded in
 * the same unit, so non-ASCII (Bangla) payloads round-trip either way.
 *
 * @throws {DeshiQrError} on any invalid payload, edit, or resulting payload.
 */
export function update(
  payload: string,
  edits?: PayloadEdits | null,
  options?: UpdateOptions,
): string {
  // ---- input checks (throw, in this order) ------------------------------
  const text = normalize(payload);
  if (text.length === 0) {
    throw new DeshiQrError("EMPTY_PAYLOAD", "The payload is empty.");
  }
  if (text.length > MAX_PAYLOAD_LENGTH) {
    throw new DeshiQrError("UNSUPPORTED", "The payload is longer than 4096 characters.");
  }

  let parsed: ParsedPayload;
  try {
    parsed = parseWithMode(text);
  } catch (error) {
    if (DeshiQrError.is(error)) throw error;
    throw new DeshiQrError("BAD_TLV", error instanceof Error ? error.message : "Malformed payload.");
  }
  const fields = parsed.fields;
  const mode = parsed.mode;

  const last = fields[fields.length - 1];
  if (!last || last.tag !== CHECKSUM_TAG) {
    throw new DeshiQrError(
      "MISSING_FIELD",
      "The payload does not end with a checksum (tag 63).",
      CHECKSUM_TAG,
    );
  }
  if (!HEX4_RE.test(last.value)) {
    throw new DeshiQrError("BAD_TLV", "The checksum must be four hexadecimal characters.", CHECKSUM_TAG);
  }
  if (crc16(text.slice(0, -4)) !== last.value.toUpperCase()) {
    throw new DeshiQrError("CHECKSUM_MISMATCH", "The checksum does not match.", CHECKSUM_TAG);
  }

  assertNoDuplicateTags(fields, mode);

  // ---- apply edits -------------------------------------------------------
  const plan = resolveEdits(edits);
  const working = fields.filter((field) => field.tag !== CHECKSUM_TAG);

  for (const edit of plan.aliasEdits) {
    applyAt(working, edit.path.split("/"), edit.path, edit.value, mode);
  }
  for (const edit of plan.tagPathEdits) {
    applyAt(working, edit.path.split("/"), edit.path, edit.value, mode);
  }

  // ---- point of initiation follows the amount ---------------------------
  if (plan.touched54 && !plan.touched01) {
    const hasAmount = working.some((field) => field.tag === "54");
    setTopLevel(working, "01", hasAmount ? "12" : "11");
  }

  // ---- re-seal (same length unit as the input) --------------------------
  const body = `${encodeFields(working, mode)}${CHECKSUM_TAG}04`;
  const result = body + crc16(body);

  // ---- validate the result: errors throw, warnings are surfaced ---------
  const report = validate(result);
  if (!report.ok) {
    const first = report.errors[0] as DeshiQrIssue;
    throw new DeshiQrError(first.code as DeshiQrCode, first.message, first.tag);
  }

  const editedPaths = new Set([...plan.aliasEdits, ...plan.tagPathEdits].map((edit) => edit.path));
  const warnings: DeshiQrIssue[] = IDENTITY_PATHS.filter((path) => editedPaths.has(path))
    .slice()
    .sort()
    .map((path) => ({ code: "RISKY_EDIT", message: RISKY_EDIT_MESSAGE, tag: path }));
  warnings.push(...report.warnings);

  const safeOptions: UpdateOptions =
    options !== null && typeof options === "object" ? options : {};
  const surfaced = filterWarnings(warnings, safeOptions.warnings);
  const onWarning = safeOptions.onWarning ?? defaultWarningSink;
  for (const warning of surfaced) onWarning(warning);

  return result;
}
