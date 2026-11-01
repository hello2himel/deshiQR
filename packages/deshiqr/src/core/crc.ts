/**
 * CRC-16/CCITT-FALSE — the checksum used by EMVCo-style QR payloads, including
 * Bangla QR (NPSB).
 *
 * Parameters: poly 0x1021, init 0xFFFF, no input/output reflection, no final XOR.
 * The checksum is the uppercase, zero-padded hex of the 16-bit result.
 * Anchor vector: crc16("123456789") === "29B1".
 */

const encoder = new TextEncoder();

const TABLE: Uint16Array = (() => {
  const table = new Uint16Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n << 8;
    for (let bit = 0; bit < 8; bit++) {
      c = (c & 0x8000) !== 0 ? ((c << 1) ^ 0x1021) & 0xffff : (c << 1) & 0xffff;
    }
    table[n] = c;
  }
  return table;
})();

/** CRC-16/CCITT-FALSE of a string, as 4 uppercase hex characters (e.g. "29B1"). */
export function crc16(input: string): string {
  let crc = 0xffff;
  for (const byte of encoder.encode(input)) {
    crc = ((crc << 8) ^ TABLE[((crc >>> 8) ^ byte) & 0xff]) & 0xffff;
  }
  return crc.toString(16).toUpperCase().padStart(4, "0");
}
