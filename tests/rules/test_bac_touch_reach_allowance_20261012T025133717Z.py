"""Rule (BAC flow only): BAC's position wobble counts as extra touch reach.

Frozen BAC ball coordinates sit a few pixels off the video and wobble more
than the Live tracker's coordinates. In the BAC flow only, when the normal
Law 12 touch check credits nobody at a deflection, each player's distance to
the ball is shortened by the track's measured wobble (times the engine's
touch noise multiple). The touch reach and the duel margin still apply.
The Live flow never uses this allowance, so its output does not change.
"""

from __future__ import annotations

import re
from pathlib import Path

from football_poc.bac_chrono_tolerance import bac_toucher
from football_poc.chrono_engine import ChronoSettings, _toucher

SETTINGS = ChronoSettings()
ROOT = Path(__file__).resolve().parents[2]


def _box(track_id: int, team: str, x1: float, x2: float, y1: float = 500.0, y2: float = 568.0):
    return {"track_id": track_id, "team": team, "x1": x1, "x2": x2, "y1": y1, "y2": y2}


def test_bac_wobble_extends_touch_reach_20261012T025133717Z():
    # 27 px from a 68 px tall player: 0.40 heights, just past the 0.35 reach.
    boxes = [_box(16, "red", 1000.0, 1030.0), _box(63, "black", 1300.0, 1330.0)]
    ball = (1057.0, 540.0)
    assert _toucher(ball, boxes, SETTINGS) is None
    assert bac_toucher(ball, boxes, SETTINGS, noise_px=0.0) is None
    assert bac_toucher(ball, boxes, SETTINGS, noise_px=5.0)["track_id"] == 16


def test_bac_allowance_keeps_the_duel_rule_20261012T025133718Z():
    boxes = [_box(16, "red", 1000.0, 1030.0), _box(63, "black", 1084.0, 1114.0)]
    assert bac_toucher((1057.0, 540.0), boxes, SETTINGS, noise_px=5.0) is None


def test_bac_allowance_has_a_limit_20261012T025133719Z():
    boxes = [_box(16, "red", 1000.0, 1030.0)]
    assert bac_toucher((1100.0, 540.0), boxes, SETTINGS, noise_px=5.0) is None


def test_live_flow_never_runs_the_bac_allowance_20261012T025133720Z():
    processor = (ROOT / "scripts" / "process-alfheim-segment.py").read_text(encoding="utf-8")
    assert re.search(
        r'"football_poc\.bac_chrono_tolerance"\s*if ball_source == "bac"\s*'
        r'else "football_poc\.chrono_engine"',
        processor,
    )
    engine = (ROOT / "src" / "football_poc" / "chrono_engine.py").read_text(encoding="utf-8")
    assert "bac_chrono_tolerance import" not in engine
