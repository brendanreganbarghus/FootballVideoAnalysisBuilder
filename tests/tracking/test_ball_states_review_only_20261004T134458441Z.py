from pathlib import Path

from football_poc import possession_cli


def test_ball_states_next_to_tracks_are_not_sent_to_engine(
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
