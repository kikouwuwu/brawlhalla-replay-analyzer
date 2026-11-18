"""Parser del formato .replay de Brawlhalla.

Estructura portada de BrawlhallaReplayLibrary (MIT, AllHailCheese):
https://github.com/allhailcheese/BrawlhallaReplayLibrary

El replay NO guarda posiciones, daño ni golpes: guarda la configuración de la
partida, los jugadores, los cambios de input de cada jugador con su timestamp
y los momentos en que cada jugador perdió un stock. El juego reconstruye la
partida re-simulando esos inputs.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from pathlib import Path
from typing import Dict, List, Optional, Union

from .bitreader import BitReader


class ObjectType(IntEnum):
    INPUTS = 1
    END = 2
    HEADER = 3
    GAME_DATA = 4
    KNOCKOUT_FACES = 5
    RESULTS = 6
    FACES = 7
    INVALID = 8


class InputFlags(IntFlag):
    NONE = 0
    AIM_UP = 1 << 0
    DOWN = 1 << 1  # "Drop" en el juego: abajo / bajar de plataforma
    LEFT = 1 << 2
    RIGHT = 1 << 3
    JUMP = 1 << 4
    PRIORITISE_NEUTRAL = 1 << 5
    HEAVY = 1 << 6
    LIGHT = 1 << 7
    DODGE = 1 << 8
    PICKUP_THROW = 1 << 9
    TAUNT_UP = 1 << 10
    TAUNT_RIGHT = 1 << 11
    TAUNT_DOWN = 1 << 12
    TAUNT_LEFT = 1 << 13


class InvalidReplayError(ValueError):
    pass


@dataclass
class Header:
    random_seed: int
    playlist_id: int
    playlist_name: Optional[str]
    online: bool


@dataclass
class GameSettings:
    flags: int
    max_players: int
    duration: int
    round_duration: int
    starting_lives: int
    scoring_type_id: int
    score_to_win: int
    game_speed: int
    damage_multiplier: int
    level_set_id: int
    item_spawn_rule_set_id: int
    weapon_spawn_rate_id: int
    gadget_spawn_rate_id: int
    custom_gadget_selection: int
    variation: int


@dataclass
class Hero:
    hero_id: int
    costume_id: int
    stance_index: int
    weapon_skin_1: int
    weapon_skin_2: int


@dataclass
class Player:
    entity_id: int
    player_id: int
    name: str
    team: int
    is_bot: bool
    heroes: List[Hero]


@dataclass
class Input:
    timestamp: int
    flags: InputFlags


@dataclass
class Face:
    entity_id: int
    timestamp: int


@dataclass
class Result:
    length: int
    scores: Dict[int, int]


@dataclass
class Replay:
    version: int
    header: Header
    settings: GameSettings
    level_id: int
    players: List[Player]
    results: List[Result] = field(default_factory=list)
    deaths: List[Face] = field(default_factory=list)
    inputs: Dict[int, List[Input]] = field(default_factory=dict)

    @property
    def length_ms(self) -> int:
        if self.results:
            return max(r.length for r in self.results)
        last = [i.timestamp for inputs in self.inputs.values() for i in inputs]
        return max(last, default=0)

    def player(self, entity_id: int) -> Optional[Player]:
        return next((p for p in self.players if p.entity_id == entity_id), None)


def _read_header(bits: BitReader) -> Header:
    seed = bits.read_u32()
    playlist_id = bits.read_u32()
    playlist_name = bits.read_string() if playlist_id != 0 else None
    return Header(seed, playlist_id, playlist_name, bits.read_bool())


def _read_settings(bits: BitReader) -> GameSettings:
    return GameSettings(*(bits.read_u32() for _ in range(15)))


def _read_hero(bits: BitReader) -> Hero:
    hero_id = bits.read_u32()
    costume_id = bits.read_u32()
    stance_index = bits.read_u32()
    bits.read_bool()  # el juego lo ignora
    weapon_skin_2 = bits.read_bits(15)
    bits.read_bool()  # qué arma se usa para el morph
    weapon_skin_1 = bits.read_bits(15)
    return Hero(hero_id, costume_id, stance_index, weapon_skin_1, weapon_skin_2)


def _read_player(bits: BitReader, hero_count: int) -> Player:
    entity_id = bits.read_i32()
    player_id = bits.read_i32()
    name = bits.read_string()

    for _ in range(6):  # color, spawn bot, companion, emitter, trail, theme
        bits.read_u32()
    for _ in range(8):  # taunts equipados
        bits.read_u32()
    bits.read_u16()  # taunt de victoria
    bits.read_u16()  # taunt de derrota
    while bits.read_bool():  # bitfields de taunts que posee
        bits.read_u32()
    bits.read_u16()  # avatar
    team = bits.read_i32()
    bits.read_i32()  # connection time
    heroes = [_read_hero(bits) for _ in range(hero_count)]
    is_bot = bits.read_bool()
    if bits.read_bool():  # handicaps
        for _ in range(3):
            bits.read_u32()

    return Player(entity_id, player_id, name, team, is_bot, heroes)


def _read_game_data(bits: BitReader):
    settings = _read_settings(bits)
    level_id = bits.read_u32()
    hero_count = bits.read_u16()
    if not 1 <= hero_count <= 5:
        raise InvalidReplayError(f"Cantidad de leyendas inválida: {hero_count}")
    players = []
    while bits.read_bool():
        players.append(_read_player(bits, hero_count))
    if not players:
        raise InvalidReplayError("El replay no tiene jugadores")
    bits.read_u32()  # checksum
    return settings, level_id, players


def _read_result(bits: BitReader) -> Result:
    length = bits.read_u32()
    scores = {}
    if bits.read_bool():
        while bits.read_bool():
            entity_id = bits.read_bits(5)
            scores[entity_id] = bits.read_i16()
    bits.read_u32()  # fanfare de fin de partida
    return Result(length, scores)


def _read_faces(bits: BitReader) -> List[Face]:
    faces = []
    while bits.read_bool():
        entity_id = bits.read_bits(5)
        faces.append(Face(entity_id, bits.read_i32()))
    return sorted(faces, key=lambda f: f.timestamp)


def _read_inputs(bits: BitReader) -> Dict[int, List[Input]]:
    inputs: Dict[int, List[Input]] = {}
    while bits.read_bool():
        entity_id = bits.read_bits(5)
        count = bits.read_i32()
        entity_inputs = inputs.setdefault(entity_id, [])
        for _ in range(count):
            timestamp = bits.read_i32()
            flags = bits.read_bits(14) if bits.read_bool() else 0
            entity_inputs.append(Input(timestamp, InputFlags(flags)))
    return inputs


def parse_bytes(raw: bytes) -> Replay:
    try:
        data = zlib.decompress(raw)
    except zlib.error as exc:
        raise InvalidReplayError("El archivo no es un replay válido (zlib)") from exc

    bits = BitReader(data)
    version = bits.read_u32()
    header = None
    game_data = None
    results: List[Result] = []
    deaths: List[Face] = []
    inputs: Dict[int, List[Input]] = {}

    while True:
        obj_type = bits.read_bits(4)
        if obj_type == ObjectType.HEADER:
            header = _read_header(bits)
        elif obj_type == ObjectType.GAME_DATA:
            game_data = _read_game_data(bits)
        elif obj_type == ObjectType.RESULTS:
            results.append(_read_result(bits))
        elif obj_type == ObjectType.KNOCKOUT_FACES:
            deaths = _read_faces(bits)
        elif obj_type == ObjectType.FACES:
            _read_faces(bits)  # caras de victoria, no se usan
        elif obj_type == ObjectType.INPUTS:
            inputs = _read_inputs(bits)
        elif obj_type == ObjectType.END:
            break
        else:
            raise InvalidReplayError(f"Tipo de objeto desconocido: {obj_type}")

    if header is None or game_data is None:
        raise InvalidReplayError("Faltan el header o los datos de la partida")

    settings, level_id, players = game_data
    return Replay(version, header, settings, level_id, players, results, deaths, inputs)


def parse_file(path: Union[str, Path]) -> Replay:
    return parse_bytes(Path(path).read_bytes())
