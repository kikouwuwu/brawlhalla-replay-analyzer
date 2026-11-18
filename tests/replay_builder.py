"""Genera replays sintéticos para tests, escribiendo el formato al revés del parser."""

from __future__ import annotations

import zlib
from typing import Dict, List, Tuple

from bhanalyzer.bitreader import xor_bytes


class BitWriter:
    def __init__(self):
        self._bits: List[int] = []

    def bits(self, value: int, count: int):
        for i in range(count - 1, -1, -1):
            self._bits.append((value >> i) & 1)

    def bool(self, value: bool):
        self._bits.append(int(value))

    def u16(self, value: int):
        self.bits(value & 0xFFFF, 16)

    def u32(self, value: int):
        self.bits(value & 0xFFFFFFFF, 32)

    def string(self, value: str):
        data = value.encode("utf-8")
        self.u16(len(data))
        for b in data:
            self.bits(b, 8)

    def to_bytes(self) -> bytes:
        padded = self._bits + [0] * (-len(self._bits) % 8)
        out = bytearray()
        for i in range(0, len(padded), 8):
            byte = 0
            for bit in padded[i:i + 8]:
                byte = (byte << 1) | bit
            out.append(byte)
        return bytes(out)


def build_replay(
    players: List[Tuple[int, str]],
    inputs: Dict[int, List[Tuple[int, int]]],
    deaths: List[Tuple[int, int]],
    length_ms: int,
) -> bytes:
    w = BitWriter()
    w.u32(250)  # versión

    w.bits(3, 4)  # header
    w.u32(1234)
    w.u32(7)
    w.string("Ranked 1v1")
    w.bool(True)

    w.bits(4, 4)  # game data
    for _ in range(15):
        w.u32(3)
    w.u32(12)  # level id
    w.u16(1)  # leyendas por jugador
    for entity_id, name in players:
        w.bool(True)
        w.u32(entity_id)
        w.u32(entity_id * 10)
        w.string(name)
        for _ in range(6 + 8):
            w.u32(0)
        w.u16(0)
        w.u16(0)
        w.bool(True)  # un bitfield de taunts
        w.u32(0b101)
        w.bool(False)
        w.u16(0)
        w.u32(entity_id)  # team
        w.u32(0)
        w.u32(4)  # hero id
        w.u32(0)
        w.u32(0)
        w.bool(False)
        w.bits(0, 15)
        w.bool(False)
        w.bits(0, 15)
        w.bool(False)  # bot
        w.bool(False)  # handicaps
    w.bool(False)
    w.u32(0)  # checksum

    w.bits(6, 4)  # results
    w.u32(length_ms)
    w.bool(True)
    for entity_id, _ in players:
        w.bool(True)
        w.bits(entity_id, 5)
        w.u16(1)
    w.bool(False)
    w.u32(0)

    w.bits(5, 4)  # knockout faces
    for entity_id, ts in deaths:
        w.bool(True)
        w.bits(entity_id, 5)
        w.u32(ts)
    w.bool(False)

    w.bits(1, 4)  # inputs
    for entity_id, entity_inputs in inputs.items():
        w.bool(True)
        w.bits(entity_id, 5)
        w.u32(len(entity_inputs))
        for ts, flags in entity_inputs:
            w.u32(ts)
            w.bool(flags != 0)
            if flags:
                w.bits(flags, 14)
    w.bool(False)

    w.bits(2, 4)  # fin
    return zlib.compress(xor_bytes(w.to_bytes()))
