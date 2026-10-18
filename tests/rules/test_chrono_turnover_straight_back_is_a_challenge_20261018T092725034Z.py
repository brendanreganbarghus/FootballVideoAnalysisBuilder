"""Chronological engine: a turnover straight back is a challenge, not two turnovers.

Project turnover definition: the team loses the ball when an opponent gains
control of it. When the team that lost the ball has it straight back, from
the opponent's feet, the opponent only challenged for it (or one camera put
him nearest for a moment while the player on the ball was hidden): nobody's
possession changed, so neither turnover is written. An opponent who plays
the ball on to a player further away did win it.
"""

from football_poc.chrono_engine import ChronoResult, ChronoSettings, _Control, _control_change


def _black_loses_to_red(result):
    black, red = _Control(2, "black", 10.0, 12.4, (500.0, 500.0), 40.0, 2), \
        _Control(9, "red", 12.6, 12.6, (510.0, 505.0), 40.0, 2)
    assert _control_change(result, black, red, ChronoSettings())
    return red


def _turnovers(result):
    return [(e["team"], e["from_player_track_id"], e["to_player_track_id"])
            for e in result.events]


def test_turnover_straight_back_is_a_challenge_20261018T092725034Z():
    result = ChronoResult()
    red = _black_loses_to_red(result)
    red.last_seconds, red.feet = 13.0, (530.0, 505.0)
    back = _Control(3, "black", 13.2, 13.2, (545.0, 510.0), 40.0, 2)
    assert _control_change(result, red, back, ChronoSettings())
    assert result.events == []


def test_opponent_who_plays_it_away_won_it_20261018T092725035Z():
    result = ChronoResult()
    red = _black_loses_to_red(result)
    far = _Control(3, "black", 13.2, 13.2, (650.0, 505.0), 40.0, 2)
    _control_change(result, red, far, ChronoSettings())
    assert _turnovers(result) == [("black", 2, 9), ("red", 9, 3)]


def test_opponent_who_keeps_it_won_it_20261018T092725036Z():
    result = ChronoResult()
    red = _black_loses_to_red(result)
    later = _Control(3, "black", 15.0, 15.0, (515.0, 505.0), 40.0, 2)
    _control_change(result, red, later, ChronoSettings())
    assert _turnovers(result) == [("black", 2, 9), ("red", 9, 3)]