"""Public JSON contracts of the analysis handlers (request.json / response.json).

These models validate what the frontend or the assistant sends. Strings that
name things (struct ids, source ids) are checked against registered values by
the analysis handler; nothing here is ever executed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

REQUEST_SCHEMA = "earth-detective/request"
RESPONSE_SCHEMA = "earth-detective/response"
HANDLER_VERSION = "1.0.0"

# Error codes (response.errors[].code).
INVALID_REQUEST = "INVALID_REQUEST"
UNKNOWN_STRUCT = "UNKNOWN_STRUCT"
SOURCE_ERROR = "SOURCE_ERROR"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
IRREGULAR_SERIES = "IRREGULAR_SERIES"
CADENCE_INCOMPATIBLE = "CADENCE_INCOMPATIBLE"
UNIT_INCOMPATIBLE = "UNIT_INCOMPATIBLE"
METHOD_NOT_AVAILABLE = "METHOD_NOT_AVAILABLE"
UNSUPPORTED_SPATIAL = "UNSUPPORTED_SPATIAL"
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
INTERNAL = "INTERNAL"


class HandlerError(Exception):
    """A typed, user-facing failure. Never carries tracebacks or secrets."""

    def __init__(self, code: str, message: str, scope: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.scope = scope or {}

    def to_dict(self) -> dict:
        return error_item(self.code, self.message, self.scope)


def error_item(code: str, message: str, scope: Optional[dict] = None) -> dict:
    return {"code": code, "message": message, "scope": scope or {}}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Hypothesis(_Strict):
    kind: Literal["trend", "change_point", "threshold", "relationship", "forecast_threshold"]
    direction: Optional[Literal["increasing", "decreasing", "any"]] = None
    min_rate: Optional[float] = Field(default=None, ge=0)
    operator: Optional[Literal[">", "<", ">=", "<="]] = None
    value: Optional[float] = None
    statistic: Optional[Literal["last", "max", "min", "mean"]] = None
    sign: Optional[Literal["positive", "negative", "any"]] = None
    lags: Optional[list[int]] = Field(default=None, max_length=12)
    window: Optional[dict[str, str]] = None
    at_step: Optional[int] = Field(default=None, ge=1)


class AnalysisSpec(_Strict):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    struct: str = Field(min_length=1, max_length=64)
    targets: list[str] = Field(min_length=1, max_length=10)
    roles: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    hypothesis: Optional[Hypothesis] = None


class Options(_Strict):
    include_steps: bool = True
    max_points_per_array: int = Field(default=5000, ge=50, le=100000)
    allow_partial: bool = True


class RequestDocument(_Strict):
    doc_schema: Literal["earth-detective/request"] = Field(default=REQUEST_SCHEMA, alias="schema")
    schema_version: Literal[1] = 1
    request_id: Optional[str] = Field(default=None, max_length=80)
    origin: Literal["manual", "assistant"] = "manual"
    language: Literal["es", "en"] = "es"
    investigation: dict[str, Any]
    analyses: list[AnalysisSpec] = Field(min_length=1, max_length=10)
    options: Options = Field(default_factory=Options)


class ResponseDocument(_Strict):
    """Top-level shape of response.json; nested blocks are documented in docs/plan-maestro/23."""

    doc_schema: Literal["earth-detective/response"] = Field(default=RESPONSE_SCHEMA, alias="schema")
    schema_version: Literal[1] = 1
    request_id: Optional[str] = None
    request_hash: Optional[str] = None
    status: Literal["completed", "partial", "failed"]
    generated_at: str
    engine: dict[str, Any]
    series: list[dict[str, Any]]
    analyses: list[dict[str, Any]]
    assistant_digest: dict[str, Any]
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]


def _scrub(investigation: dict) -> dict:
    """Drop display-only fields so equal scientific requests hash equally."""
    clean = copy.deepcopy(investigation)
    for key in ("title", "objective", "description"):
        clean.pop(key, None)
    for feature in (clean.get("geography", {}).get("selection", {}) or {}).get("features", []) or []:
        if isinstance(feature, dict) and isinstance(feature.get("properties"), dict):
            feature["properties"].pop("name", None)
    return clean


def request_hash(request: RequestDocument) -> str:
    """sha256 of the canonical request without id, origin, language and display names."""
    payload = request.model_dump(by_alias=True, mode="json")
    for key in ("request_id", "origin", "language"):
        payload.pop(key, None)
    payload["investigation"] = _scrub(payload["investigation"])
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def export_schemas() -> dict:
    """JSON Schemas for the frontend and the assistant (generated on demand)."""
    return {
        "request": RequestDocument.model_json_schema(by_alias=True),
        "response": ResponseDocument.model_json_schema(by_alias=True),
    }
