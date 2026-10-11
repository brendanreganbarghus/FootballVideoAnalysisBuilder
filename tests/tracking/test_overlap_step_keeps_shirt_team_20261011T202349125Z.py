"""Rule: the overlap step keeps the shirt team of an overlapping box.

The overlap step re-reads the kit of every box that touches another box. A
box that overlaps another must be read with the same shirt rule as the first
kit reading: a red shirt over black shorts stays red. Otherwise the shirt
reading is overwritten and two overlapping players swap teams.
"""

from __future__ import annotations

from football_poc.player_tracking import (
    COLOR_FEATURES,
    PlayerPoint,
    PlayerTrack,
    resolve_overlap_teams,
)

TEAM_COLORS = {
    "red": ([0.0, 0.3, 0.1, 0.3, 0.3, 0.0, 0.6, 0.2, 0.1, 0.1], [0.1] * 10),
    "black": ([0.0, 0.0, 0.8, 0.0, 0.1, 0.0, 0.0, 0.9, 0.0, 0.1], [0.1] * 10),
}


def _scores(shirt, shorts):
    scores = {f"shirt_{key}": value for key, value in zip(COLOR_FEATURES, shirt)}
    scores |= {f"shorts_{key}": value for key, value in zip(COLOR_FEATURES, shorts)}
    return scores


RED_SHIRT_BLACK_SHORTS = _scores([0.0, 0.25, 0.2, 0.25, 0.3], [0.0, 0.0, 1.0, 0.0, 0.0])
BLACK_KIT = _scores([0.0, 0.0, 0.8, 0.0, 0.1], [0.0, 0.0, 0.9, 0.0, 0.1])


def _track(track_id, box, scores):
    point = PlayerPoint(0, 0.0, 0.9, *box, team="red", color_scores=scores)
    return PlayerTrack(track_id, [point], team="red")


def test_overlap_step_keeps_shirt_team_20261011T202349125Z():
    header = _track(1, (100.0, 100.0, 130.0, 175.0), RED_SHIRT_BLACK_SHORTS)
    front = _track(2, (105.0, 120.0, 135.0, 175.0), BLACK_KIT)
    resolve_overlap_teams(
        [header, front], team_profile="red-black", team_colors=TEAM_COLORS
    )
    assert header.points[0].team == "red"
    assert front.points[0].team == "black"
