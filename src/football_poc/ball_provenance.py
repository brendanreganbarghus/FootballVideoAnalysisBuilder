from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


MINIMUM_DIRECT_BALL_PROVENANCE = 0.90


def validate_ball_provenance(
    ball_tracks: Path,
    ball_state_estimates: Path,
    *,
    output: Path,
    enforce_threshold: bool = True,
) -> dict[str, object]:
    track_payload = json.loads(ball_tracks.read_text(encoding="utf-8"))
    state_payload = json.loads(
        ball_state_estimates.read_text(encoding="utf-8")
    )
    track_manifest = Path(str(track_payload.get("manifest", ""))).resolve()
    state_manifest = Path(str(state_payload.get("manifest", ""))).resolve()
    if track_manifest != state_manifest:
        raise ValueError(
            "Ball tracks and state estimates have different runtime manifests"
        )
    states = state_payload.get("states", [])
    if not states:
        raise ValueError("Ball-state estimates contain no sampled frames")
    direct_frames = sorted(
        int(state["source_frame"])
        for state in states
        if bool(state.get("event_evidence_eligible", False))
    )
    estimated_frames = sorted(
        int(state["source_frame"])
        for state in states
        if not bool(state.get("event_evidence_eligible", False))
    )
    direct_ratio = len(direct_frames) / len(states)
    report: dict[str, object] = {
        "status": (
            "passed"
            if direct_ratio >= MINIMUM_DIRECT_BALL_PROVENANCE
            else "review_required"
        ),
        "minimum_direct_provenance": MINIMUM_DIRECT_BALL_PROVENANCE,
        "sampled_frame_count": len(states),
        "direct_frame_count": len(direct_frames),
        "estimated_frame_count": len(estimated_frames),
        "direct_provenance": round(direct_ratio, 6),
        "threshold_enforcement": (
            "blocking" if enforce_threshold else "report_only"
        ),
        "pipeline_action": (
            "continue"
            if direct_ratio >= MINIMUM_DIRECT_BALL_PROVENANCE
            or not enforce_threshold
            else "blocked"
        ),
        "direct_frames": direct_frames,
        "estimated_frames": estimated_frames,
        "states_by_evidence": dict(
            sorted(
                Counter(
                    str(state.get("state", "unknown")) for state in states
                ).items()
            )
        ),
        "ball_tracks_sha256": hashlib.sha256(
            ball_tracks.read_bytes()
        ).hexdigest(),
        "ball_state_estimates_sha256": hashlib.sha256(
            ball_state_estimates.read_bytes()
        ).hexdigest(),
        "review_policy": (
            "Human review authorizes proceeding but never promotes an "
            "estimated frame to direct runtime evidence."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if enforce_threshold and direct_ratio < MINIMUM_DIRECT_BALL_PROVENANCE:
        raise ValueError(
            "Ball provenance review required before rules-engine inference: "
            f"{len(direct_frames)}/{len(states)} direct frames "
            f"({direct_ratio:.1%}) is below the "
            f"{MINIMUM_DIRECT_BALL_PROVENANCE:.0%} gate"
        )
    return report
