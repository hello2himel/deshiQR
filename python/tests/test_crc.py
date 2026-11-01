"""CRC-16/CCITT-FALSE checksum helper."""

from __future__ import annotations

import unittest

import _support  # noqa: F401

from deshiqr.crc import crc16
from fixtures import STATIC_PAYLOAD


class CrcTests(unittest.TestCase):
    def test_anchor_vector(self):
        self.assertEqual(crc16("123456789"), "29B1")

    def test_always_four_uppercase_hex_characters(self):
        for text in ("", "A", "0002010102", "abc"):
            checksum = crc16(text)
            self.assertEqual(len(checksum), 4)
            self.assertEqual(checksum, checksum.upper())
            int(checksum, 16)

    def test_sealed_fixture_matches_its_checksum(self):
        self.assertEqual(crc16(STATIC_PAYLOAD[:-4]), STATIC_PAYLOAD[-4:])


if __name__ == "__main__":
    unittest.main()
