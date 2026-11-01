/**
 * Stable, machine-readable error codes.
 *
 * `update()` throws a `DeshiQrError` carrying one of these codes; `validate()`
 * reports the error codes in `errors` and the warning codes in `warnings`.
 */
export type DeshiQrCode =
  | "EMPTY_PAYLOAD"
  | "UNSUPPORTED"
  | "BAD_TLV"
  | "MISSING_FIELD"
  | "CHECKSUM_MISMATCH"
  | "DUPLICATE_TAG"
  | "BAD_AMOUNT"
  | "BAD_TAG"
  | "BAD_VALUE";

/**
 * One problem found by `validate()` (in `errors` or `warnings`) or surfaced to
 * `update()`'s `onWarning` callback.
 */
export interface DeshiQrIssue {
  /** Stable code, e.g. `CHECKSUM_MISMATCH` or `MISSING_TAG`. */
  code: string;
  /** Human-readable explanation. */
  message: string;
  /** Offending tag or tag path, e.g. `"59"`, `"62/01"`, `"26/03"`. */
  tag?: string;
}

/**
 * Every failure in deshiQR is a `DeshiQrError` with a machine-readable `code`,
 * a human-readable `message`, and the offending tag/path when there is one.
 */
export class DeshiQrError extends Error {
  readonly code: DeshiQrCode;
  readonly tag?: string;

  constructor(code: DeshiQrCode, message: string, tag?: string) {
    super(message);
    this.name = "DeshiQrError";
    this.code = code;
    if (tag !== undefined) this.tag = tag;
  }

  static is(error: unknown): error is DeshiQrError {
    return error instanceof DeshiQrError;
  }
}
