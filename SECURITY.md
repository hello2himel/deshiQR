# Security policy

## What deshiQR is, in security terms

deshiQR edits Bangla QR **payloads**: it takes a payload string and an `edits` object and returns the
updated payload string. It ships as one npm package (`deshiqr`), one Python package (`deshiqr`) and a static browser bundle
on GitHub Pages (`window.DeshiQR`). It runs no server, stores nothing, and has no accounts.

It is **not** a payment service provider:

- deshiQR never takes custody of funds, holds balances, or routes money.
- deshiQR does not confirm that a payment happened. A QR is an instruction to pay; nothing here proves
  money moved.
- deshiQR is not affiliated with bKash, Nagad, Rocket, or NPSB.
- Running a payment service in Bangladesh may require a Bangladesh Bank licence. Get local legal advice
  before building a business that handles money. This project deliberately stops at payload strings.

## Edits are at the caller's risk

The editor applies whatever edits you ask for. Editing the account (`26/03`), the institution AID
(`26/00`) or the merchant name (`59`) can mislead a payer into paying someone else. `update` surfaces a
`RISKY_EDIT` warning for those fields, but it does not block them: only edit payloads you own and only
change what you are entitled to change.

## What is protected, and what is not

- **The payload is public data.** The account number is printed on shop walls and is meant to be
  scanned and shared. Masking it in a UI is cosmetic. The bundle is public for the same reason: it
  only rewrites a payload string the caller already has.
- **Nothing secret is stored or required.** There is no server, database, key or secret; there is no
  merchant record to leak and nothing to configure.
- **Verify your payload source.** deshiQR edits whatever well-formed payload it is given. A swapped or
  malicious payload produces a perfectly valid payload for the wrong account, so keep the base payload
  on your own trusted side and compare the name the banking app shows with the shop's name before
  paying.
- **Impersonation is the real risk.** Anyone can copy a payload from a shop and publish a page that
  encodes it. deshiQR cannot detect that; the payer's app shows the account holder name for a reason.
- **No QR rendering is involved.** deshiQR returns a payload string; whatever library or service you
  use to render it is your trust boundary.
- **Hosting misconfiguration.** If you put credentials in client code, you own that breach. The
  libraries need none.

## No real data in this repository

Fixtures are synthetic: account `01000000000`, `DEMO STORE`, dummy NPSB tokens. Never open a pull
request containing a real QR payload, screenshot, account number, or NPSB token.

## Reporting a vulnerability

Email **hello2himel@proton.me** with:

- a description and impact,
- reproduction steps or a minimal proof of concept,
- the affected package/version (npm `deshiqr`, pip `deshiqr`) and, if relevant, the deployment URL.

Please do not open a public issue for a live vulnerability. We aim to acknowledge within 72 hours and
to ship a fix or mitigation within 14 days for confirmed issues. Coordinated disclosure is appreciated;
credit will be given unless you prefer otherwise.
