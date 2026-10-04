from __future__ import annotations

from football_poc.engine.common import *

def retain_stable_possession_segments(
    segments: Iterable[PossessionSegment],
    *,
    minimum_observations: int,
    trusted_single_observation_track_ids: set[int],
) -> list[PossessionSegment]:
    return [
        segment
        for segment in segments
        if len(segment.observations) >= minimum_observations
        or (
            len(segment.observations) == 1
            and segment.player_track_id in trusted_single_observation_track_ids
        )
    ]

def include_supported_single_touch_senders(
    segments: Iterable[PossessionSegment],
    stable_segments: Iterable[PossessionSegment],
    *,
    co_visible_track_pairs: Iterable[frozenset[int]],
    maximum_transfer_seconds: float,
    minimum_transfer_heights: float,
) -> list[PossessionSegment]:
    stable = list(stable_segments)
    stable_keys = {
        (segment.player_track_id, segment.start_seconds, segment.end_seconds)
        for segment in stable
    }
    distinct_pairs = set(co_visible_track_pairs)
    supported = list(stable)
    for sender in segments:
        sender_key = (
            sender.player_track_id,
            sender.start_seconds,
            sender.end_seconds,
        )
        if sender_key in stable_keys or len(sender.observations) != 1:
            continue
        touch = sender.observations[0]
        if touch.control_ratio > 0.35:
            continue
        receiver = next(
            (
                candidate
                for candidate in stable
                if candidate.team == sender.team
                and candidate.player_track_id != sender.player_track_id
                and frozenset(
                    (sender.player_track_id, candidate.player_track_id)
                ) in distinct_pairs
                and (
                    controlled := [
                        observation
                        for observation in candidate.observations
                        if observation.control_ratio <= 0.5
                    ]
                )
                and len(controlled) >= 2
                and 0
                <= controlled[0].clip_seconds - touch.clip_seconds
                <= maximum_transfer_seconds
                and hypot(
                    controlled[0].ball_x - touch.ball_x,
                    controlled[0].ball_y - touch.ball_y,
                )
                / max(
                    1.0,
                    (touch.player_height + controlled[0].player_height) / 2,
                )
                >= minimum_transfer_heights
            ),
            None,
        )
        if receiver is not None:
            supported.append(sender)
    return sorted(supported, key=lambda segment: segment.start_seconds)

def build_possession_segments(
    observations: Iterable[PossessionObservation],
    *,
    segment_gap_seconds: float,
    identity_switch_radius_heights: float,
    co_visible_track_return_seconds: float = 0.0,
    co_visible_track_pairs: Iterable[frozenset[int]] = (),
) -> list[PossessionSegment]:
    if co_visible_track_return_seconds < 0:
        raise ValueError("Co-visible track return duration cannot be negative")
    ordered = sorted(observations, key=lambda item: item.clip_seconds)
    incompatible_track_pairs = set(co_visible_track_pairs)
    if co_visible_track_return_seconds > 0:
        for index, first in enumerate(ordered):
            for middle_index in range(index + 1, len(ordered)):
                middle = ordered[middle_index]
                if (
                    middle.clip_seconds - first.clip_seconds
                    > co_visible_track_return_seconds
                ):
                    break
                if middle.player_track_id == first.player_track_id:
                    continue
                if any(
                    last.player_track_id == first.player_track_id
                    and last.clip_seconds - middle.clip_seconds
                    <= co_visible_track_return_seconds + 1e-9
                    for last in ordered[middle_index + 1 :]
                    if last.clip_seconds - middle.clip_seconds
                    <= co_visible_track_return_seconds + 1e-9
                ):
                    incompatible_track_pairs.add(
                        frozenset(
                            (first.player_track_id, middle.player_track_id)
                        )
                    )
    segments: list[PossessionSegment] = []
    for observation_index, observation in enumerate(ordered):
        if not segments:
            segments.append(
                PossessionSegment(
                    observation.team,
                    observation.player_track_id,
                    [observation],
                )
            )
            continue
        current = segments[-1]
        previous = current.observations[-1]
        gap = observation.clip_seconds - previous.clip_seconds
        player_distance = hypot(
            observation.player_x - previous.player_x,
            observation.player_y - previous.player_y,
        )
        player_scale = max(
            1.0, (observation.player_height + previous.player_height) / 2
        )
        same_physical_player = (
            observation.player_track_id == previous.player_track_id
            or player_distance / player_scale <= identity_switch_radius_heights
        )
        continuous_dribble = False
        if (
            len(current.observations) >= 2
            and previous.control_ratio <= 1.0
            and observation.control_ratio <= 1.0
            and gap > 0
        ):
            earlier = current.observations[-2]
            incoming = (
                previous.ball_x - earlier.ball_x,
                previous.ball_y - earlier.ball_y,
            )
            outgoing = (
                observation.ball_x - previous.ball_x,
                observation.ball_y - previous.ball_y,
            )
            incoming_distance = hypot(*incoming)
            outgoing_distance = hypot(*outgoing)
            direction_cosine = (
                (
                    incoming[0] * outgoing[0]
                    + incoming[1] * outgoing[1]
                )
                / (incoming_distance * outgoing_distance)
                if incoming_distance > 0 and outgoing_distance > 0
                else -1.0
            )
            ball_speed_heights = outgoing_distance / gap / player_scale
            continuous_dribble = (
                direction_cosine >= 0.9
                and ball_speed_heights <= 5.0
            )
        prior_track_returns = (
            observation.player_track_id != current.player_track_id
            and frozenset(
                (observation.player_track_id, current.player_track_id)
            )
            in incompatible_track_pairs
        )
        if (
            gap <= segment_gap_seconds
            and observation.team == current.team
            and (same_physical_player or continuous_dribble)
            and not prior_track_returns
        ):
            current.observations.append(observation)
            continue
        segments.append(
            PossessionSegment(
                observation.team,
                observation.player_track_id,
                [observation],
            )
        )
    return segments

def _co_visible_track_pairs(
    players: dict[int, list[dict[str, Any]]],
) -> set[frozenset[int]]:
    pairs: set[frozenset[int]] = set()
    for frame_players in players.values():
        track_ids = sorted(
            {
                int(player["track_id"])
                for player in frame_players
                if player.get("track_id") is not None
            }
        )
        for index, first in enumerate(track_ids):
            for second in track_ids[index + 1 :]:
                pairs.add(frozenset((first, second)))
    return pairs

def collapse_transient_opponent_segments(
    segments: Iterable[PossessionSegment],
    *,
    maximum_transient_seconds: float,
    maximum_occlusion_seconds: float | None = None,
    maximum_owner_speed_heights_per_second: float = 3.0,
    minimum_owner_direction_cosine: float | None = None,
) -> list[PossessionSegment]:
    if maximum_transient_seconds < 0:
        raise ValueError("Maximum transient opponent duration cannot be negative")
    if maximum_occlusion_seconds is not None and maximum_occlusion_seconds < 0:
        raise ValueError("Maximum occlusion duration cannot be negative")
    if maximum_owner_speed_heights_per_second <= 0:
        raise ValueError("Maximum owner speed must be positive")
    if (
        minimum_owner_direction_cosine is not None
        and not -1 <= minimum_owner_direction_cosine <= 1
    ):
        raise ValueError("Owner direction cosine must be between -1 and 1")
    source = list(segments)
    accepted: list[PossessionSegment] = []
    index = 0
    while index < len(source):
        current = source[index]
        if accepted and current.team != accepted[-1].team:
            prior_team = accepted[-1].team
            end = index
            while end < len(source) and source[end].team != prior_team:
                end += 1
            if end < len(source):
                transient_duration = (
                    source[end - 1].end_seconds - current.start_seconds
                )
                owner_continuity = _plausible_owner_continuity(
                    accepted[-1],
                    source[end],
                    maximum_seconds=maximum_occlusion_seconds,
                    maximum_speed_heights_per_second=(
                        maximum_owner_speed_heights_per_second
                    ),
                    minimum_direction_cosine=minimum_owner_direction_cosine,
                )
                following_gap = (
                    source[end].start_seconds - source[end - 1].end_seconds
                )
                continuity_window = (
                    maximum_occlusion_seconds
                    if maximum_occlusion_seconds is not None
                    else maximum_transient_seconds
                )
                coherent_opponent_control = any(
                    len(segment.observations) >= 3
                    and sum(
                        observation.control_ratio <= 0.5
                        for observation in segment.observations
                    )
                    >= 1
                    for segment in source[index:end]
                )
                if not coherent_opponent_control:
                    for opponent_index in range(index, end):
                        opponent = source[opponent_index]
                        if (
                            len(opponent.observations) < 2
                            or not any(
                                observation.control_ratio <= 0.5
                                for observation in opponent.observations
                            )
                        ):
                            continue
                        controlled_teammate_seen = False
                        for later in source[end + 1 :]:
                            if (
                                later.start_seconds - opponent.end_seconds
                                > maximum_transient_seconds + 1e-9
                            ):
                                break
                            if later.team != opponent.team:
                                continue
                            if (
                                later.player_track_id
                                == opponent.player_track_id
                                and controlled_teammate_seen
                            ):
                                coherent_opponent_control = True
                                break
                            if (
                                later.player_track_id
                                != opponent.player_track_id
                                and len(later.observations) >= 2
                                and any(
                                    observation.control_ratio <= 0.5
                                    for observation in later.observations
                                )
                            ):
                                controlled_teammate_seen = True
                        if coherent_opponent_control:
                            break
                transient_bridge = (
                    transient_duration <= maximum_transient_seconds
                    and following_gap <= continuity_window
                    and not coherent_opponent_control
                )
                # A coherent "opponent" spell on the same player track that
                # then resumes for the owner team is a team-label flicker,
                # not opponent control.
                long_opponent_tracks = {
                    segment.player_track_id
                    for segment in source[index:end]
                    if len(segment.observations) >= 3
                }
                opponent_label_flicker = (
                    long_opponent_tracks == {source[end].player_track_id}
                    and len(source[end].observations) >= 2
                )
                owner_continuity_allowed = owner_continuity and (
                    len(source[end].observations) >= 3
                    or not coherent_opponent_control
                    or opponent_label_flicker
                )
                if (
                    transient_bridge
                    or owner_continuity_allowed
                ):
                    following = source[end]
                    if (
                        accepted[-1].team == following.team
                        and accepted[-1].observations[-1].player_track_id
                        == following.observations[0].player_track_id
                    ):
                        accepted[-1].observations.extend(following.observations)
                        index = end + 1
                        continue
                    index = end
                    continue
        accepted.append(current)
        index += 1
    return accepted

def _plausible_owner_continuity(
    previous: PossessionSegment,
    following: PossessionSegment,
    *,
    maximum_seconds: float | None,
    maximum_speed_heights_per_second: float,
    minimum_direction_cosine: float | None = None,
) -> bool:
    if maximum_seconds is None or previous.team != following.team:
        return False
    start = previous.observations[-1]
    end = following.observations[0]
    elapsed = end.clip_seconds - start.clip_seconds
    if elapsed <= 0 or elapsed > maximum_seconds:
        return False
    scale = max(1.0, (start.player_height + end.player_height) / 2)
    distance_heights = hypot(
        end.player_x - start.player_x,
        end.player_y - start.player_y,
    ) / scale
    if distance_heights / elapsed > maximum_speed_heights_per_second:
        return False
    if minimum_direction_cosine is None:
        return True
    if len(previous.observations) < 2:
        return False
    prior = previous.observations[-2]
    owner_motion = (
        start.player_x - prior.player_x,
        start.player_y - prior.player_y,
    )
    continuation = (
        end.player_x - start.player_x,
        end.player_y - start.player_y,
    )
    owner_distance = hypot(*owner_motion)
    continuation_distance = hypot(*continuation)
    if owner_distance == 0 or continuation_distance == 0:
        return False
    direction_cosine = (
        owner_motion[0] * continuation[0]
        + owner_motion[1] * continuation[1]
    ) / (owner_distance * continuation_distance)
    return direction_cosine >= minimum_direction_cosine

def _smooth_teams(
    observations: list[PossessionObservation],
    window_seconds: float,
) -> list[PossessionObservation]:
    if window_seconds <= 0:
        return list(observations)
    smoothed: list[PossessionObservation] = []
    for index, observation in enumerate(observations):
        nearby = [
            item
            for item in observations
            if abs(item.clip_seconds - observation.clip_seconds) <= window_seconds
        ]
        votes: dict[str, float] = defaultdict(float)
        for item in nearby:
            votes[item.team] += 1 / max(0.1, item.control_ratio) ** 2
        team = max(votes, key=votes.get)
        continued_team_control = (
            index > 0
            and observations[index - 1].team == observation.team
            and observation.clip_seconds
            - observations[index - 1].clip_seconds
            <= window_seconds
        )
        if (
            team == observation.team
            or observation.control_ratio <= 0.35
            or continued_team_control
        ):
            smoothed.append(observation)
    return smoothed



def run(results_dir: Path, settings: PossessionLedgerSettings = PossessionLedgerSettings()) -> dict[str, Any]:
    possession = read_stage_json(results_dir / "possession.json")
    segments = possession.get("segments", [])
    return {
        "stage": "possession_ledger",
        "segment_count": len(segments),
        "segments": segments if settings.include_segments else [],
        "team_order": [segment.get("team") for segment in segments],
        "player_order": [segment.get("player_track_id") for segment in segments],
    }
