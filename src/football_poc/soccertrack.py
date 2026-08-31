from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_LABELS = frozenset(
    {
        "ball_player_block",
        "cross",
        "drive",
        "free_kick",
        "goal",
        "header",
        "high_pass",
        "out",
        "pass",
        "player_successful_tackle",
        "shot",
        "throw_in",
    }
)

_GAME_TIME_PATTERN = re.compile(r"^\s*(?P<half>\d+)\s*-\s*(?P<minutes>\d+):(?P<seconds>\d{2})\s*$")
_REGULATION_HALF_SECONDS = 45 * 60


@dataclass(frozen=True)
class SoccerTrackAction:
    half: int
    label: str
    source_position_ms: int
    match_seconds: float
    half_seconds: float
    clock_seconds: int
    team: str | None
    player_id: str | None
    visibility: str | None

    def as_clip_dict(self, clip_start_seconds: float) -> dict[str, object]:
        value = asdict(self)
        value["clip_seconds"] = round(self.half_seconds - clip_start_seconds, 3)
        return value


@dataclass(frozen=True)
class ActionWindow:
    half: int
    start_seconds: float
    duration_seconds: float
    actions: tuple[SoccerTrackAction, ...]

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + self.duration_seconds

    @property
    def counts(self) -> dict[str, int]:
        return dict(sorted(Counter(action.label for action in self.actions).items()))


class SoccerTrackMatch:
    def __init__(
        self,
        *,
        root: Path,
        match_id: str,
        fps: float,
        actions: Iterable[SoccerTrackAction],
        schema_variant: str,
    ) -> None:
        self.root = root
        self.match_id = match_id
        self.fps = fps
        self.actions = tuple(sorted(actions, key=lambda action: action.match_seconds))
        self.schema_variant = schema_variant

    @classmethod
    def load(cls, root: str | Path, match_id: str) -> SoccerTrackMatch:
        dataset_root = Path(root)
        bas_path = (
            dataset_root
            / "bas"
            / str(match_id)
            / f"{match_id}_12_class_events.json"
        )
        if not bas_path.is_file():
            raise FileNotFoundError(f"SoccerTrack BAS file does not exist: {bas_path}")

        payload = json.loads(bas_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("SoccerTrack BAS payload must be a JSON object")

        raw_actions, schema_variant = _get_raw_actions(payload)
        fps = float(payload.get("fps", 25.0))
        if fps <= 0:
            raise ValueError("SoccerTrack FPS must be greater than zero")

        actions = tuple(_parse_action(item) for item in raw_actions)
        if not actions:
            raise ValueError("SoccerTrack BAS file contains no actions")

        return cls(
            root=dataset_root,
            match_id=str(match_id),
            fps=fps,
            actions=actions,
            schema_variant=schema_variant,
        )

    def video_path(self, half: int, *, calibrated: bool = False) -> Path:
        _validate_half(half)
        half_name = "1st" if half == 1 else "2nd"
        video_dir = self.root / "videos" / self.match_id
        names = (
            [f"{self.match_id}_calibrated_panorama_{half_name}_half.mp4"]
            if calibrated
            else [
                f"{self.match_id}_panorama_{half_name}_half.mp4",
                f"{self.match_id}_calibrated_panorama_{half_name}_half.mp4",
            ]
        )
        for name in names:
            candidate = video_dir / name
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            f"No {'calibrated ' if calibrated else ''}SoccerTrack video found for "
            f"match {self.match_id}, half {half} under {video_dir}"
        )

    def actions_for_half(self, half: int) -> tuple[SoccerTrackAction, ...]:
        _validate_half(half)
        return tuple(action for action in self.actions if action.half == half)

    def actions_in_window(
        self, *, half: int, start_seconds: float, duration_seconds: float
    ) -> tuple[SoccerTrackAction, ...]:
        _validate_window(start_seconds, duration_seconds)
        end_seconds = start_seconds + duration_seconds
        return tuple(
            action
            for action in self.actions
            if action.half == half
            and start_seconds <= action.half_seconds < end_seconds
        )

    def select_event_window(
        self,
        *,
        half: int,
        duration_seconds: float = 60.0,
        required_labels: Iterable[str] = ("shot",),
    ) -> ActionWindow:
        _validate_half(half)
        if duration_seconds <= 0:
            raise ValueError("Window duration must be greater than zero")

        required = frozenset(_normalize_label(label) for label in required_labels)
        half_actions = self.actions_for_half(half)
        anchors = [
            action for action in half_actions if not required or action.label in required
        ]
        if not anchors:
            labels = ", ".join(sorted(required))
            raise ValueError(f"No matching event anchors in half {half}: {labels}")

        candidates: list[ActionWindow] = []
        for anchor in anchors:
            start = max(0.0, anchor.half_seconds - duration_seconds / 2)
            actions = self.actions_in_window(
                half=half,
                start_seconds=start,
                duration_seconds=duration_seconds,
            )
            candidates.append(
                ActionWindow(
                    half=half,
                    start_seconds=start,
                    duration_seconds=duration_seconds,
                    actions=actions,
                )
            )

        return max(
            candidates,
            key=lambda window: (
                sum(action.label in required for action in window.actions),
                sum(action.label in {"pass", "high_pass"} for action in window.actions),
                len(window.actions),
                -window.start_seconds,
            ),
        )

    def write_window_manifest(self, window: ActionWindow, output: str | Path) -> Path:
        video = self.video_path(window.half)
        manifest = {
            "dataset": "SoccerTrack v2",
            "match_id": self.match_id,
            "half": window.half,
            "fps": self.fps,
            "video": str(video.resolve()),
            "start_seconds": round(window.start_seconds, 3),
            "end_seconds": round(window.end_seconds, 3),
            "duration_seconds": round(window.duration_seconds, 3),
            "start_frame": round(window.start_seconds * self.fps),
            "end_frame": round(window.end_seconds * self.fps),
            "action_counts": window.counts,
            "actions": [
                action.as_clip_dict(window.start_seconds)
                for action in window.actions
            ],
            "source_schema": self.schema_variant,
        }
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return destination


def _get_raw_actions(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    for field in ("actions", "annotations"):
        value = payload.get(field)
        if value is not None:
            if not isinstance(value, list) or not all(
                isinstance(item, dict) for item in value
            ):
                raise ValueError(f"SoccerTrack '{field}' must be a list of objects")
            return value, field
    raise ValueError("SoccerTrack BAS payload has neither 'actions' nor 'annotations'")


def _parse_action(raw: dict[str, Any]) -> SoccerTrackAction:
    game_time = raw.get("gameTime")
    match = _GAME_TIME_PATTERN.match(str(game_time))
    if match is None:
        raise ValueError(f"Invalid SoccerTrack gameTime: {game_time!r}")

    half = int(match.group("half"))
    _validate_half(half)
    clock_seconds = int(match.group("minutes")) * 60 + int(match.group("seconds"))
    position_ms = _parse_position(raw.get("position"))
    source_seconds = position_ms / 1000
    scheduled_half_start = (half - 1) * _REGULATION_HALF_SECONDS

    if half > 1 and source_seconds >= scheduled_half_start:
        match_seconds = source_seconds
        half_seconds = source_seconds - scheduled_half_start
    else:
        half_seconds = source_seconds
        match_seconds = scheduled_half_start + source_seconds

    label = _normalize_label(str(raw.get("label", "")))
    if label not in SUPPORTED_LABELS:
        raise ValueError(f"Unsupported SoccerTrack action label: {raw.get('label')!r}")

    team_value = raw.get("team")
    team = str(team_value).lower() if team_value is not None else None
    if team not in {None, "left", "right"}:
        raise ValueError(f"Invalid SoccerTrack team: {team_value!r}")

    player_value = raw.get("player_id")
    visibility_value = raw.get("visibility")
    return SoccerTrackAction(
        half=half,
        label=label,
        source_position_ms=position_ms,
        match_seconds=match_seconds,
        half_seconds=half_seconds,
        clock_seconds=clock_seconds,
        team=team,
        player_id=str(player_value) if player_value is not None else None,
        visibility=str(visibility_value) if visibility_value is not None else None,
    )


def _normalize_label(label: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", label.strip().lower())).strip(
        "_"
    )


def _parse_position(value: Any) -> int:
    try:
        position = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid SoccerTrack position: {value!r}") from error
    if position < 0:
        raise ValueError("SoccerTrack position cannot be negative")
    return position


def _validate_half(half: int) -> None:
    if half not in {1, 2}:
        raise ValueError(f"SoccerTrack half must be 1 or 2, got {half}")


def _validate_window(start_seconds: float, duration_seconds: float) -> None:
    if start_seconds < 0:
        raise ValueError("Window start cannot be negative")
    if duration_seconds <= 0:
        raise ValueError("Window duration must be greater than zero")
