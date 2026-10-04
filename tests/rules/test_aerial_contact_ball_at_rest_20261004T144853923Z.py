"""Rule: a ball lying still is not a head or chest touch, even when position
noise makes it look like it turned; a moving ball that turns still is."""

from football_poc.engine.ball_evidence import _control_observations


def _observed(path):
    balls = {
        frame: [
            {
                "track_id": 1,
                "source_frame": frame,
                "clip_seconds": frame / 25.0,
                "x": x,
                "y": y,
            }
        ]
        for frame, (x, y) in path.items()
    }
    players = {
        25: [
            {
                "track_id": 7,
                "team": "red",
                "x1": 490.0,
                "x2": 510.0,
                "y1": 495.0,
                "y2": 545.0,
            }
        ]
    }
    observations = _control_observations(
        players,
        balls,
        control_radius_heights=1.8,
        maximum_ground_contact_height_ratio=0.4,
        maximum_aerial_contact_direction_cosine=0.5,
    )
    return [observation.source_frame for observation in observations]


def test_ball_at_rest_above_feet_is_not_an_aerial_touch_20261004T144853923Z():
    path = {20: (500.5, 510.0), 25: (500.0, 510.0), 30: (500.5, 510.5)}
    assert _observed(path) == []


def test_moving_ball_turning_above_feet_is_an_aerial_touch_20261004T144853923Z():
    path = {20: (530.0, 510.0), 25: (500.0, 510.0), 30: (530.0, 530.0)}
    assert _observed(path) == [25]
