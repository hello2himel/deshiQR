"""Make ``src/`` importable when the tests run via ``unittest discover``."""

from __future__ import annotations

import os
import sys

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import warnings  # noqa: E402

from deshiqr import DeshiQrWarning  # noqa: E402

# The default update() sink is warnings.warn; keep the suite output focused.
warnings.simplefilter("ignore", DeshiQrWarning)
