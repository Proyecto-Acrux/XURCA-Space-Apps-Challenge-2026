"""Decision layer: turns step results into findings and a verdict on the hypothesis.

Deterministic rules, no language model. The challenge questions are answered
literally in every finding: what changes (`what`), where (`where`), how much
(`how_much`) and whether it is significant (`significant`, `p_value`).

Fixed rules:
  * p >= alpha, or a confidence interval that includes 0 -> "inconclusive"
    ("no hay evidencia suficiente"); never "sin cambios".
  * Anomalies, trends and events are different findings.
  * No "percentage of certainty" is ever produced: closeness to a hypothesis
    is expressed through the p-value, the interval and the sign.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any, Optional

import numpy as np

from ..services.station_catalogs import ENTITY_ROUTES

SPI_DEFICIT = -1.0   # documented SPI state thresholds (plan: -1 / +1)
SPI_EXCESS = 1.0
OPERATORS = {">": lambda a, b: a > b, "<": lambda a, b: a < b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b}


def _f(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _step(steps: list, prefix: str, completed: bool = True):
    for item in steps:
        if item.step_id == prefix or item.step_id.startswith(prefix + ":"):
            if not completed or item.status == "completed":
                return item
    return None


def _what(series: dict, prepared) -> dict:
    return {"variable": series.get("variable"), "family": prepared.meta["family"], "source_id": series.get("id"),
            "provider": series.get("provider"), "product": series.get("product"), "unit": prepared.meta["unit"]}


def _where(series: dict, source: Optional[dict]) -> dict:
    coordinates = series.get("coordinates")
    entity = (source or {}).get("access") in ENTITY_ROUTES
    mode = "entity" if entity else ("point" if coordinates else "unknown")
    return {"mode": mode, "coordinates": coordinates, "label": series.get("location")}


def _when(prepared) -> dict:
    dates = prepared.meta["dates"]
    return {"start": dates[0], "end": dates[-1], "cadence": prepared.profile["cadence"], "n": prepared.profile["n"]}


def _finding(kind: str, series, source, prepared, **fields) -> dict:
    base = {"type": kind, "what": _what(series, prepared), "where": _where(series, source), "when": _when(prepared),
            "how_much": None, "significant": None, "p_value": None, "alpha": None, "test": None,
            "conclusiveness": "not_tested", "statement_key": f"{kind}.descriptive", "notes": [], "limitations": []}
    base.update(fields)
    return base


def _gap(kind: str, series, source, prepared, steps: list, why: str) -> dict:
    failed = [f"{s.step_id}: {s.reason}" for s in steps if s.status != "completed" and not s.optional and s.reason]
    return _finding(kind, series, source, prepared, conclusiveness="insufficient_data",
                    statement_key=f"{kind}.insufficient_data", notes=[why] + failed)


# ----------------------------------------------------------------------------- per struct

def _describe(ctx) -> dict:
    step = _step(ctx["steps"], "summary")
    if step is None:
        return {"findings": [_gap("descriptive", ctx["series"], ctx["source"], ctx["prepared"], ctx["steps"],
                                  "No se pudo calcular el resumen.")], "verdict": None, "charts": []}
    p = step.payload
    unit = ctx["prepared"].meta["unit"]
    finding = _finding("descriptive", ctx["series"], ctx["source"], ctx["prepared"],
                       how_much={"n": p["n"], "mean": _f(p["mean"]), "std": _f(p["std"]), "minimum": _f(p["minimum"]),
                                 "maximum": _f(p["maximum"]), "unit": unit,
                                 "quantiles": {f"{q:g}": _f(v) for q, v in zip(p["quantile_levels"], p["quantile_values"])}},
                       statement_key="descriptive.summary",
                       limitations=["Describe las observaciones recibidas; no es un promedio de área ni un total anual."])
    return {"findings": [finding], "verdict": None,
            "charts": [{"kind": "timeseries", "series_ref": ctx["series"].get("id")}]}


def _trend(ctx) -> dict:
    steps, params, prepared = ctx["steps"], ctx["params"], ctx["prepared"]
    slope = _step(steps, "slope")
    test = _step(steps, "test_modified") or _step(steps, "test")
    if slope is None or test is None:
        why = "No se pudo estimar la tendencia o su significancia."
        return {"findings": [_gap("trend", ctx["series"], ctx["source"], prepared, steps, why)],
                "verdict": _verdict_trend(ctx["hypothesis"], None), "charts": []}
    s, alpha = slope.payload, params["alpha"]
    estimate, lower, upper = float(s["slope"]), float(s["lower"]), float(s["upper"])
    p_value = float(test.payload["p_value"])
    significant = p_value < alpha
    excludes_zero = lower > 0 or upper < 0
    conclusive = significant and excludes_zero
    direction = "increasing" if estimate > 0 else "decreasing" if estimate < 0 else "none"
    unit = prepared.meta["unit"]
    span = prepared.profile["span_years"]
    notes = []
    if significant != excludes_zero:
        notes.append("El valor p y el intervalo de confianza no coinciden (la prueba y el intervalo usan supuestos "
                     "distintos); se trata como no concluyente.")
    if _step(steps, "deseason") is None:
        notes.append("La serie no se desestacionalizó antes de estimar la pendiente.")
    base = prepared.derived.get("baseline")
    if base and base.get("note"):
        notes.append(base["note"])
    if prepared.profile["cadence"] == "irregular":
        notes.append("Serie irregular: no se corrigió por muestreo desigual.")
    finding = _finding(
        "trend", ctx["series"], ctx["source"], prepared,
        how_much={"per_year": estimate, "per_decade": estimate * 10, "unit": f"{unit}/decade",
                  "unit_per_year": f"{unit}/year",
                  "interval": {"lower": lower * 10, "upper": upper * 10, "level": float(s["confidence"]),
                               "unit": f"{unit}/decade"},
                  "total_change": estimate * span, "total_change_unit": unit, "span_years": span,
                  "direction": direction},
        significant=significant, p_value=p_value, alpha=alpha, test=test.method_id,
        conclusiveness="conclusive" if conclusive else "inconclusive",
        statement_key=f"trend.significant.{direction}" if conclusive else "trend.inconclusive",
        notes=notes,
        limitations=["La significancia no establece causalidad ni importancia física.",
                     "El intervalo de la pendiente supone independencia serial; con autocorrelación es demasiado angosto.",
                     "Un solo punto o estación no representa el promedio de una región."])
    charts = [{"kind": "timeseries_trend", "series_ref": ctx["series"].get("id"),
               "overlays": [{"type": "trend_slope", "step": "slope", "per_year": estimate,
                             "lower_per_year": lower, "upper_per_year": upper, "level": float(s["confidence"])}]}]
    return {"findings": [finding], "verdict": _verdict_trend(ctx["hypothesis"], finding), "charts": charts}


def _verdict_trend(hypothesis: Optional[dict], finding: Optional[dict]) -> Optional[dict]:
    if hypothesis is None:
        return None
    base = {"hypothesis": hypothesis}
    if finding is None or finding["conclusiveness"] == "insufficient_data":
        return {**base, "status": "not_testable", "reason_key": "verdict.not_testable", "evidence": {}}
    how = finding["how_much"]
    evidence = {"p_value": finding["p_value"], "alpha": finding["alpha"],
                "interval_excludes_zero": how["interval"]["lower"] > 0 or how["interval"]["upper"] < 0,
                "observed_direction": how["direction"], "per_decade": how["per_decade"], "unit": how["unit"]}
    if finding["conclusiveness"] != "conclusive":
        return {**base, "status": "inconclusive", "reason_key": "verdict.inconclusive", "evidence": evidence}
    wanted = hypothesis.get("direction", "any")
    matches = wanted == "any" or wanted == how["direction"]
    evidence["direction_matches"] = matches
    if matches and hypothesis.get("min_rate") is not None and abs(how["per_year"]) < hypothesis["min_rate"]:
        evidence["min_rate"] = hypothesis["min_rate"]
        return {**base, "status": "not_supported", "reason_key": "verdict.trend.below_min_rate", "evidence": evidence}
    status = "supported" if matches else "not_supported"
    return {**base, "status": status, "reason_key": f"verdict.trend.{status}", "evidence": evidence}


def _anomaly(ctx) -> dict:
    step = _step(ctx["steps"], "anomalies")
    prepared = ctx["prepared"]
    if step is None:
        return {"findings": [_gap("anomaly", ctx["series"], ctx["source"], prepared, ctx["steps"],
                                  "No se pudieron calcular las anomalías.")],
                "verdict": _verdict_threshold(ctx["hypothesis"], None), "charts": []}
    values = np.asarray(step.payload["values"], dtype=float)
    dates = prepared.meta["dates"]
    kind = ctx["params"]["kind"]
    unit = prepared.meta["unit"] if kind == "absolute" else "%" if kind == "percent" else "1"
    peak = int(np.argmax(np.abs(values)))
    base = prepared.derived.get("baseline")
    finding = _finding(
        "anomaly", ctx["series"], ctx["source"], prepared,
        how_much={"kind": kind, "unit": unit, "last": float(values[-1]), "last_date": dates[-1],
                  "mean": float(values.mean()), "largest": float(values[peak]), "largest_date": dates[peak],
                  "n": int(values.size)},
        statement_key="anomaly.descriptive", notes=[base["note"]] if base and base.get("note") else [],
        limitations=["La adecuación del período de referencia la decide quien consulta.",
                     "Una anomalía no es una tendencia ni un evento: son resultados distintos."])
    finding["baseline"] = base
    charts = [{"kind": "anomaly_bars", "series_ref": ctx["series"].get("id"), "values_step": "anomalies", "unit": unit}]
    return {"findings": [finding], "verdict": _verdict_threshold(ctx["hypothesis"], values), "charts": charts}


def _verdict_threshold(hypothesis: Optional[dict], values) -> Optional[dict]:
    if hypothesis is None:
        return None
    base = {"hypothesis": hypothesis}
    if values is None or len(values) == 0:
        return {**base, "status": "not_testable", "reason_key": "verdict.not_testable", "evidence": {}}
    statistic = hypothesis.get("statistic", "last")
    observed = {"last": values[-1], "max": values.max(), "min": values.min(), "mean": values.mean()}[statistic]
    met = OPERATORS[hypothesis["operator"]](float(observed), float(hypothesis["value"]))
    return {**base, "status": "supported" if met else "not_supported",
            "reason_key": "verdict.threshold.met" if met else "verdict.threshold.unmet",
            "evidence": {"statistic": statistic, "observed": float(observed), "operator": hypothesis["operator"],
                         "value": hypothesis["value"], "descriptive_only": True}}


def _spi(ctx) -> dict:
    prepared = ctx["prepared"]
    dates = prepared.meta["dates"]
    findings, used = [], []
    for step in ctx["steps"]:
        if not step.step_id.startswith("spi:") or step.status != "completed":
            continue
        p = step.payload
        spi, valid = np.asarray(p["spi"], dtype=float), np.asarray(p["valid"], dtype=bool)
        if not valid.any():
            continue
        v = spi[valid]
        position = np.flatnonzero(valid)
        findings.append(_finding(
            "index", ctx["series"], ctx["source"], prepared,
            how_much={"scale_months": int(p["scale"]), "n_valid": int(valid.sum()),
                      "deficit_fraction": float(np.mean(v <= SPI_DEFICIT)),
                      "excess_fraction": float(np.mean(v >= SPI_EXCESS)),
                      "last": float(v[-1]), "last_date": dates[int(position[-1])],
                      "minimum": float(v.min()), "unit": "1",
                      "thresholds": {"deficit": SPI_DEFICIT, "excess": SPI_EXCESS}},
            statement_key="spi.descriptive",
            notes=([f"Meses con calibración de menos de 20 años (baja robustez): {w}" for w in p["warnings"] if "Low robustness" in w]),
            limitations=["No se suman SPI de distintas escalas.", "El SPI no es humedad del suelo.",
                         "La bondad de ajuste de la distribución gamma no se evaluó."]))
        used.append(step.step_id)
    if not findings:
        return {"findings": [_gap("index", ctx["series"], ctx["source"], prepared, ctx["steps"],
                                  "No se pudo calcular el SPI en ninguna escala.")], "verdict": None, "charts": []}
    return {"findings": findings, "verdict": None,
            "charts": [{"kind": "spi_states", "series_ref": ctx["series"].get("id"), "steps": used}]}


def _fit(ctx) -> dict:
    step = _step(ctx["steps"], "fit")
    prepared = ctx["prepared"]
    if step is None:
        return {"findings": [_gap("fit", ctx["series"], ctx["source"], prepared, ctx["steps"],
                                  "No se pudo ajustar el modelo.")], "verdict": None, "charts": []}
    p = step.payload
    unit = prepared.meta["unit"]
    how = {"model": step.method_id, "parameters": _plain(p.get("parameters", {})), "metrics": _plain(p.get("metrics", {})),
           "time_unit": "year", "unit": unit}
    parameters = p.get("parameters", {})
    if step.method_id == "linear" and _f(parameters.get("slope")) is not None:
        how["slope_per_year"] = float(parameters["slope"])
        how["slope_unit"] = f"{unit}/year"
    finding = _finding("fit", ctx["series"], ctx["source"], prepared, how_much=how, statement_key="fit.descriptive",
                       limitations=["Ajuste descriptivo dentro de la muestra: no evalúa significancia ni es un pronóstico validado."])
    return {"findings": [finding], "verdict": None,
            "charts": [{"kind": "timeseries", "series_ref": ctx["series"].get("id"), "fit_step": "fit"}]}


def _add_months(day: date, count: int) -> date:
    index = day.year * 12 + day.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


def _forecast(ctx) -> dict:
    step = _step(ctx["steps"], "forecast")
    prepared, hypothesis = ctx["prepared"], ctx["hypothesis"]
    if step is None:
        return {"findings": [_gap("forecast", ctx["series"], ctx["source"], prepared, ctx["steps"],
                                  "No se pudo generar el pronóstico.")],
                "verdict": _verdict_forecast(hypothesis, None), "charts": [], "forecast": None}
    p = step.payload
    unit = prepared.meta["unit"]
    last = date.fromisoformat(prepared.meta["dates"][-1])
    central = [float(v) for v in p["central"]]
    times = [_add_months(last, i).isoformat() for i in range(1, len(central) + 1)]
    lower = [_f(v) for v in p["lower"]]
    upper = [_f(v) for v in p["upper"]]
    has_interval = any(v is not None for v in lower)
    interval = p["interval"]
    block = {
        "mode": p["mode"], "model": p["model"], "delivered": p["delivered"], "unit": unit,
        "issue_date": prepared.meta["dates"][-1], "times": times, "central": central, "central_kind": "point_forecast",
        "interval": ({"level": interval["level"], "lower": lower, "upper": upper,
                      "empirical_coverage": interval["empirical_coverage"], "calibrated": interval["calibrated"],
                      "kind": "predictive"} if has_interval else None),
        "baseline": {"name": p["best_baseline"], "values": [float(v) for v in p["baseline_values"]]},
        "skill_vs_baseline": [_f(v) for v in p["skill_vs_best_baseline"]],
        "horizon_requested": p["horizon_requested"], "horizon_validated": p["horizon_validated"],
        "not_superior_to_baseline": p["not_superior_to_baseline"],
        "backtest": {"n_origins": p["backtest"]["n_origins"], "initial_train": p["backtest"]["initial_train"],
                     "design": p["backtest"]["design"]},
        "uncertainty": p["uncertainty"],
        "assumptions": ["Pronóstico estadístico de la serie; no incluye predictores físicos ni escenarios."],
    }
    finding = _finding(
        "forecast", ctx["series"], ctx["source"], prepared,
        how_much={"horizon_steps": len(central), "unit": unit, "first": central[0], "last": central[-1],
                  "model": p["model"], "delivered": p["delivered"], "mode": p["mode"],
                  "horizon_validated": p["horizon_validated"]},
        conclusiveness="validated" if p["mode"] == "validated_forecast" else "exploratory",
        statement_key=f"forecast.{p['mode']}", notes=list(p["warnings"]),
        limitations=["Es un pronóstico estadístico de una sola serie.",
                     "El intervalo es predictivo (valores futuros), no un intervalo de confianza de un parámetro.",
                     "El desempeño pasado no garantiza el futuro."])
    finding["not_superior_to_baseline"] = p["not_superior_to_baseline"]
    return {"findings": [finding], "verdict": _verdict_forecast(hypothesis, block), "forecast": block,
            "charts": [{"kind": "forecast_fan", "series_ref": ctx["series"].get("id")}]}


def _verdict_forecast(hypothesis: Optional[dict], block: Optional[dict]) -> Optional[dict]:
    if hypothesis is None:
        return None
    base = {"hypothesis": hypothesis}
    if block is None:
        return {**base, "status": "not_testable", "reason_key": "verdict.not_testable", "evidence": {}}
    index = hypothesis["at_step"] - 1
    compare = OPERATORS[hypothesis["operator"]]
    value = float(hypothesis["value"])
    central = block["central"][index]
    evidence = {"central": central, "operator": hypothesis["operator"], "value": value, "at_step": hypothesis["at_step"],
                "date": block["times"][index], "mode": block["mode"]}
    interval = block["interval"]
    if interval and interval["lower"][index] is not None and interval["upper"][index] is not None:
        inside = [compare(interval["lower"][index], value), compare(interval["upper"][index], value)]
        evidence.update({"lower": interval["lower"][index], "upper": interval["upper"][index],
                         "interval_calibrated": interval["calibrated"]})
        status = "supported" if all(inside) else "not_supported" if not any(inside) else "inconclusive"
    else:
        status = "supported" if compare(central, value) else "not_supported"
        evidence["descriptive_only"] = True
    if block["mode"] != "validated_forecast" and status == "supported":
        evidence["caveat"] = "pronóstico no validado: la condición se cumple solo en la estimación central"
    return {**base, "status": status, "reason_key": f"verdict.forecast.{status}", "evidence": evidence}


def _plain(mapping) -> dict:
    return {str(k): _f(v) if isinstance(v, (int, float)) else v for k, v in dict(mapping).items()}


BUILDERS = {"describe": _describe, "trend_significance": _trend, "anomaly": _anomaly,
            "drought_spi": _spi, "regression_fit": _fit, "forecast": _forecast}


def build(struct, params: dict, steps: list, prepared, series: dict, source: Optional[dict],
          hypothesis: Optional[dict]) -> dict:
    """Findings, verdict and chart descriptors for one analysis."""
    builder = BUILDERS.get(struct.struct_id)
    if builder is None:
        return {"findings": [], "verdict": None, "charts": []}
    return builder({"struct": struct, "params": params, "steps": steps, "prepared": prepared, "series": series,
                    "source": source, "hypothesis": hypothesis})
