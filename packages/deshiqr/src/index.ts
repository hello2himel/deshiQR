/**
 * deshiqr — edit and validate Bangla QR (NPSB / EMVCo) payloads.
 *
 * Two functions, one job: load a payload, edit tags, get the new payload back.
 * QR rendering/decoding is intentionally out of scope — render the returned
 * payload with whatever QR library you already use.
 *
 * Zero dependencies, environment-agnostic (browser, Node, Deno, edge runtimes).
 */
export { update } from "./core/edit.ts";
export type { EditValue, PayloadEdits, UpdateOptions } from "./core/edit.ts";

export { validate } from "./core/validate.ts";
export type { ValidateOptions, ValidationReport } from "./core/validate.ts";

export { DeshiQrError } from "./core/errors.ts";
export type { DeshiQrCode, DeshiQrIssue } from "./core/errors.ts";
