"""Algorithm Handler: choose and run the registered methods of an analysis struct.

This module contains no formulas. It walks the steps of a struct in order, picks
the first candidate whose named condition holds, and runs it through the
scientific engine (`models.execution.analyze`). A failing step never aborts the
analysis: it is reported and, if other steps depend on it, they are skipped.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Optional

import numpy as np

from ..models.catalog_registry import catalog_registry
from ..models.contracts import AnalysisRequest as MethodRequest, VariableData
from ..models.execution import AnalysisCancelled, ExecutionContext, analyze
from .analysis_structs import AnalysisStruct, Candidate, Step
from .contracts import INSUFFICIENT_DATA, INTERNAL, METHOD_NOT_AVAILABLE

PAIR_BUDGET = 2_000_000

_REGISTRY = None


def registry():
    """Method registry, built once per process."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = catalog_registry(include_optional=True)
    return _REGISTRY


def available_methods() -> set:
    return {spec.method_id for spec in registry().describe()}


def method_versions() -> dict:
    return {spec.method_id: spec.version for spec in registry().describe()}


@dataclass
class StepResult:
    step_id: str
    label: str
    status: str                       # completed | failed | skipped
    method_id: Optional[str] = None
    method_version: Optional[str] = None
    parameters: dict = field(default_factory=dict)
    payload: Any = None               # raw engine payload (not serialized)
    outputs: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    selected_because: str = ""
    reason: str = ""
    error_code: Optional[str] = None
    optional: bool = False
    loop_key: Any = None
    uncertainty: str = "not_estimated"

    def to_dict(self) -> dict:
        item = {"step": self.step_id, "label": self.label, "method_id": self.method_id,
                "method_version": self.method_version, "status": self.status,
                "parameters": self.parameters, "outputs": self.outputs, "units": self.units,
                "warnings": self.warnings, "selected_because": self.selected_because,
                "uncertainty": self.uncertainty}
        if self.reason:
            item["reason"] = self.reason
        if self.loop_key is not None:
            item["loop_key"] = self.loop_key
        return item


# ----------------------------------------------------------------------------- conditions

def _condition(name: str, profile: dict, prepared, params: dict, available: set):
    n = profile.get("n", 0)
    if name == "always":
        return True, ""
    if name == "monthly_cycle":
        ok = (profile.get("cadence") == "monthly" and prepared.meta.get("groups") is not None
              and prepared.derived.get("baseline") is not None and profile.get("n_years", 0) >= 2)
        return ok, "serie mensual con período de referencia" if ok else "requiere serie mensual de al menos 2 años"
    if name == "seasonal":
        ok = profile.get("cadence") == "monthly" and prepared.meta.get("groups") is not None \
            and profile.get("n_years", 0) >= 2
        return ok, "serie mensual con ciclo estacional" if ok else "no hay ciclo estacional observable"
    if name == "not_seasonal":
        ok, _ = _condition("seasonal", profile, prepared, params, available)
        return (not ok), ""
    if name == "autocorrelated":
        r1, threshold = profile.get("lag1_autocorrelation"), profile.get("lag1_threshold")
        ok = bool(profile.get("regular") and 4 <= n <= 2000 and r1 is not None and threshold is not None
                  and abs(r1) > threshold)
        return ok, (f"|r1|={abs(r1):.2f} supera {threshold:.2f}" if ok else "sin autocorrelación de lag 1 detectable")
    if name == "pairs_ok":
        ok = n * (n - 1) // 2 <= PAIR_BUDGET
        return ok, "" if ok else f"n={n} excede el presupuesto de {PAIR_BUDGET} pares; agregá a una cadencia menor"
    if name.startswith("param:"):
        key, _, wanted = name[6:].partition("=")
        ok = str(params.get(key)) == wanted
        return ok, ""
    raise ValueError(f"Condición desconocida: {name}")


def _resolve_token(value, prepared, params: dict, extra: dict):
    if isinstance(value, str):
        if value == "@groups":
            return prepared.meta["groups"]
        if value == "@scale":
            return extra["scale"]
        if value.startswith("$"):
            key = value[1:]
            for source in (extra, prepared.derived, params):
                if key in source and source[key] is not None:
                    return source[key]
            raise ValueError(f"Falta el parámetro {key}")
    return value


def _compact(value, limit: int, notes: list):
    """Plain JSON-safe copy; long arrays are omitted (reported), non-finite -> None."""
    if isinstance(value, np.ndarray):
        if value.size > limit:
            notes.append(f"Un arreglo de {value.size} elementos se omitió (límite {limit}).")
            return {"omitted": True, "length": int(value.size)}
        return _compact(value.tolist(), limit, notes)
    if isinstance(value, np.generic):
        return _compact(value.item(), limit, notes)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (bool, int, str)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _compact(v, limit, notes) for k, v in value.items() if k != "warnings"}
    if isinstance(value, (list, tuple)):
        if len(value) > limit:
            notes.append(f"Una lista de {len(value)} elementos se omitió (límite {limit}).")
            return {"omitted": True, "length": len(value)}
        return [_compact(v, limit, notes) for v in value]
    return str(value)


def _report_parameters(parameters: dict) -> dict:
    report = {}
    for key, value in parameters.items():
        if isinstance(value, np.ndarray):
            report[key] = f"<{value.size} etiquetas>"
        else:
            report[key] = value if isinstance(value, (bool, int, float, str)) or value is None else str(value)
    return report


# ----------------------------------------------------------------------------- execution

def _run_candidate(analysis_id: str, step_key: str, candidate: Candidate, variable: str, dataset,
                   prepared, params: dict, extra: dict, context: ExecutionContext, limit: int):
    resolved = {name: _resolve_token(value, prepared, params, extra)
                for name, value in dict(candidate.params).items()}
    request = MethodRequest(f"{analysis_id}:{step_key}", candidate.method_id, variable, resolved)
    result = analyze(dataset, request, registry(), context)
    notes: list = []
    outputs = _compact(result.payload, limit, notes)
    return resolved, result, outputs, notes


def execute(struct: AnalysisStruct, prepared, params: dict, analysis_id: str, *,
            max_points_per_array: int = 5000, context: Optional[ExecutionContext] = None) -> list:
    """Run the steps of `struct` in order. Returns a StepResult per executed step (per scale for loops)."""
    context = context or ExecutionContext()
    available = available_methods()
    profile = prepared.profile
    dataset = prepared.dataset
    working = "y"
    status_by_step: dict = {}
    results: list = []

    for step in struct.steps:
        blocked = [dep for dep in step.inputs if status_by_step.get(dep) != "completed"]
        if blocked:
            status_by_step[step.step_id] = "skipped"
            results.append(StepResult(step.step_id, step.label or step.step_id, "skipped", optional=step.optional,
                                      reason="Depende de un paso que no se completó: " + ", ".join(blocked)))
            continue
        if step.loop == "per_scale":
            iterations = [({"scale": int(scale)}, f"{step.step_id}:{int(scale)}", int(scale)) for scale in params["scales"]]
        else:
            iterations = [({}, step.step_id, None)]

        completed_any = False
        for extra, step_key, loop_key in iterations:
            chosen, why, rejected = None, "", []
            for candidate in step.candidates:
                if candidate.method_id not in available:
                    rejected.append(f"{candidate.method_id}: no está disponible en esta instalación")
                    continue
                ok, reason = _condition(candidate.when, profile, prepared, params, available)
                if ok:
                    chosen, why = candidate, reason
                    break
                rejected.append(f"{candidate.method_id}: {reason}" if reason else f"{candidate.method_id}: no aplica")
            if chosen is None:
                code = METHOD_NOT_AVAILABLE if rejected and all("disponible" in item for item in rejected) else None
                results.append(StepResult(step_key, step.label or step.step_id, "skipped", optional=step.optional,
                                          loop_key=loop_key, error_code=code,
                                          reason="Ningún método aplicable. " + "; ".join(rejected)))
                continue
            because = (chosen.note or chosen.method_id) + (f" ({why})" if why else "")
            try:
                resolved, result, outputs, notes = _run_candidate(
                    analysis_id, step_key, chosen, working, dataset, prepared, params, extra, context,
                    max_points_per_array)
            except AnalysisCancelled:
                results.append(StepResult(step_key, step.label or step.step_id, "failed", chosen.method_id,
                                          optional=step.optional, loop_key=loop_key, reason="Análisis cancelado",
                                          error_code=INTERNAL, selected_because=because))
                continue
            except ImportError as error:
                results.append(StepResult(step_key, step.label or step.step_id, "failed", chosen.method_id,
                                          optional=step.optional, loop_key=loop_key, reason=str(error),
                                          error_code=METHOD_NOT_AVAILABLE, selected_because=because))
                continue
            except ValueError as error:
                results.append(StepResult(step_key, step.label or step.step_id, "failed", chosen.method_id,
                                          optional=step.optional, loop_key=loop_key, reason=str(error),
                                          error_code=INSUFFICIENT_DATA, selected_because=because))
                continue
            except Exception as error:  # engine failures must not abort the other steps
                results.append(StepResult(step_key, step.label or step.step_id, "failed", chosen.method_id,
                                          optional=step.optional, loop_key=loop_key,
                                          reason=f"{type(error).__name__}: {str(error)[:200]}",
                                          error_code=INTERNAL, selected_because=because))
                continue
            completed_any = True
            results.append(StepResult(
                step_key, step.label or step.step_id, "completed", result.method_id, result.method_version,
                _report_parameters(resolved), result.payload, outputs, dict(result.metric_units),
                list(result.warnings) + notes, because, optional=step.optional, loop_key=loop_key,
                uncertainty=result.uncertainty))
            if step.produces == "series":
                values = np.asarray(result.payload["values"], dtype=np.float64)
                unit = dataset.variables["y"].unit
                dataset = replace(dataset, variables={**dataset.variables,
                                                      "work": VariableData(values, ("time",), unit)})
                working = "work"
        status_by_step[step.step_id] = "completed" if completed_any else "failed"
    return results
