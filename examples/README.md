# deshiQR examples

Runnable examples — all static, no server required. All of them do the same thing: **load a Bangla QR payload, apply
edits, print the updated payload and its warnings.** None of them render a QR code — the payload is
just a string, so encode/render it however you like.

Every example uses the **same synthetic demo payload** from
[`docs/demo-payloads.md`](../docs/demo-payloads.md): fake account `01000000000`, merchant `DEMO
STORE`, city `Dhaka`, dummy NPSB tokens. Never paste a real merchant payload into an example, a test
fixture or a docs page.

| Example                                  | Platform                              | Run it                                                     |
| ---------------------------------------- | ------------------------------------- | ---------------------------------------------------------- |
| [`browser.html`](./browser.html)         | browser, single bundle, no build step | `pnpm build`, then open the file in a browser              |
| [`node.mjs`](./node.mjs)                 | Node 22+ (ESM)                        | `pnpm build && node examples/node.mjs`                     |
| [`python.py`](./python.py)               | Python 3.9+                           | `python3 examples/python.py` (or `pip install ./python`)   |
| [`../cdn/index.html`](../cdn/index.html) | the GitHub Pages bundle demo          | published with the bundle by `.github/workflows/pages.yml` |

The public contract is in [`docs/api.md`](../docs/api.md); the field table and a worked edit are in
[`docs/format.md`](../docs/format.md).

## Prerequisites

From the repo root:

```bash
pnpm install
pnpm build   # builds packages/deshiqr/dist/ (the npm package + the browser bundle)
```

That produces one npm package, `deshiqr`, with:

- the two functions `update(payload, edits, options?)` and `validate(payload, options?)`;
- `dist/deshiqr.global.js` — one IIFE bundle for plain `<script src>` pages (global `DeshiQR`).

The Python package lives in [`../python`](../python) (`pip install ./python`, or just run the example
from the repo root).

## 1. `browser.html`

Open the file directly in a browser after `pnpm build` (it loads
`../packages/deshiqr/dist/deshiqr.global.js`), or serve the repo root with any static server. Enter a
payload, an amount and (optionally) a currency, press **Update payload**, and it shows the updated
payload string and any warnings. There is no QR on this page.

```html
<script src="../packages/deshiqr/dist/deshiqr.global.js"></script>
<script>
  const updated = DeshiQR.update(payload, { amount: 500, currency: "050" });
  document.querySelector("#output").textContent = updated;
</script>
```

In production, load the same file from jsDelivr/unpkg
(`https://cdn.jsdelivr.net/npm/deshiqr@0.1.0/dist/deshiqr.global.js`) or self-host it. The bundle also
exposes `DeshiQR.validate`.

## 2. `node.mjs`

```bash
pnpm build
node examples/node.mjs
```

It imports `deshiqr` when the package is installed and falls back to the repo build otherwise. It
demonstrates:

- `update(payload, { amount: 500, reference: "BILL123" })` — amount formatted to `500.00`, tag `01`
  set to `12`, `62/01` inserted, checksum re-sealed;
- `validate(updated)` — `{ ok, errors, warnings }`, never throws;
- `onWarning` — warnings never block an edit;
- `{ amount: null }` — removal, and `update(payload, {})` — validate-only (byte-identical result).

In a real project: `npm install deshiqr` and `import { update, validate } from "deshiqr";`.

## 3. `python.py`

```bash
# from the repo root, no install needed:
python3 examples/python.py

# or install the package:
pip install ./python
python3 examples/python.py
```

It uses `from deshiqr import update, validate` with the same semantics, the same edit keys
(`customerLabel` stays camelCase) and the same error/warning codes. Warnings go to
`warnings.warn(…, DeshiQrWarning)` by default, or to `UpdateOptions(on_warning=…)`.

## Notes

- The payloads here are public data in the real world, but a swapped payload is a scam. Keep your base
  payload on your trusted side and compare the name the payer's app shows with the shop's name.
- Editing identity fields (`26/00`, `26/03`, `59`) raises a `RISKY_EDIT` warning because it can mislead
  payers. Only edit payloads you own — see [`../SECURITY.md`](../SECURITY.md).
- A QR is an instruction to pay, not proof that money moved. deshiQR does not confirm payments.
