from pathlib import Path

import pytest

from football_poc.alfheim_segments import (
    alfheim_source_info,
    plan_alfheim_segment,
    resolve_alfheim_pano,
)


def make_pano(tmp_path: Path, count: int = 10) -> Path:
    pano = tmp_path / "pano"
    pano.mkdir()
    for index in range(count):
        (pano / f"{index:04d}_clip.h264").touch()
    return pano


def test_pano_path_defaults_to_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FOOTBALL_ALFHEIM_PANO", raising=False)

    assert resolve_alfheim_pano(tmp_path) == (tmp_path / "pano").resolve()


def test_pano_path_uses_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    master = tmp_path / "Innovationday Artifacts" / "alfheim" / "pano"
    monkeypatch.setenv("FOOTBALL_ALFHEIM_PANO", str(master))

    assert resolve_alfheim_pano(tmp_path) == master.resolve()


def test_source_info_uses_three_second_segments(tmp_path: Path) -> None:
    assert alfheim_source_info(make_pano(tmp_path, 10)) == {
        "segment_count": 10,
        "segment_seconds": 3.0,
        "duration_seconds": 30.0,
    }


def test_segment_plan_supports_arbitrary_start_and_duration(
    tmp_path: Path,
) -> None:
    plan = plan_alfheim_segment(
        make_pano(tmp_path),
        start_seconds=7.5,
        duration_seconds=8,
    )

    assert plan.first_segment == 2
    assert plan.segment_count == 4
    assert plan.source_start_seconds == 6
    assert plan.clip_start_seconds == 1.5
    assert plan.duration_seconds == 8


def test_segment_plan_clips_at_end_of_source(tmp_path: Path) -> None:
    plan = plan_alfheim_segment(
        make_pano(tmp_path),
        start_seconds=28,
        duration_seconds=10,
    )

    assert plan.first_segment == 9
    assert plan.segment_count == 1
    assert plan.duration_seconds == 2


def test_segment_plan_limits_expensive_requests(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not exceed 300"):
        plan_alfheim_segment(
            make_pano(tmp_path, 200),
            start_seconds=0,
            duration_seconds=301,
        )
