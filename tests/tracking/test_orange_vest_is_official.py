"""Rule: in the red-black profile a saturated warm crop with no white trim is an
orange high-visibility vest (steward/ballboy) and is labelled official, so it
never casts a red-team vote."""

from football_poc.player_tracking import classify_color_scores


def test_orange_vest_without_white_is_official_20261005T032122564Z():
    scores = {"warm": 0.5, "white": 0.0, "dark": 0.05, "yellow": 0.1}
    assert classify_color_scores(scores, team_profile="red-black") == "official"


def test_red_kit_with_white_trim_stays_red_20261005T032122565Z():
    scores = {"warm": 0.3, "white": 0.2, "dark": 0.05, "yellow": 0.0}
    assert classify_color_scores(scores, team_profile="red-black") == "red"


def test_dark_kit_still_black_before_vest_rule_20261005T032122566Z():
    scores = {"warm": 0.4, "white": 0.0, "dark": 0.35, "yellow": 0.0}
    assert classify_color_scores(scores, team_profile="red-black") == "black"
