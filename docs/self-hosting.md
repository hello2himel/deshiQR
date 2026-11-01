# Hosting deshiQR on GitHub Pages

deshiQR is static. There is no server, no database and no HTTP endpoint. The "API" served from GitHub
Pages is the browser bundle: it exposes `window.DeshiQR.update` and `window.DeshiQR.validate`, and the
edit runs in the visitor's browser. GitHub Pages cannot execute server-side code, so there is nothing
to deploy except static files.

For server-side runtimes use the packages instead: npm `deshiqr` (Node/Deno/Bun/workers) or PyPI
`deshiqr` (Python 3.9+). Same implementation, same error and warning codes.

**What gets published:**

- `https://<owner>.github.io/<repo>/deshiqr.global.js` — the bundle (`window.DeshiQR`)
- `https://<owner>.github.io/<repo>/` — an interactive demo (`cdn/index.html`) that takes a payload,
  amount/currency, and shows the updated payload + warnings

The workflow is [`.github/workflows/pages.yml`](../.github/workflows/pages.yml). It runs on every push
to `main` (and manually).

---

## 1. Build and check locally

```bash
pnpm install
pnpm build           # writes packages/deshiqr/dist/
pnpm check:globals   # verifies the bundle in a browser-only sandbox
```

The bundle is `packages/deshiqr/dist/deshiqr.global.js`.

---

## 2. Enable Pages

1. Repository **Settings → Pages → Build and deployment**.
2. Set **Source** to **GitHub Actions** (once).
3. Push to `main`, or run the **Publish browser bundle (GitHub Pages)** workflow manually from the
   Actions tab.

The deploy publishes the bundle and `cdn/index.html` as the site root.

---

## 3. Use the bundle

```html
<script src="https://<owner>.github.io/<repo>/deshiqr.global.js"></script>
<script>
  const updated = DeshiQR.update(payload, { amount: 500, currency: "050" });
  const report = DeshiQR.validate(updated);
</script>
```

- One global: `window.DeshiQR` with `update`, `validate` and `DeshiQrError`.
- No network calls, keys, CORS or configuration. The visitor's browser does the edit.
- The same file is served by jsDelivr/unpkg via the npm package once published:
  `https://cdn.jsdelivr.net/npm/deshiqr@0.1.0/dist/deshiqr.global.js`.

---

## 4. Updating the published bundle

1. Edit `packages/deshiqr/src/`.
2. `pnpm build && pnpm test && pnpm check:globals`.
3. Commit and push to `main`; the workflow redeploys Pages.

GitHub Pages caches aggressively. If a fresh deploy looks stale, hard-refresh, or load the bundle
with a version query (`deshiqr.global.js?v=0.1.1`).

---

## 5. Custom domain / repo path

- Project Pages live under `/<repo>/`; the workflow copies `deshiqr.global.js` next to `index.html`, so
  relative script paths work anywhere.
- Add a custom domain under Settings → Pages; GitHub provisions HTTPS.
- There is no server-side component to point at the custom domain — only static files.

---

## Limits

- **Static only.** GitHub Pages cannot accept POST requests or run functions. If you need an HTTP API,
  run the npm/Python package (or a thin wrapper around it) on your own server/serverless platform; it
  is not included here.
- **No secrets.** The bundle contains none and needs none.
- **Payloads are public data.** Verify where a payload came from and compare the name the payer's app
  shows with the shop's name before paying.

---

## Troubleshooting

| Symptom                             | Likely cause                                                                  |
| ----------------------------------- | ----------------------------------------------------------------------------- |
| `deshiqr.global.js` returns 404     | Pages not enabled with "GitHub Actions", or the workflow has not run yet      |
| Demo page works but bundle is stale | Pages/CDN cache; redeploy or add a `?v=` query                                |
| `DeshiQR is not defined`            | The `<script>` tag has not loaded yet, or the path is wrong for project Pages |
| Workflow fails at `check:globals`   | Run `pnpm build && pnpm check:globals` locally and fix the bundle first       |
| Need an HTTP endpoint               | Not supported by GitHub Pages — use the npm/Python packages in your backend   |
