#!/usr/bin/env python3
"""deshiQR — Python example: update + validate a Bangla QR payload (no QR rendering).

Run from the repo root:
    python3 examples/python.py

Or after installing the package:
    pip install ./python
    python3 examples/python.py

The payload is the synthetic `DEMO STORE` fixture from docs/demo-payloads.md — never a real
merchant payload.
"""

import pathlib
import sys

try:
    from deshiqr import UpdateOptions, update, validate
except ModuleNotFoundError:  # running from a checkout without `pip install ./python`
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python" / "src"))
    from deshiqr import UpdateOptions, update, validate

STATIC_PAYLOAD = (
    "00020101021126470014bd.org.bb.npsb010202020420020311010000000005204601653030505802BD5910"
    "DEMO STORE6005Dhaka62060602FT80660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBBIG5vdCByZWFs"
    "ISE=81660014bd.org.bb.npsb0144ZGVzaGlxciBkdW1teSB0b2tlbiBCIG5vdCByZWFsISE=6304295D"
)

# 1. Apply edits. Edits keys are the same aliases/tag paths as JavaScript.
updated = update(STATIC_PAYLOAD, {"amount": 500, "reference": "BILL123"})
print("Updated payload:")
print(updated)
print()

# 2. Validate the result (never throws; collects every error and warning).
report = validate(updated)
print("validate:", {"ok": report.ok, "errors": report.errors, "warnings": report.warnings})
print()

# 3. Options: a dict or an UpdateOptions dataclass. Warnings never block the edit.
update(
    STATIC_PAYLOAD,
    {"amount": 500, "account": "01000000000"},
    UpdateOptions(on_warning=lambda issue: print("warning:", issue.code, issue.tag, "-", issue.message)),
)
print()

# 4. `null` removes a tag; update(payload) / update(payload, {}) is validate-only.
without_amount = update(updated, {"amount": None})
print("validate-only identical:", update(STATIC_PAYLOAD, {}) == STATIC_PAYLOAD)
print("warnings with filter:", validate(updated, {"warnings": ["59", "62/01"]}).warnings)
print("amount removed:", without_amount)
