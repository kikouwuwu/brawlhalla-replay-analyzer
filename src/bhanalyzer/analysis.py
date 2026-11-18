"""Estadísticas e insights a partir de los inputs de un replay.

Como el replay no trae posiciones, no se puede distinguir un ataque en el
suelo de uno aéreo (nlight vs nair) ni saber si un golpe conectó. Lo que sí
se puede medir es qué presionó cada jugador, cuándo y qué hacía antes de
perder cada stock.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .replay import Face, Input, InputFlags, Replay

PRE_DEATH_WINDOW_MS = 2000
LATE_DODGE_WINDOW_MS = 1000


@dataclass
class Action:
    timestamp: int
    name: str


@dataclass
class DeathContext:
    timestamp: int
    stock_duration_ms: int
    actions_before: List[str]
    dodged_late: bool


@dataclass
class PlayerStats:
    entity_id: int
    name: str
    is_bot: bool
    hero_ids: List[int]
    total_actions: int
    actions_per_minute: float
    attacks: Counter
    dodges: Counter
    jumps: int
    deaths: List[DeathContext]
    insights: List[str] = field(default_factory=list)

    @property
    def total_attacks(self) -> int:
        return sum(self.attacks.values())

    @property
    def total_dodges(self) -> int:
        return sum(self.dodges.values())


def _direction(flags: InputFlags) -> str:
    side = bool(flags & (InputFlags.LEFT | InputFlags.RIGHT))
    if flags & InputFlags.DOWN:
        return "down"
    if side and not flags & InputFlags.PRIORITISE_NEUTRAL:
        return "side"
    return "neutral"


def extract_actions(inputs: List[Input]) -> List[Action]:
    """Convierte los cambios de estado de input en acciones (botón recién presionado)."""
    actions = []
    previous = InputFlags.NONE
    for item in inputs:
        pressed = item.flags & ~previous
        direction = _direction(item.flags)
        if pressed & InputFlags.LIGHT:
            actions.append(Action(item.timestamp, f"light_{direction}"))
        if pressed & InputFlags.HEAVY:
            actions.append(Action(item.timestamp, f"sig_{direction}"))
        if pressed & InputFlags.DODGE:
            kind = "spot" if direction == "neutral" and not item.flags & InputFlags.AIM_UP else "directional"
            actions.append(Action(item.timestamp, f"dodge_{kind}"))
        if pressed & InputFlags.JUMP:
            actions.append(Action(item.timestamp, "jump"))
        if pressed & InputFlags.PICKUP_THROW:
            actions.append(Action(item.timestamp, "pickup_throw"))
        previous = item.flags
    return actions


def _death_contexts(actions: List[Action], deaths: List[Face]) -> List[DeathContext]:
    contexts = []
    stock_start = 0
    for death in deaths:
        window = [a for a in actions if death.timestamp - PRE_DEATH_WINDOW_MS <= a.timestamp <= death.timestamp]
        dodged_late = any(
            a.name.startswith("dodge") and a.timestamp >= death.timestamp - LATE_DODGE_WINDOW_MS for a in window
        )
        contexts.append(DeathContext(
            timestamp=death.timestamp,
            stock_duration_ms=death.timestamp - stock_start,
            actions_before=[a.name for a in window],
            dodged_late=dodged_late,
        ))
        stock_start = death.timestamp
    return contexts


def _insights(stats: PlayerStats) -> List[str]:
    tips = []
    if stats.total_attacks >= 20:
        move, count = stats.attacks.most_common(1)[0]
        share = count / stats.total_attacks
        if share >= 0.35:
            tips.append(
                f"El {share:.0%} de tus ataques es {move}. Eres predecible: "
                "un rival atento va a esperar ese ataque y castigarlo."
            )
        if stats.attacks.get("sig_neutral", 0) + stats.attacks.get("sig_side", 0) + stats.attacks.get("sig_down", 0) > stats.total_attacks * 0.5:
            tips.append("Más de la mitad de tus ataques son signatures: son lentas y fáciles de castigar si fallan.")

    if stats.total_dodges and stats.total_attacks:
        ratio = stats.total_dodges / stats.total_attacks
        if ratio > 0.8:
            tips.append(
                f"Esquivas {ratio:.1f} veces por cada ataque. Esquivar de más te deja sin dodge "
                "justo cuando el rival te presiona."
            )

    if stats.deaths:
        late = sum(d.dodged_late for d in stats.deaths)
        if late / len(stats.deaths) >= 0.5:
            tips.append(
                f"En {late} de {len(stats.deaths)} muertes esquivaste en el último segundo: "
                "es probable que te estén leyendo el dodge y castigando el cooldown."
            )
        passive = sum(1 for d in stats.deaths if not d.actions_before)
        if passive:
            tips.append(f"En {passive} muerte(s) no presionaste nada en los 2 s previos: revisa si te quedaste quieto bajo presión.")

    return tips


def analyze_player(replay: Replay, entity_id: int) -> PlayerStats:
    player = replay.player(entity_id)
    inputs = replay.inputs.get(entity_id, [])
    actions = extract_actions(inputs)
    minutes = max(replay.length_ms, 1) / 60000

    combat = [a for a in actions if a.name != "jump"]
    stats = PlayerStats(
        entity_id=entity_id,
        name=player.name if player else f"Entidad {entity_id}",
        is_bot=player.is_bot if player else False,
        hero_ids=[h.hero_id for h in player.heroes] if player else [],
        total_actions=len(actions),
        actions_per_minute=len(combat) / minutes,
        attacks=Counter(a.name for a in actions if a.name.startswith(("light", "sig"))),
        dodges=Counter(a.name for a in actions if a.name.startswith("dodge")),
        jumps=sum(1 for a in actions if a.name == "jump"),
        deaths=_death_contexts(actions, [d for d in replay.deaths if d.entity_id == entity_id]),
    )
    stats.insights = _insights(stats)
    return stats


def analyze(replay: Replay, player_name: Optional[str] = None) -> Dict[int, PlayerStats]:
    players = replay.players
    if player_name:
        players = [p for p in players if p.name.lower() == player_name.lower()]
    return {p.entity_id: analyze_player(replay, p.entity_id) for p in players}
