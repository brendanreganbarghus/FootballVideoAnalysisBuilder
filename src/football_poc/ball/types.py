from __future__ import annotations

from .settings import *  # noqa: F401,F403

@dataclass(frozen=True)
class BallPoint:
    source_frame: int
    clip_seconds: float
    confidence: float
    x: float
    y: float
    interpolated: bool = False
    box_diagonal: float = 0.0
    evidence: str = "detector"
    temporal_score: float | None = None
    source_attribution: str = "yolo26_observed"


@dataclass
class BallTrack:
    track_id: int
    points: list[BallPoint]

    @property
    def last(self) -> BallPoint:
        return self.points[-1]

    def predicted_center(self, clip_seconds: float) -> tuple[float, float]:
        if len(self.points) < 2:
            return self.last.x, self.last.y
        previous, current = self.points[-2:]
        elapsed = current.clip_seconds - previous.clip_seconds
        if elapsed <= 0:
            return current.x, current.y
        future = clip_seconds - current.clip_seconds
        return (
            current.x + (current.x - previous.x) / elapsed * future,
            current.y + (current.y - previous.y) / elapsed * future,
        )


@dataclass(frozen=True)
class _BallCandidate:
    point: BallPoint
    near_player_feet: bool


@dataclass(frozen=True)
class _UnanchoredStaticCluster:
    x: float
    y: float


@dataclass(frozen=True)
class _TemplateBridge:
    track_index: int
    first: BallPoint
    second: BallPoint
    target_frame: int
    template_points: tuple[BallPoint, ...]


@dataclass(frozen=True)
class _TemplateMatch:
    x: float
    y: float
    score: float


@dataclass(frozen=True)
class _CircleCandidate:
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class _BidirectionalTemplateBridge:
    track_index: int
    frame_step: int
    previous: BallPoint | None
    first: BallPoint
    second: BallPoint
    following: BallPoint | None
    bridge_kind: str = "short_motion"

    @property
    def frames(self) -> tuple[int, ...]:
        direction = 1 if self.second.source_frame > self.first.source_frame else -1
        return tuple(
            range(
                self.first.source_frame,
                self.second.source_frame + direction,
                direction * self.frame_step,
            )
        )


@dataclass(frozen=True)
class _MotionBridge:
    track_index: int
    first: BallPoint
    second: BallPoint

    @property
    def target_frame(self) -> int:
        return (self.first.source_frame + self.second.source_frame) // 2

    @property
    def frames(self) -> tuple[int, int, int]:
        return (
            self.first.source_frame,
            self.target_frame,
            self.second.source_frame,
        )


@dataclass(frozen=True)
class _ForwardTemplatePlan:
    track_index: int
    frame_step: int
    previous: BallPoint
    seed: BallPoint
    template_points: tuple[BallPoint, ...]
    target_frames: tuple[int, ...]

    @property
    def frames(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                {
                    *(point.source_frame for point in self.template_points),
                    *self.target_frames,
                }
            )
        )


@dataclass(frozen=True)
class _RawMotionProposal:
    point: BallPoint
    mode: str
    appearance_score: float
    foreground_score: float = 0.0
    compactness_score: float = 0.0
    scale_score: float = 0.0
    appearance_consistency_score: float = 0.0
    verification_score: float = 0.0
    trajectory_score: float = 0.0
    attention_support: int = 0
    attention_score: float = 0.0


@dataclass(frozen=True)
class _MotionStreakCandidate:
    source_frame: int
    x: float
    y: float
    width: int
    height: int
    area: float
    visual_score: float


@dataclass(frozen=True)
class _MotionStreakPath:
    points: tuple[_MotionStreakCandidate, ...]
    score: float
    velocity_x: float | None = None
    velocity_y: float | None = None


@dataclass(frozen=True)
class _RawMotionDiagnostics:
    generated: int = 0
    rejected_scale_or_shape: int = 0
    rejected_appearance: int = 0
    rejected_player_body: int = 0
    rejected_ambiguity: int = 0
    rejected_temporal_consistency: int = 0
    near_feet: int = 0
    trajectory_corridor: int = 0
    global_fallback: int = 0
    rejected_verification: int = 0
    rejected_path_plausibility: int = 0
    rejected_alternative_margin: int = 0
    near_feet_generated: int = 0
    trajectory_corridor_generated: int = 0
    global_fallback_generated: int = 0
    minimum_accepted_trajectory_margin: float | None = None
    mean_accepted_trajectory_margin: float | None = None
    attention_accepted: int = 0
    attention_rejected_visual_evidence: int = 0
    attention_rejected_convergence: int = 0
    attention_rejected_temporal_path: int = 0
    startup_points_rejected: int = 0


@dataclass(frozen=True)
class _PlayerAttentionCone:
    origin_x: float
    origin_y: float
    direction_x: float
    direction_y: float
    confidence: float
    player_height: float


@dataclass(frozen=True)
class _KalmanPrediction:
    source_frame: int
    x: float
    y: float
    covariance: np.ndarray


@dataclass(frozen=True)
class _KalmanReacquisitionDiagnostics:
    successes: int = 0
    yolo_candidates: int = 0
    raw_motion_candidates: int = 0
    near_feet: int = 0
    trajectory_corridor: int = 0
    global_fallback: int = 0
    expired_predictions: int = 0
    bidirectional_rejections: int = 0
    visual_evidence_misses: int = 0
    conflicts: int = 0


@dataclass(frozen=True)
class _DenseFlowSample:
    x: float
    y: float
    confidence: float


@dataclass(frozen=True)
class _FocusedBallDetection:
    x: float
    y: float
    confidence: float
    variant: tuple[int, int]
    width: float
    height: float


@dataclass(frozen=True)
class _DenseFlowDiagnostics:
    accepted_points: int = 0
    successful_bridges: int = 0
    rejected_drift: int = 0
    expired_bridges: int = 0
    endpoint_disagreement: int = 0
    insufficient_feature_support: int = 0
    appearance_rejections: int = 0
    player_upper_body_rejections: int = 0
    minimum_path_confidence: float | None = None
    mean_path_confidence: float | None = None
