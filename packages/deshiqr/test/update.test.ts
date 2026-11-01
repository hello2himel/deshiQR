import assert from "node:assert/strict";
import { test } from "node:test";
import { DeshiQrError } from "../src/core/errors.ts";
import { encodeFields, findValue, parse, parseSubfields } from "../src/core/tlv.ts";
import { update, validate, type DeshiQrIssue } from "../src/index.ts";
import {
  DYNAMIC_500_PAYLOAD,
  GENERIC_STATIC_PAYLOAD,
  MINIMAL_PAYLOAD,
  REFERENCE,
  STATIC_PAYLOAD,
  fieldsOf,
  rebuild,
  removeField,
} from "./fixtures.ts";

type Edits = Parameters<typeof update>[1];
type Options = NonNullable<Parameters<typeof update>[2]>;

function valueOf(payload: string, tag: string): string | null {
  return findValue(parse(payload), tag);
}

function tagsOf(payload: string): string[] {
  return parse(payload).map((field) => field.tag);
}

function subValueOf(payload: string, parent: string, tag: string): string | null {
  const value = valueOf(payload, parent) ?? "";
  return findValue(parseSubfields(value), tag);
}

function captured(payload: string, edits: Edits, options: Options = {}) {
  const warnings: DeshiQrIssue[] = [];
  const result = update(payload, edits, {
    ...(options ?? {}),
    onWarning: (warning) => warnings.push(warning),
  });
  return { payload: result, warnings };
}

function errorOf(fn: () => unknown): DeshiQrError {
  try {
    fn();
  } catch (error) {
    assert.ok(DeshiQrError.is(error), `expected a DeshiQrError, got ${String(error)}`);
    return error;
  }
  assert.fail("expected the call to throw");
}

// ---- amount -------------------------------------------------------------

test("amount alias produces the pinned dynamic payload", () => {
  assert.equal(update(STATIC_PAYLOAD, { amount: 500, reference: REFERENCE }), DYNAMIC_500_PAYLOAD);
});

test("amount is formatted to exactly two decimals", () => {
  assert.equal(valueOf(update(STATIC_PAYLOAD, { amount: "1250.5" }), "54"), "1250.50");
  assert.equal(valueOf(update(STATIC_PAYLOAD, { amount: 500 }), "54"), "500.00");
  assert.equal(valueOf(update(STATIC_PAYLOAD, { amount: "0.01" }), "54"), "0.01");
  assert.equal(valueOf(update(STATIC_PAYLOAD, { amount: 99999999.99 }), "54"), "99999999.99");
});

test("adding an amount flips tag 01 to dynamic", () => {
  assert.equal(valueOf(update(STATIC_PAYLOAD, { amount: 500 }), "01"), "12");
});

test("replacing an existing amount keeps it a single tag", () => {
  const result = update(DYNAMIC_500_PAYLOAD, { amount: 777 });
  assert.equal(valueOf(result, "54"), "777.00");
  assert.equal(tagsOf(result).filter((tag) => tag === "54").length, 1);
});

test("removing the amount flips tag 01 back to static", () => {
  const result = update(DYNAMIC_500_PAYLOAD, { amount: null });
  assert.equal(valueOf(result, "54"), null);
  assert.equal(valueOf(result, "01"), "11");
});

test("removing an absent amount is a no-op", () => {
  assert.equal(update(STATIC_PAYLOAD, { amount: null }), STATIC_PAYLOAD);
});

// ---- aliases ------------------------------------------------------------

test("currency, country, mcc and city aliases map to their tags", () => {
  const result = update(STATIC_PAYLOAD, { currency: "840", country: "US", mcc: "5411", city: "Sylhet" });
  assert.equal(valueOf(result, "53"), "840");
  assert.equal(valueOf(result, "58"), "US");
  assert.equal(valueOf(result, "52"), "5411");
  assert.equal(valueOf(result, "60"), "Sylhet");
});

test("name alias maps to tag 59", () => {
  assert.equal(valueOf(update(STATIC_PAYLOAD, { name: "NEW STORE" }), "59"), "NEW STORE");
});

test("reference alias edits tag 62/01 and keeps the rest of the template", () => {
  const result = update(STATIC_PAYLOAD, { reference: "BILL123" });
  assert.equal(subValueOf(result, "62", "01"), "BILL123");
  assert.equal(subValueOf(result, "62", "06"), "FT");
  assert.deepEqual(
    parseSubfields(valueOf(result, "62") ?? "").map((field) => field.tag),
    ["01", "06"],
  );
});

test("customerLabel alias edits tag 62/06", () => {
  assert.equal(subValueOf(update(STATIC_PAYLOAD, { customerLabel: "CUST" }), "62", "06"), "CUST");
});

test("account and institution aliases edit the account template", () => {
  const result = update(STATIC_PAYLOAD, { account: "01700000000", institution: "example.org.bank" });
  assert.equal(subValueOf(result, "26", "03"), "01700000000");
  assert.equal(subValueOf(result, "26", "00"), "example.org.bank");
});

// ---- tag paths ----------------------------------------------------------

test("tag path wins over an alias for the same tag", () => {
  const result = update(STATIC_PAYLOAD, { amount: 500, "54": 7 });
  assert.equal(valueOf(result, "54"), "7.00");
});

test("tag path wins over an alias regardless of key order", () => {
  const result = update(STATIC_PAYLOAD, { "59": "PATH STORE", name: "ALIAS STORE" });
  assert.equal(valueOf(result, "59"), "PATH STORE");
});

test("new top-level tags are inserted in ascending numeric order", () => {
  const result = update(STATIC_PAYLOAD, { "56": "hello" });
  const tags = tagsOf(result);
  assert.ok(tags.indexOf("56") > tags.indexOf("53"));
  assert.ok(tags.indexOf("56") < tags.indexOf("58"));
});

test("nested tag path inserts a sub-tag in sorted order", () => {
  const result = update(STATIC_PAYLOAD, { "62/02": "X" });
  assert.deepEqual(
    parseSubfields(valueOf(result, "62") ?? "").map((field) => field.tag),
    ["02", "06"],
  );
});

test("deep tag path edits an existing subtree", () => {
  const result = update(STATIC_PAYLOAD, { "80/00": "example.org.new" });
  assert.equal(subValueOf(result, "80", "00"), "example.org.new");
  assert.notEqual(subValueOf(result, "80", "01"), null);
});

test("null removes a top-level tag", () => {
  assert.equal(valueOf(update(STATIC_PAYLOAD, { "60": null }), "60"), null);
});

test("null removes a sub-tag and keeps the template", () => {
  const result = update(DYNAMIC_500_PAYLOAD, { "62/01": null });
  assert.equal(subValueOf(result, "62", "01"), null);
  assert.equal(subValueOf(result, "62", "06"), "FT");
});

test("a template that becomes empty is removed entirely", () => {
  const result = update(DYNAMIC_500_PAYLOAD, { "62/01": null, "62/06": null });
  assert.equal(valueOf(result, "62"), null);
});

test("removal propagates up through nested templates", () => {
  const result = update(STATIC_PAYLOAD, { "80/00": null, "80/01": null });
  assert.equal(valueOf(result, "80"), null);
  assert.notEqual(valueOf(result, "81"), null);
});

test("a template that becomes empty during a nested edit is dropped", () => {
  const result = update(STATIC_PAYLOAD, { "62/06": null });
  assert.equal(valueOf(result, "62"), null);
});

// ---- 01 / 54 coupling ---------------------------------------------------

test("an explicitly edited 01 is not overridden by the amount", () => {
  const result = update(STATIC_PAYLOAD, { amount: 500, "01": "11" });
  assert.equal(valueOf(result, "01"), "11");
  assert.equal(valueOf(result, "54"), "500.00");
});

test("an explicitly edited 01 is not overridden by an amount removal", () => {
  const result = update(DYNAMIC_500_PAYLOAD, { "54": null, "01": "12" });
  assert.equal(valueOf(result, "01"), "12");
  assert.equal(valueOf(result, "54"), null);
});

// ---- no-op / idempotency / provider-agnostic ----------------------------

test("empty or omitted edits return the payload byte for byte", () => {
  assert.equal(update(STATIC_PAYLOAD, {}), STATIC_PAYLOAD);
  assert.equal(update(STATIC_PAYLOAD), STATIC_PAYLOAD);
  assert.equal(update(STATIC_PAYLOAD, null), STATIC_PAYLOAD);
});

test("the same edits twice produce the same payload", () => {
  const edits = { amount: 1250.5, name: "DEMO STORE 2", reference: "BILL-1" };
  const once = update(STATIC_PAYLOAD, edits);
  assert.equal(update(once, edits), once);
});

test("editing an amount changes only tags 01 and 54 (provider-agnostic invariant)", () => {
  const before = fieldsOf(GENERIC_STATIC_PAYLOAD);
  const after = fieldsOf(update(GENERIC_STATIC_PAYLOAD, { amount: 1250.5 }));

  assert.deepEqual(
    after.filter((field) => field.tag !== "01" && field.tag !== "54"),
    before.filter((field) => field.tag !== "01"),
    "a field other than 01/54 changed",
  );
  assert.equal(valueOf(update(GENERIC_STATIC_PAYLOAD, { amount: 1250.5 }), "01"), "12");
  assert.match(valueOf(update(GENERIC_STATIC_PAYLOAD, { amount: 1250.5 }), "54") ?? "", /^1250\.50$/);
});

// ---- errors -------------------------------------------------------------

test("EMPTY_PAYLOAD for empty and non-string payloads", () => {
  for (const input of ["", "   ", 42, null, undefined, {}] as unknown as string[]) {
    assert.equal(errorOf(() => update(input, {})).code, "EMPTY_PAYLOAD");
  }
});

test("UNSUPPORTED for payloads longer than 4096 characters", () => {
  assert.equal(errorOf(() => update("0".repeat(4097), {})).code, "UNSUPPORTED");
});

test("BAD_TLV for malformed TLV", () => {
  assert.equal(errorOf(() => update("0005AB", {})).code, "BAD_TLV");
});

test("MISSING_FIELD when there is no trailing checksum", () => {
  const error = errorOf(() => update("000201010211", {}));
  assert.equal(error.code, "MISSING_FIELD");
  assert.equal(error.tag, "63");
});

test("CHECKSUM_MISMATCH when the CRC does not match", () => {
  const error = errorOf(() => update(STATIC_PAYLOAD.slice(0, -4) + "0000", {}));
  assert.equal(error.code, "CHECKSUM_MISMATCH");
  assert.equal(error.tag, "63");
});

test("BAD_TLV when the checksum is not four hexadecimal characters", () => {
  const error = errorOf(() => update(STATIC_PAYLOAD.slice(0, -4) + "ZZZZ", {}));
  assert.equal(error.code, "BAD_TLV");
  assert.equal(error.tag, "63");
});

test("DUPLICATE_TAG is rejected for duplicate top-level tags", () => {
  const payload = rebuild(STATIC_PAYLOAD, (fields) => {
    fields.splice(1, 0, { tag: "59", value: "OTHER STORE" });
  });
  const error = errorOf(() => update(payload, {}));
  assert.equal(error.code, "DUPLICATE_TAG");
  assert.equal(error.tag, "59");
});

test("DUPLICATE_TAG is rejected for duplicate nested tags", () => {
  const payload = rebuild(DYNAMIC_500_PAYLOAD, (fields) => {
    const index = fields.findIndex((field) => field.tag === "62");
    const children = parseSubfields(fields[index]?.value ?? "");
    fields[index] = {
      tag: "62",
      value: encodeFields([...children, { tag: "01", value: "SECOND REFERENCE" }]),
    };
  });
  const error = errorOf(() => update(payload, {}));
  assert.equal(error.code, "DUPLICATE_TAG");
  assert.equal(error.tag, "62/01");
});

test("BAD_AMOUNT rejects every invalid amount without rounding", () => {
  const bad = [0, -1, 100000000, Number.NaN, Number.POSITIVE_INFINITY, "abc", "1.234", 1.005, 0.1 + 0.2, "0.00", "", " 500"];
  for (const amount of bad) {
    assert.equal(
      errorOf(() => update(STATIC_PAYLOAD, { amount: amount as number })).code,
      "BAD_AMOUNT",
      `accepted ${String(amount)}`,
    );
  }
});

test("BAD_TAG rejects tag 63 edits", () => {
  for (const edits of [{ "63": "0000" }, { "63/01": "x" }] as unknown as Edits[]) {
    const error = errorOf(() => update(STATIC_PAYLOAD, edits));
    assert.equal(error.code, "BAD_TAG");
    assert.equal(error.tag, "63");
  }
});

test("BAD_TAG rejects keys that are neither aliases nor tag paths", () => {
  for (const key of ["amountt", "5", "54/", "", "abc/01"]) {
    const error = errorOf(() => update(STATIC_PAYLOAD, { [key]: "x" } as unknown as Edits));
    assert.equal(error.code, "BAD_TAG");
    assert.equal(error.tag, key);
  }
});

test("BAD_TAG when a nested path's parent is missing", () => {
  const error = errorOf(() => update(MINIMAL_PAYLOAD, { "62/01": "X" }));
  assert.equal(error.code, "BAD_TAG");
  assert.equal(error.tag, "62/01");
});

test("BAD_TAG when a nested path's parent is not valid TLV", () => {
  const broken = rebuild(STATIC_PAYLOAD, (fields) => {
    const index = fields.findIndex((field) => field.tag === "80");
    fields[index] = { tag: "80", value: "not-tlv" };
  });
  const error = errorOf(() => update(broken, { "80/01": "X" }));
  assert.equal(error.code, "BAD_TAG");
  assert.equal(error.tag, "80/01");
});

test("BAD_TAG when a parent edit runs before its nested edit (depth order)", () => {
  const error = errorOf(() => update(STATIC_PAYLOAD, { "62": null, "62/01": "X" } as unknown as Edits));
  assert.equal(error.code, "BAD_TAG");
  assert.equal(error.tag, "62/01");
});

test("aliases are applied before tag paths", () => {
  const result = update(STATIC_PAYLOAD, { reference: "X", "62": null } as unknown as Edits);
  assert.equal(valueOf(result, "62"), null);
});

test("BAD_VALUE rejects values that are not string/number/null", () => {
  for (const value of [true, false, {}, [], Symbol("x")] as unknown[]) {
    const error = errorOf(() => update(STATIC_PAYLOAD, { name: value } as unknown as Edits));
    assert.equal(error.code, "BAD_VALUE");
    assert.equal(error.tag, "59");
  }
});

test("BAD_VALUE rejects a value longer than 99 characters", () => {
  const error = errorOf(() => update(STATIC_PAYLOAD, { name: "x".repeat(100) }));
  assert.equal(error.code, "BAD_VALUE");
  assert.equal(error.tag, "59");
});

test("BAD_VALUE when a template's encoded value would exceed 99 characters", () => {
  const error = errorOf(() => update(STATIC_PAYLOAD, { "62/02": "x".repeat(95) }));
  assert.equal(error.code, "BAD_VALUE");
});

test("BAD_VALUE rejects edits that are not an object", () => {
  for (const edits of [[], "amount", 42, true] as unknown[]) {
    const error = errorOf(() => update(STATIC_PAYLOAD, edits as Edits));
    assert.equal(error.code, "BAD_VALUE");
  }
});

test("editing a 26/62 template to invalid TLV throws BAD_TLV after validation", () => {
  const error = errorOf(() => update(STATIC_PAYLOAD, { "26": "garbage" }));
  assert.equal(error.code, "BAD_TLV");
  assert.equal(error.tag, "26");
});

test("replacing the whole opaque 80 value with non-TLV is allowed", () => {
  const result = update(STATIC_PAYLOAD, { "80": "opaque-token" });
  assert.equal(valueOf(result, "80"), "opaque-token");
  assert.equal(validate(result).ok, true);
});

// ---- warnings -----------------------------------------------------------

test("RISKY_EDIT warns when the account or name is edited", () => {
  const { warnings } = captured(STATIC_PAYLOAD, { name: "NEW STORE" });
  assert.deepEqual(warnings, [
    {
      code: "RISKY_EDIT",
      message: "Editing the account/name can mislead payers; only edit what you own.",
      tag: "59",
    },
  ]);
});

test("RISKY_EDIT warnings are sorted by path lexicographically", () => {
  const { warnings } = captured(STATIC_PAYLOAD, {
    institution: "example.org.bank",
    account: "01700000000",
    name: "NEW STORE",
  });
  const risky = warnings.filter((warning) => warning.code === "RISKY_EDIT").map((warning) => warning.tag);
  assert.deepEqual(risky, ["26/00", "26/03", "59"]);
});

test("warnings from the edited payload are surfaced after RISKY_EDIT", () => {
  const { warnings } = captured(STATIC_PAYLOAD, { name: "NEW STORE", city: "x".repeat(16) });
  assert.equal(warnings[0]?.code, "RISKY_EDIT");
  assert.ok(warnings.some((warning) => warning.code === "FIELD_TOO_LONG" && warning.tag === "60"));
});

test("an unknown new tag is allowed with an UNKNOWN_TAG warning", () => {
  const { payload, warnings } = captured(STATIC_PAYLOAD, { "61": "extra" });
  assert.equal(valueOf(payload, "61"), "extra");
  assert.deepEqual(
    warnings.map((warning) => [warning.code, warning.tag]),
    [["UNKNOWN_TAG", "61"]],
  );
});

test("warnings: false suppresses every warning", () => {
  const { warnings } = captured(STATIC_PAYLOAD, { name: "NEW STORE" }, { warnings: false });
  assert.deepEqual(warnings, []);
});

test("warnings: [tag] suppresses warnings for that tag/path only", () => {
  const { warnings } = captured(STATIC_PAYLOAD, { name: "NEW STORE", "61": "extra" }, { warnings: ["59"] });
  assert.deepEqual(
    warnings.map((warning) => warning.tag),
    ["61"],
  );
});

test("suppression matches the exact tag path, not a parent path", () => {
  const tooLongReference = update(STATIC_PAYLOAD, { "62/01": "x".repeat(33) });
  const exact = captured(tooLongReference, { name: "NEW STORE" }, { warnings: ["62/01"] });
  const parent = captured(tooLongReference, { name: "NEW STORE" }, { warnings: ["62"] });
  assert.equal(exact.warnings.some((warning) => warning.tag === "62/01"), false);
  assert.equal(parent.warnings.some((warning) => warning.tag === "62/01"), true);
});

test("warnings go to console.warn by default", () => {
  const messages: unknown[] = [];
  const original = console.warn;
  console.warn = (...args: unknown[]) => messages.push(...args);
  try {
    update(STATIC_PAYLOAD, { name: "NEW STORE" });
  } finally {
    console.warn = original;
  }
  assert.equal(messages.length, 1);
  assert.match(String(messages[0]), /RISKY_EDIT/);
});

test("edited identity tags from tag paths also trigger RISKY_EDIT", () => {
  const { warnings } = captured(STATIC_PAYLOAD, { "26/03": "01700000000" });
  assert.deepEqual(
    warnings.filter((warning) => warning.code === "RISKY_EDIT").map((warning) => warning.tag),
    ["26/03"],
  );
});

test("removing the name still counts as editing an identity field", () => {
  const { warnings } = captured(STATIC_PAYLOAD, { "59": null });
  assert.equal(warnings.some((warning) => warning.code === "RISKY_EDIT" && warning.tag === "59"), true);
});

// ---- misc ---------------------------------------------------------------

test("update re-seals with an uppercase CRC-16 checksum", () => {
  const result = update(STATIC_PAYLOAD, { name: "NEW STORE" });
  assert.match(result.slice(-4), /^[0-9A-F]{4}$/);
  assert.equal(validate(result).ok, true);
});

test("update tolerates a null options argument", () => {
  const result = update(STATIC_PAYLOAD, { name: "NEW STORE" }, null as unknown as Options);
  assert.equal(valueOf(result, "59"), "NEW STORE");
});

test("update throws a DeshiQrError instance for every failure", () => {
  const error = errorOf(() => update(STATIC_PAYLOAD, { amount: -1 }));
  assert.ok(error instanceof Error);
  assert.equal(error.name, "DeshiQrError");
  assert.equal(error.code, "BAD_AMOUNT");
  assert.equal(error.tag, "54");
});

test("editing unrelated tags leaves an inconsistent 01/54 pair alone", () => {
  const inconsistent = rebuild(STATIC_PAYLOAD, (fields) => {
    removeField(fields, "63");
    fields.push({ tag: "54", value: "500.00" });
    fields.sort((a, b) => Number(a.tag) - Number(b.tag));
  });
  const result = update(inconsistent, { name: "NEW STORE" });
  assert.equal(valueOf(result, "01"), "11");
  assert.equal(valueOf(result, "54"), "500.00");
});
