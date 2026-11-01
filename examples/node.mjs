#!/usr/bin/env node
/**
 * deshiQR — Node example: update + validate a Bangla QR payload. No QR rendering here.
 *
 * Run from the repo root (after `pnpm build`):
 *   node examples/node.mjs
 *
 * Or in your own project with the published package installed:
 *   npm install deshiqr
 *   node node.mjs
 *
 * The published import is:
 *   import { update, validate } from "deshiqr";
 * The loader below falls back to the repo build so this file also runs from a checkout.
 *
 * The payload is the synthetic `DEMO STORE` fixture from docs/demo-payloads.md — never a real
 * merchant payload.
 */

async function loadDeshiQR() {
  try {
    return await import("deshiqr");
  } catch {
    const built = new URL("../packages/deshiqr/dist/index.js", import.meta.url).href;
    return await import(built);
  }
}

const { update, validate } = await loadDeshiQR();

const STATIC_PAYLOAD =
  "00020101021126470014bd.org.bb.npsb010202020420020311010000000005204601653030505802BD5910DEMO STORE6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304295D";

// 1. Apply edits. `amount` is formatted to exactly 2 decimals; `reference` maps to tag 62/01.
const updated = update(STATIC_PAYLOAD, { amount: 500, reference: "BILL123" });
console.log("Updated payload:");
console.log(updated);
console.log();

// 2. Validate the result (never throws).
const report = validate(updated);
console.log("validate:", { ok: report.ok, errors: report.errors, warnings: report.warnings });
console.log();

// 3. Warnings go to onWarning (default: console.warn) and never block the edit.
update(
  STATIC_PAYLOAD,
  { amount: 500, account: "01000000000" },
  {
    onWarning: (issue) => console.log("warning:", issue.code, issue.tag ?? "(no tag)", "-", issue.message),
  },
);
console.log();

// 4. Edits can be any tag path, and null removes a tag. Validate-only is `update(payload)`/`{}`.
const withoutAmount = update(updated, { amount: null });
console.log(
  "amount removed:",
  withoutAmount.endsWith("6304295D") ? "restored static payload" : withoutAmount,
);
console.log("validate-only identical:", update(STATIC_PAYLOAD, {}) === STATIC_PAYLOAD);
console.log("removed warnings:", validate(withoutAmount, { warnings: false }).warnings);
