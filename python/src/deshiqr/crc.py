"""CRC-16/CCITT-FALSE, the checksum used by EMVCo-style QR payloads (including
Bangla QR / NPSB).

Parameters: polynomial 0x1021, initial value 0xFFFF, no input/output reflection,
no final XOR. The checksum is the uppercase, zero-padded hex of the 16-bit result.

Anchor vector: ``crc16("123456789") == "29B1"``.
"""

from __future__ import annotations

_TABLE = []
for _n in range(256):
    _c = _n << 8
    for _ in range(8):
        if _c & 0x8000:
            _c = ((_c << 1) ^ 0x1021) & 0xFFFF
        else:
            _c = (_c << 1) & 0xFFFF
    _TABLE.append(_c)
del _n, _c
_TABLE_TUPLE = tuple(_TABLE)
del _TABLE

_MASK = 0xFFFF


def crc16(input: str) -> str:
    """CRC-16/CCITT-FALSE of a UTF-8 string, as four uppercase hex characters."""
    data = input.encode("utf-8") if isinstance(input, str) else str(input).encode("utf-8")
    crc = 0xFFFF
    table = _TABLE_TUPLE
    for byte in data:
        crc = ((crc << 8) ^ table[((crc >> 8) ^ byte) & 0xFF]) & _MASK
    return format(crc, "04X")
