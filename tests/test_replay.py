import pytest

from bhanalyzer import InputFlags as F
from bhanalyzer import InvalidReplayError, analyze, parse_bytes
from bhanalyzer.cli import main

from replay_builder import build_replay


def sample_replay() -> bytes:
    spam = []
    t = 0
    for _ in range(25):  # side light repetido: debería salir como predecible
        spam += [(t, F.RIGHT | F.LIGHT), (t + 50, 0)]
        t += 200
    spam += [(t, F.DODGE), (t + 50, 0)]  # dodge justo antes de morir
    spam += [(t + 100, F.DOWN | F.HEAVY), (t + 150, 0), (t + 200, F.JUMP), (t + 250, 0)]
    return build_replay(
        players=[(1, "kikou"), (2, "rival")],
        inputs={1: spam, 2: [(100, F.LIGHT), (150, 0)]},
        deaths=[(1, t + 600), (2, 9000)],
        length_ms=60000,
    )


def test_parse_metadata():
    replay = parse_bytes(sample_replay())
    assert replay.version == 250
    assert replay.header.playlist_name == "Ranked 1v1"
    assert replay.level_id == 12
    assert [p.name for p in replay.players] == ["kikou", "rival"]
    assert replay.players[0].heroes[0].hero_id == 4
    assert replay.length_ms == 60000
    assert len(replay.inputs[1]) == 56


def test_analysis():
    stats = analyze(parse_bytes(sample_replay()))[1]
    assert stats.attacks["light_side"] == 25
    assert stats.attacks["sig_down"] == 1
    assert stats.dodges["dodge_spot"] == 1
    assert stats.jumps == 1
    assert len(stats.deaths) == 1
    assert stats.deaths[0].dodged_late
    assert any("predecible" in tip for tip in stats.insights)


def test_filter_by_player():
    assert list(analyze(parse_bytes(sample_replay()), "RIVAL")) == [2]


def test_invalid_file():
    with pytest.raises(InvalidReplayError):
        parse_bytes(b"esto no es un replay")


def test_cli(tmp_path, capsys):
    path = tmp_path / "partida.replay"
    path.write_bytes(sample_replay())
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "kikou" in out and "Qué mejorar" in out
