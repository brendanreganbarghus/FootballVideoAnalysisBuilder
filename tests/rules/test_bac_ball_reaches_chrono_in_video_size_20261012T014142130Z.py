"""Rule: a BAC ball reaches the chronological engine in video size, all observed.

BAC coordinates are stored in the provider panorama space, while player
feet come from YOLO in video frame size. The chronological engine compares
them directly, so its BAC input is converted to video size and declares that
size. BAC has no tracker statuses: every coordinate is ``observed`` and the
engine decides out-of-play itself from the calibrated pitch (Law 9), rather
than a guess from the image position (a high ball can project over a line
while still in play).
"""

from __future__ import annotations

from football_poc.bac_chrono_inputs import bac_ball_in_video_size, bac_ball_states
from football_poc.image_space import ball_coordinate_size

CALIBRATION = {"image_width": 4450, "image_height": 2000}
VIDEO = (3840.0, 1726.0)


def _bac(points):
    return {
        "manifest": "m.json",
        "source_kind": "evaluation_only_provider_coordinates",
        "tracks": [{"track_id": 1, "points": points}],
    }


def _point(frame, x, y):
    return {"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y}


def test_bac_ball_converted_to_video_size_and_declared_20261012T014142130Z() -> None:
    stored = _bac([_point(0, 4450.0, 2000.0), _point(5, 2225.0, 1000.0)])
    converted = bac_ball_in_video_size(stored, CALIBRATION, VIDEO)

    xs = [(p["x"], p["y"]) for p in converted["tracks"][0]["points"]]
    assert xs[0] == (3840.0, 1726.0)
    assert xs[1] == (1920.0, 863.0)
    assert ball_coordinate_size(converted, VIDEO) == VIDEO
    assert stored["tracks"][0]["points"][0]["x"] == 4450.0


def test_bac_status_leaves_out_of_play_to_engine_20261012T014142131Z() -> None:
    # A point far outside any pitch outline is still "observed".
    ball = _bac([_point(f, 100.0 + f, -500.0 if f == 10 else 900.0) for f in range(0, 40, 5)])
    payload = bac_ball_states(ball, [], "c.json")

    assert {s["state"] for s in payload["states"]} == {"observed"}
    assert all(s["event_evidence_eligible"] for s in payload["states"])
    assert all("aerial" in s for s in payload["states"])
    assert payload["policy"]["trajectory_estimates_are_for_continuity_and_search_only"]
    assert payload["policy"]["out_of_play_decided_by_engine"]
