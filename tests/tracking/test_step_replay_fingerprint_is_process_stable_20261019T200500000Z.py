"""Rule: a ball-step code fingerprint is identical in every process.

Step replay reuses a saved step result only when the step's code fingerprint
matches. Python randomises set order per process (hash seed), so the
fingerprint must not depend on it; otherwise unchanged code reruns every time.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src"
PROBE = (
    "import football_poc.ball as b;"
    "print(b._step_code_fingerprint(b._add_motion_supported_points))"
)


def _fingerprint(seed: str) -> str:
    environment = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(SOURCE)}
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_step_code_fingerprint_ignores_process_hash_seed():
    fingerprints = {_fingerprint(seed) for seed in ("1", "2", "3")}
    assert len(fingerprints) == 1
