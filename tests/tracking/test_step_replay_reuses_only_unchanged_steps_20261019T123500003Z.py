"""Rule: step replay reuses a saved step only when its code and inputs match.

Step replay is a cached-rerun diagnostic. A saved step result is reused only
when the step's code fingerprint and its input fingerprint are both unchanged;
any change runs the step again. Large temporary files go to the local scratch
folder when FOOTBALL_LOCAL_SCRATCH is set, otherwise they stay in the output.
"""

from __future__ import annotations

from pathlib import Path

import football_poc.ball as ball

_calls: list[int] = []


def _step(values: list[int], *, factor: int) -> list[int]:
    _calls.append(1)
    return [value * factor for value in values]


def _other_step(values: list[int], *, factor: int) -> list[int]:
    _calls.append(1)
    return [value * factor + 1 for value in values]


def test_unchanged_step_is_reused_20261019T123500003Z(tmp_path: Path) -> None:
    _calls.clear()
    first = ball._StepReplay(tmp_path).call("s", _step, ([1, 2],), {"factor": 3})
    replay = ball._StepReplay(tmp_path)
    second = replay.call("s", _step, ([1, 2],), {"factor": 3})

    assert first == second == [3, 6]
    assert len(_calls) == 1
    assert replay.report()["reused_steps"] == ["s"]


def test_changed_input_reruns_step_20261019T123500004Z(tmp_path: Path) -> None:
    _calls.clear()
    ball._StepReplay(tmp_path).call("s", _step, ([1, 2],), {"factor": 3})
    replay = ball._StepReplay(tmp_path)

    assert replay.call("s", _step, ([1, 2],), {"factor": 4}) == [4, 8]
    assert len(_calls) == 2
    assert replay.report()["rerun_steps"] == ["s"]


def test_changed_code_reruns_step_20261019T123500005Z(tmp_path: Path) -> None:
    _calls.clear()
    ball._StepReplay(tmp_path).call("s", _step, ([1, 2],), {"factor": 3})

    assert ball._StepReplay(tmp_path).call(
        "s", _other_step, ([1, 2],), {"factor": 3}
    ) == [4, 7]
    assert len(_calls) == 2


def test_scratch_folder_follows_setting_20261019T123500006Z(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "segment" / "analytics-cache"
    monkeypatch.delenv("FOOTBALL_LOCAL_SCRATCH", raising=False)
    assert ball._ball_scratch_directory(output) == output

    monkeypatch.setenv("FOOTBALL_LOCAL_SCRATCH", str(tmp_path / "scratch"))
    scratch = ball._ball_scratch_directory(output)
    assert scratch.parent == tmp_path / "scratch" / "ball"
    assert scratch.name.startswith("analytics-cache-")
    assert scratch == ball._ball_scratch_directory(output)
