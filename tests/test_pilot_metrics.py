import json

from football_poc.pilot_metrics import build_pilot_metrics


def test_pilot_metrics_publish_possession_distance_and_events(tmp_path) -> None:
    calibration = tmp_path / "calibration.json"
    players = tmp_path / "players.json"
    possession = tmp_path / "possession.json"
    events = tmp_path / "events.json"
    output = tmp_path / "pilot.json"
    calibration.write_text(
        json.dumps(
            {
                "pitch_dimensions_metres": {"length": 100, "width": 50},
                "image_points": [[0, 0], [100, 0], [100, 50], [0, 50]],
                "pitch_points_metres": [[0, 0], [100, 0], [100, 50], [0, 50]],
            }
        ),
        encoding="utf-8",
    )
    players.write_text(
        json.dumps(
            {
                "tracks": [
                    {
                        "track_id": 14,
                        "team": "blue",
                        "points": [
                            {"clip_seconds": 0, "x1": 9, "x2": 11, "y2": 10},
                            {"clip_seconds": 1, "x1": 12, "x2": 14, "y2": 14},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    possession.write_text(
        json.dumps(
            {
                "observations": [
                    {"clip_seconds": 0, "team": "blue"},
                    {"clip_seconds": 1, "team": "white"},
                    {"clip_seconds": 2, "team": "blue"},
                ]
            }
        ),
        encoding="utf-8",
    )
    events.write_text(
        json.dumps(
            [
                {
                    "event_type": "pass_candidate",
                    "clip_seconds": 1,
                    "team": "blue",
                }
            ]
        ),
        encoding="utf-8",
    )

    build_pilot_metrics(
        player_tracks_path=players,
        possession_path=possession,
        events_path=events,
        calibration_path=calibration,
        output_path=output,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    block = payload["blocks"][0]
    assert block["teams"]["blue"]["possession_percent"] == 66.7
    assert block["teams"]["blue"]["pass_candidates"] == 1
    assert block["players"][0]["distance_metres"] == 5
