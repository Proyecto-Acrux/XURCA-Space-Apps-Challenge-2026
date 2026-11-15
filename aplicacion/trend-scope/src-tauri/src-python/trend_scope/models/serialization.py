"""Bounded, strict JSON transport. Never silently turn nonfinite values into null."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import json
import math
from collections.abc import Mapping
from typing import Any

import numpy as np


def to_jsonable(value: Any, *, max_items: int = 100_000) -> Any:
    """Convert dataclasses/NumPy with a shared scalar/container budget before expansion."""
    if isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 1:
        raise ValueError("max_items must be a positive integer")
    remaining = max_items

    def convert(item: Any, depth: int = 0) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 64:
            raise ValueError("JSON item/depth limit exceeded")
        if isinstance(item, np.ndarray):
            if item.size > remaining:
                raise ValueError("Array exceeds JSON item limit; retain it in Python")
            return convert(item.tolist(), depth + 1)
        if isinstance(item, np.generic):
            return convert(item.item(), depth + 1)
        if is_dataclass(item) and not isinstance(item, type):
            return {f.name: convert(getattr(item, f.name), depth + 1) for f in fields(item)}
        if isinstance(item, Mapping):
            if not all(isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            return {key: convert(val, depth + 1) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(val, depth + 1) for val in item]
        if item is None or isinstance(item, (str, bool, int)):
            return item
        if isinstance(item, float) and math.isfinite(item):
            return item
        raise ValueError("Nonfinite or unsupported JSON value")

    return convert(value)


def dumps(value: Any, *, max_items: int = 100_000, max_bytes: int = 2_000_000) -> str:
    """Encode a small transport result; bulk arrays must remain outside IPC."""
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    encoded = json.dumps(to_jsonable(value, max_items=max_items), allow_nan=False, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError("JSON byte limit exceeded")
    return encoded
