"""Rule: the focused search prefers the ball-coloured spot over a nearer rival."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

DIAMETER = 12.0


def _spot(x: float, y: float) -> list:
    # Three crop sizes agree on the spot, enough for a consensus.
    return [
        ball_tracking._FocusedBallDetection(
            x=x, y=y, confidence=0.05, variant=(radius, 640),
            width=10.0, height=10.0,
        )
        for radius in (96, 120, 144)
    ]


def _chosen(matches_ball_colour) -> tuple[float, float]:
    boot = _spot(105.0, 100.0)
    ball = _spot(78.0, 108.0)
    group = ball_tracking._multiscale_detection_consensus(
        [*boot, *ball],
        expected_x=100.0,
        expected_y=100.0,
        reference_diameter=DIAMETER,
        matches_ball_colour=matches_ball_colour,
    )
    return group[0].x, group[0].y


def test_focused_search_prefers_ball_coloured_spot_20261017T220338815Z() -> None:
    """A white boot beside the ball's guessed path is not the ball.

    A ball rising beside a player's head and a boot nearer the guessed path
    can both be seen by the detector across crop sizes. The ball's colour,
    learned from this video's confident detections, tells them apart, so
    the ball-coloured spot wins even when it is further from the guess.
    Without a colour match the nearest spot still wins.
    """
    def ball_coloured(x: float, y: float) -> bool:
        return x < 90.0

    assert _chosen(ball_coloured) == (78.0, 108.0)
    assert _chosen(None) == (105.0, 100.0)
    assert _chosen(lambda x, y: False) == (105.0, 100.0)
    assert _chosen(lambda x, y: True) == (105.0, 100.0)


def test_gap_walk_keeps_ball_coloured_sighting_20261017T225132350Z() -> None:
    """A slow gap walk does not replace a ball-coloured sighting.

    The walk follows whatever it finds step by step from a gap end, so it can
    drift onto a boot or a line. When the frame already has a sighting with
    the ball's colour, or a colour closer to the ball's than the walked
    point, the sighting is kept. Without colour evidence, or when the walked
    point is at least as close in colour, the walk still replaces it.
    """
    ball = ball_tracking.BallPoint(40, 1.6, 0.2, 100.0, 100.0, box_diagonal=12)
    drift = ball_tracking.BallPoint(40, 1.6, 0.02, 190.0, 80.0, box_diagonal=12)

    def merge(distances):
        candidates = {40: (ball, 0.5, 12.0)}
        accepted = {40}
        ball_tracking._merge_walked_points(
            candidates, accepted, {40: drift}, 12.0,
            ball_colour_distance=(
                None if distances is None
                else lambda point: distances[point is ball]
            ),
        )
        return candidates[40][0]

    # {is_ball: distance from the ball's learned colour range}
    assert merge({True: 0.0, False: 20.0}) is ball
    assert merge({True: 0.0, False: None}) is ball
    assert merge({True: 2.0, False: 19.0}) is ball
    assert merge(None) is drift
    assert merge({True: 0.0, False: 0.0}) is drift
    assert merge({True: 5.0, False: 0.0}) is drift
    assert merge({True: 5.0, False: 5.0}) is drift
    assert merge({True: None, False: 20.0}) is drift
