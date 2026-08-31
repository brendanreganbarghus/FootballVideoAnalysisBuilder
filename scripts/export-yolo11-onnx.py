from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a YOLO checkpoint to an optimized ONNX model."
    )
    parser.add_argument("model", type=Path)
    parser.add_argument("--image-size", type=int, default=1280)
    parser.add_argument("--half", action="store_true")
    parser.add_argument("--dynamic", action="store_true")
    parser.add_argument("--simplify", action="store_true")
    args = parser.parse_args()
    if not args.model.is_file():
        raise FileNotFoundError(f"Model checkpoint does not exist: {args.model}")
    model = YOLO(str(args.model))
    exported = model.export(
        format="onnx",
        imgsz=args.image_size,
        half=args.half,
        dynamic=args.dynamic,
        simplify=args.simplify,
    )
    print(f"ONNX model written to {Path(exported).resolve()}")


if __name__ == "__main__":
    main()
