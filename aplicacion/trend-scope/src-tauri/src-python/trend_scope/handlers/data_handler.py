"""Data Handler: single public entry point, request.json -> response.json.

Sequence (docs/plan-maestro/23_ARQUITECTURA_HANDLERS.md):
validate -> resolve structs -> acquire series (reusing the existing connectors)
-> prepare data -> run the algorithms -> decide -> assemble the response.
Failures never escape as exceptions: they come back as typed errors inside the
response, and independent analyses keep going (status "partial").
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import ValidationError

from ..models.serialization import to_jsonable
from ..models.stats.multiple_testing import fdr_bh
from ..services import acquisition, evidence
from . import algorithm_handler, analysis_handler, decision, preparation, spatial
from .analysis_structs import BY_ID
from .contracts import (
    HANDLER_VERSION, INTERNAL, INVALID_REQUEST, RESPONSE_SCHEMA, SOURCE_ERROR, UNSUPPORTED_SPATIAL,
    AnalysisSpec, HandlerError, RequestDocument, error_item, request_hash,
)

DIGEST_LIMIT = 6000
MAX_ITEMS = 5_000_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _response(request_id, req_hash, status, series, analyses, errors, warnings=None, methods=None) -> dict:
    document = {
        "schema": RESPONSE_SCHEMA, "schema_version": 1, "request_id": request_id, "request_hash": req_hash,
        "status": status, "generated_at": _now(),
        "engine": {"handler_version": HANDLER_VERSION, "methods": methods or {}},
        "series": series, "analyses": analyses, "warnings": warnings or [], "errors": errors,
    }
    document["assistant_digest"] = _digest(document)
    return document


def _failed(raw: Any, errors: list, req_hash: Optional[str] = None) -> dict:
    request_id = raw.get("request_id") if isinstance(raw, dict) and isinstance(raw.get("request_id"), str) else None
    return _response(request_id, req_hash, "failed", [], [], errors)


def _validation_errors(error: ValidationError) -> list:
    items = []
    for detail in error.errors()[:8]:
        place = ".".join(str(part) for part in detail.get("loc", ()))
        items.append(error_item(INVALID_REQUEST, f"{place}: {detail.get('msg', 'valor inválido')}", {"field": place}))
    return items


def _acquire(investigation: dict, ids: list) -> tuple:
    """Series by source id. Falls back to one source at a time so a failure stays isolated."""
    def fetch(inv: dict) -> list:
        return evidence.with_evidence(acquisition.acquire(inv))

    series, errors = {}, {}
    try:
        for source_id, item in zip(ids, fetch(investigation)):
            series[source_id] = item
        return series, errors
    except ValueError:
        pass
    except Exception as error:  # connectors may fail in unforeseen ways
        errors["*"] = f"{type(error).__name__}: {str(error)[:200]}"
    sources = {item["id"]: item for item in investigation["sources"]}
    for source_id in ids:
        try:
            series[source_id] = fetch({**investigation, "sources": [sources[source_id]]})[0]
        except ValueError as error:
            errors[source_id] = str(error)
        except Exception as error:
            errors[source_id] = f"{type(error).__name__}: {str(error)[:200]}"
    return series, errors


def _analyze_one(spec, resolved, series: Optional[dict], source: dict, source_error: Optional[str], options) -> dict:
    struct = resolved.struct
    scope = {"analysis_id": spec.id}
    block = {"id": spec.id, "struct": struct.struct_id, "kind": struct.kind, "status": "failed",
             "targets": list(spec.targets), "parameters_effective": resolved.params, "data_profile": None,
             "transformations": [], "steps": [], "findings": [], "verdict": None, "forecast": None,
             "charts": [], "warnings": [], "errors": []}
    if series is None:
        block["errors"].append(error_item(SOURCE_ERROR, source_error or "La fuente no devolvió datos.", scope))
        return block
    try:
        prepared = preparation.prepare(series, source, struct, resolved.params, scope)
    except HandlerError as error:
        block["errors"].append(error.to_dict())
        return block
    block["data_profile"] = prepared.profile
    block["transformations"] = prepared.transformations
    issues = list(prepared.issues) + analysis_handler.check(struct, resolved.params, prepared.profile, scope)
    if issues:
        block["errors"].extend(issues)
        return block

    steps = algorithm_handler.execute(struct, prepared, resolved.params, spec.id,
                                      max_points_per_array=options.max_points_per_array)
    outcome = decision.build(struct, resolved.params, steps, prepared, series, source, resolved.hypothesis)
    block["findings"], block["verdict"], block["charts"] = outcome["findings"], outcome["verdict"], outcome["charts"]
    block["forecast"] = outcome.get("forecast")
    if options.include_steps:
        block["steps"] = [item.to_dict() for item in steps]
    required_failed = [s for s in steps if not s.optional and s.status != "completed"]
    for item in required_failed:
        block["errors"].append(error_item(item.error_code or INTERNAL, f"{item.label}: {item.reason}",
                                          {**scope, "step": item.step_id}))
    for item in steps:
        block["warnings"].extend({"step": item.step_id, "message": text} for text in item.warnings)
    completed = [s for s in steps if s.status == "completed" and not s.optional]
    if not required_failed:
        block["status"] = "completed"
    elif completed:
        block["status"] = "partial"
    return block


def _analyze_pattern(spec, resolved, sample_ids: list, series_by_id: dict, sources: dict, source_errors: dict, request) -> dict:
    """Trend on every sample point + false discovery rate control across the points."""
    trend = BY_ID["trend_significance"]
    params = {name: resolved.params[name] for name in trend.params}
    options = request.options.model_copy(update={"include_steps": False})
    blocks = []
    for index, sample_id in enumerate(sample_ids, 1):
        sub = AnalysisSpec(id=f"{spec.id}.{index}", struct="trend_significance", targets=[sample_id])
        sub_resolved = analysis_handler.ResolvedAnalysis(sub.id, trend, params, None)
        blocks.append(_analyze_one(sub, sub_resolved, series_by_id.get(sample_id), sources[sample_id],
                                   source_errors.get(sample_id) or source_errors.get("*"), options))
    trends = [f for b in blocks for f in b["findings"] if f["type"] == "trend" and f.get("p_value") is not None]
    alpha = resolved.params["alpha"]
    findings = []
    if trends:
        result = fdr_bh([f["p_value"] for f in trends], alpha=alpha)
        for finding, q, rejected in zip(trends, result["q_values"], result["rejected"]):
            finding["q_value"], finding["significant_fdr"] = float(q), bool(rejected)
        slopes = [f["how_much"]["per_decade"] for f in trends]
        first = trends[0]
        findings.append({
            "type": "spatial_pattern", "what": first["what"],
            "where": {"mode": "area_sample", "n_points": len(sample_ids), "coordinates": None,
                      "label": "Muestra de puntos dentro del polígono (no es un promedio zonal)"},
            "when": first["when"],
            "how_much": {"n_points": len(sample_ids), "n_analyzed": len(trends),
                         "n_significant_raw": sum(1 for f in trends if f["significant"]),
                         "n_significant_fdr": int(result["rejected"].sum()), "alpha": alpha,
                         "mean_per_decade": sum(slopes) / len(slopes), "unit": first["how_much"]["unit"],
                         "n_positive": sum(1 for v in slopes if v > 0), "n_negative": sum(1 for v in slopes if v < 0)},
            "significant": None, "p_value": None, "alpha": alpha, "test": "benjamini_hochberg_fdr",
            "conclusiveness": "descriptive", "statement_key": "spatial.pattern",
            "notes": ["Muestra de puntos: no representa el promedio ni la totalidad del área."],
            "limitations": ["Los puntos vecinos no son independientes: el control de falsos descubrimientos es aproximado.",
                            "La resolución de la fuente puede ser mayor que el espaciado de la muestra."]})
    findings.extend(trends)
    statuses = [b["status"] for b in blocks]
    status = ("completed" if all(s == "completed" for s in statuses)
              else "partial" if any(s in ("completed", "partial") for s in statuses) else "failed")
    return {"id": spec.id, "struct": "spatial_pattern", "kind": resolved.struct.kind, "status": status,
            "targets": list(spec.targets), "parameters_effective": resolved.params,
            "data_profile": next((b["data_profile"] for b in blocks if b["data_profile"]), None),
            "transformations": [], "steps": [], "findings": findings, "verdict": None, "forecast": None,
            "charts": [{"kind": "map_points", "series_refs": list(sample_ids)}],
            "warnings": [w for b in blocks for w in b["warnings"][:1]],
            "errors": [e for b in blocks for e in b["errors"]]}


def _digest(document: dict) -> dict:
    """Compact, array-free summary for the assistant."""
    def build(level: int) -> dict:
        analyses = []
        for block in document["analyses"]:
            findings = []
            for finding in block.get("findings", []):
                if level >= 2:
                    keep = {k: finding.get(k) for k in ("type", "how_much", "significant", "p_value", "statement_key")}
                elif level == 1:
                    keep = {k: v for k, v in finding.items() if k != "limitations"}
                else:
                    keep = finding
                findings.append(keep)
            analyses.append({"id": block["id"], "struct": block["struct"], "status": block["status"],
                             "findings": findings, "verdict": block.get("verdict"),
                             "warnings": [w["message"] for w in block.get("warnings", [])[:3]],
                             "errors": [e["message"] for e in block.get("errors", [])]})
        sources = [{k: s.get(k) for k in ("id", "provider", "product", "unit", "url", "retrievedAt", "coordinates")}
                   for s in document["series"]]
        return {"request_hash": document.get("request_hash"), "status": document["status"],
                "analyses": analyses, "sources": sources, "errors": [e["message"] for e in document["errors"]],
                "truncated": level >= 2}

    for level in (0, 1, 2):
        digest = build(level)
        if len(json.dumps(to_jsonable(digest, max_items=MAX_ITEMS), allow_nan=False)) <= DIGEST_LIMIT:
            return digest
    return digest


def _run(raw: dict) -> dict:
    try:
        request = RequestDocument.model_validate(raw)
    except ValidationError as error:
        return _failed(raw, _validation_errors(error))
    digest_hash = request_hash(request)
    investigation = copy.deepcopy(request.investigation)
    sources = {item["id"]: item for item in (investigation.get("sources") or [])
               if isinstance(item, dict) and isinstance(item.get("id"), str)}

    errors, resolved = [], []
    for spec in request.analyses:
        try:
            item = analysis_handler.resolve(spec)
        except HandlerError as error:
            errors.append(error.to_dict())
            continue
        missing = [target for target in spec.targets if target not in sources]
        if missing:
            errors.append(error_item(INVALID_REQUEST, "Variables inexistentes en investigation.sources: "
                                     + ", ".join(missing), {"analysis_id": spec.id}))
            continue
        resolved.append((spec, item))
    expansions: dict = {}
    for spec, item in resolved:
        if item.struct.struct_id == "spatial_pattern":
            try:
                new_sources, ids = spatial.expand(spec, item.params, sources, investigation)
            except HandlerError as error:
                errors.append(error.to_dict())
                continue
            sources.update(new_sources)
            expansions[spec.id] = ids
    if errors:
        return _failed(raw, errors, digest_hash)

    needed = list(dict.fromkeys(target for spec, _ in resolved for target in (expansions.get(spec.id) or spec.targets)))
    filtered = {**investigation, "methods": [], "sources": [sources[target] for target in needed]}
    series_by_id, source_errors = _acquire(filtered, needed)

    blocks, global_errors = [], []
    for spec, item in resolved:
        target = spec.targets[0]
        series = series_by_id.get(target)
        message = source_errors.get(target) or source_errors.get("*")
        try:
            if spec.id in expansions:
                block = _analyze_pattern(spec, item, expansions[spec.id], series_by_id, sources, source_errors, request)
            else:
                block = _analyze_one(spec, item, series, sources[target], message, request.options)
        except Exception as error:  # an analysis must never take down the response
            block = {"id": spec.id, "struct": item.struct.struct_id, "kind": item.struct.kind, "status": "failed",
                     "targets": list(spec.targets), "parameters_effective": item.params, "data_profile": None,
                     "transformations": [], "steps": [], "findings": [], "verdict": None, "forecast": None,
                     "charts": [], "warnings": [],
                     "errors": [error_item(INTERNAL, f"Error inesperado ({type(error).__name__}): {str(error)[:200]}",
                                           {"analysis_id": spec.id})]}
        blocks.append(block)
    for target, message in source_errors.items():
        if target != "*":
            global_errors.append(error_item(SOURCE_ERROR, message, {"source_id": target}))

    statuses = [block["status"] for block in blocks]
    if all(status == "completed" for status in statuses):
        status = "completed"
    elif any(status in ("completed", "partial") for status in statuses):
        status = "partial"
    else:
        status = "failed"
    if status == "partial" and not request.options.allow_partial:
        status = "failed"

    used = {step["method_id"]: algorithm_handler.method_versions().get(step["method_id"])
            for block in blocks for step in block["steps"] if step.get("method_id")}
    series_out = [series_by_id[target] for target in needed if target in series_by_id]
    return _response(request.request_id, digest_hash, status, series_out, blocks, global_errors, methods=used)


def run(raw: dict) -> dict:
    """request.json (dict) -> response.json (dict). Never raises."""
    try:
        return to_jsonable(_run(raw), max_items=MAX_ITEMS)
    except Exception as error:
        return _failed(raw, [error_item(INTERNAL, f"Error inesperado ({type(error).__name__}): {str(error)[:200]}")])
