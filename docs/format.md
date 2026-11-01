# Bangla QR payload format

The QR printed by bKash (and accepted by other Bangla QR capable apps) is an EMVCo-style TLV payload.
deshiQR calls this a **Bangla QR**. This page is the field-level reference the library is built
against, and the source of truth for edits.

## Reference implementations

The format is language-neutral. This repo ships two implementations, one package per platform, both
pinned to the same synthetic fixtures in [`demo-payloads.md`](./demo-payloads.md):

- **JavaScript/TypeScript** — npm `deshiqr` (canonical): `update` and `validate`. Also loadable as the
  browser global `window.DeshiQR` from `dist/deshiqr.global.js`.
- **Python** — `pip install deshiqr` ([`../python/`](../python/README.md)), a stdlib-only port with the
  same two functions.

Other languages can implement this page directly: the only requirements are strict TLV parsing,
CRC-16/CCITT-FALSE, and the editing rules below.

## Encoding

Every field is `TTLLVV…`:

| Part  | Bytes | Meaning                                   |
| ----- | ----- | ----------------------------------------- |
| `TT`  | 2     | two-digit tag, as ASCII digits            |
| `LL`  | 2     | two-digit **decimal** length of the value |
| `VV…` | `LL`  | value, UTF-8                              |

The standard counts `LL` in **UTF-8 bytes**, not characters. A value containing non-ASCII text (a
Bangla merchant name, for example) therefore counts three bytes per Bangla character: the name
`রহিম ট্রেডার্স` is 14 characters but 40 bytes, so its field is written `5940রহিম ট্রেডার্স`, and the
same payload's city `ঢাকা` is 4 characters / 12 bytes → `6012ঢাকা`. deshiQR parses such payloads by
walking byte offsets and decoding each value as UTF-8, so real bKash/bank Bangla QRs work.

Some producers count characters instead of bytes. deshiQR auto-detects the unit by parsing and then
re-encoding the payload: it tries **bytes first**, then **characters**, and accepts the first unit that
round-trips to the exact input. All-ASCII payloads round-trip in both (one byte is one character), so
they detect as bytes and their bytes on the wire are unchanged.

The detected unit is remembered: `update()` re-encodes a character-counted payload with character
lengths and a byte-counted payload with byte lengths. `update(payload)` / `update(payload, {})` is
still a byte-identical round-trip for valid input in either unit.

A value's encoded length must fit in two digits: at most 99 units — 99 bytes in a byte-counted payload,
99 characters in a character-counted one. The `Length` values in the field table below are **character
counts** of the documented field constraints.

There is no terminator and no escaping. The payload is the concatenation of the fields, ending with
the checksum field. Values that are themselves TLV trees (tags `26`, `62`, `80`, `81`) have a length
covering their whole subtree, counted in the same unit as their parent (UTF-8 bytes for standard
payloads).

## Field table

Tags not listed here are still allowed (they are preserved, and reported with an `UNKNOWN_TAG`
warning). `alias` is the key you can pass in `edits` instead of the tag path.

| Tag/path   | Name                   | Alias           | Syntax                    | Length | Known values / notes                                                                                                                        |
| ---------- | ---------------------- | --------------- | ------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `00`       | payload format         | —               | exactly `01`              | 2      | `01`                                                                                                                                        |
| `01`       | point of initiation    | —               | `11` static, `12` dynamic | 2      | auto-set by amount edits unless explicitly edited                                                                                           |
| `26`       | account template       | —               | TLV subtree               | ≤ 99   | keep; edit sub-tags below at own risk                                                                                                       |
| `26/00`    | institution AID        | `institution`   | ASCII                     | ≤ 32   | `bd.org.bb.npsb` (NPSB Bangla QR); other providers unverified                                                                               |
| `26/01`    | template version       | —               | 2 digits                  | 2      | `02` in samples                                                                                                                             |
| `26/02`    | scheme/variant         | —               | 4 digits                  | 4      | `2002` in samples                                                                                                                           |
| `26/03`    | account identifier     | `account`       | alphanumerics             | 4–34   | format constraint; samples use 11 digits (synthetic `01000000000`)                                                                          |
| `52`       | merchant category code | `mcc`           | 4 digits                  | 4      | examples: `5411` grocery, `6016` financial institutions, `5999` specialty retail; merchant/provider chooses                                 |
| `53`       | currency               | `currency`      | ISO 4217 numeric          | 3      | `050` = BDT (the Bangla QR currency). Other ISO codes (`356`, `764`, `840`, `978`) are accepted structurally but unverified for this format |
| `54`       | amount                 | `amount`        | decimal, exactly 2 dp     | 4–11   | `0.01`–`99999999.99` (max 8 integer digits + `.` + 2 decimals); no silent rounding                                                          |
| `58`       | country                | `country`       | ISO 3166-1 alpha-2        | 2      | `BD`                                                                                                                                        |
| `59`       | merchant name          | `name`          | text                      | 1–25   | exactly as issued on the merchant QR                                                                                                        |
| `60`       | merchant city          | `city`          | text                      | 1–15   | e.g. `Dhaka`                                                                                                                                |
| `62`       | additional data        | —               | TLV subtree               | ≤ 99   | optional                                                                                                                                    |
| `62/01`    | reference / bill no.   | `reference`     | printable ASCII           | 1–32   | e.g. `BILL123`; bKash dynamic QRs typically use 25 characters (verify per account type)                                                     |
| `62/06`    | customer label         | `customerLabel` | text                      | ≤ 99   | `FT` in bKash samples                                                                                                                       |
| `80`, `81` | token templates        | —               | TLV subtree               | ≤ 99   | opaque; `00` AID, `01` base64 token (~44 chars); preserve verbatim                                                                          |
| `63`       | CRC-16/CCITT-FALSE     | —               | 4 uppercase hex           | 4      | computed automatically; edits rejected                                                                                                      |
| other      | unknown tag            | tag path        | any                       | ≤ 99   | allowed with `UNKNOWN_TAG` warning                                                                                                          |

Lengths and character sets in this table are **format constraints** enforced by the editor. Values
under "known values" are illustrative examples, not a complete registry: a merchant or provider may
use other MCCs, and only `050` (BDT) is verified as the Bangla QR currency here. Fixtures in this repo
are synthetic; never derive the field table from a real merchant payload.

### Editing risk

Editing `26/03` (account), `26/00` (institution) or `59` (merchant name) changes who a payer would
pay. That can mislead people — only edit payloads you own. `update` surfaces a `RISKY_EDIT` warning for
those fields but still performs the edit (callers own the decision). The opaque token templates `80`
and `81` must be preserved verbatim; the editor never rewrites them. See
[`../SECURITY.md`](../SECURITY.md).

## Checksum

CRC-16/CCITT-FALSE over every UTF-8 byte **before** the final four characters, with the literal prefix
`6304` included:

1. Build the payload with the checksum field prefix: `… + "6304"`.
2. `crc = crc16(payloadWithPrefix)` (init `0xFFFF`, polynomial `0x1021`, no reflection, no final
   XOR) — a 16-bit value.
3. Append the uppercase, zero-padded hex (`"29B1"`).

Verification: `crc16(payload.slice(0, -4)) === payload.slice(-4)`. Anchor vector:
`crc16("123456789") === "29B1"`.

`63` is always dropped and re-sealed after a non-empty edit, even when its value would be unchanged.
Editing `63` directly is rejected with `BAD_TAG`. A validate-only call (`update(payload)` or
`update(payload, {})`) returns the payload untouched.

## Editing semantics

- An `edits` object maps aliases or tag paths to values. Tag paths match `^[0-9]{2}(/[0-9]{2})*$`.
- A tag-path key and an alias for the same target in one call: the tag path wins.
- `null` removes the tag (top-level tag or sub-tag). Removing a template's last sub-tag removes the
  template itself; setting a whole template to `""` keeps an explicitly empty template field.
- New tags are allowed (any two-digit tag). They are inserted in ascending numeric order at their
  level; existing fields keep their current order.
- Editing a nested path whose parent tag is absent or not valid TLV raises `BAD_TAG`. Tags `80`/`81`
  are opaque: their whole value may be replaced, and a nested edit under them is allowed only when the
  current value is valid TLV.
- Editing `01` is allowed. When the edits target the amount and `01` is not edited explicitly, `01` is
  set to `12` when `54` exists after the edits and to `11` when it does not. Edits that do not target
  the amount leave `01` untouched.
- The amount (`54` and the `amount` alias) must be a number or numeric string with at most 2
  decimals; it is formatted to exactly 2 decimals. Values are never rounded, and values that are not a
  valid amount (≤ 0, > 99,999,999.99, or more than 2 decimals) raise `BAD_AMOUNT`.
- Values that are not a string or number (other than `null`) raise `BAD_VALUE`; encoded values longer
  than 99 units (UTF-8 bytes in a byte-counted payload, characters in a character-counted one) raise
  `BAD_VALUE` too.

## Worked example

Input — the synthetic static fixture from [`demo-payloads.md`](./demo-payloads.md), CRC `295D`:

```
00020101021126470014bd.org.bb.npsb010202020420020311010000000005204601653030505802BD5910DEMO STORE6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304295D
```

Edits:

```js
update(staticPayload, { amount: 500, reference: "BILL123" });
```

Output — a dynamic payload with a new CRC `DB6A`:

```
00020101021226470014bd.org.bb.npsb010202020420020311010000000005204601653030505406500.005802BD5910DEMO STORE6005Dhaka62170107BILL1230602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304DB6A
```

What changed:

| Field                    | Before   | After                    | Why                               |
| ------------------------ | -------- | ------------------------ | --------------------------------- |
| `01` point of initiation | `11`     | `12`                     | `54` exists after the edits       |
| `54` amount              | absent   | `500.00`                 | `amount: 500` formatted to 2 dp   |
| `62/01` reference        | absent   | `BILL123`                | `reference` alias                 |
| `62` subtree             | `0602FT` | `0107BILL1230602FT`      | inserted in sub-tag order (01,06) |
| `63` checksum            | `295D`   | `DB6A`                   | re-sealed after the edit          |
| everything else          | —        | unchanged, byte for byte | only the rows above differ        |

Removing the amount is the inverse edit: `update(amountOnlyPayload, { amount: null })` drops `54` and
sets `01` back to `11`, re-sealing the checksum. Applied to the amount-only output `…63049781`, the
result is the original static payload (`…6304295D`).

## Real-world reality check

- Apps that scan Bangla QR expect the account, name and tokens to belong together. Changing the
  account number or name to a _different_ owner is not a supported use case; deshiQR edits the fields
  you ask for and keeps everything else exactly as issued.
- Payloads are public data, but they are not yours to swap. Verify where a payload came from and
  compare the name the banking app shows with the shop's name before paying.
- The parser is provider-agnostic, but the known values above were observed on bKash/NPSB payloads.
  Other providers are reported as unverified (`UNKNOWN_INSTITUTION`) rather than asserted as tested.
