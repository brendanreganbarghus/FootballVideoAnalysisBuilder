from __future__ import annotations

from football_poc.engine.common import load_legacy_into

load_legacy_into(globals())

__all__ = [name for name in globals() if not name.startswith("__")]
