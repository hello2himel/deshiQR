import { defineConfig } from "tsup";

export default defineConfig([
  {
    // Main entry: update + validate. No DOM side effects, no QR code.
    entry: { index: "src/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: true,
    target: "es2022",
    outExtension: ({ format }) => ({ js: format === "cjs" ? ".cjs" : ".js" }),
  },
  {
    // Single browser global for plain <script> usage: window.DeshiQR.
    // Served by unpkg/jsDelivr (`dist/deshiqr.global.js`) and the CDN workflow.
    entry: { deshiqr: "src/global.ts" },
    format: ["iife"],
    globalName: "DeshiQR",
    sourcemap: true,
    target: "es2020",
    minify: true,
  },
]);
