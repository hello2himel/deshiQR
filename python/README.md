# deshiqr (Python)

[![PyPI](https://img.shields.io/pypi/v/deshiqr.svg)](https://pypi.org/project/deshiqr/)
[![Python versions](https://img.shields.io/pypi/pyversions/deshiqr.svg)](https://pypi.org/project/deshiqr/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](../LICENSE)

Load a **Bangla QR** (NPSB / EMVCo) payload, edit any tag, validate it, and get
the updated payload back. Two functions, no state, no network, no QR rendering —
you render the QR however you like.

This is a faithful, standard-library-only port of the zero-dependency
[`deshiqr`](https://www.npmjs.com/package/deshiqr) npm package
([`packages/deshiqr`](../packages/deshiqr)); both expose exactly the same
behaviour, codes and messages.

- **Zero runtime dependencies.** Python 3.9+, standard library only.
- `update(payload, edits, options=None)` — edit aliases or numeric tag paths,
  remove tags with `None`, re-seal the checksum and return the new payload.
- `validate(payload, options=None)` — non-throwing validation with stable error
  and warning codes; never surprises you with an exception.
- Provider-agnostic: only the tags you edit (plus the checksum, and tag `01`
  when you change the amount) differ from the input.
- Type hints throughout (`py.typed`).

deshiQR never touches money, never talks to a bank and never generates a QR.

## Install

```sh
pip install deshiqr
```

## Quickstart

```python
from deshiqr import update, validate

# Synthetic demo payload — not a real merchant.
payload = (
    "00020101021126470014bd.org.bb.npsb0102020204200203110100000000053030505802"
    "BD5910DEMO STORE6005Dhaka63049C89"
)

# Add an amount: tag 54 is inserted and tag 01 flips to dynamic ("12").
updated = update(payload, {"amount": 500, "reference": "BILL123"})
print(updated)

report = validate(updated)
print(report.ok, report.errors, report.warnings)  # True [] []

# Warnings go to the stdlib warnings module unless you redirect them.
seen = []
update(payload, {"name": "DEMO STORE 2"}, {"onWarning": seen.append})
for issue in seen:
    print(issue.code, issue.tag, issue.message)  # RISKY_EDIT 59 …
```

`update` raises `DeshiQrError` for invalid input or invalid edits. `validate`
never raises; it collects every problem and returns a `ValidationReport` with
`.ok`, `.errors` and `.warnings` lists of `DeshiQrIssue` (`.code`, `.message`,
`.tag`).

## `update(payload, edits, options=None) -> str`

`edits` is a mapping from a named alias or a numeric tag path to a string, a
number, or `None` (removal). Tag paths look like `"54"`, `"62/01"`, `"26/03"` or
`"80/01"`. If a call contains both an alias and a tag path for the same target,
**the tag path wins**. `None` removes the tag; removing every sub-tag empties and
drops the enclosing template.

| alias           | tag/path                                                   |
| --------------- | ---------------------------------------------------------- |
| `amount`        | `54` (number or numeric string, formatted to exactly 2 dp) |
| `currency`      | `53`                                                       |
| `country`       | `58`                                                       |
| `mcc`           | `52`                                                       |
| `name`          | `59`                                                       |
| `city`          | `60`                                                       |
| `reference`     | `62/01`                                                    |
| `customerLabel` | `62/06`                                                    |
| `account`       | `26/03`                                                    |
| `institution`   | `26/00`                                                    |

```python
update(payload, {"amount": "1250.5"})        # tag 54 -> "1250.50", tag 01 -> "12"
update(payload, {"amount": None})            # remove the amount, tag 01 -> "11"
update(payload, {"62/01": "BILL123"})        # nested edit inside tag 62
update(payload, {"city": None})              # remove tag 60
update(payload, {"name": "X", "59": "Y"})    # "Y" (tag path wins)
```

Rules enforced for you:

- **Tag `63` is never editable** — the CRC-16/CCITT-FALSE checksum is always
  dropped and re-sealed (uppercase, 4 hex characters).
- **Amounts are never rounded.** More than two decimals, zero, negatives,
  non-numeric values and values above `99999999.99` raise `BAD_AMOUNT`.
- **Tag `01` follows the amount** unless you edit `01` explicitly: after an edit
  that touches `54`, `01` becomes `"12"` when an amount is present and `"11"`
  when it is removed.
- **New tags are inserted in ascending numeric order** at their level; existing
  fields keep their current order. New tags are allowed, with an `UNKNOWN_TAG`
  warning.
- **Nested edits require a valid parent template.** Editing `"62/01"` when tag
  `62` is missing or not valid TLV raises `BAD_TAG`. Tags `80` and `81` are
  preserved verbatim until you edit inside them.

## `validate(payload, options=None) -> ValidationReport`

Reports every problem in one pass:

| error code          | when                                                       |
| ------------------- | ---------------------------------------------------------- |
| `EMPTY_PAYLOAD`     | empty or non-string payload                                |
| `BAD_TLV`           | malformed TLV, invalid nested template, bad checksum field |
| `MISSING_FIELD`     | payload does not end with tag `63`                         |
| `CHECKSUM_MISMATCH` | CRC of the input does not match                            |
| `DUPLICATE_TAG`     | the same tag appears twice at the same level               |
| `UNSUPPORTED`       | payload longer than 4096 characters                        |

`update` additionally raises `BAD_AMOUNT`, `BAD_TAG` and `BAD_VALUE` for bad
edits, and rejects duplicate tags in its input with `DUPLICATE_TAG`.

Advisory warnings (all suppressible):

| warning code             | when                                                                   |
| ------------------------ | ---------------------------------------------------------------------- |
| `MISSING_TAG`            | recommended tag absent: `00`, `01`, `59`                               |
| `UNKNOWN_TAG`            | tag/path not in the documented field table                             |
| `BAD_FIELD_VALUE`        | value violates the field's documented syntax                           |
| `FIELD_TOO_LONG`         | value longer than the field's documented maximum                       |
| `UNKNOWN_CURRENCY`       | `53` not in `050, 356, 764, 840, 978`                                  |
| `NON_BD_COUNTRY`         | `58` is not `BD`                                                       |
| `UNKNOWN_INSTITUTION`    | `26/00` is not `bd.org.bb.npsb` (unverified provider, still supported) |
| `UNKNOWN_MCC`            | `52` not in `5411, 6016, 5999`                                         |
| `STATIC_WITH_AMOUNT`     | `01` is `11` but tag `54` is present                                   |
| `DYNAMIC_WITHOUT_AMOUNT` | `01` is `12` but tag `54` is absent                                    |
| `RISKY_EDIT`             | `update` edited an identity/account field (`26/00`, `26/03`, `59`)     |

## Warnings and suppression

Both functions accept an `options` argument that is either a dict or an options
dataclass:

```python
from deshiqr import UpdateOptions, ValidateOptions

# dict form (camelCase keys, matching the spec)
update(payload, {"name": "X"}, {"warnings": ["59"], "onWarning": print})

# dataclass form
update(payload, {"name": "X"}, UpdateOptions(warnings=False))
validate(payload, ValidateOptions(warnings=["26/00"]))
```

- `warnings=True` (default) shows every warning; `False` hides them all.
- A list of tag/path strings suppresses warnings whose `.tag` matches **exactly**
  (`"62"` does not suppress `"62/01"`).
- `onWarning` / `on_warning` receives each visible `DeshiQrIssue`. Without it,
  `update` calls the standard library's `warnings.warn` with
  `deshiqr.DeshiQrWarning` (JavaScript uses `console.warn`).
- `validate` only filters the `warnings` in its report; errors are always kept.

Warnings never block an edit. Errors always raise from `update` and are returned
by `validate`.

## Documentation

- [`docs/format.md`](../docs/format.md) — the Bangla QR field table (tags,
  aliases, syntax, lengths, known values).
- [`docs/api.md`](../docs/api.md) — `update`/`validate` reference and the
  static browser bundle on GitHub Pages.
- [`docs/demo-payloads.md`](../docs/demo-payloads.md) — synthetic fixtures used
  by this test suite.

## Development

```sh
python3 -m unittest discover -s tests -v
# Python 3.9 (uv):
PYTHONPATH=src uv run --python 3.9 --no-project python -m unittest discover -s tests
python3 -m pip wheel . --no-deps
```

## License

MIT — see [`LICENSE`](LICENSE).
