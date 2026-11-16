# 09 — Contratos JSON y API

## 1. Principios

1. **JSON es el único formato de intercambio** entre frontend, IA y backend.
2. **Varios objetos pequeños y coherentes**, no uno gigante: solicitud, plan, resultado, estado de job y descriptores.
3. **Un solo contrato de entrada** (`AnalysisRequest`) para el configurador manual y para la IA.
4. **Fuente de verdad única:** los modelos Pydantic de `PY/handler/contracts.py`. De ahí se exporta JSON Schema a `PY/handler/schemas/*.schema.json`, que consumen el frontend (validación y tipos JSDoc) y la IA (salida estructurada).
5. **Sin HTTP:** la "API" son comandos PyTauri. Los nombres de este documento son nombres de comando.
6. **Convención de nombres:** `snake_case` en todos los contratos nuevos. Los contratos existentes (`cfg_data.json`, series con `month`, `retrievedAt`) no se tocan; el adaptador `NormalizedSeries` hace de frontera.

### Nombres y colisiones

`M/contracts.py` ya define `AnalysisRequest` y `AnalysisResult` (contrato interno de **un método**). Los contratos públicos del Handler usan los mismos nombres en JSON, pero viven en otro módulo; dentro de `handler/` los internos se importan con alias (`MethodRequest`, `MethodResult`). No se renombra nada en `M/`.

### Versionado

- Cada objeto lleva `schema_version` (`"2.0"`; la `1` es la de `cfg_data.json`).
- Cambio compatible (campo opcional nuevo, valor nuevo en un enumerado tolerado por los consumidores) → sube el menor.
- Cambio incompatible → sube el mayor; el backend acepta la versión mayor anterior durante una fase de transición.
- Todo cambio de contrato requiere la aprobación de una persona de cada equipo (ver `20_PLAN_INTEGRACION_GITHUB.md`).

---

## 2. `AnalysisRequest`

| Campo | Tipo | Oblig. | Valor por defecto | Restricciones |
|---|---|---|---|---|
| `schema_version` | `"2.0"` | Sí | — | |
| `request_id` | string (UUID) | No | generado | Fuera de la huella |
| `input_mode` | `"manual" | "assistant"` | No | `"manual"` | Fuera de la huella |
| `analysis.kind` | `"auto" | "descriptive" | "trend" | "anomaly" | "multivariable" | "forecast" | "scenario" | "composite"` | No | `"auto"` | Restringe, no fuerza |
| `analysis.phenomenon_ids` | string[] | No | `[]` | 0–5 ids del catálogo |
| `analysis.operations` | `{recipe_id, params}`[] | No | `[]` | Solo recetas registradas; modo avanzado |
| `location.geometry` | GeoJSON `Point | Polygon | MultiPolygon` | Sí* | — | Lat −90..90, lon −180..180 |
| `location.crs` | `"EPSG:4326"` | No | `"EPSG:4326"` | Único admitido en 2.0 |
| `location.spatial_mode` | `"auto" | "point" | "entity" | "area_mean" | "grid"` | No | `"auto"` | |
| `location.entity_id` | string | No | `null` | Fija estación o tramo |
| `location.name` | string | No | `null` | Fuera de la huella |
| `period.start`, `period.end` | fecha ISO | No | Mayor período cubierto | `start < end ≤ hoy` |
| `issue_time` | fecha-hora ISO UTC | No | Hoy 00:00 UTC | Solo predicción |
| `variables[]` | objeto | No | Las del fenómeno | 1–10 |
| `variables[].variable_id` | string | Sí | — | Id canónico |
| `variables[].role` | `"target" | "explanatory" | "confounder" | "context"` | No | Según fenómeno | |
| `variables[].source_preference` | string[] | No | `[]` | `source_id` registrados |
| `variables[].attributes` | objeto | No | `{}` | p. ej. `{"depth": "0-7cm"}`, `{"overpass": "day"}` |
| `temporal.frequency` | `"native" | "daily" | "8-day" | "16-day" | "monthly" | "seasonal" | "annual"` | No | Según receta | |
| `spatial.resolution` | `"native" | "coarsest"` | No | `"coarsest"` | Nunca más fina que la nativa |
| `forecast.horizon` | `{value: int, unit: "day"|"week"|"month"}` | Si predice | — | |
| `forecast.mode` | `"auto" | "forecast" | "scenario" | "extrapolation"` | No | `"auto"` | |
| `forecast.scenario_assumptions[]` | `{variable_id, description, values?}` | Si escenario | `[]` | |
| `uncertainty.confidence_level` | number | No | `0.95` | 0.80–0.99 |
| `uncertainty.interval_level` | number | No | `0.90` | `0.95` solo si hay cobertura verificada |
| `scientific_params.baseline_period` | `{start, end}` | No | 1991–2020 si se cubre | |
| `scientific_params.min_coverage` | number | No | `0.8` | 0.5–1.0 |
| `scientific_params.significance_alpha` | number | No | `0.05` | |
| `scientific_params.lags` | `{unit, candidates: int[]}` | No | Los del fenómeno | Predefinidos, no optimizados |
| `scientific_params.spi_scales` | int[] | No | `[1,3,6,12]` | |
| `constraints.max_runtime_s` | int | No | `600` | |
| `constraints.allow_partial` | bool | No | `true` | |
| `constraints.allow_sample_data` | bool | No | `false` | Si `true`, los datos de muestra van rotulados |
| `presentation.language` | `"es" | "en"` | No | `"es"` | Fuera de la huella |

\* Excepto variables sin geografía (p. ej. índice ONI).

### Ejemplo — Caso 1 (tendencia de temperatura)

```json
{
  "schema_version": "2.0",
  "request_id": "5d0f4a0e-6f0f-4d7b-9a55-3a2c1e9f8b10",
  "input_mode": "assistant",
  "analysis": { "kind": "trend", "phenomenon_ids": ["N1.1.0"] },
  "location": {
    "geometry": { "type": "Point", "coordinates": [-66.3356, -33.2950] },
    "crs": "EPSG:4326",
    "name": "San Luis, San Luis, Argentina"
  },
  "period": { "start": "2006-01-01", "end": "2025-12-31" },
  "variables": [ { "variable_id": "air_temperature_2m_mean", "role": "target" } ],
  "temporal": { "frequency": "monthly" },
  "presentation": { "language": "es" }
}
```

---

## 3. `ValidationReport` (respuesta de `validate_request`)

```json
{
  "schema_version": "2.0",
  "valid": true,
  "request_hash": "sha256:9c1e…",
  "canonical_request": { "…": "solicitud con valores por defecto aplicados" },
  "defaults_applied": [
    { "field": "scientific_params.baseline_period", "value": { "start": "1991-01-01", "end": "2020-12-31" }, "reason": "Q02: base fija cubierta por la fuente" },
    { "field": "uncertainty.confidence_level", "value": 0.95, "reason": "IC95 de la planilla" }
  ],
  "missing": [],
  "errors": [],
  "warnings": [
    { "code": "PARTIAL_PHENOMENON", "message": "N1.1.0 incluye LST; no se solicitó y su producto no tiene procesador disponible." }
  ],
  "suggestions": []
}
```

`missing[]`: `{ field, reason, options[] }`. `errors[]`: objetos `Error` (§9).

---

## 4. `AnalysisPlan`

| Campo | Tipo | Descripción |
|---|---|---|
| `schema_version` | `"2.0"` | |
| `plan_id` | string | `sha256(request_hash + knowledge_version + capabilities_fingerprint)` |
| `request_hash` | string | |
| `knowledge_version` | string | Versión de `knowledge/` |
| `intent` | objeto | `mode`, `operations[]`, `assumptions[]` |
| `phenomena[]` | `PhenomenonResolution` | Estado por fenómeno |
| `sources[]` | objeto | Por variable: `selected`, `alternatives[]`, `rejected[]` con motivo, `substitution` |
| `nodes[]` | `PlanNode` | |
| `checks[]` | string[] | Controles Q planificados |
| `eligibility[]` | objeto | Decisión predictiva previa por modelo |
| `blocked[]` | `{what, code, reason, alternatives[]}` | |
| `execution_mode` | `"sync" | "async"` | |
| `estimated` | `{fetch_nodes, cached_nodes, external_waits}` | Sin estimar segundos |
| `warnings[]` | objeto | |

`PlanNode`: `{ node_id, op, label, params, inputs: node_id[], produces, cacheable, source_id?, algorithm_id?, model_id? }`.

### Ejemplo — plan del Caso 1 (abreviado)

```json
{
  "schema_version": "2.0",
  "plan_id": "sha256:41ab…",
  "request_hash": "sha256:9c1e…",
  "knowledge_version": "2026.11.0",
  "intent": {
    "mode": "catalog",
    "operations": [ { "kind": "trend", "recipe_id": "R-TREND", "phenomenon_id": "N1.1.0", "branch": "T2m" } ],
    "assumptions": [ "Punto único; no representa el promedio provincial." ]
  },
  "phenomena": [
    {
      "phenomenon_id": "N1.1.0",
      "status": "PARTIAL",
      "planned_branches": ["T2m"],
      "blocked_branches": [ { "what": "LST", "code": "NOT_REQUESTED", "reason": "Variable no solicitada." } ],
      "prediction_mode_catalog": "derived_from_forecast",
      "prediction_mode_effective": null
    }
  ],
  "sources": [
    {
      "variable_id": "air_temperature_2m_mean",
      "selected": { "source_id": "nasa.power.monthly", "product": "POWER Monthly", "native_code": "T2M" },
      "substitution": { "required_product": "X02", "used_product": "X03", "same_quantity": true,
                        "note": "ERA5 (X02) no está disponible como serie; se usa NASA POWER (X03), opcional en el catálogo." },
      "alternatives": [ { "source_id": "noaa.ncei.station", "native_code": "TAVG" } ],
      "rejected": [ { "source_id": "copernicus.cds", "code": "RAW_ONLY", "reason": "Sin procesador de NetCDF." } ]
    }
  ],
  "nodes": [
    { "node_id": "n1", "op": "fetch", "label": "Descargar T2M (NASA POWER)", "source_id": "nasa.power.monthly",
      "params": { "native_code": "T2M", "start": "1991-01", "end": "2025-12" }, "inputs": [], "produces": "series", "cacheable": true },
    { "node_id": "n2", "op": "normalize", "label": "Normalizar unidades y calendario", "params": { "unit": "degC" }, "inputs": ["n1"], "produces": "series", "cacheable": false },
    { "node_id": "n3", "op": "qa", "label": "Cobertura y faltantes", "params": { "checks": ["Q01", "Q11"] }, "inputs": ["n2"], "produces": "series", "cacheable": false },
    { "node_id": "n4", "op": "transform", "label": "Climatología 1991–2020", "params": { "kind": "climatology", "baseline": ["1991-01", "2020-12"] }, "inputs": ["n3"], "produces": "climatology", "cacheable": false },
    { "node_id": "n5", "op": "transform", "label": "Anomalías mensuales", "params": { "kind": "anomaly", "window": ["2006-01", "2025-12"] }, "inputs": ["n3", "n4"], "produces": "series", "cacheable": false },
    { "node_id": "n6", "op": "analyze", "label": "Pendiente de Sen", "algorithm_id": "sen", "params": {}, "inputs": ["n5"], "produces": "estimate", "cacheable": false },
    { "node_id": "n7", "op": "analyze", "label": "Intervalo de confianza de Sen", "algorithm_id": "sen_interval", "params": { "level": 0.95 }, "inputs": ["n5"], "produces": "estimate", "cacheable": false },
    { "node_id": "n8", "op": "analyze", "label": "Mann-Kendall estacional", "algorithm_id": "seasonal_mann_kendall", "params": { "seasons": "month" }, "inputs": ["n5"], "produces": "test", "cacheable": false },
    { "node_id": "n9", "op": "validate", "label": "Controles científicos", "params": { "checks": ["Q02", "Q03", "Q12"] }, "inputs": ["n4", "n6", "n7", "n8"], "produces": "validation", "cacheable": false },
    { "node_id": "n10", "op": "assemble", "label": "Hallazgos y resultado", "params": {}, "inputs": ["n3", "n5", "n6", "n7", "n8", "n9"], "produces": "result", "cacheable": false }
  ],
  "checks": ["Q01", "Q02", "Q03", "Q11", "Q12"],
  "eligibility": [],
  "blocked": [],
  "execution_mode": "sync",
  "estimated": { "fetch_nodes": 1, "cached_nodes": 0, "external_waits": 0 },
  "warnings": [ { "code": "FETCH_EXTENDED", "message": "Se descarga desde 1991 para calcular la climatología de referencia." } ]
}
```

*Los `node_id` reales son huellas; se abrevian para la lectura.*

---

## 5. `JobStatus`

```json
{
  "schema_version": "2.0",
  "job_id": "job_7f3c2a",
  "plan_id": "sha256:41ab…",
  "state": "running",
  "progress": { "done_nodes": 4, "total_nodes": 10, "current": { "node_id": "n5", "label": "Anomalías mensuales" } },
  "nodes": [
    { "node_id": "n1", "state": "completed", "cache_status": "miss", "attempts": 1 },
    { "node_id": "n5", "state": "running" }
  ],
  "started_at": "2026-11-15T14:02:11Z",
  "updated_at": "2026-11-15T14:02:14Z",
  "partial_result_available": true,
  "error": null
}
```

`state`: `queued | running | waiting_external | completed | partial | failed | cancelled`.
Estado de nodo: `pending | ready | running | waiting_external | completed | failed | skipped | cancelled`.

---

## 6. `AnalysisResult`

| Campo | Tipo | Descripción |
|---|---|---|
| `schema_version` | `"2.0"` | |
| `result_id`, `job_id`, `plan_id`, `request_hash` | string | |
| `status` | `"completed" | "partial" | "failed" | "unsupported" | "cancelled"` | |
| `request` | `AnalysisRequest` canónica | |
| `summary` | `{headline_key, values}` | Clave de plantilla + valores; **no** texto libre generado |
| `findings[]` | `ScientificFinding` | |
| `series[]` | `SeriesBlock` | Datos para graficar |
| `method_results[]` | `MethodResultBlock` | Salida de cada método, con versión |
| `forecasts[]` | `ForecastBlock` | |
| `validation[]` | `ValidationStatus` | |
| `sources[]` | `SourceUse` | Procedencia completa |
| `how_computed[]` | `Step` | Pasos ordenados para «Cómo se calculó» |
| `visualization[]` | `VizHint` | Metadatos de presentación |
| `warnings[]`, `errors[]` | objeto | |
| `versions` | `{knowledge, handler, methods{}, models{}}` | |
| `timing` | `{started_at, finished_at}` | |

### 6.1 `ScientificFinding`

| Campo | Tipo | Valores |
|---|---|---|
| `finding_id` | string | |
| `phenomenon_id` | string \| null | |
| `finding_type` | enum | `descriptive | trend | anomaly | event | change_point | association | forecast | scenario | extrapolation | data_gap` |
| `variable_ids` | string[] | |
| `statement_key` | string | Plantilla de texto versionada (i18n) |
| `values` | objeto | Magnitud, unidad, IC, p, p ajustada, método, período |
| `conclusiveness` | enum | `conclusive | inconclusive | insufficient_data` |
| `evidence_level` | enum | `observation | association | consistent_with_hypothesis | validated_prediction | causal` (*`causal` nunca se emite*) |
| `exploratory` | bool | |
| `allowed_claims` | string[] | De la planilla, columna J |
| `forbidden_claims` | string[] | De la planilla, columna K |
| `alternatives` | string[] | Explicaciones alternativas y variables de confusión |
| `limitations` | string[] | |
| `operational_disclaimer` | bool | Q14 |
| `supported_by` | `{node_ids[], validation_ids[]}` | |

### 6.2 `ValidationStatus`

```json
{
  "validation_id": "v3",
  "check_id": "Q03",
  "title": "Tendencia y significación",
  "status": "pass",
  "applies_to": { "node_ids": ["n6", "n7", "n8"], "variable_id": "air_temperature_2m_mean" },
  "measured": { "p_value": 0.012, "p_method": "seasonal_mann_kendall", "ci_excludes_zero": true },
  "threshold": { "alpha": 0.05, "origin": "request.scientific_params.significance_alpha" },
  "message_key": "q03.pass",
  "on_fail_output": "No concluyente"
}
```

`status`: `pass | warn | block | not_applicable`.

### 6.3 `SeriesBlock`, `SourceUse`, `VizHint`

```json
{
  "series_id": "s1",
  "variable_id": "air_temperature_2m_mean",
  "role": "target",
  "kind": "anomaly",
  "unit": "degC",
  "frequency": "monthly",
  "time": ["2006-01-01", "2006-02-01"],
  "values": [0.4, -0.2],
  "valid": [true, true],
  "source_ref": "src1",
  "coverage_fraction": 1.0,
  "node_id": "n5"
}
```

```json
{
  "source_ref": "src1",
  "source_id": "nasa.power.monthly",
  "provider": "NASA LaRC POWER",
  "product": "POWER Monthly",
  "version": "unverified",
  "kind": "reanalysis",
  "native_code": "T2M",
  "unit_native": "degC",
  "unit_normalized": "degC",
  "conversions": [],
  "resolution": { "native": "0.5x0.625 deg", "effective_m": 50000 },
  "geometry_used": { "type": "Point", "coordinates": [-66.3356, -33.2950] },
  "entity": null,
  "period_requested": ["1991-01", "2025-12"],
  "period_returned": ["1991-01", "2025-12"],
  "retrieved_at": "2026-11-15T14:02:12Z",
  "cache_status": "miss",
  "url": "https://power.larc.nasa.gov/…",
  "substitution": { "required_product": "X02", "used_product": "X03", "same_quantity": true },
  "demo": false
}
```

```json
{
  "viz_id": "z1",
  "kind": "timeseries_trend",
  "title_key": "viz.trend.title",
  "series_refs": ["s1"],
  "overlays": [
    { "type": "trend_line", "method_ref": "m1" },
    { "type": "confidence_band", "method_ref": "m2", "level": 0.95 }
  ],
  "axes": { "x": "time", "y": { "unit": "degC", "label_key": "var.air_temperature_2m_mean.anomaly" } },
  "badges": ["reanalysis", "point_sample"],
  "legend_note_key": "note.not_lst"
}
```

`VizHint.kind`: `timeseries | timeseries_trend | anomaly_bars | spi_states | multi_panel_aligned | scatter | lag_correlogram | forecast_fan | scenario_lines | probability_bars | map_points | map_entities | map_raster | table`.

Los algoritmos **no** conocen `VizHint`: lo arma `findings.py` a partir del tipo de hallazgo. El frontend elige el componente por `kind`; un `kind` desconocido cae a `table`.

### 6.4 `ForecastBlock`

| Campo | Descripción |
|---|---|
| `forecast_id`, `model_id`, `model_version` | |
| `mode` | `validated_forecast | conditional_scenario | exploratory_extrapolation` |
| `target_variable`, `unit`, `frequency` | |
| `issue_time`, `valid_times[]` | |
| `central[]` | Estimación central (mediana o media, indicada en `central_kind`) |
| `quantiles` | `{ "0.05": [...], "0.95": [...] }` o `null` |
| `interval` | `{ level, empirical_coverage, calibrated: bool }` o `null` |
| `event` | `{ definition, probability[], calibrated }` o `null`; **no** se inventan probabilidades para variables continuas |
| `horizon_validated` | Máximo horizonte con evidencia |
| `baseline` | `{ id, values[], metrics }` |
| `skill_vs_baseline` | Por horizonte |
| `metrics_on_holdout` | MAE, RMSE, sesgo |
| `not_superior_to_baseline` | bool |
| `training_period`, `n_training` | |
| `inputs_from_models[]` | Predicciones usadas como entrada |
| `uncertainty_propagation` | `ensemble_members | residual_based | not_propagated` |
| `assumptions[]` | Supuestos del escenario |

---

## 7. Descriptores

- **`AlgorithmDescriptor`** y **`ModelDescriptor`**: campos en `03_ALGORITHM_HANDLER.md` §7 y §8.
- **`DataSourceDescriptor`**: campos y ejemplo en `07_MATRIZ_FUENTES.md` §4.

## 8. `Capabilities` (respuesta de `get_capabilities`)

```json
{
  "schema_version": "2.0",
  "knowledge_version": "2026.11.0",
  "fingerprint": "sha256:77d0…",
  "analysis_kinds": ["descriptive", "trend", "anomaly", "multivariable", "forecast", "scenario", "composite"],
  "phenomena": [
    {
      "id": "N1.1.0", "level": "N1", "family": "N1.1", "priority": "MVP",
      "title": { "es": "Tendencia de temperatura del aire y LST (por separado)" },
      "availability": "partial",
      "branches": [
        { "name": "T2m", "state": "available", "variables": ["air_temperature_2m_mean"] },
        { "name": "LST", "state": "blocked", "reason_code": "RAW_ONLY" }
      ],
      "recipes": ["R-TREND"],
      "prediction": { "catalog_mode": "derived_from_forecast", "enabled_horizons": [] },
      "forbidden_claims": ["No confundir LST con temperatura del aire"]
    }
  ],
  "variables": [ { "variable_id": "air_temperature_2m_mean", "unit": "degC", "sources": ["nasa.power.monthly", "noaa.ncei.station"] } ],
  "recipes": [ { "recipe_id": "R-TREND", "params_schema": { "…": "…" } } ],
  "sources": [ { "source_id": "nasa.firms.area", "connection_state": "unverified_auth", "credentials_present": false } ],
  "models": [],
  "parameter_limits": { "max_variables": 10, "max_phenomena": 5, "max_period_years": 90 },
  "unsupported_examples": [ { "code": "EXACT_IGNITION_LOCATION", "alternatives": ["B9.2", "B9.1"] } ]
}
```

`availability`: `available | partial | historical_only | blocked | unsupported`.
Parámetro `scope`: `{ priority?, level?, family?, phenomenon_ids?, include?: ["phenomena","variables","sources","models","recipes"] }`.

---

## 9. Errores

```json
{
  "code": "TEMPORAL_INCOMPATIBLE",
  "message_key": "error.temporal_incompatible",
  "detail": { "source_id": "nasa.swot.hydrocron", "product_start": "2022-12-16", "requested_start": "2005-01-01" },
  "recoverable": false,
  "scope": { "variable_id": "water_surface_elevation", "node_id": null },
  "suggestions": [
    { "action": "use_source", "source_id": "argentina.ina.series", "note": "Altura hidrométrica de estación para series largas (verificar datum)." },
    { "action": "shorten_period", "start": "2022-12-16" }
  ]
}
```

| Código | Significado | ¿Recuperable? |
|---|---|---|
| `INVALID_REQUEST` | No cumple el esquema o las combinaciones permitidas | No |
| `UNSUPPORTED` | Fuera de los límites científicos o de las capacidades | No |
| `NOT_AUTOMATABLE` | El recurso es un portal o documento, no una API (T21) | No |
| `INSUFFICIENT_DATA` | No alcanza cobertura o historia | No |
| `SOURCE_UNAVAILABLE` | La fuente no respondió tras los reintentos | Sí (más tarde) |
| `CREDENTIALS_MISSING` | Falta la credencial de la fuente (T19) | Sí (al configurarla) |
| `TEMPORAL_INCOMPATIBLE` | El período no es cubierto por el producto (T12) | No |
| `SPATIAL_INCOMPATIBLE` | Escalas no conciliables o geometría no admitida (T13) | No |
| `UNIT_INCOMPATIBLE` | Unidades o datum sin conversión registrada (T15) | No |
| `METHOD_NOT_AVAILABLE` | Falta una dependencia opcional | No |
| `MODEL_NOT_ELIGIBLE` | No hay modelo habilitado para ese alcance u horizonte | No |
| `LEAKAGE_BLOCKED` | Un predictor no estaba disponible en la emisión (T10) | No |
| `TIMEOUT` | Se superó el tiempo del nodo o del job | Sí |
| `CANCELLED` | Cancelado por el usuario | — |
| `INTERNAL` | Error inesperado (con identificador de registro) | — |

Los comandos nuevos devuelven **siempre** un objeto (resultado o `{ "error": Error }`); no dependen del texto de `InvokeException`. Los comandos existentes conservan su comportamiento.

---

## 10. Comandos (API)

| Comando | Entrada | Salida | Red | Uso |
|---|---|---|---|---|
| `get_capabilities` | `{ scope? }` | `Capabilities` | No | IA y configurador |
| `validate_request` | `{ request }` | `ValidationReport` | No | Validación en vivo; aclaraciones |
| `plan_analysis` | `{ request }` | `AnalysisPlan` | No | Vista previa del plan |
| `submit_analysis` | `{ request, wait_ms? }` | `JobStatus` (+ `result` si terminó dentro de `wait_ms`) | Sí | Ejecución |
| `job_status` | `{ job_id }` | `JobStatus` | No | Sondeo |
| `job_result` | `{ job_id }` | `AnalysisResult` (puede ser `partial`) | No | Resultado |
| `cancel_job` | `{ job_id }` | `JobStatus` | No | Cancelación |
| `list_results` | `{ limit? }` | Resumen de resultados guardados | No | Historial |

**No se duplican comandos existentes:**

| Existente | Relación con los nuevos |
|---|---|
| `acquire_data` | Se conserva como vía heredada hasta completar el recorrido 1; después el frontend deja de usarlo para análisis |
| `evaluate_coverage` | Su lógica pasa al `SourceSelector`; el comando se mantiene para el asistente actual hasta que JP migre a `validate_request` |
| `search_places`, `list_appeears`, `list_ina_variables` | Se reutilizan sin cambios |
| `execute_regression` | Heredado, sin nuevos usos |
| `interpret_question`, `assistant_*` | Se reutilizan; cambia el contrato de salida del asistente (ver `11_INTEGRACION_IA_FRONTEND.md`) |

**Operaciones simples vs extensas:** `submit_analysis` con `wait_ms` (p. ej. 3000) devuelve el resultado en la misma llamada si el plan es `sync` y termina a tiempo; en otro caso devuelve el `JobStatus` y el frontend sondea. Un único camino de código para ambos casos.

---

## 11. Compatibilidad entre modo manual e IA

| Aspecto | Regla |
|---|---|
| Esquema | El mismo JSON Schema de `AnalysisRequest` valida el formulario y la salida de la IA |
| Normalización | `canonical.normalize` se aplica a ambos; los campos de presentación quedan fuera de la huella |
| Lugares | Ambos resuelven nombres con `search_places` y envían **coordenadas**; el nombre no entra en la huella |
| Valores por defecto | Los aplica **solo el backend**; ni el formulario ni la IA rellenan valores por defecto por su cuenta |
| Prueba | T17: dos solicitudes equivalentes ⇒ mismo `request_hash` ⇒ mismo `plan_id` ⇒ mismos resultados numéricos |

---

## 12. Migración desde `cfg_data.json` (schemaVersion 1)

- `cfg_data.json` sigue siendo el **estado del espacio de trabajo** (lo que el usuario está editando); `AnalysisRequest` es lo que se **envía**.
- Se agrega a `cfg_data` una sección `analysis` (versión 2 del archivo) con fenómenos, variables canónicas, parámetros científicos y horizonte. `sources[]` actual se conserva como preferencia de fuente.
- `requestBuilder` (frontend) convierte `cfg_data` v2 → `AnalysisRequest`. La migración v1 → v2 se hace en `configuration.js: loadWorkspace`, donde ya viven las migraciones.
- `methods: []` deja de usarse y `validate_investigation` conserva su rechazo para la vía heredada.
