from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from math import hypot
from statistics import median


@dataclass(frozen=True)
class Detection:
    track_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def height(self) -> float:
        return max(self.y2 - self.y1, 1.0)


@dataclass(frozen=True)
class ActionEvent:
    event_type: str
    timestamp_seconds: float
    confidence: float
    actor_track_id: int | None
    details: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ActionEngine:
    """Infers simple image-space actions from tracked object trajectories."""

    def __init__(
        self,
        *,
        control_radius_heights: float = 1.25,
        walking_speed_heights_per_second: float = 0.12,
        running_speed_heights_per_second: float = 1.5,
        departure_speed_heights_per_second: float = 2.0,
        history_seconds: float = 1.0,
    ) -> None:
        self.control_radius_heights = control_radius_heights
        self.walking_speed = walking_speed_heights_per_second
        self.running_speed = running_speed_heights_per_second
        self.departure_speed = departure_speed_heights_per_second
        self.history_seconds = history_seconds
        self._person_history: dict[
            int, deque[tuple[float, float, float, float]]
        ] = defaultdict(deque)
        self._ball_history: deque[tuple[float, float, float]] = deque()
        self._controller_id: int | None = None
        self._released_by: int | None = None

    def update(
        self, timestamp_seconds: float, detections: list[Detection]
    ) -> tuple[dict[int, str], list[ActionEvent]]:
        people = [
            detection
            for detection in detections
            if detection.class_name == "person" and detection.track_id >= 0
        ]
        balls = [
            detection for detection in detections if detection.class_name == "sports ball"
        ]

        motion_states: dict[int, str] = {}
        for person in people:
            center_x, center_y = person.center
            history = self._person_history[person.track_id]
            history.append((timestamp_seconds, center_x, center_y, person.height))
            self._trim_person_history(history, timestamp_seconds)
            motion_states[person.track_id] = self._motion_state(history)

        events: list[ActionEvent] = []
        if not balls:
            return motion_states, events

        ball = max(balls, key=lambda detection: detection.confidence)
        ball_x, ball_y = ball.center
        self._ball_history.append((timestamp_seconds, ball_x, ball_y))
        self._trim_ball_history(timestamp_seconds)

        controller, proximity = self._find_controller(ball, people)
        controller_id = controller.track_id if controller else None

        if controller_id is not None and controller_id != self._controller_id:
            confidence = max(0.0, min(1.0, 1.0 - proximity))
            events.append(
                ActionEvent(
                    event_type="ball_control_candidate",
                    timestamp_seconds=timestamp_seconds,
                    confidence=confidence,
                    actor_track_id=controller_id,
                    details="Ball is close to the tracked player's lower body.",
                )
            )
            self._released_by = None

        if (
            self._controller_id is not None
            and controller_id is None
            and self._released_by != self._controller_id
        ):
            scale = median(person.height for person in people) if people else 1.0
            speed = self._trajectory_speed(self._ball_history, scale)
            if speed >= self.departure_speed:
                confidence = min(1.0, speed / (self.departure_speed * 2))
                events.append(
                    ActionEvent(
                        event_type="pass_or_shot_candidate",
                        timestamp_seconds=timestamp_seconds,
                        confidence=confidence,
                        actor_track_id=self._controller_id,
                        details=(
                            "Ball departed a controlling player at "
                            f"{speed:.2f} player-heights/second."
                        ),
                    )
                )
                self._released_by = self._controller_id

        self._controller_id = controller_id
        return motion_states, events

    def _find_controller(
        self, ball: Detection, people: list[Detection]
    ) -> tuple[Detection | None, float]:
        best_person: Detection | None = None
        best_ratio = float("inf")
        ball_x, ball_y = ball.center

        for person in people:
            person_x = (person.x1 + person.x2) / 2
            person_foot_y = person.y2
            ratio = hypot(ball_x - person_x, ball_y - person_foot_y) / person.height
            if ratio < best_ratio:
                best_person = person
                best_ratio = ratio

        if best_ratio > self.control_radius_heights:
            return None, best_ratio
        return best_person, best_ratio / self.control_radius_heights

    def _motion_state(
        self, history: deque[tuple[float, float, float, float]]
    ) -> str:
        if len(history) < 2:
            return "unknown"
        start_time, start_x, start_y, start_height = history[0]
        end_time, end_x, end_y, end_height = history[-1]
        elapsed = end_time - start_time
        if elapsed <= 0:
            return "unknown"
        scale = max((start_height + end_height) / 2, 1.0)
        speed = hypot(end_x - start_x, end_y - start_y) / scale / elapsed
        if speed < self.walking_speed:
            return "stationary"
        if speed < self.running_speed:
            return "walking"
        return "running"

    @staticmethod
    def _trajectory_speed(
        history: deque[tuple[float, float, float]], scale: float
    ) -> float:
        if len(history) < 2:
            return 0.0
        start_time, start_x, start_y = history[0]
        end_time, end_x, end_y = history[-1]
        elapsed = end_time - start_time
        if elapsed <= 0:
            return 0.0
        return hypot(end_x - start_x, end_y - start_y) / max(scale, 1.0) / elapsed

    def _trim_person_history(
        self,
        history: deque[tuple[float, float, float, float]],
        timestamp_seconds: float,
    ) -> None:
        while history and timestamp_seconds - history[0][0] > self.history_seconds:
            history.popleft()

    def _trim_ball_history(self, timestamp_seconds: float) -> None:
        while (
            self._ball_history
            and timestamp_seconds - self._ball_history[0][0] > self.history_seconds
        ):
            self._ball_history.popleft()

