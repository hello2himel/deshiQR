/**
 * Browser-global smoke test: the built IIFE bundle (`dist/deshiqr.global.js`)
 * must load in a bare browser-like context and expose exactly the public API.
 *
 * Run `pnpm build` first; the test is skipped when the bundle is missing.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { DYNAMIC_500_PAYLOAD, REFERENCE, STATIC_PAYLOAD } from "./fixtures.ts";

const PACKAGE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BUNDLE = resolve(PACKAGE_DIR, "dist/deshiqr.global.js");
const skip = existsSync(BUNDLE) ? false : "run `pnpm build` first";

interface GlobalApi {
  update: (payload: string, edits?: unknown, options?: unknown) => string;
  validate: (payload: string, options?: unknown) => { ok: boolean; errors: unknown[]; warnings: unknown[] };
  DeshiQrError: new (code: string, message: string) => Error;
}

function loadBundle(): Record<string, GlobalApi> {
  const code = readFileSync(BUNDLE, "utf8");
  const sandbox: Record<string, unknown> = { TextEncoder, TextDecoder, crypto: globalThis.crypto };
  vm.runInNewContext(code, sandbox, { filename: "deshiqr.global.js" });
  return sandbox as Record<string, GlobalApi>;
}

test("the bundle defines one global with exactly update, validate and DeshiQrError", { skip }, () => {
  const sandbox = loadBundle();
  const api = sandbox.DeshiQR as unknown as GlobalApi;
  assert.ok(api, "window.DeshiQR was not defined");
  assert.equal(typeof api.update, "function");
  assert.equal(typeof api.validate, "function");
  assert.equal(typeof api.DeshiQrError, "function");
  assert.deepEqual(Object.keys(api).sort(), ["DeshiQrError", "update", "validate"]);
});

test("the global bundle needs no DOM, no process and no require()", { skip }, () => {
  const code = readFileSync(BUNDLE, "utf8");
  assert.equal(/\brequire\s*\(/.test(code), false);
  assert.equal(/\bprocess\./.test(code), false);
  assert.equal(typeof loadBundle().DeshiQR, "object");
});

test("global update reproduces the pinned fixture byte for byte", { skip }, () => {
  const api = loadBundle().DeshiQR as unknown as GlobalApi;
  assert.equal(api.update(STATIC_PAYLOAD, { amount: 500, reference: REFERENCE }), DYNAMIC_500_PAYLOAD);
});

test("global validate returns a clean report for the static fixture", { skip }, () => {
  const api = loadBundle().DeshiQR as unknown as GlobalApi;
  const report = api.validate(STATIC_PAYLOAD);
  assert.deepEqual(JSON.parse(JSON.stringify(report)), { ok: true, errors: [], warnings: [] });
});

test("global update throws a coded DeshiQrError", { skip }, () => {
  const api = loadBundle().DeshiQR as unknown as GlobalApi;
  assert.throws(
    () => api.update(STATIC_PAYLOAD, { amount: -1 }),
    (error: unknown) =>
      error instanceof api.DeshiQrError &&
      (error as Error & { code: string }).code === "BAD_AMOUNT",
  );
});
