from __future__ import annotations

from football_poc.engine.common import *

def _control_observations(
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    control_radius_heights: float,
    maximum_flyby_speed_pixels_per_second: float | None = None,
    maximum_flyby_speed_heights_per_second: float | None = None,
    minimum_flyby_direction_cosine: float = 0.85,
    maximum_ground_contact_height_ratio: float | None = None,
    maximum_aerial_contact_direction_cosine: float = 0.5,
    future_control_confirmation_seconds: float = 0.0,
) -> list[PossessionObservation]:
    if (
        maximum_flyby_speed_pixels_per_second is not None
        and maximum_flyby_speed_pixels_per_second <= 0
    ):
        raise ValueError("Maximum fly-by pixel speed must be positive")
    if (
        maximum_flyby_speed_heights_per_second is not None
        and maximum_flyby_speed_heights_per_second <= 0
    ):
        raise ValueError("Maximum fly-by normalized speed must be positive")
    if (
        maximum_flyby_speed_pixels_per_second is not None
        or maximum_flyby_speed_heights_per_second is not None
    ):
        if not -1 <= minimum_flyby_direction_cosine <= 1:
            raise ValueError("Fly-by direction cosine must be between -1 and 1")
    if (
        maximum_ground_contact_height_ratio is not None
        and maximum_ground_contact_height_ratio < 0
    ):
        raise ValueError("Maximum ground-contact height ratio cannot be negative")
    if not -1 <= maximum_aerial_contact_direction_cosine <= 1:
        raise ValueError("Aerial-contact direction cosine must be between -1 and 1")
    if future_control_confirmation_seconds < 0:
        raise ValueError("Future control confirmation cannot be negative")
    motion = _ball_motion_evidence(balls)
    wide_turns = _ball_wide_turn_cosines(balls)
    proximity_by_track: dict[int, list[tuple[float, float, float]]] = defaultdict(
        list
    )
    for source_frame, frame_balls in balls.items():
        for ball in frame_balls:
            for player in players.get(source_frame, []):
                height = max(1.0, float(player["y2"]) - float(player["y1"]))
                player_x = (float(player["x1"]) + float(player["x2"])) / 2
                player_y = float(player["y2"])
                distance = hypot(
                    float(ball["x"]) - player_x,
                    float(ball["y"]) - player_y,
                )
                ratio = distance / height
                if ratio <= control_radius_heights:
                    proximity_by_track[int(player["track_id"])].append(
                        (
                            float(ball["clip_seconds"]),
                            (player_y - float(ball["y"])) / height,
                            ratio,
                        )
                    )
    observations: list[PossessionObservation] = []
    for source_frame, frame_balls in sorted(balls.items()):
        frame_players = players.get(source_frame, [])
        candidates: list[
            tuple[float, float, dict[str, Any], dict[str, Any]]
        ] = []
        for ball in frame_balls:
            evidence = motion.get(
                (int(ball["track_id"]), int(source_frame))
            )
            ball_candidates: list[
                tuple[float, float, dict[str, Any], dict[str, Any]]
            ] = []
            for player in frame_players:
                height = max(1.0, float(player["y2"]) - float(player["y1"]))
                player_x = (float(player["x1"]) + float(player["x2"])) / 2
                player_y = float(player["y2"])
                distance = hypot(
                    float(ball["x"]) - player_x,
                    float(ball["y"]) - player_y,
                )
                ratio = distance / height
                ball_height_ratio = (
                    player_y - float(ball["y"])
                ) / height
                horizontal_ratio = abs(
                    float(ball["x"]) - player_x
                ) / height
                future_control_confirmed = (
                    future_control_confirmation_seconds > 0
                    and maximum_ground_contact_height_ratio is not None
                    and bool(observations)
                    and observations[-1].team == str(player["team"])
                    and any(
                        0
                        < candidate_seconds - float(ball["clip_seconds"])
                        <= future_control_confirmation_seconds
                        and candidate_height_ratio
                        <= maximum_ground_contact_height_ratio
                        and candidate_ratio <= 0.5
                        for (
                            candidate_seconds,
                            candidate_height_ratio,
                            candidate_ratio,
                        ) in proximity_by_track[int(player["track_id"])]
                    )
                )
                elevated_without_deflection = (
                    maximum_ground_contact_height_ratio is not None
                    and ball_height_ratio > maximum_ground_contact_height_ratio
                    and not future_control_confirmed
                    and (
                        evidence is None
                        or (
                            evidence[1] > maximum_aerial_contact_direction_cosine
                            and wide_turns.get(
                                (int(ball["track_id"]), int(source_frame)),
                                1.0,
                            )
                            > WIDE_TURN_MAXIMUM_COSINE
                        )
                        or horizontal_ratio > 0.5
                    )
                )
                if elevated_without_deflection:
                    continue
                if ratio <= control_radius_heights:
                    ball_candidates.append((distance, ratio, ball, player))
            if not ball_candidates:
                continue
            nearest = min(ball_candidates, key=lambda item: item[0])
            nearest_matches_prior_owner = (
                bool(observations)
                and observations[-1].team == str(nearest[3]["team"])
            )
            future_nearest_control_confirmed = (
                nearest_matches_prior_owner
                and any(
                    0
                    < candidate_seconds - float(nearest[2]["clip_seconds"])
                    <= future_control_confirmation_seconds
                    and candidate_height_ratio
                    <= (
                        maximum_ground_contact_height_ratio
                        if maximum_ground_contact_height_ratio is not None
                        else 0.4
                    )
                    and candidate_ratio <= 0.5
                    for (
                        candidate_seconds,
                        candidate_height_ratio,
                        candidate_ratio,
                    ) in proximity_by_track[int(nearest[3]["track_id"])]
                )
            )
            if (
                evidence is not None
                and evidence[1] >= minimum_flyby_direction_cosine
                and not future_nearest_control_confirmed
            ):
                pixel_flyby = (
                    maximum_flyby_speed_pixels_per_second is not None
                    and evidence[0] >= maximum_flyby_speed_pixels_per_second
                )
                nearest_height = max(
                    1.0,
                    float(nearest[3]["y2"]) - float(nearest[3]["y1"]),
                )
                normalized_flyby = (
                    maximum_flyby_speed_heights_per_second is not None
                    and evidence[0] / nearest_height
                    >= maximum_flyby_speed_heights_per_second
                )
                if pixel_flyby or normalized_flyby:
                    continue
            candidates.extend(ball_candidates)
        if not candidates:
            continue
        _, ratio, ball, player = min(candidates, key=lambda item: item[0])
        observations.append(
            PossessionObservation(
                source_frame=source_frame,
                clip_seconds=float(ball["clip_seconds"]),
                team=str(player["team"]),
                player_track_id=int(player["track_id"]),
                player_x=(float(player["x1"]) + float(player["x2"])) / 2,
                player_y=float(player["y2"]),
                player_height=max(
                    1.0, float(player["y2"]) - float(player["y1"])
                ),
                ball_x=float(ball["x"]),
                ball_y=float(ball["y"]),
                control_ratio=round(ratio, 4),
                ball_interpolated=bool(ball.get("interpolated", False)),
                ball_evidence=str(ball.get("evidence", "detector")),
                ball_state=str(ball.get("state", "observed")),
                ball_uncertainty_radius_pixels=(
                    float(ball["uncertainty_radius_pixels"])
                    if ball.get("uncertainty_radius_pixels") is not None
                    else None
                ),
                ball_event_evidence_eligible=bool(
                    ball.get("event_evidence_eligible", True)
                ),
            )
        )
    return observations

# A ball nearly at rest against a player's body moves only a few pixels per
# sample, so the turn of a head or chest touch can hide inside one sample of
# position noise. Measuring the turn across two samples on each side shows it.
WIDE_TURN_SAMPLES = 2
# The wider window smooths over a real bend, so it must show a clear turn of
# at least a right angle; a slight bend is not evidence of a touch.
WIDE_TURN_MAXIMUM_COSINE = 0.0


def _ball_wide_turn_cosines(
    balls: dict[int, list[dict[str, Any]]],
) -> dict[tuple[int, int], float]:
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_points in balls.values():
        for point in frame_points:
            if not point.get("interpolated", False):
                tracks[int(point["track_id"])].append(point)
    cosines: dict[tuple[int, int], float] = {}
    for track_id, points in tracks.items():
        ordered = sorted(points, key=lambda point: float(point["clip_seconds"]))
        for index in range(WIDE_TURN_SAMPLES, len(ordered) - WIDE_TURN_SAMPLES):
            previous = ordered[index - WIDE_TURN_SAMPLES]
            current = ordered[index]
            following = ordered[index + WIDE_TURN_SAMPLES]
            incoming = (
                float(current["x"]) - float(previous["x"]),
                float(current["y"]) - float(previous["y"]),
            )
            outgoing = (
                float(following["x"]) - float(current["x"]),
                float(following["y"]) - float(current["y"]),
            )
            incoming_distance = hypot(*incoming)
            outgoing_distance = hypot(*outgoing)
            if incoming_distance == 0 or outgoing_distance == 0:
                continue
            cosines[(track_id, int(current["source_frame"]))] = (
                incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
            ) / (incoming_distance * outgoing_distance)
    return cosines


def _ball_motion_evidence(
    balls: dict[int, list[dict[str, Any]]],
) -> dict[tuple[int, int], tuple[float, float]]:
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_points in balls.values():
        for point in frame_points:
            if not point.get("interpolated", False):
                tracks[int(point["track_id"])].append(point)
    evidence: dict[tuple[int, int], tuple[float, float]] = {}
    for track_id, points in tracks.items():
        ordered = sorted(points, key=lambda point: float(point["clip_seconds"]))
        for previous, current, following in zip(
            ordered, ordered[1:], ordered[2:]
        ):
            incoming_seconds = float(current["clip_seconds"]) - float(
                previous["clip_seconds"]
            )
            outgoing_seconds = float(following["clip_seconds"]) - float(
                current["clip_seconds"]
            )
            if incoming_seconds <= 0 or outgoing_seconds <= 0:
                continue
            incoming = (
                float(current["x"]) - float(previous["x"]),
                float(current["y"]) - float(previous["y"]),
            )
            outgoing = (
                float(following["x"]) - float(current["x"]),
                float(following["y"]) - float(current["y"]),
            )
            incoming_distance = hypot(*incoming)
            outgoing_distance = hypot(*outgoing)
            if incoming_distance == 0 or outgoing_distance == 0:
                continue
            cosine = (
                incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
            ) / (incoming_distance * outgoing_distance)
            speed = max(
                incoming_distance / incoming_seconds,
                outgoing_distance / outgoing_seconds,
            )
            evidence[(track_id, int(current["source_frame"]))] = (
                speed,
                cosine,
            )
    return evidence

def _load_player_points(
    path: Path, expected_manifest: Path
) -> dict[int, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not _matches_manifest_reference(
        payload.get("manifest", ""),
        expected_manifest,
    ):
        raise ValueError("Player tracks were created for a different manifest")
    points: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for track in payload.get("tracks", []):
        for point in track.get("points", []):
            point_team = point.get("team")
            if point_team not in {"red", "black", "blue", "white"}:
                continue
            value = dict(point)
            value["team"] = point_team
            value["track_id"] = int(track["track_id"])
            value["role"] = track.get("role", "player")
            points[int(point["source_frame"])].append(value)
    return points

def _load_ball_points(
    path: Path,
    expected_manifest: Path,
    *,
    state_estimates_path: Path | None = None,
) -> dict[int, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not _matches_manifest_reference(
        payload.get("manifest", ""),
        expected_manifest,
    ):
        raise ValueError("Ball tracks were created for a different manifest")
    points: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for track in payload.get("tracks", []):
        for point in track.get("points", []):
            value = dict(point)
            value["track_id"] = int(track["track_id"])
            value.setdefault("state", "observed")
            value.setdefault("event_evidence_eligible", True)
            points[int(point["source_frame"])].append(value)
    if state_estimates_path is None or not state_estimates_path.is_file():
        return points

    state_payload = json.loads(
        state_estimates_path.read_text(encoding="utf-8")
    )
    if not _matches_manifest_reference(
        state_payload.get("manifest", ""),
        expected_manifest,
    ):
        raise ValueError(
            "Ball-state estimates were created for a different manifest"
        )
    policy = state_payload.get("policy", {})
    if not policy.get(
        "trajectory_estimates_are_for_continuity_and_search_only",
        False,
    ):
        raise ValueError(
            "Ball-state estimates do not declare continuity-only trajectory use"
        )
    existing_frames = set(points)
    for state in state_payload.get("states", []):
        source_frame = int(state["source_frame"])
        if source_frame not in existing_frames or "event_evidence_eligible" not in state:
            continue
        for value in points[source_frame]:
            value["event_evidence_eligible"] = bool(state["event_evidence_eligible"])
            value["state"] = state.get("state", value["state"])
    track_ids = {
        int(point["track_id"])
        for frame_points in points.values()
        for point in frame_points
    }
    if len(track_ids) != 1:
        raise ValueError(
            "Ball-state continuity requires exactly one accepted ball track"
        )
    track_id = next(iter(track_ids))
    for state in state_payload.get("states", []):
        source_frame = int(state["source_frame"])
        if source_frame in existing_frames:
            continue
        if bool(state.get("event_evidence_eligible", False)):
            raise ValueError(
                "Missing ball-track frames cannot be promoted as direct evidence"
            )
        if state.get("x") is None or state.get("y") is None:
            continue
        value = dict(state)
        value["track_id"] = track_id
        value["interpolated"] = True
        points[source_frame].append(value)
    return points

def _event_ball_evidence(
    event: PredictedEvent,
    balls: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    start = float(event.clip_seconds)
    end = float(
        event.completion_seconds
        if event.completion_seconds is not None
        else event.clip_seconds
    )
    if end < start:
        start, end = end, start
    relevant = [
        point
        for frame_points in balls.values()
        for point in frame_points
        if start - 0.2 <= float(point["clip_seconds"]) <= end + 0.2
    ]
    if not relevant:
        return {
            "status": "unavailable",
            "direct_frames": [],
            "estimated_frames": [],
            "evidence_types": [],
            "maximum_uncertainty_radius_pixels": None,
            "review_note": "No ball sample overlaps this event interval.",
        }
    direct_frames = sorted(
        {
            int(point["source_frame"])
            for point in relevant
            if bool(point.get("event_evidence_eligible", True))
        }
    )
    estimated_frames = sorted(
        {
            int(point["source_frame"])
            for point in relevant
            if not bool(point.get("event_evidence_eligible", True))
        }
    )
    status = (
        "mixed"
        if direct_frames and estimated_frames
        else "direct"
        if direct_frames
        else "estimated"
    )
    uncertainties = [
        float(point["uncertainty_radius_pixels"])
        for point in relevant
        if point.get("uncertainty_radius_pixels") is not None
    ]
    return {
        "status": status,
        "direct_frames": direct_frames,
        "estimated_frames": estimated_frames,
        "evidence_types": sorted(
            {str(point.get("evidence", "detector")) for point in relevant}
        ),
        "maximum_uncertainty_radius_pixels": (
            round(max(uncertainties), 3) if uncertainties else None
        ),
        "review_note": (
            "Trajectory estimates supported continuity only; speed and "
            "direction evidence used direct ball observations."
            if estimated_frames
            else "All overlapping ball samples have direct detector or "
            "recovery evidence."
        ),
    }

def _ball_evidence_summary(
    balls: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    points = [
        point for frame_points in balls.values() for point in frame_points
    ]
    direct_frames = sorted(
        {
            int(point["source_frame"])
            for point in points
            if bool(point.get("event_evidence_eligible", True))
        }
    )
    estimated_frames = sorted(
        {
            int(point["source_frame"])
            for point in points
            if not bool(point.get("event_evidence_eligible", True))
        }
    )
    states = Counter(str(point.get("state", "observed")) for point in points)
    return {
        "total_frames": len(set(direct_frames) | set(estimated_frames)),
        "direct_frame_count": len(direct_frames),
        "estimated_frame_count": len(estimated_frames),
        "direct_frames": direct_frames,
        "estimated_frames": estimated_frames,
        "frames_by_state": {
            state: sorted(
                {
                    int(point["source_frame"])
                    for point in points
                    if str(point.get("state", "observed")) == state
                }
            )
            for state in sorted(states)
        },
        "motion_evidence_policy": (
            "Only direct detector or recovery observations provide ball speed "
            "and direction evidence. Estimated states support continuity and "
            "proximity only."
        ),
    }

def _matches_manifest_reference(
    recorded_manifest: object,
    expected_manifest: Path,
) -> bool:
    recorded = Path(str(recorded_manifest or "")).resolve()
    expected = expected_manifest.resolve()
    if recorded == expected:
        return True

    def segment_identity(path: Path) -> tuple[str, ...] | None:
        parts = path.parts
        for index, part in enumerate(parts):
            if re.fullmatch(r"segment-\d{4}-\d{3}", part):
                identity = [value.casefold() for value in parts[index:]]
                # Bundles published before the single review workflow kept
                # their artifacts in a per-workflow namespace folder.
                if len(identity) > 2 and identity[1] in LEGACY_NAMESPACES:
                    del identity[1]
                return tuple(identity)
        return None

    recorded_identity = segment_identity(recorded)
    return (
        recorded_identity is not None
        and recorded_identity == segment_identity(expected)
    )



def run(results_dir: Path, settings: BallEvidenceSettings = BallEvidenceSettings()) -> dict[str, Any]:
    possession = read_stage_json(results_dir / "possession.json")
    observations = possession.get("observations", [])
    return {
        "stage": "ball_evidence",
        "observation_count": len(observations),
        "has_ball_state_estimates": "ball_evidence_summary" in possession,
        "ball_evidence_summary": possession.get("ball_evidence_summary", {}) if settings.include_summary else {},
        "evidence_values": sorted({item.get("ball_evidence", "detector") for item in observations}),
        "state_values": sorted({item.get("ball_state", "observed") for item in observations}),
    }
