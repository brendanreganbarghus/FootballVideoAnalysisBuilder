from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _gate_unanchored_start_points_by_attention(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
) -> tuple[tuple[BallTrack, ...], int]:
    tracks = tuple(tracks)
    if not tracks or len(records) < 3:
        return tracks, 0
    ordered_frames = sorted(int(record["source_frame"]) for record in records)
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    frame_index = {
        source_frame: index
        for index, source_frame in enumerate(ordered_frames)
    }
    grayscale = _read_sampled_grayscale_frames(video, ordered_frames)
    start_seconds = min(float(record["clip_seconds"]) for record in records)
    startup_end = start_seconds + float(
        SOCCERTRACK_PLAYER_ATTENTION_PROFILE["startup_seconds"]
    )
    rejected = 0
    filtered_tracks: list[BallTrack] = []
    for track in tracks:
        ordered_points = sorted(
            track.points,
            key=lambda point: point.source_frame,
        )
        retained: list[BallPoint] = []
        anchored = False
        for point_index, point in enumerate(ordered_points):
            if anchored or point.clip_seconds > startup_end:
                retained.append(point)
                anchored = True
                continue
            if _has_sustained_detector_confirmation(
                ordered_points,
                point_index=point_index,
                frame_step=frame_step,
            ):
                retained.append(point)
                anchored = True
                continue
            index = frame_index.get(point.source_frame)
            if index is None or index == 0 or index >= len(ordered_frames) - 1:
                rejected += 1
                continue
            cones = _player_attention_cones(
                grayscale[ordered_frames[index - 1]],
                grayscale[point.source_frame],
                grayscale[ordered_frames[index + 1]],
                records_by_frame[point.source_frame],
            )
            support, score = _attention_convergence(point, cones)
            appearance_score = _adjacent_appearance_consistency(
                grayscale[ordered_frames[index - 1]],
                grayscale[point.source_frame],
                grayscale[ordered_frames[index + 1]],
                point,
                reference_diameter=max(1.0, point.box_diagonal),
            )
            crop_radius = max(4, round(point.box_diagonal * 0.8))
            left = max(0, round(point.x) - crop_radius)
            right = min(width, round(point.x) + crop_radius + 1)
            top = max(0, round(point.y) - crop_radius)
            bottom = min(height, round(point.y) + crop_radius + 1)
            crop = grayscale[point.source_frame][top:bottom, left:right]
            contrast = (
                float(np.percentile(crop, 90) - np.percentile(crop, 10))
                if crop.size
                else 0.0
            )
            confirmation_count = int(
                SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                    "startup_forward_confirmation_frames"
                ]
            )
            following = ordered_points[
                point_index + 1 : point_index + 1 + confirmation_count
            ]
            forward_confirmed = (
                len(following) == confirmation_count
                and all(
                    candidate.source_frame
                    == point.source_frame + frame_step * offset
                    for offset, candidate in enumerate(following, start=1)
                )
                and all(
                    hypot(
                        second.x - first.x,
                        second.y - first.y,
                    )
                    / ((second.source_frame - first.source_frame) / fps)
                    <= 1600.0
                    for first, second in zip(
                        [point, *following[:-1]],
                        following,
                    )
                )
            )
            if (
                support
                >= int(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "startup_minimum_converging_players"
                    ]
                )
                and score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "startup_minimum_convergence_score"
                    ]
                )
                and appearance_score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "minimum_appearance_consistency_score"
                    ]
                )
                and contrast >= 24
                and forward_confirmed
                and not _inside_player_upper_body(
                    point,
                    records_by_frame[point.source_frame],
                )
            ):
                retained.append(point)
                anchored = True
            else:
                rejected += 1
        if retained:
            filtered_tracks.append(BallTrack(track.track_id, retained))
    return tuple(filtered_tracks), rejected


def _has_sustained_detector_confirmation(
    points: list[BallPoint],
    *,
    point_index: int,
    frame_step: int,
    minimum_points: int = 3,
) -> bool:
    sequence = points[point_index : point_index + minimum_points]
    return (
        len(sequence) == minimum_points
        and all(
            point.source_attribution == "yolo26_observed"
            and not point.interpolated
            for point in sequence
        )
        and all(
            second.source_frame - first.source_frame == frame_step
            for first, second in zip(sequence, sequence[1:])
        )
    )


def _add_raw_motion_proposals(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    detector_candidates: Iterable[BallPoint] = (),
) -> tuple[tuple[BallTrack, ...], _RawMotionDiagnostics]:
    tracks = tuple(tracks)
    if not tracks or len(records) < 3:
        return tracks, _RawMotionDiagnostics()
    trusted = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    trusted_frames = {point.source_frame for point in trusted}
    detector_candidate_frames = {
        point.source_frame for point in detector_candidates
    }
    reference_diameter = median(
        point.box_diagonal
        for point in trusted
        if point.box_diagonal > 0
    )
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    ordered_frames = sorted(records_by_frame)
    grayscale = _read_sampled_grayscale_frames(video, ordered_frames)
    proposals_by_frame: dict[int, list[_RawMotionProposal]] = {}
    counters: Counter[str] = Counter()
    pending_frames = [
        (previous_frame, source_frame, following_frame)
        for previous_frame, source_frame, following_frame in zip(
            ordered_frames,
            ordered_frames[1:],
            ordered_frames[2:],
        )
        if source_frame not in trusted_frames
        and source_frame not in detector_candidate_frames
    ]

    def frame_proposals(
        frames: tuple[int, int, int],
    ) -> tuple[tuple[_RawMotionProposal, ...], Counter[str]]:
        previous_frame, source_frame, following_frame = frames
        return _raw_motion_frame_proposals(
            previous=grayscale[previous_frame],
            current=grayscale[source_frame],
            following=grayscale[following_frame],
            record=records_by_frame.get(source_frame),
            source_frame=source_frame,
            clip_seconds=float(records_by_frame[source_frame]["clip_seconds"]),
            width=width,
            height=height,
            reference_diameter=reference_diameter,
            trusted=trusted,
            frame_step=frame_step,
        )

    for (_, source_frame, _), (proposals, rejected) in zip(
        pending_frames,
        _ordered_parallel_map(frame_proposals, pending_frames),
    ):
        proposals_by_frame[source_frame] = list(proposals)
        counters.update(rejected)
        counters["generated"] += len(proposals)

    selected, selection_rejections = _select_raw_motion_proposals(
        proposals_by_frame,
        trusted=trusted,
        frame_step=frame_step,
        fps=fps,
        reference_diameter=reference_diameter,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    counters.update(selection_rejections)
    selected = tuple(
        proposal
        for proposal in selected
        if _has_local_restoration_support(
            proposal.point,
            trusted=trusted,
            frame_step=frame_step,
        )
        and _point_path_is_plausible(
            proposal.point,
            trusted=[
                *trusted,
                *(
                    other.point
                    for other in selected
                    if other is not proposal
                ),
            ],
            frame_step=frame_step,
            fps=fps,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )
    )
    if not selected:
        return tracks, _motion_diagnostics(counters)

    additions_by_track: dict[int, list[BallPoint]] = defaultdict(list)
    for proposal in selected:
        track_index = min(
            range(len(tracks)),
            key=lambda index: min(
                abs(proposal.point.source_frame - point.source_frame)
                for point in tracks[index].points
            ),
        )
        additions_by_track[track_index].append(proposal.point)
        counters[proposal.mode] += 1
    enriched = tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions_by_track[index]],
                key=lambda point: point.source_frame,
            ),
        )
        for index, track in enumerate(tracks)
    )
    return enriched, _motion_diagnostics(counters)


def _read_sampled_grayscale_frames(
    video: Path,
    source_frames: Iterable[int],
) -> dict[int, np.ndarray]:
    required = set(source_frames)
    if not required:
        return {}
    if (
        _ACTIVE_GRAYSCALE_FRAME_STORE is not None
        and _ACTIVE_GRAYSCALE_FRAME_STORE.video == video.resolve()
        and required.issubset(_ACTIVE_GRAYSCALE_FRAME_STORE.source_frame_set)
    ):
        return _ACTIVE_GRAYSCALE_FRAME_STORE.read(required)
    frames: dict[int, np.ndarray] = {}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(required) + 1):
            if source_frame not in required:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to source frame {source_frame} in {video}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {source_frame} from {video}"
                )
            frames[source_frame] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    finally:
        capture.release()
    return frames


def _raw_motion_frame_proposals(
    *,
    previous: np.ndarray,
    current: np.ndarray,
    following: np.ndarray,
    record: dict[str, Any],
    source_frame: int,
    clip_seconds: float,
    width: int,
    height: int,
    reference_diameter: float,
    trusted: list[BallPoint],
    frame_step: int,
    difference_threshold: int = SOCCERTRACK_RAW_MOTION_PROFILE[
        "difference_threshold"
    ],
    minimum_circularity: float = SOCCERTRACK_RAW_MOTION_PROFILE[
        "minimum_circularity"
    ],
    minimum_appearance_range: float = SOCCERTRACK_RAW_MOTION_PROFILE[
        "minimum_appearance_range"
    ],
) -> tuple[tuple[_RawMotionProposal, ...], Counter[str]]:
    previous_difference = cv2.absdiff(current, previous)
    following_difference = cv2.absdiff(current, following)
    motion = cv2.min(previous_difference, following_difference)
    _, mask = cv2.threshold(
        motion,
        difference_threshold,
        255,
        cv2.THRESH_BINARY,
    )
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    minimum_extent = max(
        2.0,
        reference_diameter
        * SOCCERTRACK_RAW_MOTION_PROFILE[
            "minimum_extent_ball_diameters"
        ],
    )
    maximum_extent = max(
        8.0,
        reference_diameter
        * SOCCERTRACK_RAW_MOTION_PROFILE[
            "maximum_extent_ball_diameters"
        ],
    )
    minimum_area = max(
        3.0,
        reference_diameter**2
        * SOCCERTRACK_RAW_MOTION_PROFILE[
            "minimum_area_ball_diameters_squared"
        ],
    )
    maximum_area = max(
        40.0,
        reference_diameter**2
        * SOCCERTRACK_RAW_MOTION_PROFILE[
            "maximum_area_ball_diameters_squared"
        ],
    )
    counters: Counter[str] = Counter()
    proposals: list[_RawMotionProposal] = []
    attention_cones = _player_attention_cones(
        previous,
        current,
        following,
        record,
    )
    for contour in contours:
        x, y, blob_width, blob_height = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        circularity = (
            4 * np.pi * area / perimeter**2
            if perimeter > 0
            else 0.0
        )
        if (
            area < minimum_area
            or area > maximum_area
            or min(blob_width, blob_height) < minimum_extent
            or max(blob_width, blob_height) > maximum_extent
            or max(blob_width, blob_height)
            / max(1, min(blob_width, blob_height))
            > 2.2
            or circularity < minimum_circularity
        ):
            counters["rejected_scale_or_shape"] += 1
            continue
        moments = cv2.moments(contour)
        if moments["m00"] <= 0:
            counters["rejected_scale_or_shape"] += 1
            continue
        center_x = float(moments["m10"] / moments["m00"])
        center_y = float(moments["m01"] / moments["m00"])
        point = BallPoint(
            source_frame=source_frame,
            clip_seconds=clip_seconds,
            confidence=0.0,
            x=center_x,
            y=center_y,
            box_diagonal=hypot(blob_width, blob_height),
        )
        if not _inside_soccertrack_pitch(point, width, height):
            continue
        if _inside_player_upper_body(point, record):
            counters["rejected_player_body"] += 1
            continue
        radius = max(3, round(reference_diameter * 0.8))
        left = max(0, round(center_x) - radius)
        right = min(current.shape[1], round(center_x) + radius + 1)
        top = max(0, round(center_y) - radius)
        bottom = min(current.shape[0], round(center_y) + radius + 1)
        crop = current[top:bottom, left:right]
        appearance_range = float(
            np.percentile(crop, 90) - np.percentile(crop, 10)
        )
        if appearance_range < minimum_appearance_range:
            counters["rejected_appearance"] += 1
            continue
        mode = _motion_search_mode(
            point,
            record=record,
            trusted=trusted,
            frame_step=frame_step,
            reference_diameter=reference_diameter,
        )
        counters[f"{mode}_generated"] += 1
        contour_fill = area / max(1.0, blob_width * blob_height)
        # The filled contour lies inside its bounding rectangle, so the
        # masked mean over that rectangle equals the full-frame masked mean.
        motion_window = motion[y : y + blob_height, x : x + blob_width]
        foreground_mask = np.zeros_like(motion_window)
        cv2.drawContours(
            foreground_mask,
            [contour],
            -1,
            255,
            -1,
            offset=(-x, -y),
        )
        foreground_strength = float(
            cv2.mean(motion_window, mask=foreground_mask)[0]
        )
        foreground_score = min(1.0, foreground_strength / 64.0)
        compactness_score = min(
            1.0,
            (min(1.0, circularity / 0.8) + min(1.0, contour_fill))
            / 2,
        )
        scale_ratio = max(
            1e-6,
            hypot(blob_width, blob_height) / reference_diameter,
        )
        scale_score = float(np.exp(-abs(np.log(scale_ratio))))
        texture_score = min(1.0, appearance_range / 64.0)
        appearance_consistency_score = _adjacent_appearance_consistency(
            previous,
            current,
            following,
            point,
            reference_diameter=reference_diameter,
        )
        lower_body_penalty = (
            float(
                SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                    "lower_body_interior_penalty"
                ]
            )
            if _inside_player_lower_body(point, record)
            else 0.0
        )
        verification_score = max(
            0.0,
            min(
                1.0,
                foreground_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "foreground_weight"
                    ]
                )
                + compactness_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "compactness_weight"
                    ]
                )
                + scale_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "scale_weight"
                    ]
                )
                + texture_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "texture_weight"
                    ]
                )
                + appearance_consistency_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "appearance_consistency_weight"
                    ]
                )
                - lower_body_penalty,
            ),
        )
        trajectory_score = _proposal_trajectory_score(
            point,
            trusted=trusted,
            frame_step=frame_step,
            reference_diameter=reference_diameter,
        )
        attention_support, attention_score = _attention_convergence(
            point,
            attention_cones,
        )
        proposals.append(
            _RawMotionProposal(
                point=BallPoint(
                    source_frame=source_frame,
                    clip_seconds=clip_seconds,
                    confidence=round(
                        min(1.0, circularity * appearance_range / 64),
                        6,
                    ),
                    x=center_x,
                    y=center_y,
                    box_diagonal=hypot(blob_width, blob_height),
                    evidence=f"raw_motion_{mode}",
                    temporal_score=None,
                    source_attribution="raw_motion_micro_crop_supported",
                ),
                mode=mode,
                appearance_score=appearance_range,
                foreground_score=foreground_score,
                compactness_score=compactness_score,
                scale_score=scale_score,
                appearance_consistency_score=(
                    appearance_consistency_score
                ),
                verification_score=verification_score,
                trajectory_score=trajectory_score,
                attention_support=attention_support,
                attention_score=attention_score,
            )
        )
    return tuple(proposals), counters


class _SampledGrayscaleFrameStore:
    def __init__(
        self,
        *,
        video: Path,
        source_frames: list[int],
        output: Path,
        reuse: bool,
    ) -> None:
        self.video = video.resolve()
        self.source_frames = source_frames
        self.source_frame_set = frozenset(source_frames)
        self.output = output
        self.reuse = reuse
        self.data_path = output / "decoded-sampled-grayscale-u8.dat"
        self.metadata_path = output / "decoded-sampled-grayscale.json"
        self.metrics_path = output / "decode-cache-metrics.json"
        self.frame_indexes = {
            source_frame: index
            for index, source_frame in enumerate(source_frames)
        }
        self.array: np.memmap | None = None
        self.metrics: dict[str, Any] = {
            "schema_version": 1,
            "mode": "reuse" if reuse else "fresh",
            "video_opens": 0,
            "decoded_frames": 0,
            "grabbed_frames": 0,
            "cache_frame_hits": 0,
            "cache_requests": 0,
            "build_seconds": 0.0,
        }

    def _expected_metadata(self, *, width: int, height: int) -> dict[str, Any]:
        video_stat = self.video.stat()
        return {
            "schema_version": 1,
            "video": str(self.video),
            "video_size": video_stat.st_size,
            "video_modified_ns": video_stat.st_mtime_ns,
            "source_frames": self.source_frames,
            "width": width,
            "height": height,
            "dtype": "uint8",
            "colorspace": "opencv_bgr_to_gray",
        }

    def open(self) -> None:
        if not self.source_frames:
            return
        self.output.mkdir(parents=True, exist_ok=True)
        capture = cv2.VideoCapture(str(self.video))
        self.metrics["video_opens"] += 1
        try:
            if not capture.isOpened():
                raise ValueError(f"Could not open benchmark video: {self.video}")
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            expected = self._expected_metadata(width=width, height=height)
            expected_bytes = len(self.source_frames) * width * height
            if (
                self.reuse
                and self.metadata_path.is_file()
                and self.data_path.is_file()
                and json.loads(self.metadata_path.read_text(encoding="utf-8"))
                == expected
                and self.data_path.stat().st_size == expected_bytes
            ):
                self.array = np.memmap(
                    self.data_path,
                    dtype=np.uint8,
                    mode="r",
                    shape=(len(self.source_frames), height, width),
                )
                self.metrics["reused_existing_cache"] = True
                return

            self.data_path.unlink(missing_ok=True)
            self.metadata_path.unlink(missing_ok=True)
            started = time.perf_counter()
            array = np.memmap(
                self.data_path,
                dtype=np.uint8,
                mode="w+",
                shape=(len(self.source_frames), height, width),
            )
            required = self.source_frame_set
            last_required = self.source_frames[-1]
            for source_frame in range(last_required + 1):
                if source_frame not in required:
                    if not capture.grab():
                        raise RuntimeError(
                            f"Could not skip to source frame {source_frame} "
                            f"in {self.video}"
                        )
                    self.metrics["grabbed_frames"] += 1
                    continue
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError(
                        f"Could not read source frame {source_frame} "
                        f"from {self.video}"
                    )
                array[self.frame_indexes[source_frame]] = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2GRAY,
                )
                self.metrics["decoded_frames"] += 1
            array.flush()
            self.metadata_path.write_text(
                json.dumps(expected, indent=2),
                encoding="utf-8",
            )
            self.metrics["build_seconds"] = round(
                time.perf_counter() - started,
                3,
            )
            self.metrics["reused_existing_cache"] = False
            self.array = array
        finally:
            capture.release()

    def read(self, required: set[int]) -> dict[int, np.ndarray]:
        if self.array is None:
            raise RuntimeError("Sampled grayscale frame store is not open")
        self.metrics["cache_requests"] += 1
        self.metrics["cache_frame_hits"] += len(required)
        return {
            source_frame: self.array[self.frame_indexes[source_frame]]
            for source_frame in required
        }

    def close(self, *, delete_cache: bool) -> None:
        self.metrics["cache_bytes"] = (
            self.data_path.stat().st_size
            if self.data_path.is_file()
            else 0
        )
        self.metrics["deleted_after_success"] = delete_cache
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self.metrics_path.write_text(
            json.dumps(self.metrics, indent=2),
            encoding="utf-8",
        )
        if self.array is not None:
            self.array.flush()
            memory_map = getattr(self.array, "_mmap", None)
            if memory_map is not None:
                memory_map.close()
            self.array = None
        if delete_cache:
            self.data_path.unlink(missing_ok=True)
            self.metadata_path.unlink(missing_ok=True)
