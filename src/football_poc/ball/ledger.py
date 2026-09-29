from __future__ import annotations

from .settings import *  # noqa: F401,F403


@dataclass(frozen=True)
class FrameLedgerEntry:
    source_frame: int
    clip_seconds: float
    status: str = "unresolved"
    x: float | None = None
    y: float | None = None
    confirming_module: str | None = None
    evidence: dict[str, Any] | None = None
    confidence: float | None = None
    source_attribution: str = "detected"
    rejection_reasons: tuple[dict[str, str], ...] = ()
    box_diagonal: float = 0.0
    point_evidence: str = "detector"
    point_source_attribution: str = "yolo26_observed"
    temporal_score: float | None = None

    def to_point(self) -> BallPoint:
        if self.status != "confirmed" or self.x is None or self.y is None:
            raise ValueError("Only confirmed ledger entries can become BallPoint")
        return BallPoint(
            source_frame=self.source_frame,
            clip_seconds=self.clip_seconds,
            confidence=float(self.confidence or 0.0),
            x=float(self.x),
            y=float(self.y),
            interpolated=self.confirming_module == "02_time_machine",
            box_diagonal=float(self.box_diagonal),
            evidence=self.point_evidence,
            temporal_score=self.temporal_score,
            source_attribution=self.point_source_attribution,
            confirming_module=self.confirming_module,
            rejection_reasons=self.rejection_reasons,
            ledger_source_attribution=self.source_attribution,
        )


class FrameLedger:
    def __init__(self, frames: Iterable[tuple[int, float]]) -> None:
        entries: dict[int, FrameLedgerEntry] = {}
        for frame, seconds in frames:
            entries[int(frame)] = FrameLedgerEntry(
                source_frame=int(frame),
                clip_seconds=float(seconds),
            )
        if not entries:
            raise ValueError("FrameLedger requires at least one sampled frame")
        self._entries = dict(sorted(entries.items()))

    @property
    def entries(self) -> dict[int, FrameLedgerEntry]:
        return dict(self._entries)

    def confirm(
        self,
        frame: int,
        *,
        x: float,
        y: float,
        confirming_module: str,
        evidence: dict[str, Any],
        confidence: float,
        clip_seconds: float | None = None,
        box_diagonal: float = 0.0,
        point_evidence: str = "detector",
        point_source_attribution: str = "yolo26_observed",
        temporal_score: float | None = None,
    ) -> FrameLedgerEntry:
        source_frame = int(frame)
        if source_frame not in self._entries:
            raise KeyError(f"Frame {source_frame} is not in the sampled ledger")
        current = self._entries[source_frame]
        if current.status == "confirmed":
            raise ValueError(
                f"Frame {source_frame} is already confirmed by "
                f"{current.confirming_module}"
            )
        updated = FrameLedgerEntry(
            source_frame=source_frame,
            clip_seconds=(
                float(clip_seconds)
                if clip_seconds is not None
                else current.clip_seconds
            ),
            status="confirmed",
            x=float(x),
            y=float(y),
            confirming_module=str(confirming_module),
            evidence=dict(evidence),
            confidence=float(confidence),
            source_attribution="detected",
            rejection_reasons=current.rejection_reasons,
            box_diagonal=float(box_diagonal),
            point_evidence=str(point_evidence),
            point_source_attribution=str(point_source_attribution),
            temporal_score=temporal_score,
        )
        self._entries[source_frame] = updated
        return updated

    def reject(self, frame: int, module: str, reason: str) -> None:
        source_frame = int(frame)
        if source_frame not in self._entries:
            return
        current = self._entries[source_frame]
        if current.status == "confirmed":
            return
        self._entries[source_frame] = replace(
            current,
            rejection_reasons=(
                *current.rejection_reasons,
                {"module": str(module), "reason": str(reason)},
            ),
        )

    def withdraw(self, frame: int, module: str, reason: str) -> None:
        """Return a confirmation to unresolved within the confirming module.

        Only the module that confirmed a frame may withdraw it, while that
        module is still running; later modules still cannot edit a lock.
        """
        source_frame = int(frame)
        current = self._entries.get(source_frame)
        if current is None or current.status != "confirmed":
            return
        if current.confirming_module != str(module):
            raise ValueError(
                f"Frame {source_frame} was confirmed by "
                f"{current.confirming_module}, not {module}"
            )
        self._entries[source_frame] = FrameLedgerEntry(
            source_frame=source_frame,
            clip_seconds=current.clip_seconds,
            rejection_reasons=(
                *current.rejection_reasons,
                {"module": str(module), "reason": str(reason)},
            ),
        )

    def unresolved_frames(self) -> tuple[int, ...]:
        return tuple(
            frame
            for frame, entry in self._entries.items()
            if entry.status == "unresolved"
        )

    def confirmed(self, frame: int) -> FrameLedgerEntry | None:
        entry = self._entries.get(int(frame))
        if entry is None or entry.status != "confirmed":
            return None
        return entry

    def confirmed_entries(self) -> tuple[FrameLedgerEntry, ...]:
        return tuple(
            entry
            for entry in self._entries.values()
            if entry.status == "confirmed"
        )

    def confirmed_points(self) -> list[BallPoint]:
        return [entry.to_point() for entry in self.confirmed_entries()]

    def to_tracks(self) -> tuple[BallTrack, ...]:
        points = sorted(self.confirmed_points(), key=lambda point: point.source_frame)
        return (BallTrack(track_id=1, points=points),) if points else tuple()

    def module_summary(self) -> dict[str, Any]:
        confirmed = Counter(
            entry.confirming_module
            for entry in self._entries.values()
            if entry.status == "confirmed"
        )
        reasons = Counter(
            reason["reason"]
            for entry in self._entries.values()
            if entry.status == "unresolved"
            for reason in entry.rejection_reasons
        )
        return {
            "confirmed": dict(sorted(confirmed.items())),
            "unresolved_count": sum(
                entry.status == "unresolved"
                for entry in self._entries.values()
            ),
            "top_unresolved_reasons": [
                {"reason": reason, "count": count}
                for reason, count in reasons.most_common(10)
            ],
        }

    def unresolved_state_payloads(self) -> list[dict[str, Any]]:
        return [
            {
                "source_frame": entry.source_frame,
                "clip_seconds": entry.clip_seconds,
                "confidence": None,
                "x": None,
                "y": None,
                "interpolated": False,
                "box_diagonal": None,
                "evidence": "unresolved",
                "temporal_score": None,
                "source_attribution": "unresolved",
                "state": "unresolved",
                "uncertainty_radius_pixels": None,
                "event_evidence_eligible": False,
                "confirming_module": None,
                "rejection_reasons": list(entry.rejection_reasons),
                "source_attribution_ledger": entry.source_attribution,
            }
            for entry in self._entries.values()
            if entry.status == "unresolved"
        ]
