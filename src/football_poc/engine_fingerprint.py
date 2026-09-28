"""Rules-engine source fingerprint shared with the review Canvas.

The file list and hashing order must stay identical to
``rulesEngineVersionFiles`` and ``sourceVersion`` in
``.github/extensions/football-event-review/shared/``, so that a fingerprint
recorded by the processor matches the one the Canvas computes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

RULES_ENGINE_VERSION_FILES: tuple[str, ...] = (
    "src/football_poc/match_state.py",
    "src/football_poc/player_tracking.py",
    "src/football_poc/possession.py",
    "src/football_poc/possession_cli.py",
    "src/football_poc/shots_on_target.py",
    "src/football_poc/goal_calibration.py",
    "src/football_poc/shot_evidence_adapter.py",
)


def engine_fingerprint(project_root: Path) -> str:
    digest = hashlib.sha256()
    for relative_path in RULES_ENGINE_VERSION_FILES:
        digest.update(relative_path.encode("utf-8"))
        digest.update((Path(project_root) / relative_path).read_bytes())
    return digest.hexdigest()
