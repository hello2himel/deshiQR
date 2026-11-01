# Changelog

Changes to the **deshiQR engine** (npm `deshiqr`, PyPI `deshiqr`, browser bundle). Website and
payment-page changes live in the separate [DeshiPay](https://github.com/hello2himel/deshiPay) repo.

## [Unreleased]

### Added

- UTF-8 byte-length TLV support: value fields whose declared length is the byte length of a multibyte
  value (as real Bangla QR payloads use) now round-trip correctly. ASCII payloads keep the character
  length behaviour.

## [0.1.0] — 2026-11-01

- First release: `update(payload, edits)` and `validate(payload)` for Bangla QR (NPSB/EMVCo) payloads,
  including CRC-16/CCITT-FALSE re-sealing, point-of-initiation flag consistency, field-level edits,
  warnings (with suppression), strict validation and typed errors.
- Published as npm `deshiqr` (ESM/CJS + types + IIFE browser bundle), PyPI `deshiqr`, and a GitHub
  Pages bundle demo.
