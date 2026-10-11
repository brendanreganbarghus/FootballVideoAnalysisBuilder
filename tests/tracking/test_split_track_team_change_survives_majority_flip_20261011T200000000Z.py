"""Rule: a sustained run of contradicting kit votes keeps counting after the
track's window majority flips to the new team. The run is measured against the
team the track had when the run began, so a red player whose identity is
carried onto a black defender is still split at the first black vote."""

from football_poc.player_tracking import (
    PlayerPoint,
    PlayerTrack,
    split_tracks_on_sustained_team_change,
)


def _track(votes):
    points = [
        PlayerPoint(i, i * 0.2, 0.8, 0, 0, 10, 30, team=vote)
        for i, vote in enumerate(votes)
    ]
    return PlayerTrack(7, points)


def test_run_survives_window_majority_flip_20261011T200000000Z():
    votes = ["red", "red", "black", "black", "red", "black", "black", "black", "black", "black"]
    parts = split_tracks_on_sustained_team_change([_track(votes)])
    assert [len(part.points) for part in parts] == [5, 5]


def test_return_to_original_team_resets_run_20261011T200000001Z():
    votes = ["red"] * 4 + ["black"] * 3 + ["red"] + ["black"] * 3
    parts = split_tracks_on_sustained_team_change([_track(votes)])
    assert len(parts) == 1
