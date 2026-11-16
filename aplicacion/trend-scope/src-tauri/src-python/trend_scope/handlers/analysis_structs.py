"""Declarative catalogue of analysis structs (the "procedural structures" of the map).

A struct says WHAT to run, in which order and under which conditions. It has no
formulas: every step names registered methods of the scientific engine
(`trend_scope.models`). Adding an analysis means adding an entry to STRUCTS.

Conditions are named strings evaluated by the algorithm handler:
  always | seasonal | not_seasonal | monthly_cycle | autocorrelated | pairs_ok |
  param:<key>=<value>
Parameter values starting with "$" are looked up in the effective parameters
(or derived values), "@groups" is the calendar-month label array.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

# Highest implementation phase available (docs/plan-maestro/23_ARQUITECTURA_HANDLERS.md §6).
IMPLEMENTED_PHASE = 1


@dataclass(frozen=True)
class ParamSpec:
    type: str  # float | int | str | bool | int_list | period
    default: Any = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    choices: tuple = ()
    provisional: bool = False
    description: str = ""


@dataclass(frozen=True)
class Requirements:
    cadences: tuple = ()          # allowed cadences after preparation; () = any
    regular: bool = False         # needs an unbroken regular grid
    min_points: int = 2           # provisional unless stated (decision D-03)
    max_points: Optional[int] = None   # pair budget of Sen / Mann-Kendall
    variable_families: tuple = () # () = any
    time: str = "years"           # years | months
    baseline_param: Optional[str] = None  # param holding the reference period
    depth_total: bool = False     # needs monthly precipitation depth totals


@dataclass(frozen=True)
class Candidate:
    method_id: str
    when: str = "always"
    params: Mapping = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class Step:
    step_id: str
    candidates: tuple
    label: str = ""
    inputs: tuple = ()            # step ids that must complete first
    loop: str = "none"            # none | per_scale
    optional: bool = False
    produces: str = ""            # "series" replaces the working series


@dataclass(frozen=True)
class AnalysisStruct:
    struct_id: str
    title: str
    kind: str                     # descriptive | statistical | mathematical | predictive
    targets: tuple
    requirements: Requirements
    params: Mapping
    hypotheses: tuple
    steps: tuple
    charts: tuple
    phase: int = 1
    planned: bool = False
    description: str = ""
    limitations: tuple = ()


def _common(**overrides) -> dict:
    base = {
        "aggregate": ParamSpec("str", "auto", choices=("auto", "native", "monthly", "annual"),
                               description="Agregación temporal previa al análisis"),
        "min_coverage": ParamSpec("float", 0.8, 0.5, 1.0,
                                  description="Cobertura mínima por período al agregar y para la base de referencia"),
        "gap_policy": ParamSpec("str", "drop", choices=("drop", "longest_run"),
                                description="Qué hacer con los faltantes: descartarlos o usar el tramo continuo más largo"),
    }
    base.update(overrides)
    return base


_BASELINE = ParamSpec("period", None, description="Período de referencia {start, end}; por defecto 1991-2020 si la serie lo cubre")
_ALPHA = ParamSpec("float", 0.05, 0.0001, 0.5, description="Nivel de significancia")
_CONFIDENCE = ParamSpec("float", 0.95, 0.5, 0.999, description="Nivel del intervalo de confianza")

STRUCTS: tuple = (
    AnalysisStruct(
        struct_id="describe", title="Resumen descriptivo", kind="descriptive", targets=(1, 1),
        requirements=Requirements(min_points=1),
        params=_common(),
        hypotheses=(),
        steps=(Step("summary", (Candidate("describe"),), "Estadística descriptiva"),),
        charts=("timeseries",),
        description="Cantidad, media, desvío, extremos y cuantiles de las observaciones recibidas.",
        limitations=("Describe las observaciones recibidas; no es un promedio de área ni un total anual.",),
    ),
    AnalysisStruct(
        struct_id="trend_significance", title="Tendencia y significancia", kind="statistical", targets=(1, 1),
        requirements=Requirements(cadences=("monthly", "annual", "irregular"), min_points=10, max_points=2000,
                                  time="years", baseline_param="baseline"),
        params=_common(baseline=_BASELINE, alpha=_ALPHA, confidence=_CONFIDENCE,
                       min_points=ParamSpec("int", 10, 3, 2000, provisional=True,
                                            description="Observaciones mínimas para inferir (provisional, decisión D-03)"),
                       mk_lag=ParamSpec("int", 1, 1, 24, provisional=True,
                                        description="Lag máximo de la corrección por autocorrelación (provisional)")),
        hypotheses=("trend",),
        steps=(
            Step("deseason", (Candidate("anomalies", "monthly_cycle",
                                        {"groups": "groups", "baseline": "baseline",
                                         "min_count": "$min_count", "kind": "absolute"},
                                        "Anomalías respecto del ciclo mensual de la base"),),
                 "Quitar el ciclo estacional", optional=True, produces="series"),
            Step("slope", (Candidate("sen_interval", "pairs_ok", {"confidence": "$confidence"},
                                     "Pendiente de Theil-Sen con intervalo de confianza"),),
                 "Pendiente e intervalo"),
            Step("test", (Candidate("seasonal_mann_kendall", "seasonal", {"seasons": "@groups"},
                                    "Serie mensual con ciclo: Mann-Kendall por estación"),
                          Candidate("mann_kendall", "always", {}, "Mann-Kendall sobre la serie completa")),
                 "Prueba de tendencia", inputs=()),
            Step("test_modified", (Candidate("modified_mann_kendall", "autocorrelated",
                                             {"correction": "hamed_rao", "lag": "$mk_lag", "alpha": "$alpha"},
                                             "Autocorrelación significativa: Mann-Kendall con corrección de varianza"),),
                 "Prueba con corrección por autocorrelación", optional=True),
        ),
        charts=("timeseries_trend",),
        description="Cuánto cambia una variable en el tiempo y si el cambio es estadísticamente significativo.",
        limitations=("La significancia no establece causalidad ni importancia física.",
                     "El intervalo de la pendiente supone independencia serial."),
    ),
    AnalysisStruct(
        struct_id="anomaly", title="Anomalías respecto de una referencia", kind="statistical", targets=(1, 1),
        requirements=Requirements(cadences=("monthly",), min_points=24, time="years", baseline_param="baseline"),
        params=_common(baseline=_BASELINE,
                       kind=ParamSpec("str", "absolute", choices=("absolute", "percent", "standardized", "robust_z"),
                                      description="Tipo de anomalía")),
        hypotheses=("threshold",),
        steps=(Step("anomalies", (Candidate("anomalies", "monthly_cycle",
                                            {"groups": "groups", "baseline": "baseline",
                                             "min_count": "$min_count", "kind": "$kind"}),),
                    "Anomalías mensuales"),),
        charts=("anomaly_bars",),
        description="Desvío de cada observación respecto del promedio del mismo mes en el período de referencia.",
        limitations=("La adecuación del período de referencia la decide quien consulta.",),
    ),
    AnalysisStruct(
        struct_id="drought_spi", title="Déficit y exceso de precipitación (SPI)", kind="statistical", targets=(1, 1),
        requirements=Requirements(cadences=("monthly",), regular=True, min_points=24, time="months",
                                  variable_families=("precipitation",), baseline_param="calibration",
                                  depth_total=True),
        params=_common(gap_policy=ParamSpec("str", "longest_run", choices=("drop", "longest_run"),
                                            description="El SPI exige meses consecutivos"),
                       calibration=_BASELINE,
                       scales=ParamSpec("int_list", [1, 3, 6, 12], 1, 60,
                                        description="Escalas del SPI en meses")),
        hypotheses=(),
        steps=(Step("spi", (Candidate("spi", "always",
                                      {"groups": "groups", "calibration": "calibration", "scale": "@scale",
                                       "min_count": "$min_count"}),),
                    "SPI por escala", loop="per_scale"),),
        charts=("spi_states",),
        description="Índice de precipitación estandarizado: meses secos o lluviosos respecto de lo habitual.",
        limitations=("No se suman SPI de distintas escalas.", "El SPI no es humedad del suelo."),
    ),
    AnalysisStruct(
        struct_id="regression_fit", title="Ajuste de regresión", kind="mathematical", targets=(1, 1),
        requirements=Requirements(min_points=3, time="years"),
        params=_common(model=ParamSpec("str", "linear",
                                       choices=("linear", "polynomial", "ridge", "exponential", "logarithmic",
                                                "power", "harmonic")),
                       degree=ParamSpec("int", 2, 1, 10), alpha=ParamSpec("float", 1.0, 0.0, 1e6),
                       period=ParamSpec("float", 1.0, 1e-6, 1e6, description="Período del armónico en años"),
                       harmonics=ParamSpec("int", 1, 1, 6), trend_degree=ParamSpec("int", 1, 0, 3)),
        hypotheses=(),
        steps=(Step("fit", (
            Candidate("linear", "param:model=linear"),
            Candidate("polynomial", "param:model=polynomial", {"degree": "$degree"}),
            Candidate("ridge", "param:model=ridge", {"degree": "$degree", "alpha": "$alpha"}),
            Candidate("exponential", "param:model=exponential"),
            Candidate("logarithmic", "param:model=logarithmic"),
            Candidate("power", "param:model=power"),
            Candidate("harmonic", "param:model=harmonic",
                      {"period": "$period", "harmonics": "$harmonics", "trend_degree": "$trend_degree"}),
        ), "Ajuste"),),
        charts=("timeseries",),
        description="Ajusta un modelo matemático a la serie. Es descriptivo: no evalúa significancia.",
        limitations=("Ajuste descriptivo dentro de la muestra; no es un pronóstico validado.",),
    ),
    # --- Planned (phase 2 and 3): declared so the catalogue is honest about what is missing.
    AnalysisStruct(
        struct_id="seasonality", title="Estacionalidad", kind="mathematical", targets=(1, 1),
        requirements=Requirements(cadences=("monthly",), regular=True, min_points=24), params=_common(),
        hypotheses=(), steps=(Step("harmonic", (Candidate("harmonic"),)),), charts=("decomposition",), phase=2, planned=True),
    AnalysisStruct(
        struct_id="change_point", title="Cambios de régimen", kind="statistical", targets=(1, 1),
        requirements=Requirements(cadences=("monthly", "annual"), regular=True, min_points=24), params=_common(),
        hypotheses=("change_point",), steps=(Step("segments", (Candidate("pelt"), Candidate("cusum"))),),
        charts=("change_points",), phase=2, planned=True),
    AnalysisStruct(
        struct_id="smoothing", title="Suavizado", kind="mathematical", targets=(1, 1),
        requirements=Requirements(regular=True, min_points=4), params=_common(),
        hypotheses=(), steps=(Step("smooth", (Candidate("moving_average"), Candidate("ssa"))),),
        charts=("timeseries",), phase=2, planned=True),
    AnalysisStruct(
        struct_id="extreme_events", title="Eventos extremos", kind="statistical", targets=(1, 1),
        requirements=Requirements(min_points=24), params=_common(), hypotheses=("threshold",),
        steps=(Step("events", (Candidate("detect_events"),)),), charts=("table",), phase=2, planned=True),
    AnalysisStruct(
        struct_id="relationship", title="Asociación entre variables", kind="statistical", targets=(2, 4),
        requirements=Requirements(regular=True, min_points=24), params=_common(), hypotheses=("relationship",),
        steps=(Step("lags", (Candidate("lagged_correlation"),)), Step("fdr", (Candidate("fdr_bh"),))),
        charts=("scatter_lag",), phase=2, planned=True),
    AnalysisStruct(
        struct_id="forecast", title="Pronóstico mensual con validación", kind="predictive", targets=(1, 1),
        requirements=Requirements(cadences=("monthly",), regular=True, min_points=60, time="years"),
        params=_common(
            gap_policy=ParamSpec("str", "longest_run", choices=("drop", "longest_run"),
                                 description="El pronóstico exige meses consecutivos"),
            horizon=ParamSpec("int", 6, 1, 24, provisional=True, description="Pasos (meses) a pronosticar"),
            level=ParamSpec("float", 0.90, 0.5, 0.99, description="Nivel nominal del intervalo predictivo"),
            max_origins=ParamSpec("int", 24, 4, 200, provisional=True, description="Orígenes máximos del backtest"),
            min_residuals=ParamSpec("int", 10, 3, 200, provisional=True,
                                    description="Residuos mínimos por paso para calibrar el intervalo"),
            initial_train=ParamSpec("int", 0, 0, 100000, provisional=True,
                                    description="Meses de entrenamiento inicial (0 = automático)"),
            baseline_min_count=ParamSpec("int", 3, 2, 50, provisional=True,
                                         description="Años mínimos por mes para la referencia climatológica")),
        hypotheses=("forecast_threshold",),
        steps=(Step("forecast", (Candidate(
            "forecast_backtest", "always",
            {"groups": "groups", "horizon": "$horizon", "period": 12, "initial_train": "$initial_train",
             "max_origins": "$max_origins", "level": "$level", "min_residuals": "$min_residuals",
             "min_count": "$baseline_min_count"},
            "Candidatos contra referencias (climatología y persistencia), con backtest de origen móvil"),),
            "Pronóstico con backtest"),),
        charts=("forecast_fan",),
        description="Pronóstico estadístico de la serie. Se entrega la referencia si ningún modelo la supera.",
        limitations=("Es un pronóstico estadístico de una sola serie, sin predictores físicos ni escenarios.",
                     "El desempeño pasado no garantiza el futuro; los cambios de régimen no se modelan.",
                     "Solo se declara 'validado' con habilidad positiva fuera de muestra e intervalo con cobertura medida.")),
)

BY_ID: Mapping = {item.struct_id: item for item in STRUCTS}


# spatial_pattern reuses the trend struct on a lattice of points inside a polygon.
import dataclasses as _dc

_trend = BY_ID["trend_significance"]
SPATIAL = _dc.replace(
    _trend, struct_id="spatial_pattern", title="Patrón espacial de tendencias (muestra de puntos)",
    params={**_trend.params,
            "area_feature_id": ParamSpec("str", None, description="Id del polígono en geography.selection; por defecto el único"),
            "n_points": ParamSpec("int", 9, 4, 25, provisional=True, description="Puntos de la muestra dentro del polígono")},
    hypotheses=(), charts=("map_points",), phase=3,
    description="Tendencia en una retícula de puntos dentro de un polígono, con control de falsos descubrimientos.",
    limitations=("Es una muestra de puntos, no un promedio zonal ni un ráster.",
                 "Los puntos vecinos no son independientes: el control de falsos descubrimientos es aproximado.",
                 *_trend.limitations))
STRUCTS = STRUCTS + (SPATIAL,)
BY_ID = {item.struct_id: item for item in STRUCTS}
