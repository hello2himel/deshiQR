/**
 * Internal barrel for the payload core. The public API is re-exported from
 * `src/index.ts`. This module is the single source of truth for the browser bundle
 * (`src/global.ts`) and the Python port.
 */
export { DeshiQrError } from "./errors.ts";
export type { DeshiQrCode, DeshiQrIssue } from "./errors.ts";

export { update, RISKY_EDIT_MESSAGE } from "./edit.ts";
export type { EditValue, PayloadEdits, UpdateOptions } from "./edit.ts";

export { validate, filterWarnings } from "./validate.ts";
export type { ValidateOptions, ValidationReport } from "./validate.ts";

export { crc16 } from "./crc.ts";
export {
  DEFAULT_LENGTH_MODE,
  MAX_FIELD_LENGTH,
  byteLength,
  detectLengthMode,
  encodeField,
  encodeFields,
  findField,
  findValue,
  insertFieldSorted,
  isTag,
  normalize,
  parse,
  parseSubfields,
  parseWithMode,
  valueLength,
} from "./tlv.ts";
export type { Field, LengthMode, ParsedPayload } from "./tlv.ts";

export {
  ALIASES,
  AMOUNT_FIELD_RE,
  CHECKSUM_TAG,
  FIELD_SPECS,
  IDENTITY_PATHS,
  KNOWN_CURRENCIES,
  VERIFIED_INSTITUTION_AIDS,
  KNOWN_MCCS,
  MAX_AMOUNT,
  MAX_PAYLOAD_LENGTH,
  PARSED_TEMPLATE_TAGS,
  RECOMMENDED_TAGS,
  TAG_PATH_RE,
  TEMPLATE_TAGS,
  fieldWarnings,
  isParsedTemplateTag,
  isTemplateTag,
} from "./fields.ts";
export type { FieldSpec } from "./fields.ts";
