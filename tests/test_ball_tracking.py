from football_poc.ball_tracking import (
    BallPoint,
    _associate_tracks,
    _near_static_cell,
    _static_cells,
    BallTrack,
    interpolate_track_gaps,
)


def point(frame: int, seconds: float, x: float, y: float = 200) -> BallPoint:
    return BallPoint(frame, seconds, 0.8, x, y)


def test_static_cells_require_repeated_frame_occupancy() -> None:
    static = _static_cells(
        [
            point(1, 0.0, 100),
            point(2, 0.1, 102),
            point(3, 0.2, 98),
            point(1, 0.0, 500),
        ],
        frame_count=4,
        cell_size=20,
        occupancy=0.75,
    )

    assert static == {(5, 10)}


def test_tracker_connects_motion_across_short_gap() -> None:
    tracks = _associate_tracks(
        [
            point(1, 0.0, 100),
            point(2, 0.08, 120),
            point(5, 0.32, 180),
        ],
        max_gap_seconds=0.4,
        max_speed_pixels_per_second=500,
    )

    assert len(tracks) == 1
    assert [item.x for item in tracks[0].points] == [100, 120, 180]


def test_tracker_rejects_implausible_jump() -> None:
    tracks = _associate_tracks(
        [point(1, 0.0, 100), point(2, 0.08, 500)],
        max_gap_seconds=0.4,
        max_speed_pixels_per_second=500,
    )

    assert len(tracks) == 2


def test_static_suppression_covers_neighboring_cell_edge() -> None:
    assert _near_static_cell(
        point(1, 0.0, 109, 200),
        frozenset({(5, 10)}),
        20,
    )


def test_interpolates_short_gaps_with_provenance() -> None:
    track = BallTrack(
        1,
        [
            point(100, 0.0, 100),
            point(106, 0.24, 160),
        ],
    )

    result = interpolate_track_gaps(
        track,
        frame_step=2,
        fps=25,
        maximum_gap_seconds=0.56,
    )

    assert [item.source_frame for item in result.points] == [100, 102, 104, 106]
    assert [item.interpolated for item in result.points] == [
        False,
        True,
        True,
        False,
    ]
