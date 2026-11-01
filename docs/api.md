# `update` / `validate` API reference (v1)

deshiQR loads a well-formed Bangla QR payload, applies edits, and returns the new payload with a
re-sealed checksum. Two public functions per platform, plus a static browser bundle for GitHub Pages:

```ts
update(payload: string, edits?: PayloadEdits, options?: UpdateOptions): string
validate(payload: string, options?: ValidateOptions): ValidationReport
```

- `update` parses the payload, applies the edits, drops and recomputes tag `63`, then returns the new
  payload string. Invalid input throws a `DeshiQrError` with a `.code`; warnings never block an edit.
- `validate` never throws. It collects every error and warning into a `ValidationReport`, so it is
  safe to run on untrusted input.
- Neither function renders a QR code, reads merchant semantics, or touches the network.
- Tag `63` is always recomputed. Everything that is not edited (plus `01` when the amount is edited)
  is preserved byte for byte.

`update(payload)`, `update(payload, {})` and `update(payload, null)` are **validate-only**: the payload
comes back byte-identically (surrounding whitespace is trimmed; the checksum is recomputed, which is a
no-op for a valid input; no `01` rewrite) and warnings are surfaced normally. The `01`↔`54` coupling only happens when an edit targets tag `54` (or
the `amount` alias).

## JavaScript / TypeScript

```ts
import { update, validate, DeshiQrError } from "deshiqr";

const updated = update(staticPayload, { amount: 500, reference: "BILL123" });
// "00020101021226…6304DB6A"

const report = validate(updated);
// { ok: true, errors: [], warnings: [] }
```

The package also exports the TypeScript types `EditValue`, `PayloadEdits`, `UpdateOptions`,
`ValidateOptions`, `ValidationReport`, `DeshiQrIssue` and `DeshiQrCode` (the union of error codes).
The browser global `window.DeshiQR` exposes `update`, `validate` and `DeshiQrError`.

### `update`

| Parameter | Type                                       | Required | Rules                                                                   |
| --------- | ------------------------------------------ | -------- | ----------------------------------------------------------------------- |
| `payload` | `string`                                   | yes      | Well-formed TLV ending in a valid tag-`63` checksum, ≤ 4096 characters. |
| `edits`   | `Record<string, string \| number \| null>` | no       | Aliases or tag paths. Omitted, `null` or empty = validate-only.         |
| `options` | `UpdateOptions`                            | no       | Warning handling; see [options](#options-and-warning-suppression).      |

Returns the updated payload as a `string`. Throws `DeshiQrError` (`.code`, `.message`, optional
`.tag`) for any of the [errors](#errors) below.

```ts
update(payload, { amount: 1250.5 }); // amount is formatted as "1250.50"
update(payload, { "62/01": "BILL123", customerLabel: "FT" });
update(payload, { amount: null }); // remove the amount; 01 goes back to 11
update(dynamicPayload, { "80/01": null }); // remove an opaque sub-tag (if 80 is valid TLV)
```

### `validate`

| Parameter | Type              | Required | Rules                                                  |
| --------- | ----------------- | -------- | ------------------------------------------------------ |
| `payload` | `string`          | yes      | Any string — untrusted input is fine; it never throws. |
| `options` | `ValidateOptions` | no       | Warning filtering; errors are always kept.             |

Returns:

```ts
interface DeshiQrIssue {
  code: string; // warning or error code, see the tables below
  message: string; // human-readable explanation
  tag?: string; // tag path when known: "59", "62", "62/01", "26/03", …
}
interface ValidationReport {
  ok: boolean; // true when errors is empty
  errors: DeshiQrIssue[];
  warnings: DeshiQrIssue[];
}

validate(payload); // ok + every error and warning
validate(payload, { warnings: false }); // errors only
```

## Python

```bash
pip install deshiqr
```

The whole public surface:

```python
from deshiqr import (
    DeshiQrError,
    DeshiQrIssue,
    DeshiQrWarning,
    UpdateOptions,
    ValidateOptions,
    ValidationReport,
    update,
    validate,
)
```

Signatures:

```python
update(payload, edits=None, options=None) -> str
validate(payload, options=None) -> ValidationReport
```

```python
static_payload = "00020101021126…6304295D"

updated = update(static_payload, {"amount": 500, "reference": "BILL123"})
report = validate(updated)
print(report.ok, report.errors, report.warnings)
```

The Python port has the same semantics and the same error/warning codes as JavaScript:

- `update` raises `DeshiQrError` (`.code`, `.message`, `.tag`) for input errors and for validation
  errors in the edited result.
- `validate` never throws; it returns a `ValidationReport` with `.ok`, `.errors` and `.warnings`
  (lists of `DeshiQrIssue` with `.code`, `.message`, `.tag`).
- Edits use the exact keys documented above — the camelCase alias `customerLabel` stays
  `customerLabel` (no snake_case variant). Tag paths are quoted strings (`"62/01"`).
- Options may be a dict — `{"warnings": True | False | ["59"], "onWarning": callable}` (`on_warning`
  is also accepted) — or the dataclasses `UpdateOptions(warnings=True, on_warning=None)` and
  `ValidateOptions(warnings=True)`.
- By default, warnings are emitted with the stdlib `warnings.warn(issue.message, DeshiQrWarning)`
  (JavaScript uses `console.warn`); pass `on_warning`/`onWarning` to choose your own sink.
- `DeshiQrWarning` is exported if you want to filter the standard warning stream.

No other helpers are public: there is no payload reading, formatting, reference generation or QR code in the
Python package.

## Edits

An edits object maps **aliases** or **tag paths** to values. Values are `string | number | null`; `null`
removes the tag.

| Alias           | Tag path | Meaning                                           |
| --------------- | -------- | ------------------------------------------------- |
| `amount`        | `54`     | amount, formatted/validated to exactly 2 decimals |
| `currency`      | `53`     | ISO 4217 numeric (e.g. `050` = BDT)               |
| `country`       | `58`     | ISO 3166-1 alpha-2 (e.g. `BD`)                    |
| `mcc`           | `52`     | merchant category code                            |
| `name`          | `59`     | merchant name                                     |
| `city`          | `60`     | merchant city                                     |
| `reference`     | `62/01`  | bill number / payment reference                   |
| `customerLabel` | `62/06`  | customer label                                    |
| `account`       | `26/03`  | account identifier                                |
| `institution`   | `26/00`  | institution AID                                   |

Tag-path keys match `^[0-9]{2}(/[0-9]{2})*$`, e.g. `"54"`, `"59"`, `"62/01"`, `"26/03"`, `"80/01"`.
The full field table is in [`format.md`](./format.md#field-table).

### Edits rules

- **Aliases and tag paths.** A tag-path key and an alias targeting the same tag in one call: the tag
  path wins.
- **Ordering (deterministic).** Aliases are applied first, then tag paths; nested edits are applied
  depth-ascending, then lexicographic. This makes the result (and warning order) stable.
- **Amounts.** `amount` accepts a number or a numeric string and is formatted to exactly 2 decimals.
  Values are never rounded. `≤ 0`, `> 99,999,999.99`, or more than 2 decimals raise `BAD_AMOUNT`.
- **Removal.** `null` removes that top-level tag or sub-tag. When a nested edit removes a template's
  last sub-tag, the now-empty template is dropped too; setting a whole template to `""` explicitly
  keeps an empty template field (which `validate` accepts).
- **Checksum.** Editing `63` is rejected with `BAD_TAG`; the checksum is always dropped and re-sealed
  (uppercase CRC-16/CCITT-FALSE).
- **Nested paths.** Editing a nested path requires the parent tag to be present and its value valid
  TLV, otherwise `BAD_TAG`. Tags `80`/`81` are opaque: they are never parsed or validated, but their
  whole value may be replaced, and a nested edit under them is allowed only when the current value is
  valid TLV.
- **New tags.** New two-digit tags are allowed and inserted in ascending numeric order at their level;
  existing fields keep their current order. Unknown tags are allowed and produce an `UNKNOWN_TAG`
  warning.
- **Point of initiation.** `01` may be edited explicitly. Otherwise, when the edits target tag `54`
  (or `amount`), `01` becomes `12` if `54` exists after the edits and `11` if it does not. Edits that
  do not target the amount leave `01` untouched.
- **Duplicates.** Duplicate tags in the input are rejected with `DUPLICATE_TAG` (`update` throws;
  `validate` reports an error).
- **Minimum work.** Only tags you edit — plus `01` under the rule above and the re-sealed `63` —
  change. Account template contents, merchant name/city, MCC, currency, country and the opaque token
  templates are carried over byte for byte. This is the provider-agnostic invariant, pinned by tests.

## Options and warning suppression

After applying edits, `update` validates the result. Every validation warning is surfaced according to
`options`; none of them block the edit.

```ts
interface UpdateOptions {
  warnings?: boolean | string[]; // default true: all warnings; false: none; string[]: suppress these
  onWarning?: (issue: DeshiQrIssue) => void; // default: console.warn
}
interface ValidateOptions {
  warnings?: boolean | string[]; // same filter for the returned report; errors always kept
}
```

| `warnings`     | Behaviour                                                          |
| -------------- | ------------------------------------------------------------------ |
| `true`/omitted | Surface every warning.                                             |
| `false`        | Surface no warnings (`validate` returns none; `update` is silent). |
| `["59"]`       | Suppress warnings whose `tag`/`path` is exactly `"59"`.            |

Suppression matches the issue's `tag`/`path` **exactly**: `"62"` does **not** suppress `"62/01"`, and
`"62/01"` does not suppress `"62"`. Pass `"26"`, `"26/03"`, `"62"`, `"62/01"`, … as needed.

`update` sends each remaining warning to `onWarning` (default `console.warn`) and still returns the
payload. `validate` simply returns the filtered list. Warnings are ordered deterministically:
`RISKY_EDIT` warnings first (sorted by tag path), then validation warnings in document order.

```ts
update(payload, edits, { warnings: false });
update(payload, edits, { warnings: ["59"] });
update(payload, edits, { onWarning: (issue) => logger.warn(issue.code, issue.tag, issue.message) });

const quietReport = validate(payload, { warnings: ["62/01"] });
```

Python accepts the same options as a dict or a dataclass:

```python
from deshiqr import UpdateOptions, update, validate

update(payload, edits, {"warnings": False})
update(payload, edits, {"warnings": ["59"], "onWarning": print})  # on_warning also accepted
update(payload, edits, UpdateOptions(warnings=["62/01"], on_warning=logger.warning))

quiet_report = validate(payload, {"warnings": ["62/01"]})
```

## Warnings

Warnings are informational; they never prevent an edit. All warning codes are suppressible.

| Code                     | When                                                                                                                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `MISSING_TAG`            | A recommended tag is absent: `00`, `01`, `59`.                                                                                                                                             |
| `UNKNOWN_TAG`            | Tag/path is not in the documented field table.                                                                                                                                             |
| `BAD_FIELD_VALUE`        | Value violates the documented syntax for that field (e.g. `53` not 3 digits, `58` not 2 letters, `52` not 4 digits, `54` not a 2-decimal number).                                          |
| `FIELD_TOO_LONG`         | Value is longer than the documented maximum for a length-limited text field (`26/00` > 32, `59` > 25, `60` > 15, `62/01` > 32, `26/03` > 34). Fixed-width fields report `BAD_FIELD_VALUE`. |
| `UNKNOWN_CURRENCY`       | `53` is not one of `050`, `356`, `764`, `840`, `978` (illustrative list; `050` is BDT).                                                                                                    |
| `NON_BD_COUNTRY`         | `58` is not `BD`.                                                                                                                                                                          |
| `UNKNOWN_INSTITUTION`    | `26/00` is not `bd.org.bb.npsb` (unverified provider — still supported).                                                                                                                   |
| `UNKNOWN_MCC`            | `52` is not one of `5411`, `6016`, `5999` (illustrative examples).                                                                                                                         |
| `STATIC_WITH_AMOUNT`     | `01` is `11` (static) but `54` is present.                                                                                                                                                 |
| `DYNAMIC_WITHOUT_AMOUNT` | `01` is `12` (dynamic) but `54` is absent.                                                                                                                                                 |
| `RISKY_EDIT`             | `update` edited or removed an identity field: `26/00` (institution), `26/03` (account) or `59` (merchant name). The message warns that editing the account/name can mislead payers.        |

`RISKY_EDIT` fires on both edits and removals of those fields. It is a warning, not a block: only edit
payloads you own. See [`../SECURITY.md`](../SECURITY.md).

Example issue objects (codes are the machine-readable part; messages are identical in both languages
in the browser and in Python):

```json
{ "code": "RISKY_EDIT", "message": "Editing the account/name can mislead payers; only edit what you own.", "tag": "59" }
{ "code": "NON_BD_COUNTRY", "message": "Country is \"US\", not \"BD\".", "tag": "58" }
{ "code": "UNKNOWN_CURRENCY", "message": "Unknown currency \"999\".", "tag": "53" }
```

## Errors

`update` throws a `DeshiQrError` for the first problem it finds — an input error, or a validation
error in the edited result; `validate` collects every problem in `report.errors` and never throws. The
exception/report entries have the same `{ code, message, tag? }` shape. `DeshiQrError` also offers a
static `DeshiQrError.is(error)` type guard.

| Code                | `update` | `validate` | When                                                                                           |
| ------------------- | -------- | ---------- | ---------------------------------------------------------------------------------------------- |
| `EMPTY_PAYLOAD`     | throws   | error      | Empty or non-string payload.                                                                   |
| `UNSUPPORTED`       | throws   | error      | Payload is longer than 4096 characters.                                                        |
| `BAD_TLV`           | throws   | error      | Malformed TLV: bad tag/length, truncated value, invalid nested template.                       |
| `MISSING_FIELD`     | throws   | error      | Payload does not end with tag `63`.                                                            |
| `CHECKSUM_MISMATCH` | throws   | error      | Tag `63` does not match the CRC-16/CCITT-FALSE of the input.                                   |
| `DUPLICATE_TAG`     | throws   | error      | The same tag appears twice at the same level.                                                  |
| `BAD_AMOUNT`        | throws   | —          | Amount is not a number/numeric string, `≤ 0`, `> 99,999,999.99`, or has more than 2 decimals.  |
| `BAD_TAG`           | throws   | —          | Invalid tag path, tag `63`, or a nested path whose parent is missing/not valid TLV.            |
| `BAD_VALUE`         | throws   | —          | Value is not a string/number where allowed, or its encoded value is longer than 99 units (UTF-8 bytes in a byte-counted payload, characters in a character-counted one). |

`BAD_AMOUNT`, `BAD_TAG` and `BAD_VALUE` are edit errors and are raised by `update` only; `validate`
checks the payload itself and reports the rest. Only the first edit error is thrown (edits are applied
in the deterministic order above).

## Examples

### JavaScript

```js
import { update, validate } from "deshiqr";

const staticPayload = "00020101021126…6304295D";

// Amount edit: 01 -> 12, 54 inserted, checksum re-sealed.
const dynamicPayload = update(staticPayload, { amount: 500 });

// Add a reference, suppress warnings for the merchant name on purpose.
const withReference = update(dynamicPayload, { reference: "BILL123" }, { warnings: ["59"] });

// Validate-only: returns the payload unchanged and its warnings.
const samePayload = update(withReference, {});

const report = validate(withReference);
if (!report.ok) throw new Error(report.errors[0].message);
console.log("ok:", report.ok, "warnings:", report.warnings.length);
```

Plain browser, no build step:

```html
<script src="https://cdn.jsdelivr.net/npm/deshiqr@0.1.0/dist/deshiqr.global.js"></script>
<script>
  const updated = DeshiQR.update(payload, { amount: 500 });
</script>
```

### Python

```python
from deshiqr import update, validate

static_payload = "00020101021126…6304295D"
dynamic_payload = update(static_payload, {"amount": 500})
report = validate(dynamic_payload)
print(report.ok, report.errors, report.warnings)
```

Runnable examples: [`../examples/node.mjs`](../examples/node.mjs),
[`../examples/python.py`](../examples/python.py), [`../examples/browser.html`](../examples/browser.html).

## Guarantees and limits

- **Provider-agnostic editing.** Only the tags you edit, `01` (when the amount is edited) and the
  checksum differ; everything else is byte-identical. Tests pin this on a synthetic non-bKash layout.
- **Idempotent and stateless.** The same payload + edits give the same output, and `update(payload, {})`
  reproduces the payload exactly. No storage, no I/O, no network.
- **Byte- or character-counted lengths.** EMVCo/NPSB payloads count each field's `LL` in UTF-8 bytes
  (so non-ASCII values such as Bangla merchant names work); payloads from producers that count
  characters are auto-detected and preserved on write. See
  [`format.md`](./format.md#encoding).
- **No QR rendering.** deshiQR returns the payload string; encode/render the QR with your own tool.
- **No merchant verification or payment confirmation.** Payloads are public data. Keep the base
  payload on your trusted side, verify where it came from, and compare the name the payer's app shows
  with the shop's name. A QR is an instruction to pay, not proof that money moved.
- **Limits.** Payload ≤ 4096 characters; any encoded value ≤ 99 units (UTF-8 bytes in a byte-counted
  payload, characters in a character-counted one); amount `0.01`–`99,999,999.99` with at most 2
  decimals.
- **Provider formats can change.** Test a small amount in the provider app before shipping a pay page.

## Related

- [`format.md`](./format.md) — the field table, checksum rule, and a worked edit.
- [`demo-payloads.md`](./demo-payloads.md) — synthetic fixtures used above.
- [`self-hosting.md`](./self-hosting.md) — publishing the static bundle on GitHub Pages.
- [`../SECURITY.md`](../SECURITY.md) — what deshiQR does and does not protect.
