"""Analysis Handler: resolves an analysis request into an Analysis Struct.

It validates struct id, targets, parameters and hypothesis against the
declarative catalogue (`analysis_structs.STRUCTS`), applies defaults (only the
backend does), checks the prepared data against the struct requirements and
describes the catalogue for the form and the assistant (`capabilities`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from .algorithm_handler import available_methods
from .analysis_structs import BY_ID, STRUCTS, AnalysisStruct, ParamSpec
from .contracts import (
    BUDGET_EXCEEDED, CADENCE_INCOMPATIBLE, HANDLER_VERSION, INSUFFICIENT_DATA, INVALID_REQUEST,
    IRREGULAR_SERIES, METHOD_NOT_AVAILABLE, UNKNOWN_STRUCT, AnalysisSpec, HandlerError, error_item,
)


# Provisional horizon caps per cadence (decision D-21 pending), in steps of that cadence.
HORIZON_CAPS = {"monthly": 12, "daily": 14, "annual": 5}


@dataclass(frozen=True)
class ResolvedAnalysis:
    spec_id: str
    struct: AnalysisStruct
    params: dict
    hypothesis: Optional[dict]


def unavailable_reason(struct: AnalysisStruct) -> Optional[str]:
    if struct.planned:
        return f"Planificado para la fase {struct.phase}; todavía no está implementado."
    methods = available_methods()
    for step in struct.steps:
        if not step.optional and not any(c.method_id in methods for c in step.candidates):
            return "Falta un método del motor: " + " / ".join(c.method_id for c in step.candidates)
    return None


def _iso(value: Any, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} debe ser una fecha ISO AAAA-MM-DD") from None


def _check_param(name: str, spec: ParamSpec, value: Any):
    kind = spec.type
    if kind in ("float", "int"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} debe ser un número")
        if kind == "int":
            if not float(value).is_integer():
                raise ValueError(f"{name} debe ser un entero")
            value = int(value)
        else:
            value = float(value)
        if spec.minimum is not None and value < spec.minimum or spec.maximum is not None and value > spec.maximum:
            raise ValueError(f"{name} debe estar entre {spec.minimum} y {spec.maximum}")
        return value
    if kind == "str":
        if not isinstance(value, str) or (spec.choices and value not in spec.choices):
            raise ValueError(f"{name} debe ser uno de: {', '.join(spec.choices)}")
        return value
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{name} debe ser verdadero o falso")
        return value
    if kind == "int_list":
        if not isinstance(value, list) or not 1 <= len(value) <= 12:
            raise ValueError(f"{name} debe ser una lista de 1 a 12 enteros")
        items = [_check_param(name, ParamSpec("int", None, spec.minimum, spec.maximum), item) for item in value]
        if len(set(items)) != len(items):
            raise ValueError(f"{name} no admite valores repetidos")
        return items
    if kind == "period":
        if value is None:
            return None
        if not isinstance(value, dict) or set(value) != {"start", "end"}:
            raise ValueError(f"{name} debe tener start y end")
        start, end = _iso(value["start"], f"{name}.start"), _iso(value["end"], f"{name}.end")
        if start >= end:
            raise ValueError(f"{name}.start debe ser anterior a {name}.end")
        return {"start": start.isoformat(), "end": end.isoformat()}
    raise ValueError(f"Tipo de parámetro desconocido: {kind}")


def resolve(spec: AnalysisSpec) -> ResolvedAnalysis:
    """Validate `spec` and return its struct with effective parameters. Raises HandlerError."""
    scope = {"analysis_id": spec.id}
    struct = BY_ID.get(spec.struct)
    if struct is None:
        raise HandlerError(UNKNOWN_STRUCT, f"Análisis desconocido: {spec.struct}. Consultá list_analyses.", scope)
    reason = unavailable_reason(struct)
    if reason:
        raise HandlerError(METHOD_NOT_AVAILABLE, f"El análisis {struct.struct_id} no está disponible. {reason}", scope)
    low, high = struct.targets
    if not low <= len(spec.targets) <= high:
        raise HandlerError(INVALID_REQUEST, f"{struct.struct_id} requiere entre {low} y {high} variables.", scope)
    if len(set(spec.targets)) != len(spec.targets):
        raise HandlerError(INVALID_REQUEST, "targets no admite variables repetidas.", scope)
    unknown = sorted(set(spec.params) - set(struct.params))
    if unknown:
        raise HandlerError(INVALID_REQUEST, f"Parámetros desconocidos para {struct.struct_id}: {', '.join(unknown)}.", scope)
    effective = {}
    for name, definition in struct.params.items():
        value = spec.params.get(name, definition.default)
        try:
            effective[name] = _check_param(name, definition, value) if value is not None else None
        except ValueError as error:
            raise HandlerError(INVALID_REQUEST, str(error), scope) from None
    hypothesis = None
    if spec.hypothesis is not None:
        h = spec.hypothesis
        if h.kind not in struct.hypotheses:
            allowed = ", ".join(struct.hypotheses) or "ninguna"
            raise HandlerError(INVALID_REQUEST, f"{struct.struct_id} no admite hipótesis '{h.kind}' (admite: {allowed}).", scope)
        hypothesis = h.model_dump(exclude_none=True)
        if h.kind == "trend":
            hypothesis.setdefault("direction", "any")
        if h.kind == "forecast_threshold":
            if h.operator is None or h.value is None:
                raise HandlerError(INVALID_REQUEST, "La hipótesis forecast_threshold requiere operator y value.", scope)
            hypothesis.setdefault("at_step", effective.get("horizon") or 1)
            if hypothesis["at_step"] > (effective.get("horizon") or 1):
                raise HandlerError(INVALID_REQUEST, "at_step no puede superar el horizonte pedido.", scope)
        if h.kind == "threshold":
            if h.operator is None or h.value is None:
                raise HandlerError(INVALID_REQUEST, "La hipótesis threshold requiere operator y value.", scope)
            hypothesis.setdefault("statistic", "last")
    return ResolvedAnalysis(spec.id, struct, effective, hypothesis)


def check(struct: AnalysisStruct, params: dict, profile: dict, scope: Optional[dict] = None) -> list:
    """Requirements of the struct against the prepared data. Returns error items (empty = fine)."""
    req = struct.requirements
    scope = scope or {}
    issues = []
    n = profile.get("n", 0)
    minimum = params.get("min_points") or req.min_points
    if n < minimum:
        issues.append(error_item(INSUFFICIENT_DATA, f"Hay {n} observaciones válidas y {struct.struct_id} requiere al "
                                 f"menos {minimum} (valor provisional).", scope))
    cadence = profile.get("cadence")
    if req.cadences and cadence not in req.cadences:
        issues.append(error_item(CADENCE_INCOMPATIBLE, f"La serie tiene cadencia '{cadence}' y {struct.struct_id} "
                                 f"admite: {', '.join(req.cadences)}. Probá con el parámetro aggregate.", scope))
    if req.regular and not profile.get("regular"):
        issues.append(error_item(IRREGULAR_SERIES, "El método exige una serie regular sin faltantes. Usá "
                                 "gap_policy='longest_run' o elegí un período sin huecos.", scope))
    if req.max_points and n > req.max_points:
        issues.append(error_item(BUDGET_EXCEEDED, f"La serie tiene {n} observaciones y el límite es {req.max_points}. "
                                 "Agregá a una cadencia menor (aggregate).", scope))
    horizon = params.get("horizon")
    if horizon:
        cap = min(HORIZON_CAPS.get(cadence, 1), int(n * 0.2))
        if horizon > cap:
            issues.append(error_item(INSUFFICIENT_DATA, f"El horizonte pedido ({horizon}) supera el máximo permitido "
                                     f"para esta serie ({cap}: el menor entre el tope de la cadencia y el 20 % de las "
                                     "observaciones; valores provisionales).", scope))
    return issues


def capabilities() -> dict:
    """Catalogue for the form and the assistant. Availability reflects this installation."""
    methods = available_methods()
    analyses = []
    for struct in STRUCTS:
        reason = unavailable_reason(struct)
        req = struct.requirements
        analyses.append({
            "struct_id": struct.struct_id, "title": struct.title, "kind": struct.kind,
            "description": struct.description, "phase": struct.phase,
            "available": reason is None, "reason": reason,
            "targets": {"min": struct.targets[0], "max": struct.targets[1]},
            "params": {name: {"type": p.type, "default": p.default, "minimum": p.minimum, "maximum": p.maximum,
                              "choices": list(p.choices), "provisional": p.provisional, "description": p.description}
                       for name, p in struct.params.items()},
            "hypotheses": list(struct.hypotheses),
            "methods": sorted({c.method_id for step in struct.steps for c in step.candidates}),
            "methods_available": sorted({c.method_id for step in struct.steps for c in step.candidates
                                         if c.method_id in methods}),
            "requirements": {"cadences": list(req.cadences), "regular": req.regular, "min_points": req.min_points,
                             "max_points": req.max_points, "variable_families": list(req.variable_families)},
            "charts": list(struct.charts), "limitations": list(struct.limitations),
        })
    return {"schema": "earth-detective/analyses", "schema_version": 1, "handler_version": HANDLER_VERSION,
            "analyses": analyses, "methods_installed": sorted(methods)}
