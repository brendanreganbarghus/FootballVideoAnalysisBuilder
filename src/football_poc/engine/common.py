from __future__ import annotations

import base64
import importlib
from pathlib import Path
from types import MappingProxyType
from typing import Any, MutableMapping

from football_poc.engine._legacy_chunks import CHUNK_MODULES


def legacy_source() -> str:
    encoded = "".join(
        importlib.import_module(f"football_poc.engine.{module_name}").DATA
        for module_name in CHUNK_MODULES
    )
    return base64.b64decode(encoded.encode("ascii")).decode("utf-8")


def load_legacy_into(target_globals: MutableMapping[str, Any]) -> None:
    """Load the pre-refactor possession API into a thin compatibility shim."""
    source = legacy_source()
    filename = str(Path(__file__).with_name("_legacy_possession_source.py"))
    exec(compile(source, filename, "exec"), target_globals)


def immutable_json(value: Any) -> MappingProxyType[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("stage result must be a JSON object")
    return MappingProxyType(dict(value))
