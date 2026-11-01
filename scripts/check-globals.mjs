#!/usr/bin/env node
/**
 * Verifies the single browser (`<script src>`) bundle of the `deshiqr` package.
 *
 * A plain HTML page with no bundler must be able to load one file —
 * `dist/deshiqr.global.js` — and get exactly one global, `DeshiQR`, that exposes
 * the two public functions: `update` and `validate` (plus `DeshiQrError`).
 *
 * The bundle is executed in a bare `vm` context that only provides browser
 * primitives (TextEncoder/TextDecoder/crypto) and **no DOM**, so any accidental
 * Node dependency (`require`, `fs`, `process`) or top-level DOM access fails.
 *
 * Run after `pnpm build`: `node scripts/check-globals.mjs`
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PACKAGE_DIR = "packages/deshiqr";
const BUNDLE = `${PACKAGE_DIR}/dist/deshiqr.global.js`;

/** Synthetic fixtures from docs/demo-payloads.md — never use real merchant data here. */
const STATIC =
  "00020101021126470014bd.org.bb.npsb010202020420020311010000000005204601653030505802BD5910DEMO STORE6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304295D";
/** STATIC + amount 500 + reference — only tags 01 and 54/62-01 change. */
const DYNAMIC_500 =
  "00020101021226470014bd.org.bb.npsb010202020420020311010000000005204601653030505406500.005802BD5910DEMO STORE6005Dhaka62350125DEMOQR0VZeK2MfbVRI6w36osd0602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304F835";
const REFERENCE = "DEMOQR0VZeK2MfbVRI6w36osd";
/** A synthetic non-bKash layout: editing the amount changes 01 and 54 only. */
const GENERIC_STATIC =
  "00020101021126410022example.org.generic-qr0311017000000005204541153030505802BD5912GENERIC SHOP6006Sylhet6304818D";
const GENERIC_DYNAMIC_1250_50 =
  "00020101021226410022example.org.generic-qr03110170000000052045411530305054071250.505802BD5912GENERIC SHOP6006Sylhet630480A2";

let failures = 0;
function check(name, fn) {
  try {
    fn();
    console.log(`  ok  ${name}`);
  } catch (error) {
    failures += 1;
    console.error(`  FAIL ${name}`);
    console.error(`       ${error instanceof Error ? error.message : String(error)}`);
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

/** The browser-only primitives the bundle is allowed to use. Deliberately no DOM. */
function browserGlobals() {
  return { TextEncoder, TextDecoder, crypto: globalThis.crypto };
}

/** Load the IIFE bundle the way a browser would, into a fresh global scope. */
function loadBundle(code, extraGlobals = {}) {
  const sandbox = { ...browserGlobals(), ...extraGlobals };
  vm.runInNewContext(code, sandbox, { filename: BUNDLE });
  return sandbox;
}

assert(existsSync(resolve(ROOT, BUNDLE)), `${BUNDLE} is missing — run \`pnpm build\``);
const code = readFileSync(resolve(ROOT, BUNDLE), "utf8");
assert(!/\brequire\s*\(/.test(code), `${BUNDLE} contains require() — not a browser bundle`);
assert(!/\bprocess\./.test(code), `${BUNDLE} references process — not a browser bundle`);

console.log(`${BUNDLE} (window.DeshiQR)`);
const sandbox = loadBundle(code);
const DeshiQR = sandbox.DeshiQR;
assert(DeshiQR && typeof DeshiQR === "object", `global \`DeshiQR\` was not defined by ${BUNDLE}`);

check("defines exactly one global (`DeshiQR`)", () => {
  const extras = Object.keys(sandbox).filter(
    (key) => !["TextEncoder", "TextDecoder", "crypto"].includes(key),
  );
  assert(JSON.stringify(extras) === JSON.stringify(["DeshiQR"]), `globals=${extras.join(",")}`);
});

check("exposes exactly update, validate and DeshiQrError", () => {
  assert(typeof DeshiQR.update === "function", "missing update()");
  assert(typeof DeshiQR.validate === "function", "missing validate()");
  assert(typeof DeshiQR.DeshiQrError === "function", "missing DeshiQrError");
  assert(
    JSON.stringify(Object.keys(DeshiQR).sort()) === JSON.stringify(["DeshiQrError", "update", "validate"]),
    `exports=${Object.keys(DeshiQR).join(",")}`,
  );
});

check("no QR encoder, element or decode API is exposed", () => {
  for (const name of [
    "encode",
    "encodeFields",
    "toSvg",
    "toSvgPath",
    "toTerminal",
    "decode",
    "decodeSafe",
    "withAmount",
    "toStatic",
    "build",
    "seal",
    "newReference",
    "referenceFrom",
    "formatTaka",
    "maskAccount",
    "isBanglaQr",
    "institutionOf",
    "crc16",
    "parse",
    "DeshiQrPay",
    "defineDeshiQrPay",
  ]) {
    assert(DeshiQR[name] === undefined, `stale export ${name} is still exposed`);
  }
});

check("update() reproduces the pinned dynamic fixture byte for byte", () => {
  assert(
    DeshiQR.update(STATIC, { amount: 500, reference: REFERENCE }) === DYNAMIC_500,
    "updated payload differs from docs/demo-payloads.md",
  );
});

check("update() changes only tag 01 and 54 on a non-bKash layout", () => {
  assert(
    DeshiQR.update(GENERIC_STATIC, { amount: 1250.5 }) === GENERIC_DYNAMIC_1250_50,
    "provider-agnostic update mismatch",
  );
});

check("update(payload, {}) is a byte-identical no-op", () => {
  assert(DeshiQR.update(STATIC, {}) === STATIC, "no-op update changed the payload");
  assert(DeshiQR.update(STATIC) === STATIC, "omitted edits changed the payload");
});

check("update() throws a coded DeshiQrError", () => {
  let thrown = null;
  try {
    DeshiQR.update(STATIC, { amount: -1 });
  } catch (error) {
    thrown = error;
  }
  assert(thrown !== null, "expected update() to throw");
  assert(thrown instanceof DeshiQR.DeshiQrError, "not a DeshiQrError");
  assert(thrown.code === "BAD_AMOUNT", `code=${thrown.code}`);
});

check("validate() returns a clean report for the pinned fixture", () => {
  const report = DeshiQR.validate(STATIC);
  assert(
    JSON.stringify(report) === JSON.stringify({ ok: true, errors: [], warnings: [] }),
    `report=${JSON.stringify(report)}`,
  );
});

check("validate() reports a damaged checksum with a coded error", () => {
  const report = DeshiQR.validate(STATIC.slice(0, -4) + "0000");
  assert(report.ok === false, "expected ok=false");
  assert(
    report.errors.some((error) => error.code === "CHECKSUM_MISMATCH"),
    `codes=${report.errors.map((error) => error.code).join(",")}`,
  );
});

check("validate() reports warnings and honours suppression", () => {
  const tooLong = DeshiQR.update(STATIC, { city: "x".repeat(16) }, { warnings: false });
  const surfaced = DeshiQR.validate(tooLong);
  assert(surfaced.warnings.length === 1, `warnings=${JSON.stringify(surfaced.warnings)}`);
  assert(
    surfaced.warnings[0].code === "FIELD_TOO_LONG" && surfaced.warnings[0].tag === "60",
    `warning=${JSON.stringify(surfaced.warnings[0])}`,
  );
  const suppressed = DeshiQR.validate(tooLong, { warnings: ["60"] });
  assert(suppressed.warnings.length === 0, "suppression did not work");

  const damaged = DeshiQR.validate(STATIC.slice(0, -4) + "0000", { warnings: false });
  assert(damaged.warnings.length === 0, "warnings were not suppressed");
  assert(damaged.errors.some((error) => error.code === "CHECKSUM_MISMATCH"), "errors were dropped");
});

console.log("\npackage.json CDN fields and dist artifacts (single package)");
check("the build produces the documented dist artifacts", () => {
  for (const file of [
    "dist/index.js",
    "dist/index.cjs",
    "dist/index.d.ts",
    "dist/deshiqr.global.js",
  ]) {
    assert(existsSync(resolve(ROOT, PACKAGE_DIR, file)), `${PACKAGE_DIR}/${file} is missing`);
  }
  for (const removed of ["dist/element.js", "dist/element.d.ts"]) {
    assert(!existsSync(resolve(ROOT, PACKAGE_DIR, removed)), `${PACKAGE_DIR}/${removed} still exists`);
  }
});

check("package.json points unpkg/jsdelivr at the one browser bundle", () => {
  const manifest = JSON.parse(readFileSync(resolve(ROOT, PACKAGE_DIR, "package.json"), "utf8"));
  assert(manifest.name === "deshiqr", `name=${manifest.name}`);
  for (const field of ["unpkg", "jsdelivr"]) {
    assert(
      manifest[field] === "./dist/deshiqr.global.js",
      `${field}=${manifest[field]} (expected ./dist/deshiqr.global.js)`,
    );
    assert(
      existsSync(resolve(ROOT, PACKAGE_DIR, manifest[field])),
      `${PACKAGE_DIR}/${manifest[field]} is missing — run \`pnpm build\``,
    );
  }
});

check("package.json exports only the root entry", () => {
  const manifest = JSON.parse(readFileSync(resolve(ROOT, PACKAGE_DIR, "package.json"), "utf8"));
  assert(
    JSON.stringify(Object.keys(manifest.exports)) === JSON.stringify(["."]),
    `exports=${Object.keys(manifest.exports).join(",")}`,
  );
});

if (failures > 0) {
  console.error(`\n${failures} browser-bundle check(s) failed.`);
  process.exit(1);
}
console.log("\nall browser-bundle checks passed.");
