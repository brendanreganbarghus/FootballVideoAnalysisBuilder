"""Rule: a player track whose raw kit votes switch to the other outfield team
for four known votes in a row is split into a new player at the first
contradicting vote (identity carried through a merged box), so the new player
is labelled immediately and never inherits the old player's identity."""

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


def test_four_contradicting_votes_split_the_track_20261005T033824822Z():
    votes = ["black"] * 5 + ["red"] * 4
    parts = split_tracks_on_sustained_team_change([_track(votes)])
    assert [len(part.points) for part in parts] == [5, 4]
    assert parts[0].track_id == 7 and parts[1].track_id == 8


def test_three_contradicting_votes_keep_the_track_20261005T033824823Z():
    votes = ["black"] * 5 + ["red"] * 3 + ["black"]
    parts = split_tracks_on_sustained_team_change([_track(votes)])
    assert len(parts) == 1


def test_unknown_and_official_votes_do_not_count_20261005T033824824Z():
    votes = ["black"] * 3 + ["unknown", "official", "unknown", "official"] * 2
    parts = split_tracks_on_sustained_team_change([_track(votes)])
    assert len(parts) == 1
