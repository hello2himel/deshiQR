# deshiqr

**Edit and validate Bangladesh Bangla QR payloads** — in one zero-dependency
package.

```ts
import { update, validate } from "deshiqr";

const updated = update(payload, { amount: 500, reference: "BILL123" });
const report = validate(updated);
// { ok: true, errors: [], warnings: [] }
```

deshiQR does exactly two things:

- **`update(payload, edits, options?) → string`** — load a Bangla QR payload,
  edit any tag by alias or tag path, and get the re-sealed payload back. The
  checksum is always recomputed; everything else (account template, name, city,
  tokens) stays byte-for-byte identical, except tag `01` when an amount edit makes
  it consistent.
- **`validate(payload, options?) → { ok, errors, warnings }`** — non-throwing,
  thorough validation with stable machine-readable codes.

QR Code rendering and decoding are intentionally **not** part of this package:
render the returned payload with whatever QR library you already use.

## Install

```sh
npm install deshiqr
# or: pnpm add deshiqr
```

Browser, without a bundler:

```html
<script src="https://cdn.jsdelivr.net/npm/deshiqr@0.1.0/dist/deshiqr.global.js"></script>
<script>
  const updated = DeshiQR.update(payload, { amount: 500 });
  const report = DeshiQR.validate(updated);
</script>
```

The single global is `DeshiQR` with `update`, `validate` and `DeshiQrError`.

## `update(payload, edits, options?)`

`edits` is an object; every key is either a **named alias** or a **tag path**
(`"54"`, `"62/01"`, `"26/03"`, `"80/01"`, …). Values are `string | number | null`.
`null` removes the tag. A tag path wins over the alias for the same tag.

| alias           | tag/path | notes                                                     |
| --------------- | -------- | --------------------------------------------------------- |
| `amount`        | `54`     | number or numeric string; formatted to exactly 2 decimals |
| `currency`      | `53`     | e.g. `"050"`                                              |
| `country`       | `58`     | e.g. `"BD"`                                               |
| `mcc`           | `52`     | e.g. `"5411"`                                             |
| `name`          | `59`     | merchant name                                             |
| `city`          | `60`     | merchant city                                             |
| `reference`     | `62/01`  | bill/reference number                                     |
| `customerLabel` | `62/06`  | customer label                                            |
| `account`       | `26/03`  | account identifier                                        |
| `institution`   | `26/00`  | institution AID                                           |

Rules:

- New tags are allowed (any two-digit tag) and inserted in ascending numeric
  order at their level; existing fields keep their current order.
- Editing or removing `63` is rejected (`BAD_TAG`) — the checksum is always
  recomputed (uppercase CRC-16/CCITT-FALSE).
- Tag `01` follows the amount unless you edit it explicitly: after an amount
  edit, `01` becomes `"12"` when `54` exists and `"11"` when it was removed.
- A nested path whose parent is missing or not valid TLV is rejected (`BAD_TAG`).
- If a nested edit removes the last sub-tag of a template (`26`, `62`, `80`, `81`),
  the now-empty template is dropped as well. (Setting a whole template to `""` keeps
  an explicitly empty template, which `validate` accepts.)
- `update(payload, {})` (or no edits) returns the payload unchanged.
- Editing the account/name (`26/00`, `26/03`, `59`) emits a `RISKY_EDIT` warning:
  only edit fields you own.

### Options

```ts
update(payload, edits, {
  warnings: true, // default: all warnings
  // warnings: false,      // none
  // warnings: ["59"],     // suppress warnings whose tag/path matches exactly
  onWarning: (issue) => console.log(issue.code, issue.tag, issue.message),
});
```

Warnings never block an edit. Errors are thrown as `DeshiQrError` with a
`code`, a `message` and, when relevant, a `tag`.

## `validate(payload, options?)`

Never throws. Collects every problem:

```ts
const { ok, errors, warnings } = validate(payload, { warnings: true });
```

`ok` is true when `errors` is empty — warnings do not make a payload invalid.
`validate(payload, { warnings: false })` drops warnings; errors are always kept.

### Errors

| code                | when                                                                   |
| ------------------- | ---------------------------------------------------------------------- |
| `EMPTY_PAYLOAD`     | empty or non-string payload                                            |
| `UNSUPPORTED`       | payload longer than 4096 characters                                    |
| `BAD_TLV`           | malformed TLV (bad tag/length/truncated) or invalid `26`/`62` template |
| `MISSING_FIELD`     | the payload does not end with tag `63`                                 |
| `CHECKSUM_MISMATCH` | the CRC of the input is invalid                                        |
| `DUPLICATE_TAG`     | the same tag appears twice at the same level                           |

### Warnings

`MISSING_TAG` (`00`, `01`, `59`), `UNKNOWN_TAG`, `BAD_FIELD_VALUE`,
`FIELD_TOO_LONG`, `UNKNOWN_CURRENCY`, `NON_BD_COUNTRY`, `UNKNOWN_INSTITUTION`,
`UNKNOWN_MCC`, `STATIC_WITH_AMOUNT`, `DYNAMIC_WITHOUT_AMOUNT`, and `RISKY_EDIT`
(from `update` only). All warnings are suppressible with the `warnings` option.

## Guarantees

- Zero dependencies, environment-agnostic (Node, browser, Deno, edge runtimes).
- Provider-agnostic: an edit changes only the tags you asked for (plus tag `01`
  when the amount changes) — every other field and sub-field is preserved.
- Deterministic: the same edits on the same payload always produce the same
  payload.

## License

MIT © Himel Das
