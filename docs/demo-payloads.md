# Demo payloads (synthetic only)

Every payload on this page is **synthetic**. No real merchant, account number, name, city or NPSB
token is used anywhere in this repo. All fixtures use:

- account `01000000000` — deliberately unassignable operator prefix, not a real number
- name `DEMO STORE`, city `Dhaka`
- NPSB tokens that literally spell `deshiqr dummy token A/B not real`
- institution `bd.org.bb.npsb` (the NPSB Bangla QR account template)

If you need a new fixture, start from an existing one, change the synthetic values, and regenerate the
CRC-16/CCITT-FALSE checksum (any `update` call re-seals it). Keep it fake.

These values are used by the test suites in [`../packages/deshiqr`](../packages/deshiqr) and
[`../python/tests`](../python/tests), the examples, and the docs.

## Static QR (no amount)

The canonical fixture. `01` is `11` (static), there is no `54`, and the CRC is `295D`.

```
00020101021126470014bd.org.bb.npsb010202020420020311010000000005204601653030505802BD5910DEMO STORE6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304295D
```

## Static edited to 500.00 BDT (`{ "amount": 500 }`)

Only `01` (`11` → `12`), `54` (`500.00`, inserted after `53`) and `63` (`295D` → `9781`) change.

```
00020101021226470014bd.org.bb.npsb010202020420020311010000000005204601653030505406500.005802BD5910DEMO STORE6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=63049781
```

## Static edited to 500.00 BDT + reference `BILL123` (`{ "amount": 500, "reference": "BILL123" }`)

Adds sub-tag `62/01` inside the existing `62` template (kept in ascending sub-tag order: `01`, then
`06`), so the `62` value grows from `0602FT` to `0107BILL1230602FT` and the CRC becomes `DB6A`.

```
00020101021226470014bd.org.bb.npsb010202020420020311010000000005204601653030505406500.005802BD5910DEMO STORE6005Dhaka62170107BILL1230602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304DB6A
```

## Dynamic QR, amount 500.00, 25-character reference

This is the shape real bKash dynamic QRs use (25-character bill number in `62/01`, customer label `FT`).
The reference here is synthetic. CRC `F835`.

```
00020101021226470014bd.org.bb.npsb010202020420020311010000000005204601653030505406500.005802BD5910DEMO STORE6005Dhaka62350125DEMOQR0VZeK2MfbVRI6w36osd0602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304F835
```

## Minimal QR (no MCC, no tokens, no additional data)

CRC `9C89`.

```
00020101021126470014bd.org.bb.npsb0102020204200203110100000000053030505802BD5910DEMO STORE6005Dhaka63049C89
```

## Longer merchant name / different MCC

CRC `94E0`.

```
00020101021126470014bd.org.bb.npsb010202020420020311010000000005204541153030505802BD5919DEMO SUPER SHOP LTD6010Chattogram630494E0
```

## Generic layout (not bKash — proves provider-agnostic editing)

A synthetic layout with a made-up institution AID, a different MCC, no NPSB token templates and no
tag 62. Editing only the amount changes only `01`, `54` and `63`, so this works exactly like a bKash
payload; the tests pin it. CRC `818D`.

```
00020101021126410022example.org.generic-qr0311017000000005204541153030505802BD5912GENERIC SHOP6006Sylhet6304818D
```

Edited at 1250.50 BDT (`{ "amount": 1250.5 }`) — the only differences are `01` `11`→`12` and the
inserted `54`:

```
00020101021226410022example.org.generic-qr03110170000000052045411530305054071250.505802BD5912GENERIC SHOP6006Sylhet630480A2
```

## Warning-rich fixture

A deliberately odd but well-formed payload for exercising `validate`'s warning path. It is still
synthetic; do not copy these values into a real payload. It produces these warnings:

- `DYNAMIC_WITHOUT_AMOUNT` — `01` is `12` but there is no `54`
- `UNKNOWN_MCC` — `52` is `9999`
- `UNKNOWN_CURRENCY` — `53` is `999`
- `NON_BD_COUNTRY` — `58` is `US`
- `FIELD_TOO_LONG` — `59` is longer than 25 characters
- `UNKNOWN_TAG` — `99` is not a documented tag

CRC `6F19`.

```
00020101021226470014bd.org.bb.npsb010202020420020311010000000005204999953039995802US5939THIS DEMO MERCHANT NAME IS FAR TOO LONG6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFsISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=990301X63046F19
```

## Invalid fixtures

These are not valid payloads; tests use them for error paths.

- **Corrupted checksum** — take the static payload and replace the last four characters with `0000`
  → `CHECKSUM_MISMATCH`.
- **Truncated TLV** — drop the last 12 characters → `BAD_TLV` (or `MISSING_FIELD`, depending on where
  the truncation lands).
- **Missing checksum** — remove the whole `6304…` field → `MISSING_FIELD`.
- **Duplicate tag** — repeat a top-level field (e.g. two `59` fields) → `DUPLICATE_TAG`.
- **Oversized** — pad any payload past 4096 characters → `UNSUPPORTED`.
- **Invalid amount edit** — `update(staticPayload, { amount: 0 })` or `{ amount: "1.234" }` →
  `BAD_AMOUNT`.

## Notes

- `62/06 = "FT"` is the customer label carried by the sample bKash payloads; the editor preserves it
  when it is not edited.
- `80` and `81` are opaque NPSB token templates. The editor treats them as opaque and preserves them
  verbatim — never parse or mutate their contents.
- CRC-16/CCITT-FALSE anchor used in tests: `crc16("123456789") === "29B1"`.
- Real bKash **dynamic** QRs carry a 25-character bill number in tag `62/01`, which makes the tag `62`
  field 35 characters long (`6235 0125 <25-char reference> 0602FT`). The dynamic fixture above copies
  that shape with a synthetic reference.
- The account identifier is sub-tag `03` of the `26` account template; in the fixtures it is the
  synthetic `01000000000`.
