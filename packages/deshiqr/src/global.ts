/**
 * Browser global entry point for plain `<script src>` usage.
 *
 * The IIFE build (`dist/deshiqr.global.js`) exposes one global, `DeshiQR`, with
 * exactly the two functions (and the error class) of the package:
 *
 *   DeshiQR.update(payload, edits, options?) -> string
 *   DeshiQR.validate(payload, options?)      -> { ok, errors, warnings }
 */
export * from "./index.ts";
