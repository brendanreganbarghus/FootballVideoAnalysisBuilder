"""Rule: a published segment's regression passes while every golden M# still
matches E# one-to-one, and its status is the same everywhere.

Re-running one segment changes only that segment's status. A changed output
that still matches every M# one-to-one with no extra E# passes and becomes the
published baseline; losing an M# or adding an E# fails. The segment dropdown
and the approvals panel show the same label, and an engine change elsewhere
never marks other segments for a rerun.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / ".github" / "extensions" / "football-event-review" / "shared"


def test_regression_status_follows_golden_matches_20261018T103034156Z() -> None:
    extension = (SHARED / "review-extension.mjs").read_text(encoding="utf-8")
    renderer = (SHARED / "review-renderer.mjs").read_text(encoding="utf-8")
    run = extension.split("async function executePublishedReviewRegression")[1]
    run = run.split("\nfunction ")[0]
    assert "rebaseline = await rebaselineReprocessedSegment(segment);" in run
    assert "exactOutputMatch || matchStateMetadataOnly || goldenRebaselined" in run
    assert "segmentReviewSummaries.delete(segment);" in run

    summary = extension.split("async function segmentReviewSummary")[1]
    summary = summary.split("regressionSummary:")[0]
    assert '"stale"' not in summary
    assert "isRegressionCurrent" not in summary

    assert "Needs rerun" not in renderer
    assert "Regression mismatch" not in renderer
    dropdown = renderer.split("const options = visibleSegments.map")[1]
    dropdown = dropdown.split("segment.coordinationLease?.active")[0]
    assert "regressionJobLabel(" in dropdown
    assert "regressionStatusLabel(segmentSummary.regression)" in dropdown
