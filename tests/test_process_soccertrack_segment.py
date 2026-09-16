import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "process_soccertrack_segment",
    ROOT / "scripts" / "process-soccertrack-segment.py",
)
assert SPEC and SPEC.loader
PROCESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROCESS)


def test_cache_rebuild_requires_yolo26_detector(tmp_path: Path) -> None:
    cache = tmp_path / "detections.jsonl"
    cache.write_text(
        json.dumps({"model": "models/yolo26n.pt"}) + "\n",
        encoding="utf-8",
    )

    model = PROCESS._cached_detector_model(cache)

    assert model.name == "yolo26n.pt"
    PROCESS._require_yolo26_model(model)
    with pytest.raises(ValueError, match="YOLO26"):
        PROCESS._require_yolo26_model(Path("yolo11n.pt"))
