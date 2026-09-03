from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO
from urllib.parse import parse_qs, urlparse

from football_poc.alfheim_segments import (
    alfheim_source_info,
    plan_alfheim_segment,
    resolve_alfheim_pano,
)


class RangeRequestHandler(SimpleHTTPRequestHandler):
    range_to_send: tuple[int, int] | None = None
    analysis_processes: dict[str, subprocess.Popen[bytes]] = {}

    def do_GET(self) -> None:
        request = urlparse(self.path)
        if request.path == "/api/alfheim/info":
            try:
                self._send_json(
                    200,
                    alfheim_source_info(resolve_alfheim_pano(Path.cwd())),
                )
            except (FileNotFoundError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if request.path == "/api/alfheim/segments":
            try:
                self._send_json(200, {"segments": self._prepared_segments()})
            except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if request.path == "/api/alfheim/status":
            try:
                cache_key = parse_qs(request.query).get("cache_key", [""])[0]
                if not re.fullmatch(r"segment-\d{4}-\d{3}", cache_key):
                    raise ValueError("Invalid segment cache key")
                self._send_json(200, self._segment_status(cache_key))
            except (FileNotFoundError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
            return
        super().do_GET()

    def do_POST(self) -> None:
        request_path = urlparse(self.path).path
        if request_path == "/api/alfheim/analyze":
            self._start_segment_analysis()
            return
        if request_path != "/api/alfheim/segment":
            self.send_error(404)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 4096:
                raise ValueError("Request body must contain a small JSON object")
            payload = json.loads(self.rfile.read(content_length))
            pano = resolve_alfheim_pano(Path.cwd())
            plan = plan_alfheim_segment(
                pano,
                start_seconds=float(payload["start_seconds"]),
                duration_seconds=float(payload["duration_seconds"]),
            )
            output = (
                Path.cwd()
                / "benchmarks"
                / "alfheim"
                / "generated"
                / (
                    f"segment-{plan.first_segment:04d}-"
                    f"{plan.segment_count:03d}"
                )
            )
            playable = output / "alfheim-window-playable.mp4"
            labels = output / "ball-ground-truth.csv"
            if not playable.is_file() or not labels.is_file():
                subprocess.run(
                    [
                        sys.executable,
                        str(Path.cwd() / "scripts" / "prepare-alfheim-window.py"),
                        "--pano",
                        str(pano),
                        "--start-segment",
                        str(plan.first_segment),
                        "--segment-count",
                        str(plan.segment_count),
                        "--output",
                        str(output),
                    ],
                    cwd=Path.cwd(),
                    check=True,
                )
            relative = output.relative_to(Path.cwd()).as_posix()
            self._send_json(
                200,
                {
                    **plan.to_dict(),
                    "video_url": f"/{relative}/alfheim-window-playable.mp4",
                    "labels_url": f"/{relative}/ball-ground-truth.csv",
                    "cache_key": output.name,
                },
            )
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            subprocess.CalledProcessError,
        ) as error:
            self._send_json(400, {"error": str(error)})

    def _start_segment_analysis(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 4096:
                raise ValueError("Request body must contain a small JSON object")
            payload = json.loads(self.rfile.read(content_length))
            cache_key = str(payload["cache_key"])
            if not re.fullmatch(r"segment-\d{4}-\d{3}", cache_key):
                raise ValueError("Invalid segment cache key")
            segment = (
                Path.cwd()
                / "benchmarks"
                / "alfheim"
                / "generated"
                / cache_key
            )
            if not (segment / "manifest.json").is_file():
                raise FileNotFoundError(f"Prepared segment not found: {cache_key}")
            current = self.analysis_processes.get(cache_key)
            if current is not None and current.poll() is None:
                self._send_json(202, {"state": "processing"})
                return
            log_path = segment / "analysis.log"
            log = log_path.open("ab")
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path.cwd() / "scripts" / "process-alfheim-segment.py"),
                    str(segment),
                ],
                cwd=Path.cwd(),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            log.close()
            self.analysis_processes[cache_key] = process
            self._send_json(202, {"state": "processing", "pid": process.pid})
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            self._send_json(400, {"error": str(error)})

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _segment_status(self, cache_key: str) -> dict[str, object]:
        root = Path.cwd() / "benchmarks" / "alfheim" / "generated" / cache_key
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Prepared segment not found: {cache_key}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        cache_path = root / "analytics-cache" / "detections.jsonl"
        processed_frames = 0
        expected_frames = 0
        if cache_path.is_file():
            with cache_path.open(encoding="utf-8") as cache:
                metadata = json.loads(cache.readline())
                processed_frames = sum(1 for line in cache if line.strip())
            frame_count = int(manifest["end_frame"]) - int(manifest["start_frame"])
            expected_frames = (
                frame_count + int(metadata["stride"]) - 1
            ) // int(metadata["stride"])
        events = root / "analytics-data" / "predicted-events.json"
        tracking = root / "analytics-data" / "tracking-verification.webm"
        analysis_status_path = root / "analysis-status.json"
        analysis_status = (
            json.loads(analysis_status_path.read_text(encoding="utf-8"))
            if analysis_status_path.is_file()
            else {}
        )
        relative = root.relative_to(Path.cwd()).as_posix()
        if events.is_file():
            state = "ready"
        elif analysis_status.get("stage") == "failed":
            state = "failed"
        elif analysis_status and expected_frames and processed_frames >= expected_frames:
            state = "building"
        elif expected_frames and processed_frames >= expected_frames:
            state = "detections_ready"
        elif processed_frames:
            state = "processing"
        else:
            state = "prepared"
        return {
            "cache_key": cache_key,
            "state": state,
            "processed_frames": processed_frames,
            "expected_frames": expected_frames,
            "stage": analysis_status.get("stage"),
            "message": analysis_status.get("message"),
            "events_url": (
                f"/{relative}/analytics-data/predicted-events.json"
                if events.is_file()
                else None
            ),
            "tracking_url": (
                f"/{relative}/analytics-data/tracking-verification.webm"
                if tracking.is_file()
                else None
            ),
        }

    def _prepared_segments(self) -> list[dict[str, object]]:
        workspace = Path.cwd()
        items: list[dict[str, object]] = []
        baseline = workspace / "benchmarks" / "alfheim" / "window-555"
        baseline_video = baseline / "alfheim-window-playable.mp4"
        baseline_labels = baseline / "ball-ground-truth.csv"
        baseline_events = baseline / "analytics-data" / "predicted-events.json"
        if baseline_video.is_file() and baseline_labels.is_file():
            baseline_relative = baseline.relative_to(workspace).as_posix()
            baseline_ready = baseline_events.is_file()
            items.append(
                {
                    "cache_key": "alfheim-window-555",
                    "source_start_seconds": 555 * 3,
                    "duration_seconds": 60,
                    "state": "ready" if baseline_ready else "prepared",
                    "protected": False,
                    "video_url": (
                        f"/{baseline_relative}/alfheim-window-playable.mp4"
                    ),
                    "labels_url": f"/{baseline_relative}/ball-ground-truth.csv",
                }
            )

        generated = workspace / "benchmarks" / "alfheim" / "generated"
        if not generated.is_dir():
            return items
        for root in sorted(generated.iterdir()):
            match = re.fullmatch(r"segment-(\d{4})-(\d{3})", root.name)
            if not match or not root.is_dir():
                continue
            video = root / "alfheim-window-playable.mp4"
            labels = root / "ball-ground-truth.csv"
            if not video.is_file() or not labels.is_file():
                continue
            first_segment, segment_count = map(int, match.groups())
            status = self._segment_status(root.name)
            relative = root.relative_to(workspace).as_posix()
            items.append(
                {
                    "cache_key": root.name,
                    "source_start_seconds": first_segment * 3,
                    "duration_seconds": segment_count * 3,
                    "state": status["state"],
                    "protected": root.name
                    in {
                        "segment-0575-020",
                        "segment-0595-020",
                        "segment-0615-020",
                    },
                    "video_url": f"/{relative}/alfheim-window-playable.mp4",
                    "labels_url": f"/{relative}/ball-ground-truth.csv",
                }
            )
        return items

    def send_head(self) -> BinaryIO | None:
        path = Path(self.translate_path(self.path))
        range_header = self.headers.get("Range")
        if not range_header or not path.is_file():
            self.range_to_send = None
            return super().send_head()

        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match:
            self.send_error(416, "Only a single byte range is supported")
            return None
        size = path.stat().st_size
        start_text, end_text = match.groups()
        if not start_text:
            length = int(end_text)
            start = max(0, size - length)
            end = size - 1
        else:
            start = int(start_text)
            end = min(int(end_text) if end_text else size - 1, size - 1)
        if start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        file = path.open("rb")
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", self.date_time_string(path.stat().st_mtime))
        self.end_headers()
        self.range_to_send = (start, end)
        return file

    def copyfile(self, source: BinaryIO, outputfile: BinaryIO) -> None:
        if self.range_to_send is None:
            shutil.copyfileobj(source, outputfile)
            return
        start, end = self.range_to_send
        source.seek(start)
        remaining = end - start + 1
        while remaining:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            try:
                outputfile.write(chunk)
            except (
                BrokenPipeError,
                ConnectionAbortedError,
                ConnectionResetError,
            ):
                break
            remaining -= len(chunk)

    def end_headers(self) -> None:
        if "Range" not in self.headers:
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve local POC files with browser video range requests."
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--directory", type=Path, default=Path.cwd())
    args = parser.parse_args()
    os.chdir(args.directory)
    server = ThreadingHTTPServer((args.bind, args.port), RangeRequestHandler)
    print(f"Serving {args.directory.resolve()} on http://{args.bind}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
