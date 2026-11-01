import assert from "node:assert/strict";
import { test } from "node:test";
import { encodeFields, findValue, parse, parseSubfields } from "../src/core/tlv.ts";
import { validate, type ValidationReport } from "../src/index.ts";
import {
  DYNAMIC_500_PAYLOAD,
  GENERIC_STATIC_PAYLOAD,
  MINIMAL_PAYLOAD,
  STATIC_PAYLOAD,
  rebuild,
  removeField,
  setField,
} from "./fixtures.ts";

function warningFor(report: ValidationReport, code: string, tag?: string) {
  return report.warnings.find(
    (warning) => warning.code === code && (tag === undefined || warning.tag === tag),
  );
}

function errorFor(report: ValidationReport, code: string) {
  return report.errors.find((error) => error.code === code);
}

/** Rewrite tag 62 (a template) from a list of `[tag, value]` pairs. */
function rebuildAdditional(payload: string, subfields: Array<[string, string]>): string {
  return rebuild(payload, (fields) => {
    setField(fields, "62", encodeFields(subfields.map(([tag, value]) => ({ tag, value }))));
  });
}

/** Replace the account template (tag 26) with a list of `[tag, value]` pairs. */
function rebuildAccount(payload: string, subfields: Array<[string, string]>): string {
  return rebuild(payload, (fields) => {
    setField(fields, "26", encodeFields(subfields.map(([tag, value]) => ({ tag, value }))));
  });
}

// ---- valid payloads -----------------------------------------------------

test("every valid fixture validates cleanly and warnings-free", () => {
  for (const payload of [STATIC_PAYLOAD, DYNAMIC_500_PAYLOAD, MINIMAL_PAYLOAD]) {
    const report = validate(payload);
    assert.deepEqual(report, { ok: true, errors: [], warnings: [] });
  }
});

test("the report has exactly the documented shape", () => {
  assert.deepEqual(Object.keys(validate(STATIC_PAYLOAD)).sort(), ["errors", "ok", "warnings"]);
});

test("an unknown institution AID is a warning, not an error", () => {
  const report = validate(GENERIC_STATIC_PAYLOAD);
  assert.equal(report.ok, true);
  assert.deepEqual(
    report.warnings.map((warning) => [warning.code, warning.tag]),
    [["UNKNOWN_INSTITUTION", "26/00"]],
  );
});

// ---- input errors -------------------------------------------------------

test("EMPTY_PAYLOAD for empty and non-string payloads (never throws)", () => {
  const inputs = ["", "   ", 42, null, undefined, {}, [], true] as unknown as string[];
  for (const input of inputs) {
    const report = validate(input);
    assert.equal(report.ok, false);
    assert.deepEqual(
      report.errors.map((error) => error.code),
      ["EMPTY_PAYLOAD"],
    );
  }
});

test("UNSUPPORTED for payloads longer than 4096 characters", () => {
  const report = validate("0".repeat(5000));
  assert.equal(report.ok, false);
  assert.deepEqual(
    report.errors.map((error) => error.code),
    ["UNSUPPORTED"],
  );
});

test("BAD_TLV for malformed TLV", () => {
  for (const payload of ["0005AB", "XX0201", "00"]) {
    const report = validate(payload);
    assert.equal(report.ok, false);
    assert.ok(errorFor(report, "BAD_TLV"), payload);
  }
});

test("BAD_TLV for a truncated payload", () => {
  const report = validate(STATIC_PAYLOAD.slice(0, -12));
  assert.equal(report.ok, false);
  assert.ok(errorFor(report, "BAD_TLV"));
});

test("MISSING_FIELD when the payload does not end with tag 63", () => {
  const report = validate(STATIC_PAYLOAD.slice(0, -8));
  assert.equal(report.ok, false);
  assert.equal(errorFor(report, "MISSING_FIELD")?.tag, "63");
});

test("CHECKSUM_MISMATCH for a damaged checksum", () => {
  const report = validate(STATIC_PAYLOAD.slice(0, -4) + "0000");
  assert.equal(report.ok, false);
  assert.equal(errorFor(report, "CHECKSUM_MISMATCH")?.tag, "63");
});

test("BAD_TLV when the checksum field is not four hexadecimal characters", () => {
  const report = validate(STATIC_PAYLOAD.slice(0, -4) + "ZZZZ");
  assert.equal(report.ok, false);
  assert.equal(errorFor(report, "BAD_TLV")?.tag, "63");
});

test("DUPLICATE_TAG for a duplicate top-level tag", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => {
    fields.splice(1, 0, { tag: "59", value: "OTHER STORE" });
  });
  const report = validate(payload);
  assert.equal(report.ok, false);
  assert.equal(errorFor(report, "DUPLICATE_TAG")?.tag, "59");
  assert.match(errorFor(report, "DUPLICATE_TAG")?.message ?? "", /appears more than once/);
});

test("DUPLICATE_TAG for a duplicate nested tag", () => {
  const payload = rebuildAdditional(DYNAMIC_500_PAYLOAD, [
    ["01", "FIRST"],
    ["01", "SECOND"],
    ["06", "FT"],
  ]);
  const report = validate(payload);
  assert.equal(report.ok, false);
  assert.equal(errorFor(report, "DUPLICATE_TAG")?.tag, "62/01");
});

test("BAD_TLV when a parsed template is not valid TLV", () => {
  const brokenAccount = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, "26", "not-tlv"));
  assert.equal(errorFor(validate(brokenAccount), "BAD_TLV")?.tag, "26");

  const brokenAdditional = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, "62", "not-tlv"));
  assert.equal(errorFor(validate(brokenAdditional), "BAD_TLV")?.tag, "62");
});

test("80/81 token templates are opaque and never validated", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => {
    setField(fields, "80", "opaque-not-tlv");
    setField(fields, "81", "also-not-tlv");
  });
  const report = validate(payload);
  assert.deepEqual(report, { ok: true, errors: [], warnings: [] });
});

// ---- warnings -----------------------------------------------------------

test("MISSING_TAG warnings come first, in order 00, 01, 59", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => {
    removeField(fields, "00");
    removeField(fields, "01");
    removeField(fields, "59");
  });
  const report = validate(payload);
  assert.equal(report.ok, true);
  assert.deepEqual(
    report.warnings.map((warning) => [warning.code, warning.tag]),
    [
      ["MISSING_TAG", "00"],
      ["MISSING_TAG", "01"],
      ["MISSING_TAG", "59"],
    ],
  );
});

test("MISSING_TAG message names the missing tag", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => removeField(fields, "59"));
  assert.equal(warningFor(validate(payload), "MISSING_TAG", "59")?.message, "Missing recommended tag 59.");
});

test("UNKNOWN_TAG for an undocumented top-level tag", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, "61", "extra"));
  const report = validate(payload);
  assert.equal(report.ok, true);
  assert.equal(warningFor(report, "UNKNOWN_TAG", "61")?.message, "Unknown tag 61.");
});

test("UNKNOWN_TAG for an undocumented sub-tag", () => {
  const payload = rebuildAccount(STATIC_PAYLOAD, [
    ["00", "bd.org.bb.npsb"],
    ["01", "02"],
    ["02", "2002"],
    ["03", "01000000000"],
    ["05", "extra"],
  ]);
  assert.equal(warningFor(validate(payload), "UNKNOWN_TAG", "26/05")?.message, "Unknown tag 26/05.");
});

test("BAD_FIELD_VALUE when a documented field breaks its syntax", () => {
  const cases: Array<[string, string, string]> = [
    ["00", "02", "00"],
    ["01", "99", "01"],
    ["53", "9999", "53"],
    ["58", "USA", "58"],
    ["52", "54", "52"],
    ["54", "500", "54"],
    ["54", "0.00", "54"],
    ["59", "", "59"],
    ["60", "", "60"],
  ];
  for (const [tag, value, expectedTag] of cases) {
    const payload = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, tag, value));
    const report = validate(payload);
    assert.equal(report.ok, true, tag);
    assert.ok(warningFor(report, "BAD_FIELD_VALUE", expectedTag), `${tag}=${value}`);
    assert.equal(warningFor(report, "BAD_FIELD_VALUE", expectedTag)?.tag, expectedTag);
  }
});

test("BAD_FIELD_VALUE inside the account template", () => {
  const badVersion = rebuildAccount(STATIC_PAYLOAD, [
    ["00", "bd.org.bb.npsb"],
    ["01", "2"],
    ["02", "2002"],
    ["03", "01000000000"],
  ]);
  assert.equal(warningFor(validate(badVersion), "BAD_FIELD_VALUE", "26/01")?.tag, "26/01");

  const badVariant = rebuildAccount(STATIC_PAYLOAD, [
    ["00", "bd.org.bb.npsb"],
    ["01", "02"],
    ["02", "02"],
    ["03", "01000000000"],
  ]);
  assert.equal(warningFor(validate(badVariant), "BAD_FIELD_VALUE", "26/02")?.tag, "26/02");

  const badAccount = rebuildAccount(STATIC_PAYLOAD, [
    ["00", "bd.org.bb.npsb"],
    ["01", "02"],
    ["02", "2002"],
    ["03", "abc"],
  ]);
  assert.equal(warningFor(validate(badAccount), "BAD_FIELD_VALUE", "26/03")?.tag, "26/03");
});

test("BAD_FIELD_VALUE for an unprintable reference", () => {
  const payload = rebuildAdditional(STATIC_PAYLOAD, [["01", "bad\x01ref"]]);
  assert.equal(warningFor(validate(payload), "BAD_FIELD_VALUE", "62/01")?.tag, "62/01");
});

test("FIELD_TOO_LONG enforces the documented maxima", () => {
  const cases: Array<[string, string, string, number]> = [
    ["59", "x".repeat(26), "59", 25],
    ["60", "x".repeat(16), "60", 15],
  ];
  for (const [tag, value, expectedTag, limit] of cases) {
    const payload = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, tag, value));
    const warning = warningFor(validate(payload), "FIELD_TOO_LONG", expectedTag);
    assert.equal(warning?.tag, expectedTag);
    assert.match(warning?.message ?? "", new RegExp(`longer than ${limit}`));
  }

  const longReference = rebuildAdditional(STATIC_PAYLOAD, [["01", "x".repeat(33)]]);
  const referenceWarning = warningFor(validate(longReference), "FIELD_TOO_LONG", "62/01");
  assert.match(referenceWarning?.message ?? "", /longer than 32/);

  const longAccount = rebuildAccount(STATIC_PAYLOAD, [
    ["00", "bd.org.bb.npsb"],
    ["01", "02"],
    ["02", "2002"],
    ["03", "0".repeat(35)],
  ]);
  const accountWarning = warningFor(validate(longAccount), "FIELD_TOO_LONG", "26/03");
  assert.match(accountWarning?.message ?? "", /longer than 34/);
});

test("known-value warnings only fire when the syntax is valid", () => {
  const unknownCurrency = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, "53", "999"));
  assert.equal(warningFor(validate(unknownCurrency), "UNKNOWN_CURRENCY", "53")?.message, 'Unknown currency "999".');
  assert.equal(warningFor(validate(unknownCurrency), "BAD_FIELD_VALUE"), undefined);

  const nonBd = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, "58", "US"));
  assert.equal(warningFor(validate(nonBd), "NON_BD_COUNTRY", "58")?.message, 'Country is "US", not "BD".');
  assert.equal(warningFor(validate(nonBd), "BAD_FIELD_VALUE"), undefined);

  const unknownMcc = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, "52", "1234"));
  assert.equal(
    warningFor(validate(unknownMcc), "UNKNOWN_MCC", "52")?.message,
    'Unknown merchant category code "1234".',
  );

  const unknownInstitution = rebuildAccount(STATIC_PAYLOAD, [
    ["00", "example.org.bank"],
    ["01", "02"],
    ["02", "2002"],
    ["03", "01000000000"],
  ]);
  assert.equal(
    warningFor(validate(unknownInstitution), "UNKNOWN_INSTITUTION", "26/00")?.message,
    'Unverified institution "example.org.bank".',
  );
});

test("an account template without 26/00 warns UNKNOWN_INSTITUTION", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, "26", ""));
  const report = validate(payload);
  assert.equal(report.ok, true);
  assert.equal(warningFor(report, "UNKNOWN_INSTITUTION", "26/00")?.message, 'Unverified institution "".');
});

test("STATIC_WITH_AMOUNT fires inline right after tag 54", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => {
    setField(fields, "54", "500.00");
  });
  const report = validate(payload);
  assert.equal(report.ok, true);
  assert.equal(
    warningFor(report, "STATIC_WITH_AMOUNT", "54")?.message,
    "Static QR should not carry an amount (tag 54).",
  );
});

test("DYNAMIC_WITHOUT_AMOUNT fires inline right after tag 01", () => {
  const payload = rebuild(DYNAMIC_500_PAYLOAD, (fields) => removeField(fields, "54"));
  const report = validate(payload);
  assert.equal(report.ok, true);
  assert.equal(
    warningFor(report, "DYNAMIC_WITHOUT_AMOUNT", "54")?.message,
    "Dynamic QR has no amount (tag 54).",
  );
});

test("warning order follows payload order with coupling inline", () => {
  const payload = rebuildAdditional(
    rebuild(STATIC_PAYLOAD, (fields) => {
      setField(fields, "53", "999");
      setField(fields, "59", "DEMO STORE WITH A VERY LONG NAME");
      setField(fields, "54", "500.00");
      fields.sort((a, b) => Number(a.tag) - Number(b.tag));
    }),
    [["01", "BILL1"]],
  );
  const report = validate(payload);
  // Warning order follows payload order: 53 < 54 < 59; STATIC_WITH_AMOUNT is
  // emitted inline right after tag 54's own checks.
  assert.deepEqual(
    report.warnings.map((warning) => [warning.code, warning.tag]),
    [
      ["UNKNOWN_CURRENCY", "53"],
      ["STATIC_WITH_AMOUNT", "54"],
      ["FIELD_TOO_LONG", "59"],
    ],
  );
});

test("validate never emits RISKY_EDIT (it knows nothing about edits)", () => {
  const report = validate(STATIC_PAYLOAD);
  assert.equal(report.warnings.some((warning) => warning.code === "RISKY_EDIT"), false);
});

// ---- suppression and ok semantics --------------------------------------

test("warnings: false removes every warning but keeps errors", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => {
    setField(fields, "53", "999");
    removeField(fields, "59");
  });
  const report = validate(payload, { warnings: false });
  assert.deepEqual(report.warnings, []);
  assert.equal(report.ok, true);

  const badChecksum = validate(STATIC_PAYLOAD.slice(0, -4) + "0000", { warnings: false });
  assert.equal(badChecksum.ok, false);
  assert.deepEqual(
    badChecksum.errors.map((error) => error.code),
    ["CHECKSUM_MISMATCH"],
  );
});

test("warnings: [tag] suppresses exactly that tag", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => {
    setField(fields, "53", "999");
    setField(fields, "59", "x".repeat(26));
  });
  const report = validate(payload, { warnings: ["53"] });
  assert.deepEqual(
    report.warnings.map((warning) => warning.tag),
    ["59"],
  );
});

test("suppression does not match a parent path", () => {
  const payload = rebuildAdditional(STATIC_PAYLOAD, [["01", "x".repeat(33)]]);
  const parent = validate(payload, { warnings: ["62"] });
  const exact = validate(payload, { warnings: ["62/01"] });
  assert.equal(parent.warnings.some((warning) => warning.tag === "62/01"), true);
  assert.equal(exact.warnings.some((warning) => warning.tag === "62/01"), false);
});

test("ok is true exactly when there are no errors", () => {
  assert.equal(validate(STATIC_PAYLOAD).ok, true);
  const withWarnings = rebuild(STATIC_PAYLOAD, (fields) => setField(fields, "53", "999"));
  assert.equal(validate(withWarnings).ok, true);
  assert.equal(validate(STATIC_PAYLOAD.slice(0, -4) + "0000").ok, false);
});

test("warnings are still collected when there are errors", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => {
    removeField(fields, "59");
    removeField(fields, "00");
  });
  const damaged = payload.slice(0, -4) + "0000";
  const report = validate(damaged);
  assert.equal(report.ok, false);
  assert.ok(errorFor(report, "CHECKSUM_MISMATCH"));
  assert.deepEqual(
    report.warnings.map((warning) => warning.tag),
    ["00", "59"],
  );
});

test("validate tolerates a null options argument", () => {
  assert.doesNotThrow(() =>
    validate(STATIC_PAYLOAD, null as unknown as Parameters<typeof validate>[1]),
  );
  assert.equal(validate(STATIC_PAYLOAD, null as unknown as Parameters<typeof validate>[1]).ok, true);
});

test("validate never throws for arbitrary garbage", () => {
  for (const payload of ["\u0000", "😀", "000201", "GGGG", "0".repeat(100)]) {
    assert.doesNotThrow(() => validate(payload));
  }
});

test("a payload parsed with no checksum still reports tag errors in order", () => {
  const report = validate("0002010102116304ZZZZ");
  assert.equal(report.errors[0]?.code, "BAD_TLV");
  assert.equal(report.errors[0]?.tag, "63");
});

test("nested template duplicates are reported after top-level duplicates", () => {
  const payload = rebuildAdditional(DYNAMIC_500_PAYLOAD, [
    ["01", "FIRST"],
    ["01", "SECOND"],
  ]);
  const doubled = rebuild(payload, (fields) => {
    fields.splice(1, 0, { tag: "59", value: "OTHER STORE" });
  });
  const report = validate(doubled);
  assert.deepEqual(
    report.errors.filter((error) => error.code === "DUPLICATE_TAG").map((error) => error.tag),
    ["59", "62/01"],
  );
});

test("parse() helper is not needed to validate sub-fields", () => {
  const report = validate(STATIC_PAYLOAD);
  const accountValue = findValue(parse(STATIC_PAYLOAD), "26") ?? "";
  assert.equal(findValue(parseSubfields(accountValue), "03"), "01000000000");
  assert.deepEqual(report.warnings, []);
});
