"""Rule: an above-the-feet touch counts when the ball clearly turns over a
few samples, even if one-sample position noise hides the turn; a slight bend
over those samples is still not a touch."""

from football_poc.engine.ball_evidence import _control_observations


def _balls(path):
    return {
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


def _player_under(frame, x, y):
    return {
        frame: [
            {
                "track_id": 7,
                "team": "black",
                "x1": x - 10.0,
                "x2": x + 10.0,
                "y1": y - 5.0,
                "y2": y + 45.0,
            }
        ]
    }


def _observed_frames(path, centre):
    x, y = path[centre]
    observations = _control_observations(
        _player_under(centre, x, y),
        _balls(path),
        control_radius_heights=1.8,
        maximum_ground_contact_height_ratio=0.4,
        maximum_aerial_contact_direction_cosine=0.5,
    )
    return [observation.source_frame for observation in observations]


def test_noisy_one_sample_turn_counts_when_wide_turn_reverses_20261004T143910285Z():
    path = {
        15: (1916.2, 476.1),
        20: (1889.5, 477.1),
        25: (1893.0, 474.7),
        30: (1898.4, 476.5),
        35: (1900.1, 476.1),
    }
    assert _observed_frames(path, 25) == [25]


def test_slight_wide_bend_is_not_an_aerial_touch_20261004T143910286Z():
    path = {
        15: (1926.0, 568.0),
        20: (1918.0, 564.0),
        25: (1914.0, 570.0),
        30: (1914.0, 576.0),
        35: (1912.0, 578.0),
    }
    assert _observed_frames(path, 25) == []
