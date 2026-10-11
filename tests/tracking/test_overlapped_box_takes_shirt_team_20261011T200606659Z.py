"""Rule: in an overlapping box, the shirt decides the team.

When a player stands half behind another, his box can show his own shirt over
the shorts of the player in front. If that box overlaps another player's box
and its shirt reads one team while its shorts read the other, the box belongs
to the shirt's team. A box standing alone keeps its whole-kit reading.
"""

from __future__ import annotations

from football_poc.player_tracking import COLOR_FEATURES, nearest_team_color

# Feature order: blue, white, dark, warm, yellow (shirt, then shorts).
TEAM_COLORS = {
    "red": ([0.0, 0.3, 0.1, 0.3, 0.3, 0.0, 0.6, 0.2, 0.1, 0.1], [0.1] * 10),
    "black": ([0.0, 0.0, 0.8, 0.0, 0.1, 0.0, 0.0, 0.9, 0.0, 0.1], [0.1] * 10),
}


def _scores(shirt, shorts):
    scores = {f"shirt_{key}": value for key, value in zip(COLOR_FEATURES, shirt)}
    scores |= {f"shorts_{key}": value for key, value in zip(COLOR_FEATURES, shorts)}
    return scores


# A red shirt over black shorts, with the black reading slightly stronger overall.
RED_SHIRT_BLACK_SHORTS = _scores([0.0, 0.25, 0.2, 0.25, 0.3], [0.0, 0.0, 1.0, 0.0, 0.0])


def test_overlapped_box_takes_its_shirt_team_20261011T200606659Z():
    assert (
        nearest_team_color(RED_SHIRT_BLACK_SHORTS, TEAM_COLORS, overlapped=True)
        == "red"
    )


def test_box_standing_alone_keeps_whole_kit_reading_20261011T200606660Z():
    assert nearest_team_color(RED_SHIRT_BLACK_SHORTS, TEAM_COLORS) == "black"
