import json
from pathlib import Path

import cv2
import numpy as np

from football_poc.demo import build_demo, prepare_demo_video


def test_builds_demo_from_benchmark_artifacts(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.json"
    evaluation = tmp_path / "evaluation.json"
    simulation = tmp_path / "simulation.json"
    events = tmp_path / "events.json"
    aggregate.write_text(
        json.dumps(
            {
                "micro_average": {
                    "pass": {
                        "precision": 0.5,
                        "recall": 0.25,
                        "true_positives": 1,
                        "predicted": 2,
                        "ground_truth": 4,
                    },
                    "shot": {
                        "precision": 1.0,
                        "recall": 1.0,
                        "true_positives": 1,
                        "predicted": 1,
                        "ground_truth": 1,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    evaluation.write_text("{}", encoding="utf-8")
    simulation.write_text(
        json.dumps(
            {
                "validation": {"duplicates_suppressed": 1},
                "chunks": [
                    {
                        "index": 0,
                        "start_seconds": 0,
                        "end_seconds": 20,
                        "new_events": 1,
                        "duplicates_suppressed": 0,
                        "queue_wait_seconds": 0,
                        "state_out": {
                            "accepted_event_count": 1,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events.write_text(
        json.dumps(
            [
                {
                    "event_type": "pass_candidate",
                    "clip_seconds": 10,
                    "team": "blue",
                    "confidence": 0.8,
                }
            ]
        ),
        encoding="utf-8",
    )

    output = build_demo(
        aggregate_path=aggregate,
        evaluation_path=evaluation,
        simulation_path=simulation,
        events_path=events,
        output=tmp_path / "index.html",
    )
    html = output.read_text(encoding="utf-8")

    assert "AI Football Analytics POC" in html
    assert "50.0%" in html
    assert "pass_candidate" in html
    assert 'id="live-blue-passes"' in html
    assert 'id="live-white-passes"' in html
    assert "const events =" in html
    assert "event.clip_seconds <= seconds" in html
    assert "updateLiveStats" in html
    assert 'src="tracking-verification.webm"' in html
    assert "Primary benchmark minute" in html
    assert "Video could not be loaded" in html


def test_prepares_browser_compatible_demo_video(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    writer = cv2.VideoWriter(
        str(source),
        cv2.VideoWriter_fourcc(*"mp4v"),
        5,
        (64, 32),
    )
    assert writer.isOpened()
    for value in (0, 127, 255):
        writer.write(np.full((32, 64, 3), value, dtype=np.uint8))
    writer.release()

    output = prepare_demo_video(
        source=source,
        output=tmp_path / "demo.webm",
        maximum_width=32,
    )
    capture = cv2.VideoCapture(str(output))
    fourcc = int(capture.get(cv2.CAP_PROP_FOURCC))

    assert capture.isOpened()
    assert "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4)) == "VP80"
    assert int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) == 32
    assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) == 3
