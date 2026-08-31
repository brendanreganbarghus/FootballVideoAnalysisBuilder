import json
from pathlib import Path

import pytest

from football_poc.soccertrack import SoccerTrackMatch


def write_bas(
    root: Path,
    actions: list[dict[str, object]],
    *,
    field: str = "actions",
) -> None:
    path = root / "bas" / "117093" / "117093_12_class_events.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"match_id": "117093", "fps": 25, field: actions}),
        encoding="utf-8",
    )


def action(
    game_time: str,
    label: str,
    position: int,
    *,
    team: str = "left",
) -> dict[str, object]:
    return {
        "gameTime": game_time,
        "label": label,
        "position": str(position),
        "team": team,
        "player_id": 42,
    }


def test_loads_released_schema_and_normalizes_absolute_half_two(tmp_path: Path) -> None:
    write_bas(
        tmp_path,
        [
            action("1 - 0:01", "PASS", 680),
            action("2 - 45:00", "HIGH PASS", 2_700_760),
        ],
    )

    match = SoccerTrackMatch.load(tmp_path, "117093")

    assert match.schema_variant == "actions"
    assert match.actions[0].label == "pass"
    assert match.actions[0].half_seconds == pytest.approx(0.68)
    assert match.actions[1].label == "high_pass"
    assert match.actions[1].match_seconds == pytest.approx(2700.76)
    assert match.actions[1].half_seconds == pytest.approx(0.76)
    assert match.actions[1].player_id == "42"


def test_accepts_documented_schema_with_half_relative_positions(
    tmp_path: Path,
) -> None:
    write_bas(
        tmp_path,
        [action("2 - 00:03", "Shot", 3_000)],
        field="annotations",
    )

    match = SoccerTrackMatch.load(tmp_path, "117093")

    assert match.schema_variant == "annotations"
    assert match.actions[0].label == "shot"
    assert match.actions[0].half_seconds == pytest.approx(3)
    assert match.actions[0].match_seconds == pytest.approx(2703)


def test_selects_pass_rich_window_around_required_shot(tmp_path: Path) -> None:
    actions = [
        action("1 - 1:20", "SHOT", 80_000),
        action("1 - 1:25", "PASS", 85_000),
        action("1 - 1:30", "PASS", 90_000),
        action("1 - 3:20", "SHOT", 200_000),
        action("1 - 3:21", "PASS", 201_000),
    ]
    write_bas(tmp_path, actions)
    match = SoccerTrackMatch.load(tmp_path, "117093")

    window = match.select_event_window(half=1, duration_seconds=60)

    assert window.start_seconds == pytest.approx(50)
    assert window.counts == {"pass": 2, "shot": 1}


def test_writes_clip_relative_manifest(tmp_path: Path) -> None:
    write_bas(
        tmp_path,
        [
            action("1 - 1:20", "SHOT", 80_000),
            action("1 - 1:25", "PASS", 85_000),
        ],
    )
    video = (
        tmp_path
        / "videos"
        / "117093"
        / "117093_panorama_1st_half.mp4"
    )
    video.parent.mkdir(parents=True)
    video.touch()
    match = SoccerTrackMatch.load(tmp_path, "117093")
    window = match.select_event_window(half=1, duration_seconds=60)

    output = match.write_window_manifest(window, tmp_path / "manifest.json")
    manifest = json.loads(output.read_text(encoding="utf-8"))

    assert manifest["start_frame"] == 1250
    assert manifest["end_frame"] == 2750
    assert manifest["action_counts"] == {"pass": 1, "shot": 1}
    assert manifest["actions"][0]["clip_seconds"] == pytest.approx(30)


def test_rejects_unknown_labels(tmp_path: Path) -> None:
    write_bas(tmp_path, [action("1 - 0:01", "NEW EVENT", 1_000)])

    with pytest.raises(ValueError, match="Unsupported"):
        SoccerTrackMatch.load(tmp_path, "117093")

