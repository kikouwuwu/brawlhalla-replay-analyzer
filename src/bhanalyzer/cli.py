"""Línea de comandos: bhanalyze <replay> | bhanalyze --latest"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .analysis import PlayerStats, analyze
from .replay import InvalidReplayError, parse_file

DEFAULT_REPLAY_DIR = Path.home() / "BrawlhallaReplays"


def latest_replay(directory: Path) -> Optional[Path]:
    replays = sorted(directory.glob("*.replay"), key=lambda p: p.stat().st_mtime, reverse=True)
    return replays[0] if replays else None


def _seconds(ms: int) -> str:
    return f"{ms / 1000:.1f}s"


def format_player(stats: PlayerStats) -> str:
    lines = [
        f"== {stats.name}{' (bot)' if stats.is_bot else ''}  [leyendas: {', '.join(map(str, stats.hero_ids))}]",
        f"   Acciones por minuto: {stats.actions_per_minute:.0f}",
        f"   Ataques: {stats.total_attacks}  |  Dodges: {stats.total_dodges}  |  Saltos: {stats.jumps}",
    ]
    if stats.attacks:
        lines.append("   Ataques más usados:")
        for move, count in stats.attacks.most_common():
            lines.append(f"     {move:<14} {count:>4}  {count / stats.total_attacks:>5.0%}")
    if stats.dodges:
        lines.append("   Dodges: " + ", ".join(f"{k}={v}" for k, v in stats.dodges.most_common()))
    if stats.deaths:
        lines.append("   Muertes:")
        for i, death in enumerate(stats.deaths, 1):
            before = ", ".join(death.actions_before[-6:]) or "nada"
            lines.append(
                f"     #{i} a los {_seconds(death.timestamp)} (stock de {_seconds(death.stock_duration_ms)})"
                f" — últimos inputs: {before}"
            )
    if stats.insights:
        lines.append("   Qué mejorar:")
        lines.extend(f"     - {tip}" for tip in stats.insights)
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="bhanalyze", description="Analiza replays de Brawlhalla.")
    parser.add_argument("replay", nargs="?", type=Path, help="Ruta al archivo .replay")
    parser.add_argument("--latest", action="store_true", help="Usa el replay más reciente de la carpeta de replays")
    parser.add_argument("--dir", type=Path, default=DEFAULT_REPLAY_DIR, help="Carpeta de replays (por defecto ~/BrawlhallaReplays)")
    parser.add_argument("--player", help="Analiza solo a este jugador (nombre exacto)")
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    args = parser.parse_args(argv)

    path = args.replay
    if args.latest:
        path = latest_replay(args.dir)
        if path is None:
            print(f"No hay replays en {args.dir}", file=sys.stderr)
            return 1
    if path is None:
        parser.error("indica un archivo .replay o usa --latest")

    try:
        replay = parse_file(path)
    except (InvalidReplayError, EOFError) as exc:
        print(f"No se pudo leer {path}: {exc}", file=sys.stderr)
        return 1

    results = analyze(replay, args.player)
    if args.json:
        print(json.dumps({str(k): asdict(v) for k, v in results.items()}, indent=2, ensure_ascii=False))
        return 0

    print(f"Replay: {path.name}  |  versión {replay.version}  |  mapa {replay.level_id}  |  duración {_seconds(replay.length_ms)}")
    if replay.header.playlist_name:
        print(f"Modo: {replay.header.playlist_name}")
    for stats in results.values():
        print()
        print(format_player(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
