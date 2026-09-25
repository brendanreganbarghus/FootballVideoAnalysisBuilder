from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))

from football_poc.artifact_store import (
    discover_artifact_root,
    resolve_detector_model,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the shared and local Innovation Day prerequisites."
    )
    parser.add_argument(
        "--require-alfheim",
        action="store_true",
        help="Require the shared extracted Alfheim pano source.",
    )
    parser.add_argument(
        "--require-custom-camera",
        action="store_true",
        help="Require at least one shared custom-camera sample.",
    )
    args = parser.parse_args()

    root = discover_artifact_root()
    if root is None:
        raise FileNotFoundError(
            "Shared artifact root was not found. Set FOOTBALL_ARTIFACT_ROOT "
            "to the synchronized 'Innovationday Artifacts' directory."
        )
    required = [
        root / "00-governance" / "checksums.sha256",
        root / "10-master-data",
        root / "20-approved-models",
        root / "30-shared-baselines",
    ]
    if args.require_alfheim:
        required.append(root / "10-master-data" / "alfheim" / "pano")
    if args.require_custom_camera:
        custom = root / "10-master-data" / "custom-cameras"
        if not custom.is_dir() or not any(custom.glob("custom-*/camera.json")):
            required.append(custom / "custom-*" / "camera.json")

    missing = [path for path in required if not path.exists()]
    if missing:
        details = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            f"Innovation Day prerequisites are missing:\n{details}"
        )

    if args.require_alfheim:
        # Alfheim processing reads the v41 profile config from the ignored
        # local window-555 directory.
        shared_config = root / "30-shared-baselines" / "v41" / "alfheim-config"
        local_config = PROJECT_ROOT / "benchmarks" / "alfheim" / "window-555"
        missing_config = [
            local_config / name
            for name in ("goalkeeper-affiliations.json", "pitch-calibration.json")
            if not (local_config / name).is_file()
        ]
        if missing_config:
            details = "\n".join(f"- {path}" for path in missing_config)
            raise FileNotFoundError(
                f"Alfheim processing config is missing:\n{details}\n"
                f"Copy it from {shared_config}."
            )

    model = resolve_detector_model(PROJECT_ROOT)
    print(f"Artifact root: {root}")
    print(f"Detector model: {model}")
    print(f"Local run cache: {PROJECT_ROOT / 'benchmarks'}")
    print("Workspace is ready. Verify shared hashes before a baseline run:")
    print(f'& "{root / "00-governance" / "Verify-Artifacts.ps1"}"')


if __name__ == "__main__":
    main()
