# Contributing to deshiQR

Thanks for helping. This repo has one hard rule, a few conventions, and one invariant that must not
regress.

## The hard rule: no real payment data

Never commit a real QR payload, account number, name, NPSB token or merchant screenshot. The QR
payload is public in the physical world, but it is still someone's phone number and name, and this
repo is public.

When you need a new fixture:

1. Start from the structure in [`docs/format.md`](./docs/format.md).
2. Replace the account with `01000000000` (an unassignable operator prefix).
3. Replace name/city with `DEMO STORE` / `Dhaka`.
4. Replace NPSB tokens (tags 80/81) with a base64 string that literally says `deshiqr dummy ...`.
5. Regenerate the CRC-16/CCITT-FALSE checksum (any `update` call re-seals it).
6. Add a test that pins the behaviour, not just the bytes.

The canonical synthetic payloads live in [`docs/demo-payloads.md`](./docs/demo-payloads.md) and the
test fixtures in [`packages/deshiqr`](./packages/deshiqr) and [`python/tests`](./python/tests).

## Setup

Requirements: Node >= 22.18, pnpm 12. Python >= 3.9 for the Python package.

```sh
pnpm install
pnpm build          # the single npm package (update + validate) and the browser bundle
pnpm test           # builds, then runs the TypeScript test suite
pnpm typecheck
pnpm check:globals  # verifies the <script src> bundle after a build

cd python && python3 -m unittest discover -s tests -v   # Python port
```

`pnpm format` runs Prettier (printWidth 110) over the repo.

The repo ships two libraries and a static browser bundle; there is nothing else to run. The bundle is
published to GitHub Pages — see [`docs/self-hosting.md`](./docs/self-hosting.md).

## Repository conventions

- **One package per platform, one public API.** The npm package is `deshiqr` in
  [`packages/deshiqr`](./packages/deshiqr); the Python package is `deshiqr` in [`python`](./python).
  Both expose exactly two functions — `update(payload, edits, options?)` and `validate(payload,
options?)` — and nothing else public. Do not add a second public package name or new top-level
  helpers.
- **No QR generation, no payload reading, no UI.** deshiQR edits payload strings. The caller encodes
  and renders the QR. Do not add encoders, renderers, web components, merchant lookups or payment
  confirmations.
- `deshiqr` has **zero runtime dependencies** in both languages. Don't add one without discussing it
  in an issue first.
- The library is pure: no DOM access, no network, no I/O, no state. It must run in Node, browsers,
  Deno, workers and edge runtimes.
- `python/` is a zero-dependency port of the TypeScript core. Behaviour changes must land in both, with
  TypeScript as the source of truth; error and warning codes/messages stay identical.
- TypeScript strict mode; relative imports use explicit `.ts` extensions. Node runs and tests TS
  directly, bundlers rewrite on publish.
- Tests use `node:test` + `node:assert/strict` (Python: `unittest`). No test framework.
- **No server-side code.** deshiQR is a static bundle plus packages; there is no server function,
  database, API key or deploy step beyond GitHub Pages (`.github/workflows/pages.yml`). Keep it that
  way. The browser bundle is verified by `scripts/check-globals.mjs`.
- **The edit invariant is provider-agnostic by contract:** only the tags the caller edited, tag `01`
  (when the amount is edited) and the re-sealed checksum may change. Everything else is byte-identical.
  If a change would require provider-specific logic, it does not belong in editing; re-pin the
  guarantee with the provider-agnostic test.
- **Warning/error ordering is deterministic:** `RISKY_EDIT` warnings first (sorted by tag path), then
  validation warnings in document order. Edits apply deterministically (aliases first, then tag paths;
  nested edits depth-ascending, then lexicographic). Keep both languages identical.

## Adding a provider or field

1. Get a real payload from that provider and **sanitise it** as described above.
2. Add it to [`docs/demo-payloads.md`](./docs/demo-payloads.md) and to the fixtures used by both test
   suites.
3. Add it to the field table in [`docs/format.md`](./docs/format.md) only if the new tag is understood;
   otherwise document it as an unknown tag.
4. Keep the wording precise: unknown values are warnings (`UNKNOWN_INSTITUTION`, `UNKNOWN_CURRENCY`,
   `UNKNOWN_MCC`, `NON_BD_COUNTRY`), never hard errors. A provider can still be edited without being
   verified — say so honestly.

## Before opening a PR

- [ ] `pnpm typecheck` passes
- [ ] `pnpm test` passes
- [ ] `pnpm build` passes
- [ ] `pnpm check:globals` passes if you touched `packages/deshiqr` (it runs after a build)
- [ ] `cd python && python3 -m unittest discover -s tests -v` passes if you touched `python/`
- [ ] No real payment data anywhere in the diff
- [ ] If public behaviour changed, update `README.md`, `docs/`, the examples where relevant, and
      `CHANGELOG.md`

## Releases

Maintainers only. Update the version in `packages/deshiqr/package.json` and `python/pyproject.toml`
(keep `VERSION` in the package source in sync), commit, then push a tag:

```sh
git tag v0.1.0 && git push origin v0.1.0
```

The tag triggers two release workflows, and Pages deploys separately from `main`:

- `release.yml` — publishes the single npm package `deshiqr` with provenance (needs the `NPM_TOKEN`
  repository secret).
- `release-python.yml` — builds and publishes the Python package to PyPI using trusted publishing
  (configure the PyPI project's trusted publisher for this repo, environment `pypi`).
- `pages.yml` — publishes `dist/deshiqr.global.js` and the demo page to GitHub Pages on every push to
  `main` (enable Pages with "GitHub Actions" as the source once).

## Code of conduct

Be decent. Harassment, scams, or contributions that help impersonate merchants are not welcome.
