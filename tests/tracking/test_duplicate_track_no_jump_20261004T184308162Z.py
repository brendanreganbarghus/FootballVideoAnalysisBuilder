"""Timestamped rule: a duplicate track may not jump onto another player."""

from __future__ import annotations

from football_poc.player_tracking import PlayerPoint, _associate_players


def _box(step: int, foot_x: float, confidence: float = 0.8) -> PlayerPoint:
    return PlayerPoint(
        source_frame=step * 5,
        clip_seconds=step * 0.2,
        confidence=confidence,
        x1=foot_x - 15,
        y1=420.0,
        x2=foot_x + 15,
        y2=500.0,
    )


def _track_of(tracks, point: PlayerPoint) -> int:
    return next(track.track_id for track in tracks if point in track.points)


def test_duplicate_track_does_not_jump_to_nearby_player_20261004T184308162Z() -> None:
    owner = [_box(step, 100.0) for step in range(4)]
    duplicate_box = _box(3, 104.0, confidence=0.3)
    owner_after = _box(4, 100.0)
    other_player = _box(5, 220.0)
    owner_later = _box(5, 100.0)
    tracks = _associate_players(
        [*owner, duplicate_box, owner_after, owner_later, other_player],
        max_gap_seconds=0.5,
        max_speed_pixels_per_second=700.0,
    )

    duplicate_track = _track_of(tracks, duplicate_box)
    assert _track_of(tracks, owner_later) == _track_of(tracks, owner[0])
    assert _track_of(tracks, other_player) != duplicate_track


def test_single_track_still_bridges_gap_at_running_speed_20261004T184308163Z() -> None:
    before = [_box(step, 100.0) for step in range(3)]
    after_gap = _box(4, 220.0)
    tracks = _associate_players(
        [*before, after_gap],
        max_gap_seconds=0.5,
        max_speed_pixels_per_second=700.0,
    )

    assert _track_of(tracks, after_gap) == _track_of(tracks, before[0])
