# 23 — Arquitectura modular del backend: handlers, contratos y structs

Fecha: 2026-11-15 · Commit auditado: `052830b` (`main` = `ema_workspace`) · Estado: **aprobado como plan de implementación**; el código lo implementa Codex siguiendo `aplicacion/trend-scope/src-tauri/src-python/trend_scope/handlers/AGENTS.md`.

Relación con el resto del plan maestro: este documento **acota y precede** a `03_ALGORITHM_HANDLER.md` y `09_CONTRATOS_JSON_API.md`. El DAG, `knowledge/`, los jobs y la caché de esos documentos siguen siendo el destino; aquí se define la primera versión ejecutable, con los cuatro módulos del mapa del equipo (Data Handler, Analysis Handler, Analysis Structs, Algorithm Handler).

Rutas: `PY/` = `aplicacion/trend-scope/src-tauri/src-python/trend_scope/` · `M/` = `PY/models/`.

## Context

El mapa propuesto (`Mapa_frontend.png`) define el flujo: evento «ejecutar análisis» → `request.json` → **Data Handler** → **Analysis Handler** (devuelve un **Analysis Struct**) → **Algorithm Handler** (librerías de cálculo y predictivas) → Data Handler arma `response.json` → frontend y chatbot / algoritmo de decisión. Se pidió refinarlo solo si hace falta, tras leer todo el código (sin tocar `web app/`), y dejar la especificación lista para que **Codex** implemente los 8 puntos.

Qué se leyó y verificó (solo lectura):

- **Ramas:** `origin/API`, `eze_w`, `ema_workspace`, `Primeros_pasos_Appweb` son todas ancestros de `main` (`052830b`). Hay un solo árbol vigente.
- **Flujo real hoy:** `+page.svelte: run()` → `pyInvoke('acquire_data', {investigation})` → `services/acquisition.acquire()` → lista de series `{id, variable, unit, points:[{month,value}], provider, cadence, url, retrievedAt…}` → `services/evidence.with_evidence()` (OLS descriptivo) → gráficos. **El motor científico de `M/` no está conectado**: `execute_regression` no lo llama nadie y `validate_investigation` rechaza `methods` no vacío.
- **Motor:** `catalog_registry()` expone **37 métodos** (verificado en el venv; incluye W01–W03) y se ejecutan con `execution.analyze(dataset, request, registry, context)` sobre `ScientificDataset`. El venv ya tiene statsmodels, ruptures, pymannkendall, scikit-learn, pywt, river, tslearn. No hay xarray/netCDF4 (no se pueden leer rásters).
- **Plan maestro previo** (`docs/plan-maestro/`): propone DAG, `knowledge/`, jobs, caché y 8 comandos. Es correcto como destino, pero demasiado grande para arrancar.

**Veredicto:** el plan propuesto es válido y se conserva (4 módulos + 2 JSON). Se necesitan **9 refinamientos**, todos derivados del código real:

| # | Refinamiento | Motivo (evidencia) |
|---|---|---|
| 1 | El Data Handler **no genera CSV**: convierte las series (dicts) directo a arreglos NumPy / `ScientificDataset` | Los conectores ya devuelven JSON; CSV agrega una conversión con pérdida de metadatos. CSV queda solo como exportación opcional |
| 2 | `request.json` **embebe `cfg_data.json` tal cual** en `investigation` y agrega `analyses[]` | El frontend y el chat ya producen `cfg_data`; `acquire()` lo consume sin cambios. `methods: []` era el marcador de lugar de esto |
| 3 | `response.series[]` conserva **el formato actual de series** | `Results.svelte`/`ChartView`/`charts.js` siguen funcionando sin cambios |
| 4 | Se agrega una capa explícita de **preparación** (tiempo numérico, huecos, agregación, unidades) dentro del Data Handler | El motor exige tiempos numéricos crecientes, sin NaN; Sen/MK admiten ≤ 2000 puntos (`max_pairs`); SPI exige totales mensuales en mm con paso 1 mes |
| 5 | El **algoritmo de decisión es determinista** y vive en el backend (`decision.py`); el chatbot solo redacta | «No inventar precisión estadística»; el sistema debe funcionar sin IA |
| 6 | Nombres sin colisión: `RequestDocument`/`ResponseDocument` | `M/contracts.py` ya define `AnalysisRequest/AnalysisResult` (contrato de **un método**) y `handlers/analysis.py` ya existe (heredado) |
| 7 | Los handlers van en `PY/handlers/` (fuera de `M/`); `M/` solo recibe archivos nuevos de algoritmos | `M/` está protegido por `PRESERVATION.json` y su `AGENTS.md` prohíbe orquestación |
| 8 | Espacial: v1 = **punto / entidad**; área = **muestreo multipunto rotulado**; ráster 2D queda en el contrato pero responde `unsupported` | AppEEARS/CDS/Earthdata devuelven archivos, no series; no hay lector de ráster (D-10, D-20) |
| 9 | Un solo comando síncrono `run_analysis` (+ `list_analyses`); jobs/DAG/caché del plan maestro se difieren | `desktop.py` ya usa `to_thread.run_sync`; alcanza para el MVP |

---

## Arquitectura

```
PY/
├─ desktop.py                 + comandos run_analysis, list_analyses (los 9 existentes no cambian)
├─ handlers/
│  ├─ analysis.py             heredado, sin cambios (execute_regression)
│  ├─ contracts.py            Pydantic: RequestDocument, ResponseDocument, errores
│  ├─ data_handler.py         [3] entrada única: run(request) -> response
│  ├─ preparation.py          [3] series -> PreparedSeries -> ScientificDataset
│  ├─ analysis_handler.py     [5] catálogo de structs, resolución, capacidades
│  ├─ analysis_structs.py     [6] AnalysisStruct / Step + STRUCTS
│  ├─ algorithm_handler.py    [4] selección y ejecución procedimental
│  ├─ decision.py             hallazgos + veredicto de hipótesis (determinista)
│  └─ (schemas)               `contracts.export_schemas()` genera los JSON Schema bajo demanda
│  └─ models/                    solo archivos nuevos: [7] cálculo, [8] forecasting
```

Secuencia (igual al mapa, con los nombres reales):

1. Frontend/chat → `run_analysis({request})`.
2. `data_handler.run`: valida (`contracts`), calcula `request_hash`, llama `acquisition.acquire(investigation)` + `evidence.with_evidence` (reutilizados).
3. Por cada `analyses[i]`: `analysis_handler.resolve(spec)` → **AnalysisStruct**.
4. `preparation.prepare(series, struct.requirements, params)` → datos recortados + `DataProfile`.
5. `algorithm_handler.execute(struct, prepared, params, context)` → resultados por paso.
6. `decision.build(struct, steps, hypothesis)` → `findings[]` + `verdict`.
7. `data_handler` arma `response.json` (serialización estricta con `M/serialization.dumps`).

Reutilizar sin modificar: `acquisition.acquire`, `evidence.with_evidence`, `coverage.VARIABLES`, `catalog_registry()`, `execution.analyze` + `ExecutionContext`, `adapters/grid.analyze_grid`, `serialization.to_jsonable/dumps`, `numeric.*`, `configuration.directory()`.

---

## 1. Formato de `request.json`

Pydantic v2, `extra="forbid"`, `snake_case` (lo embebido en `investigation` conserva su camelCase).

```json
{
  "schema": "earth-detective/request",
  "schema_version": 1,
  "request_id": "uuid-opcional",
  "origin": "manual",
  "language": "es",
  "investigation": { "…": "cfg_data.json v1 completo: sources[], time{start,end,resolution}, geography.selection (GeoJSON)" },
  "analyses": [
    {
      "id": "a1",
      "struct": "trend_significance",
      "targets": ["power-temperature"],
      "roles": { "response": null, "drivers": [] },
      "params": {
        "alpha": 0.05, "confidence": 0.95,
        "aggregate": "auto", "min_coverage": 0.8,
        "baseline": { "start": "1991-01-01", "end": "2020-12-31" },
        "gap_policy": "drop"
      },
      "hypothesis": { "kind": "trend", "direction": "increasing" }
    }
  ],
  "options": { "include_steps": true, "max_points_per_array": 5000, "allow_partial": true }
}
```

| Campo | Regla |
|---|---|
| `origin` | `manual` \| `assistant`. Fuera de la huella |
| `investigation` | Se pasa a `acquire()` con `methods: []`. Selección temporal + espacial + tipo de dato **ya están ahí** (`time`, `geography`, `sources[].upstream`) |
| `analyses[]` | 1–10. `struct` ∈ ids de §6. `targets` = ids de `investigation.sources` (1 para univariado; `roles` para multivariable) |
| `params` | Solo claves declaradas por el struct; los valores por defecto los aplica **solo el backend** y se devuelven en `response.analyses[].parameters_effective` |
| `hypothesis` | Opcional. `kind` ∈ `trend` (`direction`: increasing/decreasing/any, `min_rate?`) · `change_point` (`window?`) · `threshold` (`operator`, `value`, `statistic`) · `relationship` (`sign?`, `lags`) · `forecast_threshold` (`operator`, `value`, `at_step`) |
| Pronóstico | `params.horizon` (entero, en pasos de la cadencia analizada). Tope por cadencia en §8 |
| Espacial | Derivado de la geometría de cada source: Point → `point`; estación/tramo → `entity`; polígono + `params.spatial = "sample"` → muestreo multipunto; `"grid"` → `unsupported` en v1 |
| `request_hash` | `sha256` del JSON canónico sin `request_id`, `origin`, `language`, nombres visibles |

Seguridad: solo ids registrados; sin rutas de archivo, URLs, nombres de función ni expresiones.

## 2. Formato de `response.json`

```json
{
  "schema": "earth-detective/response",
  "schema_version": 1,
  "request_id": "…", "request_hash": "sha256:…",
  "status": "completed",
  "generated_at": "2026-11-15T14:02:11Z",
  "engine": { "handler_version": "1.0.0", "methods": { "sen": "1.0.0-candidate" } },
  "series": [ { "…": "serie actual sin cambios (id, variable, unit, points[{month,value}], provider, cadence, url, retrievedAt, summary)" } ],
  "analyses": [
    {
      "id": "a1", "struct": "trend_significance", "kind": "statistical", "status": "completed",
      "targets": ["power-temperature"],
      "parameters_effective": { "alpha": 0.05, "aggregate": "monthly", "…": "…" },
      "data_profile": { "n": 300, "cadence": "monthly", "regular": true, "span_years": 25.0,
                        "missing_fraction": 0.0, "lag1_autocorrelation": 0.21, "seasonal": true },
      "transformations": [ { "operation": "to_decimal_years", "parameters": {} } ],
      "steps": [
        { "step": "slope", "method_id": "sen_interval", "method_version": "1.0.0-candidate",
          "status": "completed", "parameters": {}, "outputs": { "slope": 0.021, "lower": 0.008, "upper": 0.034 },
          "units": { "slope": "(C)/(year)" }, "warnings": [], "selected_because": "n=300 <= 2000 pares permitidos" }
      ],
      "findings": [
        { "type": "trend",
          "what": { "variable": "T2M", "source_id": "power-temperature" },
          "where": { "mode": "point", "coordinates": [-66.33, -33.29], "label": "San Luis" },
          "when": { "start": "2000-01", "end": "2024-12" },
          "how_much": { "value": 0.21, "unit": "C/decade", "interval": { "lower": 0.08, "upper": 0.34, "level": 0.95 },
                        "total_change": 0.52 },
          "significant": true, "p_value": 0.004, "alpha": 0.05, "test": "seasonal_mann_kendall",
          "statement_key": "trend.significant.increasing", "limitations": ["…"] }
      ],
      "verdict": { "hypothesis": { "kind": "trend", "direction": "increasing" },
                   "status": "supported", "reason_key": "verdict.trend.supported",
                   "evidence": { "p_value": 0.004, "interval_excludes_zero": true, "direction_matches": true } },
      "forecast": null,
      "charts": [ { "kind": "timeseries_trend", "series_ref": "power-temperature",
                    "overlays": [ { "type": "line", "step": "slope" }, { "type": "band", "step": "slope", "level": 0.95 } ] } ],
      "warnings": [], "errors": []
    }
  ],
  "assistant_digest": { "…": "resumen sin arreglos, <= 6000 caracteres: por análisis, findings + verdict + limitaciones + fuentes" },
  "warnings": [], "errors": []
}
```

- `status` global: `completed` | `partial` (algún análisis o paso falló; el resto se entrega) | `failed`.
- `status` de análisis/paso: `completed` | `partial` | `skipped` | `failed`, siempre con `reason`.
- `verdict.status`: `supported` | `not_supported` | `inconclusive` | `not_testable`. **Nunca un «% de certeza»**: la medida de «qué tanto corresponde» son `p_value`, intervalo y coincidencia de signo.
- `findings[]` responde literalmente al desafío: **what / where / how_much / significant**.
- `forecast` (solo struct predictivo): `{mode: "validated_forecast"|"exploratory_extrapolation", model, times[], central[], interval{lower[],upper[],level,empirical_coverage}|null, baseline{…}, skill_vs_baseline, horizon_validated, not_superior_to_baseline}`.
- `charts[].kind`: `timeseries` · `timeseries_trend` · `anomaly_bars` · `spi_states` · `change_points` · `decomposition` · `scatter_lag` · `forecast_fan` · `map_points` · `table` (desconocido → `table`).
- Errores tipados `{code, message, scope}`: `INVALID_REQUEST`, `UNKNOWN_STRUCT`, `SOURCE_ERROR`, `INSUFFICIENT_DATA`, `IRREGULAR_SERIES`, `UNIT_INCOMPATIBLE`, `METHOD_NOT_AVAILABLE`, `UNSUPPORTED_SPATIAL`, `BUDGET_EXCEEDED`, `INTERNAL`.
- Sin `NaN`/`Infinity`: faltantes como `null` + máscara `valid[]`.

## 3. Data_Handler (`data_handler.py` + `preparation.py`)

`run(raw: dict) -> dict`, síncrono, invocado desde `desktop.py` con `to_thread.run_sync`.

1. **Validar** con `contracts.RequestDocument`; error → response `failed` con `INVALID_REQUEST` (no excepción cruda).
2. **Adquirir** una sola vez: `with_evidence(acquire({**investigation, "methods": []}))`. Un `ValueError` del conector → `SOURCE_ERROR` y, si `allow_partial`, continúan los análisis que no dependen de esa serie.
3. **Preparar** por análisis (`preparation.prepare`):
   - parsear `month` (`YYYY-MM`, `YYYY-MM-DD`, ISO fecha-hora); series con `message`/`downloadPath` (descargas crudas) → `UNSUPPORTED_SPATIAL`;
   - **agregación** `auto|native|monthly|annual` con `min_coverage` por período (0.8, valor documentado Q01); estadístico `mean` o `sum` según la familia de variable (reusar `coverage.VARIABLES`); tasa→total explícita (POWER `PRECTOTCORR` mm/día × días del mes) registrada en `transformations`;
   - **huecos** (`gap_policy`): `drop` para métodos que admiten tiempo irregular; `longest_run` u error `IRREGULAR_SERIES` para los que exigen rejilla regular. **Nunca interpolación silenciosa**;
   - **tiempo numérico**: años decimales (tendencias → pendiente «por año»), índice de mes (SPI/STL/pronóstico) o de día;
   - variables auxiliares que piden W01/W03: `groups` (mes 1–12), `baseline`/`calibration` (0/1), unidad `"1"`; `min_count = ceil(min_coverage × años de la base)`;
   - `DataProfile`: n, cadencia, regularidad, años cubiertos, fracción faltante, autocorrelación lag-1, estacionalidad (cálculo en `M/stats/diagnostics.py`, §7);
   - salida: `ScientificDataset` con `Provenance` (kind según proveedor, `demo=False`), `TimeCoordinate`, `transformations`.
4. **Delegar**: `analysis_handler.resolve` → `algorithm_handler.execute` → `decision.build`.
5. **Ensamblar** `ResponseDocument`; decimar arreglos largos con el método `lttb` registrado (`max_points_per_array`); `serialization.dumps`.
6. **Muestreo de área** (fase 3): polígono → retícula ≤ 25 puntos dentro del perímetro (límite actual de `acquire`), una serie por punto, struct `spatial_pattern`. Rótulo fijo: «muestra de N puntos, no promedio zonal».

`desktop.py`: `run_analysis(body: {request: dict}) -> str` y `list_analyses() -> str`. No requiere cambios en Rust ni en `capabilities/default.json` (`pytauri:default` ya cubre los comandos Python).

## 4. Algorithm_Handler (`algorithm_handler.py`)

`execute(struct, prepared, params, context) -> list[StepResult]`. **No contiene fórmulas**: solo decide y llama a `analyze()` con un registro construido una vez (`catalog_registry()` cacheado a nivel de módulo).

- Recorre `struct.steps` **en orden**; cada paso puede declarar `loop`: `none` | `per_target` | `per_scale` (SPI 1/3/6/12) | `per_lag` | `per_cell` (retícula, vía `adapters/grid.analyze_grid`).
- Cada paso lista **candidatos ordenados** con condición; se ejecuta el primero aplicable y se registra `selected_because`. Si ninguno aplica → `skipped` con motivo; los pasos que dependían de él también.
- Lista blanca: solo `method_id` presentes en el registro; método opcional ausente → `METHOD_NOT_AVAILABLE` + alternativa declarada.
- Errores del motor (`ValueError`) → paso `failed` con el mensaje; no aborta el análisis.
- Cancelación y límites: `ExecutionContext` existente (256 MiB, 1e6 observaciones).

Reglas de selección (según tipo de análisis, tamaño muestral y características):

| Decisión | Regla | Origen |
|---|---|---|
| Magnitud de tendencia | `sen_interval` (pendiente + IC). Si n(n−1)/2 > `max_pairs` (n > 2000) → subir un nivel de agregación (diario→mensual→anual) | Límite real de `sen`/`mann_kendall` |
| Significancia | mensual/subanual con ≥ 2 años → `seasonal_mann_kendall` (seasons = mes); anual → `mann_kendall`; si regular, sin huecos, 4 ≤ n ≤ 2000 y \|r₁\| > 1.96/√n → además `modified_mann_kendall` (pasa a ser el p principal) | Q03 del plan maestro; límites de `optional_methods` |
| Desestacionalizar | mensual con base cubierta → `anomalies` (W01, `absolute`) antes de Sen; si la base pedida no está cubierta → base = período analizado, **rotulado** | Q02 |
| n mínimo para inferencia | `min_points` del struct (10 para MK asintótico; parámetro, marcado *provisional* hasta D-03) | AGENTS: no inventar umbrales |
| Rupturas | regular + ≥ 2 ciclos + statsmodels → `stl` → `pelt`; sin `ruptures` → `cusum` con advertencia. Rotulado «aproximación, no BFAST» | D-09 |
| Estacionalidad | `harmonic` (pasar `period` siempre: no tiene valor por defecto en el registro) + `fft` exploratorio | Defecto E6 detectado |
| Serie irregular (SWOT, INA) | solo métodos sin exigencia de paso constante | `regularity` de `MethodSpec` |
| Pronóstico | §8 | — |

## 5. Analysis_Handler (`analysis_handler.py`)

Orquestador de los análisis (descriptivos, estadísticos, matemáticos, predictivos).

- `resolve(spec) -> AnalysisStruct`: busca `spec.struct` en `STRUCTS`; valida número de `targets`, roles, claves de `params` y tipo de `hypothesis` admitido; completa valores por defecto.
- `check(struct, profile) -> list[Issue]`: requisitos del struct contra el `DataProfile` (cadencias admitidas, regularidad, n mínimo, familia de variable — p. ej. SPI solo precipitación).
- `capabilities() -> dict` (comando `list_analyses`): por struct → título, tipo, parámetros con tipo/rango/default, hipótesis admitidas, métodos usados y si están **disponibles en esta instalación**. Es lo que el chatbot y el formulario leen para armar `request.json` sin prompts estáticos.
- Agregar un análisis = agregar una entrada en `analysis_structs.py`; ningún handler cambia.

`decision.py` (algoritmo de decisión): reglas fijas —
p ≥ α o IC que incluye 0 → `inconclusive` con texto «no hay evidencia suficiente» (**nunca** «sin cambios»); tendencia, anomalía y evento son hallazgos distintos; multivariable → «asociación», nunca causa; pronóstico que no supera al baseline → `not_superior_to_baseline`.

## 6. Analysis_Structs (`analysis_structs.py`)

```python
@dataclass(frozen=True)
class Step:
    step_id: str
    candidates: tuple[Candidate, ...]   # (method_id, when: condición sobre DataProfile, params)
    inputs: tuple[str, ...] = ()        # step_ids previos o "prepared"
    loop: str = "none"
    optional: bool = False

@dataclass(frozen=True)
class AnalysisStruct:
    struct_id: str; title: str; kind: str      # descriptive | statistical | mathematical | predictive
    targets: tuple[int, int]                    # mínimo y máximo de variables
    requirements: Requirements                  # cadencias, regular, min_points, familias de variable
    params: Mapping[str, ParamSpec]             # tipo, rango, default, provisional: bool
    hypotheses: tuple[str, ...]
    steps: tuple[Step, ...]
    charts: tuple[str, ...]
```

| `struct_id` | Tipo | Pasos (métodos del registro) | Estado |
|---|---|---|---|
| `describe` | descriptivo | resumen (`descriptive`, §7) → `lttb` | Fase 1 |
| `trend_significance` | estadístico | `anomalies`* → `sen_interval` → MK estacional / MK / MK modificado | **Fase 1 (núcleo del desafío)** |
| `anomaly` | estadístico | `climatology` → `anomalies` (absolute / standardized / robust_z) | Fase 1 |
| `drought_spi` | estadístico | `spi` (`loop: per_scale`) → estados ≤ −1 / ≥ +1 | Fase 1 |
| `regression_fit` | matemático | `linear` / `polynomial` / `ridge` / `exponential` / `logarithmic` / `power` / `harmonic` | Fase 1 |
| `seasonality` | matemático | `harmonic` → `fft` → `stl`* | Fase 2 |
| `change_point` | estadístico | `stl` → `pelt` \| `cusum` | Fase 2 |
| `smoothing` | matemático | `moving_average` \| `ssa` | Fase 2 |
| `extreme_events` | estadístico | percentiles → eventos (W04) | Fase 2 (requiere W04) |
| `relationship` | estadístico | correlación con desfases **predefinidos** (W05) → FDR (W06) → `multivariable` | Fase 2 (requiere W05, W06) |
| `forecast` | predictivo | baselines (W07) → backtest (W08) → ajuste → intervalos (W09) | Fase 3 (§8) |
| `spatial_pattern` | estadístico | `trend_significance` `per_cell` sobre la retícula + FDR | Fase 3 (requiere W06) |

\* paso opcional. Un struct cuyo requisito no está implementado aparece en `list_analyses` como `available: false` con el motivo.

## 7. Librerías faltantes de cálculo (archivos nuevos en `M/`)

Protocolo de `M/AGENTS.md` sin cambios: una función por solicitud, registro aditivo en `catalog_registry.py`, estado `candidate`.

| Prioridad | Id | Archivo | Para qué struct |
|---|---|---|---|
| 1 | W17 (nuevo) | `stats/diagnostics.py`: autocorrelación lag-1, fuerza estacional | Reglas de selección de §4 |
| 1 | W18 (nuevo) | `stats/descriptive.py`: n, media, mediana, desvío, cuantiles, mín/máx | `describe` (hoy vive en `services/evidence.py` en Python puro) |
| 2 | W06 | `stats/multiple_testing.py` FDR-BH | `relationship`, `spatial_pattern` |
| 2 | W05 | `stats/lagged.py` correlación con desfases y parcial | `relationship` |
| 2 | W04 | `climate/events.py` percentiles, eventos, composites | `extreme_events` |
| 3 | W19 (nuevo) | `signal/convolution2d.py`: convolución 2D / FIR 2D sobre `(y,x)` con borde explícito (`scipy.signal`) | Nota del mapa; suavizado espacial cuando exista ráster |
| 4 | W10–W16 | ETCCDI, bootstrap, FWI, métricas probabilísticas, índices de quema, transición, hipsométrica | Independientes de los handlers; orden de la cola |

Preparación de datos (agregación, unidades, huecos, fechas) **no** va en `M/`: es `handlers/preparation.py`.

Pendientes heredados, con recomendación:

- **MAD de W01:** dejar `climatology()['mad']` **sin escalar** (estadístico descriptivo en unidades de la variable) y aplicar el factor **1.4826 dentro de `robust_z`**, documentado (`robust_z = (x − mediana) / (1.4826·MAD)`), para que sea comparable con un z normal y con los umbrales habituales. Hoy `robust_z` divide por la MAD cruda (verificado en `climatology.py`): corregir antes de aprobar W01.
- **Auditoría independiente de W01–W03** antes de que `trend_significance`, `anomaly` y `drought_spi` salgan de `candidate`; W03 se cierra después de W01.

## 8. Librerías de modelos predictivos

Existente (se **envuelve**, no se modifica): `optional_methods.forecast` con `naive`, `seasonal_naive`, `holt_winters`, `arima`, `sarima` (statsmodels) — un único holdout, sin incertidumbre.

Nuevo en `M/forecasting/`:

| Id | Archivo | Contenido |
|---|---|---|
| W07 | `baselines.py` | `climatology_forecast`, `persistence_forecast` |
| W08 | `backtest.py` | `rolling_origin` (ventana expansiva, sin fuga) → MAE, RMSE, sesgo, skill, residuales por horizonte |
| W09 | `intervals.py` | `residual_intervals` + `empirical_coverage` |
| W13 | `prob_metrics.py` | Brier, BSS, fiabilidad, CRPS (para `forecast_threshold`) |
| W20 (nuevo) | `forecasters.py` | *callables* `(train_t, train_y, horizon)` que envuelven `forecast` para `seasonal_naive`, `holt_winters`, `sarima` con órdenes **fijos y declarados** (sin búsqueda automática de órdenes) |

Selección en el Algorithm Handler:

- Requisitos: serie regular sin huecos; ≥ 2 ciclos estacionales para Holt-Winters/SARIMA; si no → solo baselines.
- Candidatos evaluados con `rolling_origin`; se elige el de menor MAE fuera de muestra; si skill ≤ 0 frente a climatología/persistencia → se entrega **el baseline** con `not_superior_to_baseline: true`.
- `mode = validated_forecast` solo con backtest, skill > 0 e intervalo con cobertura medida; en otro caso `exploratory_extrapolation` **sin intervalo**.
- **Plazo razonable:** `horizon ≤ min(tope por cadencia, 20 % de n)`; topes provisionales: mensual 12, diario 14, anual 5 (parámetros marcados *provisional* hasta D-21). Más allá → `INSUFFICIENT_DATA` con el máximo permitido.
- Fuera de alcance (ya declarado en `ENGINE_STATUS.md`): LSTM/GRU/TFT, modelos fundacionales, Prophet.
- Empaquetado: declarar `statsmodels`, `pymannkendall`, `ruptures` como grupo opcional `scientific` en `src-tauri/pyproject.toml` (D-06). Decisión de dependencias: requiere tu visto bueno al implementarse.

---

## Chatbot e interfaz (contrato, sin implementar en esta etapa)

- El chat arma `request.json` = `investigation` (que ya edita) + `analyses[]` elegidos de `list_analyses`; se valida con `schemas/request.schema.json`.
- Para explicar recibe **solo** `assistant_digest` (cabe en el límite actual de 18 000 caracteres de contexto).
- Cambio mínimo de frontend cuando se conecte: `acquisition.js` agrega `runAnalysis(request)` y `run()` usa `response.series` (mismo formato). `acquire_data` sigue funcionando.

## Orden de implementación para Codex

| Fase | Entrega | Criterio de cierre |
|---|---|---|
| 0 | Corrección MAD `robust_z` | Aplicada |
| 1 | `contracts.py`, `analysis_structs.py`, `analysis_handler.py`, `preparation.py`, `algorithm_handler.py`, `decision.py`, `data_handler.py`, comandos; W17, W18; structs `describe`, `trend_significance`, `anomaly`, `drought_spi`, `regression_fit`; comandos `run_analysis` / `list_analyses` | Recorrido request → response implementado |
| 2 | W06, W05, W04; structs `seasonality`, `change_point`, `smoothing`, `extreme_events`, `relationship` | Structs de fase 2 implementados |
| 3 | W07, W08, W09, W20, W13; struct `forecast`; muestreo de área y `spatial_pattern` | Baseline cuando no hay habilidad |
| 4 | W19, W10–W16 | Cola de `M/AGENTS.md` |


## Alcance y límites de este documento

- **Por decisión del equipo (2026-11-15) el plan no incluye benchmarks ni pruebas automáticas.** La verificación la hace el equipo probando la aplicación.
- No se leyó ni se modificó `web app/`.
- Los valores marcados *provisional* (n mínimo, topes de horizonte, penalizaciones por defecto) no provienen de la investigación científica: son parámetros configurables a la espera de D-03 y D-21 (`21_RIESGOS_Y_DECISIONES.md`).
- La conexión del frontend y del chatbot a `run_analysis` no forma parte de esta etapa; el contrato queda fijado por los schemas y fixtures.
