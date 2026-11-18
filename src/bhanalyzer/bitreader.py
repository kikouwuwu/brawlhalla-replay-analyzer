"""Lector de bits para el formato .replay de Brawlhalla.

El archivo viene comprimido con zlib. Una vez descomprimido, cada byte está
ofuscado con un XOR cíclico de 64 bytes y los datos se leen bit a bit,
del bit más significativo al menos significativo.
"""

from __future__ import annotations

REPLAY_XOR_KEY = bytes([
    0x6B, 0x10, 0xDE, 0x3C, 0x44, 0x4B, 0xD1, 0x46, 0xA0, 0x10, 0x52, 0xC1, 0xB2, 0x31, 0xD3, 0x6A,
    0xFB, 0xAC, 0x11, 0xDE, 0x06, 0x68, 0x08, 0x78, 0x8C, 0xD5, 0xB3, 0xF9, 0x6A, 0x40, 0xD6, 0x13,
    0x0C, 0xAE, 0x9D, 0xC5, 0xD4, 0x6B, 0x54, 0x72, 0xFC, 0x57, 0x5D, 0x1A, 0x06, 0x73, 0xC2, 0x51,
    0x4B, 0xB0, 0xC9, 0x8C, 0x78, 0x04, 0x11, 0x7A, 0xEF, 0x74, 0x3E, 0x46, 0x39, 0xA0, 0xC7, 0xA6,
])


def xor_bytes(data: bytes) -> bytes:
    key_len = len(REPLAY_XOR_KEY)
    return bytes(b ^ REPLAY_XOR_KEY[i % key_len] for i, b in enumerate(data))


class BitReader:
    def __init__(self, data: bytes):
        self._data = xor_bytes(data)
        self._pos = 0  # posición en bits

    @property
    def bits_left(self) -> int:
        return len(self._data) * 8 - self._pos

    def read_bool(self) -> bool:
        byte_index, bit_index = divmod(self._pos, 8)
        if byte_index >= len(self._data):
            raise EOFError("Se acabó el replay antes de lo esperado")
        self._pos += 1
        return bool(self._data[byte_index] & (1 << (7 - bit_index)))

    def read_bits(self, count: int) -> int:
        result = 0
        for _ in range(count):
            result = (result << 1) | self.read_bool()
        return result

    def read_u16(self) -> int:
        return self.read_bits(16)

    def read_i16(self) -> int:
        value = self.read_u16()
        return value - (1 << 16) if value & 0x8000 else value

    def read_u32(self) -> int:
        return self.read_bits(32)

    def read_i32(self) -> int:
        value = self.read_u32()
        return value - (1 << 32) if value & 0x80000000 else value

    def read_string(self) -> str:
        size = self.read_u16()
        return bytes(self.read_bits(8) for _ in range(size)).decode("utf-8", errors="replace")
