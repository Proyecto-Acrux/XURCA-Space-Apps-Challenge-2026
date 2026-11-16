"""Data preparation: connector series -> ScientificDataset for the scientific engine.

Everything the engine refuses to do implicitly happens here, explicitly and on
the record (`transformations`): date parsing, temporal aggregation with a
minimum coverage per period, gap policy, numeric time, unit handling for
precipitation depth, and the auxiliary labels (calendar month, reference
period). Nothing is interpolated, extrapolated or silently converted.
"""
from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import numpy as np

from ..models.contracts import Provenance, ScientificDataset, TimeCoordinate, Transformation, VariableData
from ..models.stats.diagnostics import lag1_autocorrelation, seasonal_strength
from ..services.coverage import VARIABLES
from .analysis_structs import AnalysisStruct
from .contracts import (
    CADENCE_INCOMPATIBLE, INSUFFICIENT_DATA, IRREGULAR_SERIES, UNIT_INCOMPATIBLE, UNSUPPORTED_SPATIAL,
    HandlerError, error_item,
)

VERSION = "1.0.0"
YEAR_DAYS = 365.2425
REGULAR = {"monthly", "daily", "annual"}
SUM_FAMILIES = {"earthquake-count"}
RATE_UNITS = {"mm/day", "mm/d", "mm/dia", "mm/día", "mmday-1", "mmd-1", "mm/day."}
DEPTH_UNITS = {"mm", "cm", "m"}
DEFAULT_BASELINE = (date(1991, 1, 1), date(2020, 12, 31))


@dataclass
class Prepared:
    dataset: ScientificDataset
    profile: dict
    transformations: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    derived: dict = field(default_factory=dict)


def _parse_date(stamp: Any) -> Optional[date]:
    text = str(stamp or "")
    try:
        if len(text) == 7:
            return date(int(text[:4]), int(text[5:7]), 1)
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def family_of(source: Optional[dict], series: dict) -> str:
    declared = (source or {}).get("variable")
    if declared:
        return str(declared)
    code = series.get("variable")
    for name, codes in VARIABLES.items():
        if code in codes:
            return name
    return str(code or "unknown")


def _provenance_kind(provider: str) -> str:
    text = (provider or "").lower()
    if any(key in text for key in ("power", "open-meteo", "ecmwf", "copernicus")):
        return "reanalysis"
    if any(key in text for key in ("firms", "swot", "hydrocron", "appeears", "earthdata")):
        return "satellite"
    return "observation"


def _index(cadence: str, day: date) -> int:
    if cadence == "monthly":
        return day.year * 12 + day.month - 1
    if cadence == "annual":
        return day.year
    return day.toordinal()


def _days_in_month(day: date) -> int:
    return calendar.monthrange(day.year, day.month)[1]


def _aggregate(dates, values, native: str, target: str, statistic: str, min_coverage: float):
    """Aggregate to monthly/annual periods; periods below min_coverage become NaN."""
    buckets: dict = {}
    for day, value in zip(dates, values):
        key = (day.year, day.month) if target == "monthly" else (day.year, 1)
        entry = buckets.setdefault(key, [[], 0])
        entry[1] += 1
        if not math.isnan(value):
            entry[0].append(value)
    new_dates, new_values = [], []
    for (year, month), (valid, _) in sorted(buckets.items()):
        if native == "daily":
            expected = _days_in_month(date(year, month, 1)) if target == "monthly" else (366 if calendar.isleap(year) else 365)
        elif native == "monthly":
            expected = 12
        else:
            expected = None
        if not valid or (expected is not None and len(valid) / expected < min_coverage):
            value = math.nan
        else:
            value = float(np.sum(valid)) if statistic == "sum" else float(np.mean(valid))
        new_dates.append(date(year, month, 1))
        new_values.append(value)
    return new_dates, np.array(new_values, dtype=np.float64)


def _runs(idx: np.ndarray):
    """Longest run of consecutive indices (first one on ties): (start, stop)."""
    best, start = (0, 1), 0
    for position in range(1, len(idx) + 1):
        if position == len(idx) or idx[position] - idx[position - 1] != 1:
            if position - start > best[1] - best[0]:
                best = (start, position)
            start = position
    return best


def _baseline(dates, params: dict, key: str, min_coverage: float):
    requested = params.get(key)
    if requested:
        start, end, origin = date.fromisoformat(requested["start"]), date.fromisoformat(requested["end"]), "requested"
    else:
        start, end = DEFAULT_BASELINE
        origin = "default"
    array = np.array(dates)
    mask = (array >= start) & (array <= end)
    years = sorted({day.year for day in array[mask]})
    expected = end.year - start.year + 1
    covered = bool(mask.any()) and len(years) >= math.ceil(min_coverage * expected)
    if not covered:
        if requested:
            raise HandlerError(INSUFFICIENT_DATA, f"El período de referencia {start}..{end} no está cubierto por la "
                               f"serie (años con datos: {len(years)} de {expected}).")
        mask = np.ones(len(dates), dtype=bool)
        years = sorted({day.year for day in dates})
        start, end, origin = dates[0], dates[-1], "analysis_period"
    info = {"start": start.isoformat(), "end": end.isoformat(), "source": origin, "covered": covered or origin != "default",
            "n_years": len(years), "n_observations": int(mask.sum())}
    if origin == "analysis_period":
        info["note"] = "La base 1991-2020 no está cubierta: se usó el período analizado como referencia."
    return mask, info, max(2, math.ceil(min_coverage * len(years)))


def prepare(series: dict, source: Optional[dict], struct: AnalysisStruct, params: dict, scope: Optional[dict] = None) -> Prepared:
    """Build the dataset and profile for one analysis. Raises HandlerError for unusable series."""
    scope = scope or {}
    req = struct.requirements
    if series.get("message") or not isinstance(series.get("points"), list):
        raise HandlerError(UNSUPPORTED_SPATIAL, "La fuente devolvió archivos originales o datos espaciales, no una "
                           "serie temporal analizable. En esta versión se analizan series de punto o de estación.", scope)

    transformations: list = []
    issues: list = []
    rows, unparsed = [], 0
    for point in series["points"]:
        day = _parse_date(point.get("month"))
        if day is None:
            unparsed += 1
            continue
        value = point.get("value")
        ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        rows.append((day, float(value) if ok else math.nan))
    if not rows:
        raise HandlerError(INSUFFICIENT_DATA, "La serie no tiene observaciones con fecha válida.", scope)
    if any(b[0] < a[0] for a, b in zip(rows, rows[1:])):
        rows.sort(key=lambda item: item[0])
        transformations.append({"operation": "sort_by_date", "version": VERSION, "parameters": {}})
    dates = [row[0] for row in rows]
    if len(set(dates)) != len(dates):
        raise HandlerError(IRREGULAR_SERIES, "La serie tiene fechas repetidas (por ejemplo, eventos del mismo día). "
                           "Elegí una variable agregada o un conteo diario.", scope)
    values = np.array([row[1] for row in rows], dtype=np.float64)

    unit = str(series.get("unit") or "unknown")
    unit_key = unit.lower().replace(" ", "")
    family = family_of(source, series)
    native = series.get("cadence") or "monthly"
    native = native if native in ("monthly", "daily") else "irregular"
    n_native = len(rows)

    # ---- aggregation
    aggregate = params.get("aggregate", "auto")
    limit = req.max_points
    target = native
    if aggregate in ("monthly", "annual"):
        target = aggregate
    elif aggregate == "auto" and req.cadences and native not in req.cadences:
        target = "monthly" if "monthly" in req.cadences else ("annual" if "annual" in req.cadences else native)
    if native == "monthly" and target == "monthly":
        target = native
    if target != native and native == "annual":
        raise HandlerError(CADENCE_INCOMPATIBLE, "No se puede pasar de una serie anual a una cadencia menor.", scope)
    statistic = "sum" if (family in SUM_FAMILIES or (family == "precipitation" and native == "daily"
                                                      and unit_key not in RATE_UNITS)) else "mean"
    min_coverage = float(params.get("min_coverage", 0.8))

    def apply(to_cadence):
        return _aggregate(dates, values, native, to_cadence, statistic, min_coverage)

    cadence = native
    if target != native:
        dates, values = apply(target)
        cadence = target
        transformations.append({"operation": f"aggregate_{target}", "version": VERSION,
                                "parameters": {"statistic": statistic, "min_coverage": min_coverage,
                                               "from_cadence": native, "n_before": n_native}})
    if aggregate == "auto" and limit and len(dates) - int(np.isnan(values).sum()) > limit and cadence in ("monthly", "daily", "irregular"):
        dates, values = _aggregate([d for d in (row[0] for row in rows)], np.array([row[1] for row in rows]),
                                   native, "annual", statistic, min_coverage)
        cadence = "annual"
        transformations = [t for t in transformations if not t["operation"].startswith("aggregate_")]
        transformations.append({"operation": "aggregate_annual", "version": VERSION,
                                "parameters": {"statistic": statistic, "min_coverage": min_coverage,
                                               "from_cadence": native, "n_before": n_native,
                                               "reason": f"más de {limit} observaciones"}})

    # ---- precipitation depth (SPI): rate -> monthly total, depth units only
    if req.depth_total:
        if cadence == "monthly" and unit_key in RATE_UNITS:
            values = values * np.array([_days_in_month(day) for day in dates], dtype=np.float64)
            unit, unit_key = "mm", "mm"
            transformations.append({"operation": "rate_to_monthly_total", "version": VERSION,
                                    "parameters": {"from": "mm/day", "factor": "days in month"}})
        elif unit_key not in DEPTH_UNITS:
            issues.append(error_item(UNIT_INCOMPATIBLE, f"El SPI requiere totales mensuales de precipitación en mm, cm "
                                     f"o m; la serie viene en '{unit}'.", scope))
    if req.variable_families and family not in req.variable_families:
        issues.append(error_item(UNIT_INCOMPATIBLE, f"{struct.struct_id} solo admite variables de tipo "
                                 f"{', '.join(req.variable_families)}; esta es '{family}'.", scope))

    # ---- missing values and gap policy
    idx_all = np.array([_index(cadence, day) for day in dates], dtype=np.int64)
    valid = ~np.isnan(values)
    expected_total = int(idx_all[-1] - idx_all[0] + 1) if cadence in REGULAR else len(values)
    missing_fraction = float(1 - valid.sum() / expected_total) if expected_total else 1.0
    if not valid.any():
        raise HandlerError(INSUFFICIENT_DATA, "La serie no tiene valores válidos en el período.", scope)
    dates = [day for day, ok in zip(dates, valid) if ok]
    values, idx = values[valid], idx_all[valid]
    n_dropped = int((~valid).sum())
    policy = params.get("gap_policy", "drop")
    if n_dropped:
        transformations.append({"operation": "drop_missing", "version": VERSION, "parameters": {"n_dropped": n_dropped}})
    if policy == "longest_run" and cadence in REGULAR:
        start, stop = _runs(idx)
        if stop - start < len(idx):
            transformations.append({"operation": "longest_continuous_run", "version": VERSION,
                                    "parameters": {"kept": stop - start, "discarded": len(idx) - (stop - start)}})
            dates, values, idx = dates[start:stop], values[start:stop], idx[start:stop]
    regular = bool(cadence in REGULAR and (len(idx) < 2 or np.all(np.diff(idx) == 1)))

    # ---- numeric time
    if req.time == "months" and cadence == "monthly":
        time_values, time_unit = (idx - idx[0]).astype(np.float64), "month"
    elif cadence == "monthly":
        time_values, time_unit = (idx - idx[0]) / 12.0, "year"
    elif cadence == "annual":
        time_values, time_unit = (idx - idx[0]).astype(np.float64), "year"
    else:
        time_values, time_unit = (idx - idx[0]) / YEAR_DAYS, "year"

    # ---- auxiliary labels
    variables = {"y": VariableData(values, ("time",), unit)}
    groups = None
    derived: dict = {"min_count": 2, "baseline": None}
    n_years = len({day.year for day in dates})
    if cadence == "monthly":
        groups = np.array([day.month for day in dates], dtype=np.int64)
        variables["groups"] = VariableData(groups, ("time",), "1")
        if req.baseline_param:
            mask, info, min_count = _baseline(dates, params, req.baseline_param, min_coverage)
            variables[req.baseline_param] = VariableData(mask.astype(np.int64), ("time",), "1")
            derived["baseline"], derived["min_count"] = info, min_count

    # ---- profile
    r1 = threshold = strength = None
    if regular and len(values) >= 4:
        try:
            diag = lag1_autocorrelation(time_values, values, groups=groups)
            r1, threshold = diag["r1"], diag["threshold"]
        except ValueError:
            pass
    if groups is not None and len(values) >= 24:
        try:
            strength = seasonal_strength(time_values, values, groups)["strength"]
        except ValueError:
            pass
    profile = {
        "n": int(len(values)), "cadence": cadence, "native_cadence": native, "regular": regular,
        "span_years": float((dates[-1] - dates[0]).days / YEAR_DAYS), "n_years": n_years,
        "missing_fraction": missing_fraction, "n_dropped": n_dropped, "n_unparsed": unparsed,
        "aggregated": cadence != native, "lag1_autocorrelation": r1, "lag1_threshold": threshold,
        "seasonal_strength": strength, "unit": unit, "family": family,
    }
    meta = {"dates": [day.isoformat() for day in dates], "groups": groups, "unit": unit, "family": family,
            "cadence": cadence, "time_unit": time_unit}
    dataset = ScientificDataset(
        dataset_id=str(series.get("id") or "series"), variables=variables, coordinates={},
        provenance=Provenance(
            source_id=str(series.get("id") or "series"), kind=_provenance_kind(str(series.get("provider") or "")),
            demo=False, references=((series["url"],) if isinstance(series.get("url"), str) and series["url"].strip() else ()),
            product=series.get("product") if isinstance(series.get("product"), str) else None,
            acquired_at=series.get("retrievedAt") if isinstance(series.get("retrievedAt"), str) else None),
        time=TimeCoordinate(time_values, time_unit, dates[0].isoformat(), "gregorian", frequency=cadence),
        quality={"missing_fraction": missing_fraction, "n_dropped": n_dropped, "n_unparsed": unparsed},
        transformations=tuple(Transformation(t["operation"], t["version"], t["parameters"]) for t in transformations))
    return Prepared(dataset, profile, transformations, issues, meta, derived)
