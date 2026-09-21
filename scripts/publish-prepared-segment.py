from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))

from football_poc.artifact_store import (
    publish_prepared_segment,
    verify_prepared_segment,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Publish one prepared segment and its selected workflow artifacts "
            "to the checksummed shared catalogue."
        )
    )
    parser.add_argument("segment_root", type=Path)
    parser.add_argument(
        "--workflow",
        required=True,
        choices=("innovation_day_bac", "live_iteration_25"),
    )
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--recording-id", required=True)
    args = parser.parse_args()
    segment = publish_prepared_segment(
        args.segment_root,
        workflow_id=args.workflow,
        source_metadata={
            "camera_id": args.camera_id,
            "recording_id": args.recording_id,
        },
    )
    verify_prepared_segment(segment)
    print(f"Published shared prepared segment: {segment.root}")


if __name__ == "__main__":
    main()
