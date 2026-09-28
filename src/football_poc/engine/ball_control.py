from __future__ import annotations

from football_poc.engine.common import *



def run(results_dir: Path, settings: BallControlSettings = BallControlSettings()) -> dict[str, Any]:
    possession = read_stage_json(results_dir / "possession.json")
    controls = [
        {
            "frame": item["source_frame"],
            "seconds": item["clip_seconds"],
            "team": item["team"],
            "track": item["player_track_id"],
            "control_ratio": item["control_ratio"],
        }
        for item in possession.get("observations", [])
    ]
    return {
        "stage": "ball_control_touch",
        "count": len(controls),
        "sample": controls[: settings.sample_limit],
        "teams": sorted({item["team"] for item in controls}),
        "tracks": sorted({item["track"] for item in controls}),
    }
