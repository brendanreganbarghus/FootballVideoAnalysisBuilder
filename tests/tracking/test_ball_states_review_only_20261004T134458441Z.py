from pathlib import Path

from football_poc import possession_cli


def test_ball_states_next_to_tracks_are_not_sent_to_engine_20261004T134458441Z(
    tmp_path: Path, monkeypatch
) -> None:
    tracks = tmp_path / "ball-tracks.json"
    tracks.write_text("{}")
    (tmp_path / "ball-state-estimates.json").write_text("{}")
    seen: dict[str, object] = {}

    def fake_infer(**kwargs):
        seen.update(kwargs)
        return tmp_path

    monkeypatch.setattr(possession_cli, "infer_cached_possession", fake_infer)
    args = possession_cli.build_parser().parse_args(
        ["manifest.json", "--player-tracks", "p.json", "--ball-tracks", str(tracks)]
    )
    possession_cli._infer(args)

    assert seen["ball_state_estimates_path"] is None


def test_estimated_flag_is_not_sent_to_engine_20261004T134458441Z(tmp_path: Path, monkeypatch) -> None:
    import json

    tracks = tmp_path / "ball-tracks.json"
    tracks.write_text(
        json.dumps(
            {
                "tracks": [
                    {
                        "track_id": 1,
                        "points": [
                            {"source_frame": 0, "x": 1, "y": 2, "interpolated": True},
                            {"source_frame": 5, "x": 3, "y": 4, "interpolated": False},
                        ],
                    }
                ]
            }
        )
    )
    seen: dict[str, object] = {}

    def fake_infer(**kwargs):
        seen.update(kwargs)
        return tmp_path

    monkeypatch.setattr(possession_cli, "infer_cached_possession", fake_infer)
    args = possession_cli.build_parser().parse_args(
        ["m.json", "--player-tracks", "p.json", "--ball-tracks", str(tracks),
         "--output", str(tmp_path / "out")]
    )
    possession_cli._infer(args)

    sent = json.loads(Path(seen["ball_tracks_path"]).read_text())
    points = sent["tracks"][0]["points"]
    assert [p["interpolated"] for p in points] == [False, False]
    assert [(p["x"], p["y"]) for p in points] == [(1, 2), (3, 4)]
    assert json.loads(tracks.read_text())["tracks"][0]["points"][0]["interpolated"] is True
