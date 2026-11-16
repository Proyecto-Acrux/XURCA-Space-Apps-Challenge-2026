# 10 — Casos de uso end-to-end

Diez simulaciones conceptuales para comprobar la arquitectura. Cada caso tiene los diez apartados pedidos.

> **Advertencia:** todos los valores numéricos de los resultados son **marcadores ilustrativos** (`"<…>"` o claramente rotulados). No son resultados ambientales reales: ningún análisis fue ejecutado.

Convenciones: los JSON canónicos se muestran **después** de aplicar valores por defecto, abreviados a los campos relevantes. Los `node_id` se abrevian.

---

## Caso 1 — Tendencia de temperatura

### 1. Solicitud inicial
«Quiero analizar cómo cambió la temperatura del aire en San Luis durante los últimos 20 años».

### 2. JSON canónico
```json
{
  "schema_version": "2.0",
  "analysis": { "kind": "trend", "phenomenon_ids": ["N1.1.0"] },
  "location": { "geometry": { "type": "Point", "coordinates": [-66.3356, -33.295] }, "crs": "EPSG:4326", "spatial_mode": "point" },
  "period": { "start": "2006-01-01", "end": "2025-12-31" },
  "variables": [ { "variable_id": "air_temperature_2m_mean", "role": "target" } ],
  "temporal": { "frequency": "monthly" },
  "uncertainty": { "confidence_level": 0.95 },
  "scientific_params": { "baseline_period": { "start": "1991-01-01", "end": "2020-12-31" }, "min_coverage": 0.8, "significance_alpha": 0.05 }
}
```

### 3. Resolución científica
- **Interpretación:** "temperatura del aire" → `air_temperature_2m_mean` (no LST). "Cómo cambió" → `trend`. Coincide con N1.1.0, rama T2m.
- **Ambigüedad:** "San Luis" puede ser ciudad o provincia. `search_places` devuelve ambos → la IA pregunta. Si es la provincia, el sistema informa que **hoy no hay promedio de área** y ofrece un punto representativo o varios puntos (D-20).
- **"Últimos 20 años":** se ajusta a años cerrados (2006–2025) porque la fuente termina en el último año completo; queda como `assumption`.
- **Escala:** mensual (receta `R-TREND`). Punto.

### 4. Fuentes seleccionadas
| Variable | Elegida | Motivo | Alternativa |
|---|---|---|---|
| T2m media | `nasa.power.monthly` (`T2M`) | Serie mensual por punto desde 1981: cubre la base 1991–2020 y el período | `noaa.ncei.station` (`TAVG`), observación de estación, sujeta a cobertura |

`source_substitution`: el catálogo requiere X02 (ERA5); se usa X03 (POWER), listado como opcional. Misma magnitud física. Se rotula "reanálisis, no observación" y resolución efectiva ~50 km.

### 5. DAG
`fetch(T2M 1991–2025)` → `normalize` → `qa(Q01,Q11)` → `climatology(1991–2020)` → `anomaly(2006–2025)` → { `sen`, `sen_interval`, `seasonal_mann_kendall` } → `validate(Q02,Q03,Q12)` → `assemble`. (Plan completo en `09_CONTRATOS_JSON_API.md` §4.)

### 6. Algoritmos
`sen` (existente), `seasonal_mann_kendall` (existente), `modified_mann_kendall` si hay autocorrelación y la dependencia está instalada, climatología/anomalía (N01, nuevo), IC de Sen (N02, nuevo).

### 7. Validaciones
Q01 cobertura ≥ 0.8 · Q02 base fija y misma estación del año · Q03 IC + magnitud además de p; no significación ≠ ausencia de cambio · Q11 unidad °C · Q12 tendencia ≠ evento.

### 8. Estados de error posibles
`missing: location` (ambigüedad) · `SOURCE_UNAVAILABLE` (POWER caído → se ofrece NOAA) · `INSUFFICIENT_DATA` (cobertura < 0.8) · `METHOD_NOT_AVAILABLE` (sin `pymannkendall` → MK estacional con advertencia).

### 9. Resultado JSON ilustrativo
```json
{
  "schema_version": "2.0",
  "status": "completed",
  "summary": { "headline_key": "trend.headline", "values": { "variable_id": "air_temperature_2m_mean", "period": ["2006", "2025"] } },
  "findings": [
    {
      "finding_id": "f1",
      "phenomenon_id": "N1.1.0",
      "finding_type": "trend",
      "variable_ids": ["air_temperature_2m_mean"],
      "statement_key": "trend.sen.decadal",
      "values": {
        "slope": "<pendiente>", "unit": "degC/decade",
        "ci_low": "<límite inferior>", "ci_high": "<límite superior>", "confidence_level": 0.95,
        "p_value": "<p>", "p_method": "seasonal_mann_kendall",
        "period": ["2006-01", "2025-12"], "n_valid": "<n>"
      },
      "conclusiveness": "<conclusive | inconclusive según p e IC>",
      "evidence_level": "observation",
      "exploratory": false,
      "allowed_claims": ["Reportar pendiente °C/década, IC, p ajustada y período; no significación = evidencia insuficiente"],
      "forbidden_claims": ["No confundir LST con temperatura del aire"],
      "limitations": ["Reanálisis en un punto; no representa el promedio provincial.", "Período de 20 años."],
      "supported_by": { "node_ids": ["n6", "n7", "n8"], "validation_ids": ["v1", "v2", "v3"] }
    }
  ],
  "validation": [
    { "validation_id": "v1", "check_id": "Q01", "status": "<pass|block>", "measured": { "coverage_fraction": "<valor>" }, "threshold": { "min_coverage": 0.8 } },
    { "validation_id": "v3", "check_id": "Q03", "status": "<pass|warn>" }
  ],
  "visualization": [
    { "viz_id": "z1", "kind": "timeseries_trend", "series_refs": ["s1"], "overlays": [ { "type": "trend_line" }, { "type": "confidence_band", "level": 0.95 } ], "badges": ["reanalysis", "point_sample"] },
    { "viz_id": "z2", "kind": "map_points", "badges": ["point_sample"] }
  ]
}
```

### 10. Presentación frontend
- Serie mensual de anomalías con línea de Sen y banda del IC; etiqueta de pendiente en °C/década.
- Si el hallazgo es `inconclusive`: texto «No hay evidencia suficiente de tendencia en este período», nunca «sin cambios».
- Mapa con el punto y la insignia «punto único».
- Insignias: «Reanálisis», «NASA POWER».
- Botón «Cómo se calculó»: fuente, base climatológica, métodos y versiones, cobertura, sustitución de producto.

---

## Caso 2 — Precipitaciones, humedad del suelo y vegetación

### 1. Solicitud inicial
«Quiero saber si la disminución de precipitaciones se relaciona con cambios en humedad del suelo y NDVI».

### 2. JSON canónico
```json
{
  "schema_version": "2.0",
  "analysis": { "kind": "multivariable", "phenomenon_ids": ["B2.2"] },
  "location": { "geometry": { "type": "Point", "coordinates": ["<lon>", "<lat>"] }, "spatial_mode": "point" },
  "period": { "start": "<inicio>", "end": "<fin>" },
  "variables": [
    { "variable_id": "ndvi", "role": "target" },
    { "variable_id": "precipitation_total", "role": "explanatory" },
    { "variable_id": "soil_moisture_rootzone", "role": "explanatory", "attributes": { "depth": "28-100cm" } }
  ],
  "temporal": { "frequency": "monthly" },
  "scientific_params": { "lags": { "unit": "month", "candidates": [0, 1, 2, 3] }, "significance_alpha": 0.05 }
}
```
*Los `"<…>"` se reemplazan por valores reales; la solicitud real contiene números.*

### 3. Resolución científica
- **Dos preguntas en una:** (a) ¿disminuyó la precipitación? → operación `trend` sobre precipitación; (b) ¿se relaciona con humedad y NDVI? → operación `multivariable`. Resultado: análisis `composite`.
- **Fenómeno:** B2.2 (estrés vegetal asociado a déficit de agua). B3.5 es candidato si interesa además el nivel de agua: se sugiere, no se fuerza.
- **Faltantes:** ubicación y período → aclaración.
- **Cruce:** se correlacionan **anomalías estacionales**, no valores crudos. Correlacionar series con estacionalidad compartida produce asociaciones altas y triviales.
- **Desfases:** lista predefinida del fenómeno (estado `proposed`, D-03). **No** se elige el desfase de máxima correlación.

### 4. Fuentes seleccionadas
| Variable | Elegida | Nota |
|---|---|---|
| Precipitación | `openmeteo.archive.daily` (`precipitation_sum`, ERA5) agregada a mes | Sustituye a IMERG (X01); rotulado reanálisis. Descarga troceada (EZE-11) |
| Humedad del suelo | `openmeteo.archive.daily` (28–100 cm, ERA5-Land) | **Modelo**, no observación SMAP; profundidad explícita |
| NDVI | `nasa.appeears` MOD13Q1, extracción por punto | Requiere procesador (EZE-12) y credencial; 16 días → mensual |

POWER `GWETROOT` **se descarta** para humedad: es fracción de saturación, no humedad volumétrica.

### 5. DAG
Ver diagrama D9 en `04_DIAGRAMAS.md`. La precipitación se descarga una vez y alimenta la tendencia y la asociación.

### 6. Algoritmos
`sen` + `mann_kendall` (tendencia de precipitación) · climatología/anomalías (N01) · correlación con desfases y tamaño efectivo de muestra (N05) · FDR (N06) · `multivariable` con diseño de rezagos (existente).

### 7. Validaciones
Q01 · Q02 · Q04 (FDR sobre la familia de desfases; si se seleccionara por máxima r → exploratorio) · Q05 (tasa vs acumulado) · Q06 (QA de NDVI) · Q09 (resolución efectiva = la más gruesa, ~9–25 km; NDVI de 250 m se interpreta a esa escala) · Q10 (calendarios y compuestos de 16 días) · Q13 (asociación, no causalidad) · Q17 (cosecha, cambio de uso).

**Contra correlaciones engañosas:** anomalías en lugar de valores crudos; tamaño efectivo de muestra por autocorrelación; desfases predefinidos; FDR; análisis de sensibilidad (cambiar base y período) informado en el resultado.

### 8. Estados de error posibles
`CREDENTIALS_MISSING` (AppEEARS) → resultado `partial` con precipitación–humedad · `waiting_external` (tarea AppEEARS en curso) · `INSUFFICIENT_DATA` (NDVI con nubes: cobertura < 0.8, T06) · `SPATIAL_INCOMPATIBLE` si se pidiera interpretar a 250 m.

### 9. Resultado JSON ilustrativo
```json
{
  "status": "completed",
  "findings": [
    { "finding_id": "f1", "finding_type": "trend", "variable_ids": ["precipitation_total"],
      "values": { "slope": "<pendiente>", "unit": "mm/decade", "p_value": "<p>" },
      "conclusiveness": "<según resultado>", "evidence_level": "observation" },
    { "finding_id": "f2", "phenomenon_id": "B2.2", "finding_type": "association",
      "variable_ids": ["ndvi", "precipitation_total", "soil_moisture_rootzone"],
      "statement_key": "association.lagged",
      "values": {
        "lags_tested": [0, 1, 2, 3], "lag_unit": "month",
        "by_lag": [ { "pair": ["precipitation_total", "ndvi"], "lag": 1, "r": "<r>", "p": "<p>", "q": "<q ajustado>", "n_effective": "<n>" } ],
        "multiple_testing": { "method": "benjamini_hochberg", "family_id": "B2.2.lags", "n_tests": 8 },
        "lag_selection": "predefined"
      },
      "conclusiveness": "<según q>",
      "evidence_level": "association",
      "exploratory": false,
      "allowed_claims": ["Disminución vigor coincide/precedida por déficit hídrico; hipótesis explícita"],
      "forbidden_claims": ["No declarar causalidad mediante correlación simple"],
      "alternatives": ["cosecha", "cambio de uso del suelo", "incendio", "temperatura"],
      "limitations": ["Humedad del suelo modelada (ERA5-Land), no observada.", "Escala efectiva ~9–25 km.", "Un solo punto."] }
  ]
}
```

### 10. Presentación frontend
- Panel de tres series alineadas (anomalías), eje temporal común.
- Correlograma por desfase con los desfases probados y los que superan el control de pruebas múltiples.
- Etiqueta permanente: «Asociación estadística. No demuestra causa».
- Lista «Otras explicaciones posibles».
- Advertencia de escala: «Interpretado a la resolución de la fuente más gruesa».

---

## Caso 3 — Predicción de vegetación

### 1. Solicitud inicial
«¿Cómo podría evolucionar el NDVI durante los próximos dos meses?».

### 2. JSON canónico
```json
{
  "schema_version": "2.0",
  "analysis": { "kind": "forecast", "phenomenon_ids": ["N1.3.0"] },
  "location": { "geometry": { "type": "Point", "coordinates": ["<lon>", "<lat>"] } },
  "variables": [ { "variable_id": "ndvi", "role": "target" } ],
  "temporal": { "frequency": "16-day" },
  "issue_time": "2026-11-15T00:00:00Z",
  "forecast": { "horizon": { "value": 2, "unit": "month" }, "mode": "auto" },
  "uncertainty": { "interval_level": 0.9 }
}
```

### 3. Resolución científica
- N1.3.0 admite predicción en el catálogo (`direct_forecast`, familia M3, línea PRED-02).
- **Modelo:** `pred02.ndvi.arx` (autorregresivo con estacionalidad y predictores **rezagados**; baseline climatología).
- **Datos históricos:** serie NDVI con QA; cuántos años como mínimo es D-03.
- **Variables futuras:** el modelo usa solo predictores anteriores a `issue_time`. Lluvia o humedad **futuras observadas** están prohibidas (restricción de PRED-02). Si el usuario quiere condicionar a un supuesto ("si llueve por debajo de lo normal") → `conditional_scenario`.
- **Validación del horizonte:** backtest rolling-origin; el horizonte de prueba de la planilla (1 período–2 meses) **no** es un horizonte validado.

### 4. Fuentes seleccionadas
NDVI: `nasa.appeears` MOD13Q1 (punto). Predictores: precipitación y humedad (Open-Meteo), T2m (POWER), solo valores con `available_at ≤ issue_time`.

### 5. DAG
`fetch(NDVI)` → `normalize + QA` → `qa(Q01,Q06)` → `eligibility` → `backtest(pred02, h=1..4 períodos)` → { `fit` → `predict` → `intervals` } → `validate(Q15,Q16)` → `assemble`. Predictores: `fetch` → `normalize` → `lag` → entran a `backtest` y `fit`.

### 6. Algoritmos
`multivariable` o ridge con matriz de predictores (D-23) · baselines (N09) · backtesting (N07) · intervalos (N08).

### 7. Validaciones
Q15 (transformaciones ajustadas solo en entrenamiento; `feature_available_at ≤ issue_time`) · Q16 (intervalos con cobertura empírica; si no supera al baseline, bandera) · Q06 · Q01 · Q17 (enmascarar cosecha).

### 8. Estados de error posibles
| Situación | Respuesta |
|---|---|
| **Hoy:** no hay modelo registrado ni procesador de NDVI | `MODEL_NOT_ELIGIBLE` + alternativa: análisis histórico de NDVI cuando haya datos |
| Historia insuficiente | Solo descriptivo; se informa cuánto falta |
| Backtest válido hasta 1 período | 1 período como `validated_forecast`; el resto, si se acepta, `exploratory_extrapolation` sin intervalo |
| Modelo no supera a la climatología | Se muestra la climatología con `not_superior_to_baseline` |
| Predictor posterior a la emisión | `LEAKAGE_BLOCKED` para ese predictor |

### 9. Resultado JSON ilustrativo
```json
{
  "status": "completed",
  "forecasts": [
    {
      "forecast_id": "fc1", "model_id": "pred02.ndvi.arx", "model_version": "<versión>",
      "mode": "validated_forecast",
      "target_variable": "ndvi", "unit": "1", "frequency": "16-day",
      "issue_time": "2026-11-15T00:00:00Z",
      "valid_times": ["<t+1>", "<t+2>"],
      "central_kind": "median", "central": ["<valor>", "<valor>"],
      "quantiles": { "0.05": ["<valor>", "<valor>"], "0.95": ["<valor>", "<valor>"] },
      "interval": { "level": 0.9, "empirical_coverage": "<cobertura>", "calibrated": "<bool>" },
      "event": null,
      "horizon_validated": { "value": 2, "unit": "period" },
      "baseline": { "id": "climatology", "values": ["<valor>", "<valor>"] },
      "skill_vs_baseline": ["<skill h1>", "<skill h2>"],
      "not_superior_to_baseline": false,
      "inputs_from_models": [],
      "uncertainty_propagation": "residual_based"
    },
    {
      "forecast_id": "fc2", "mode": "exploratory_extrapolation",
      "valid_times": ["<t+3>", "<t+4>"], "central": ["<valor>", "<valor>"],
      "quantiles": null, "interval": null,
      "horizon_validated": { "value": 2, "unit": "period" }
    }
  ],
  "findings": [
    { "finding_id": "f1", "finding_type": "forecast", "evidence_level": "validated_prediction",
      "forbidden_claims": ["NDVI no equivale a biomasa ni a salud ecológica completa"] }
  ]
}
```

### 10. Presentación frontend
- Gráfico de abanico: observado, mediana y banda del 90%; línea del baseline.
- Etiqueta de modo visible: «Pronóstico (validado hasta 2 períodos)» y, separado visualmente con trazo punteado y sin banda, «Tendencia extrapolada (experimental)».
- Indicador de habilidad frente a la climatología.
- Sin porcentaje de "confianza".

---

## Caso 4 — Fuego

### 1. Solicitud inicial
«Quiero analizar la relación entre temperatura, precipitaciones, humedad de suelo, vegetación y actividad histórica de fuego».

### 2. JSON canónico
```json
{
  "schema_version": "2.0",
  "analysis": { "kind": "multivariable", "phenomenon_ids": ["B9.1"] },
  "location": { "geometry": { "type": "Polygon", "coordinates": ["<anillo>"] }, "spatial_mode": "auto" },
  "period": { "start": "<inicio>", "end": "<fin>" },
  "variables": [
    { "variable_id": "active_fire_detections", "role": "target", "attributes": { "sensor": "VIIRS_SNPP" } },
    { "variable_id": "burned_area", "role": "target" },
    { "variable_id": "air_temperature_2m_mean", "role": "explanatory" },
    { "variable_id": "precipitation_total", "role": "explanatory" },
    { "variable_id": "soil_moisture_rootzone", "role": "explanatory" },
    { "variable_id": "ndvi", "role": "explanatory" }
  ],
  "temporal": { "frequency": "monthly" }
}
```

### 3. Resolución científica
El sistema obliga a distinguir cinco conceptos, cada uno con variable y leyenda propias:

| Concepto | Variable / producto | Fenómeno | Estado |
|---|---|---|---|
| Condiciones meteorológicas | T2m, precipitación, humedad del suelo | N1.1.0, N1.2.0, N1.5.0 | Disponible |
| Peligro meteorológico | Índice FWI | B9.2 | No disponible (falta N12 y variables diarias) |
| Detecciones térmicas | `active_fire_detections`, FIRMS | N1.4.0 | Disponible con clave |
| Actividad de fuego definida | Evento por celda y ventana con máscara de observabilidad | M6A | No implementado |
| Área quemada | `burned_area`, MCD64A1 | N1.4C | Bloqueado (procesador de área) |

Fenómeno: B9.1. Humedad del suelo y NDVI no figuran entre sus variables: se agregan como explicativas **declaradas por el usuario**, con hallazgo `exploratory: true`.

### 4. Fuentes seleccionadas
FIRMS (`nasa.firms.area`, por sensor) · MCD64A1 vía AppEEARS (bloqueado hasta EZE-13) · T2m (POWER) · precipitación y humedad (Open-Meteo) · NDVI (AppEEARS, EZE-12). Las series por punto se toman en el centroide del polígono, **con advertencia** de representatividad (D-20).

### 5. DAG
`fetch(FIRMS)` → `qa(Q07: sensor, confianza, duplicados)` → `count_by(mes, sensor)` ┐
`fetch(MCD64A1)` → `mask_qa` → `geodesic_area` → `aggregate(mes)` ┤→ `align` → `lagged_correlation` → `fdr` → `validate(Q04,Q07,Q08,Q13,Q14)` → `assemble`
`fetch(T, P, humedad, NDVI)` → `normalize` → `qa` → `anomaly` ┘

Detecciones y área quemada son **nodos y hallazgos separados**; ningún nodo convierte una en otra.

### 6. Algoritmos
Conteos por temporada (dataprep) · `sen`/`mann_kendall` sobre recuentos · área geodésica (dataprep) · N01, N05, N06.

### 7. Validaciones
Q07 (por sensor; "detección", no "fuego") · Q08 (área real; focos ≠ hectáreas) · Q04 · Q13 · Q14 (aviso de herramienta exploratoria + organismos oficiales) · Q18 (fracción de la región observada).

### 8. Estados de error posibles
`CREDENTIALS_MISSING` (FIRMS) con opción de datos de muestra rotulados si la solicitud lo permite (T19) · rama de área quemada `blocked` → `partial` · `UNSUPPORTED` si se pide dónde se iniciará un incendio (ver Caso 8).

### 9. Resultado JSON ilustrativo
```json
{
  "status": "partial",
  "findings": [
    { "finding_id": "f1", "finding_type": "descriptive", "variable_ids": ["active_fire_detections"],
      "statement_key": "fire.detections.count",
      "values": { "count": "<n>", "unit": "detections", "sensor": "VIIRS_SNPP", "period": ["<inicio>", "<fin>"] },
      "forbidden_claims": ["Cada foco NO es un incendio distinto ni hectárea quemada"],
      "operational_disclaimer": true },
    { "finding_id": "f2", "finding_type": "data_gap", "variable_ids": ["burned_area"],
      "statement_key": "gap.blocked_source",
      "values": { "code": "RAW_ONLY", "product": "MCD64A1" } },
    { "finding_id": "f3", "phenomenon_id": "B9.1", "finding_type": "association", "evidence_level": "association",
      "exploratory": true,
      "forbidden_claims": ["No inferir número de incendios desde detecciones FIRMS"],
      "operational_disclaimer": true }
  ],
  "visualization": [
    { "viz_id": "z1", "kind": "map_points", "title_key": "viz.fire.detections", "badges": ["detections_not_fires"] },
    { "viz_id": "z2", "kind": "timeseries", "title_key": "viz.fire.detections.monthly" }
  ]
}
```

### 10. Presentación frontend
- Capa de **detecciones** (puntos) y capa de **área quemada** (ráster) como capas, leyendas y unidades independientes (T04, T20).
- Rótulo: «Detecciones satelitales. No equivalen a incendios ni a hectáreas quemadas».
- Aviso fijo de herramienta exploratoria, no sistema de alerta.
- El peligro meteorológico aparece como «no disponible todavía».

---

## Caso 5 — Transformaciones ambientales urbanas

### 1. Solicitud inicial
«Quiero estudiar si la expansión urbana se relaciona con pérdida de vegetación y aumento de temperatura superficial».

### 2. JSON canónico
```json
{
  "schema_version": "2.0",
  "analysis": { "kind": "multivariable", "phenomenon_ids": ["B1.1", "B1.2"] },
  "location": { "geometry": { "type": "Polygon", "coordinates": ["<anillo>"] }, "spatial_mode": "grid" },
  "period": { "start": "<inicio>", "end": "<fin>" },
  "variables": [
    { "variable_id": "land_cover_class", "role": "explanatory" },
    { "variable_id": "ndvi", "role": "target" },
    { "variable_id": "land_surface_temperature_day", "role": "target", "attributes": { "overpass": "day" } }
  ]
}
```

### 3. Resolución científica
- B1.1 (expansión urbana y conversión de cobertura) + B1.2 (isla de calor superficial y pérdida de vegetación).
- **Tres resoluciones y tres ritmos:** cobertura MCD12Q1 (anual, ~500 m), NDVI MOD13Q1 (16 días, ~250 m), LST MOD11A2 (8 días, ~1 km). Escala común: **~1 km**, agregando; nunca al revés. Ritmo común: anual o estacional.
- "Temperatura superficial" → LST. El resultado no puede hablar de temperatura del aire.
- La transición a clase urbana debe **observarse** en la clasificación; no se deduce del NDVI.

### 4. Fuentes seleccionadas
Las tres vía `nasa.appeears`, extracción por área → **bloqueado hasta EZE-13**. Advertencia de `FUENTES_Y_ENLACES_v8`: MCD12Q1 "no suficiente para confirmar cambios a escala de parcela".

### 5. DAG
`fetch(MCD12Q1)` → `transition_matrix(año inicial, año final)` → `mask(celdas convertidas / no convertidas)`
`fetch(MOD13Q1)` → `mask_qa` → `aggregate(1 km, estacional)` ┐
`fetch(MOD11A2)` → `mask_qa` → `aggregate(estacional, día)` ┤→ `align` → `paired_difference(convertidas vs control)` → `bootstrap` → `validate` → `assemble`

### 6. Algoritmos
Matriz de transición (N15) · diferencial pareado + bootstrap (N11) · `sen` por grupo · `analyze_grid` con tope de celdas.

### 7. Validaciones
Q06 · Q09 · Q10 · Q13 · Q17 (comparar por clase y estación; separar cosecha y quema) · Q18 (no elegir solo píxeles favorables; informar área válida).

### 8. Estados de error posibles
**Hoy:** `blocked` por `RAW_ONLY` en las tres variables → resultado `unsupported` para este fenómeno con explicación y fecha de habilitación ligada a EZE-13 · `SPATIAL_INCOMPATIBLE` si el polígono es menor que unas pocas celdas de 1 km · límite de celdas excedido.

### 9. Resultado JSON ilustrativo
```json
{
  "status": "completed",
  "findings": [
    { "finding_id": "f1", "phenomenon_id": "B1.1", "finding_type": "descriptive",
      "statement_key": "landcover.transition",
      "values": { "from_class": "<clase>", "to_class": "urban", "area": "<km²>", "valid_area_fraction": "<fracción>" },
      "forbidden_claims": ["NDVI solo no prueba impermeabilización"] },
    { "finding_id": "f2", "phenomenon_id": "B1.2", "finding_type": "association",
      "statement_key": "paired.difference",
      "values": { "delta_lst": "<ΔLST>", "unit": "degC", "ci_low": "<…>", "ci_high": "<…>", "groups": ["converted", "control"], "effective_resolution_m": 1000 },
      "evidence_level": "association",
      "allowed_claims": ["Asociación consistente, no atribución única de temperatura"],
      "forbidden_claims": ["No afirmar isla de calor atmosférica a partir de LST"],
      "alternatives": ["tendencia regional de temperatura", "cambios de uso no urbanos", "diferencias de elevación"] }
  ]
}
```

### 10. Presentación frontend
- Mapa de transición de cobertura; mapa de ΔLST; ambos rotulados a 1 km.
- Comparación convertidas vs control con intervalo.
- Texto fijo: «No todos los cambios observados son consecuencia de la urbanización».

---

## Caso 6 — Variables oceánicas

### 1. Solicitud inicial
«Quiero analizar la relación entre temperatura superficial del océano y clorofila».

### 2. JSON canónico
```json
{
  "schema_version": "2.0",
  "analysis": { "kind": "multivariable", "phenomenon_ids": ["B5.3"] },
  "location": { "geometry": { "type": "Point", "coordinates": ["<lon>", "<lat>"] } },
  "period": { "start": "<inicio>", "end": "<fin>" },
  "variables": [
    { "variable_id": "sea_surface_temperature", "role": "target" },
    { "variable_id": "chlorophyll_a", "role": "explanatory" }
  ]
}
```

### 3. Resolución científica
B5.3 separa tres cosas:
- **Anomalía:** ola de calor marina = SST ≥ percentil 90 de la climatología diaria durante una duración mínima → hallazgo `event`.
- **Asociación:** anomalía de clorofila durante o después de los eventos → hallazgo `association`, con clorofila como variable **independiente**.
- **Predicción:** PRED-08 existe en la planilla pero choca con el catálogo (C05) → no se ofrece.

### 4. Fuentes seleccionadas
SST: `noaa.oisst.daily` (sustituye a GHRSST, X18; 0.25°). Clorofila: Ocean Color vía Earthdata → **RAW, sin procesador** → rama bloqueada.

### 5. DAG
`fetch(OISST)` → `qa` → `climatology(diaria)` → `events(≥P90, duración mínima)` → `validate(Q02,Q12)` → `assemble`. Rama de clorofila: `blocked`.

### 6. Algoritmos
N01 (climatología diaria) · N04 (eventos por percentil y duración) · N05 cuando haya clorofila.

### 7. Validaciones
Q02 · Q12 · Q13 · regla del fenómeno: «Clorofila alta NO significa marea roja tóxica».

### 8. Estados de error posibles
Punto en tierra → OISST sin valor → `INSUFFICIENT_DATA` · clorofila `blocked` → `partial` · pedido de predicción → `MODEL_NOT_ELIGIBLE` · pedido de detección de floraciones tóxicas → `UNSUPPORTED`.

### 9. Resultado JSON ilustrativo
```json
{
  "status": "partial",
  "findings": [
    { "finding_id": "f1", "phenomenon_id": "B5.3", "finding_type": "event",
      "statement_key": "marine_heatwave.events",
      "values": { "threshold": "P90", "n_events": "<n>", "events": [ { "start": "<fecha>", "end": "<fecha>", "duration_days": "<d>", "max_intensity": "<°C sobre el umbral>" } ] },
      "evidence_level": "observation" },
    { "finding_id": "f2", "finding_type": "data_gap", "variable_ids": ["chlorophyll_a"], "values": { "code": "RAW_ONLY" } }
  ],
  "warnings": [ { "code": "HAB_NOT_INFERABLE", "message_key": "warn.hab" } ]
}
```

### 10. Presentación frontend
Serie de SST con umbral y eventos sombreados; tabla de eventos; panel de clorofila «no disponible todavía»; advertencia fija sobre floraciones tóxicas.

---

## Caso 7 — Datos insuficientes

### 1. Solicitud inicial
«Quiero analizar 20 años de observaciones de SWOT».

### 2. JSON canónico
```json
{
  "schema_version": "2.0",
  "analysis": { "kind": "trend", "phenomenon_ids": ["N1.9.0"] },
  "location": { "geometry": { "type": "Point", "coordinates": ["<lon>", "<lat>"] }, "spatial_mode": "entity" },
  "period": { "start": "2006-01-01", "end": "2025-12-31" },
  "variables": [ { "variable_id": "water_surface_elevation", "role": "target", "source_preference": ["nasa.swot.hydrocron"] } ]
}
```

### 3. Resolución científica
La incompatibilidad se detecta **en el planificador, sin descargar nada**: el descriptor de SWOT declara inicio en 2022.

### 4. Fuentes seleccionadas
`nasa.swot.hydrocron`: rechazada (`TEMPORAL_INCOMPATIBLE`). Alternativa: `argentina.ina.series` (altura hidrométrica), si hay estación cercana con cobertura; `psmsl.rlr.monthly` si es costa.

### 5. DAG
No se construye el plan de ejecución; `plan_analysis` devuelve `blocked[]` con alternativas.

### 6. Algoritmos
Ninguno.

### 7. Validaciones
T12 · Q11 (el nivel de estación y la elevación SWOT tienen referencias verticales distintas: no se empalman, T15).

### 8. Estados de error posibles
`TEMPORAL_INCOMPATIBLE` (principal) · `UNIT_INCOMPATIBLE` si se pidiera unir SWOT con INA.

### 9. Resultado JSON ilustrativo
```json
{
  "status": "unsupported",
  "errors": [
    { "code": "TEMPORAL_INCOMPATIBLE", "message_key": "error.temporal_incompatible",
      "detail": { "source_id": "nasa.swot.hydrocron", "product_start": "<fecha de inicio declarada en sources.json>", "requested_start": "2006-01-01" },
      "recoverable": false,
      "suggestions": [
        { "action": "use_source", "source_id": "argentina.ina.series", "note": "Altura hidrométrica de estación; otra referencia vertical." },
        { "action": "shorten_period", "start": "<fecha de inicio>" }
      ] }
  ]
}
```

### 10. Presentación frontend
Mensaje claro: «SWOT tiene datos desde 2022; no cubre 20 años». Dos botones: «Usar estación hidrométrica» y «Analizar desde 2022». Sin gráfico vacío.

---

## Caso 8 — Solicitud no soportada

### 1. Solicitud inicial
«Decime exactamente dónde se va a iniciar un incendio dentro de seis meses».

### 2. JSON canónico
La IA **no** construye una solicitud ejecutable. Reconoce el patrón en `capabilities.unsupported_examples` (`EXACT_IGNITION_LOCATION`).

### 3. Resolución científica
- Límite científico explícito en tres documentos: PRED-05 ("NO ignición exacta"), B9.2 ("nunca predicción del incendio exacto"), glosario FWI ("No predice ubicación exacta de ignición").
- Horizonte de seis meses: fuera de todo horizonte de prueba (el del peligro meteorológico es 1–7 días).

### 4. Fuentes seleccionadas
Ninguna.

### 5. DAG
Ninguno.

### 6. Algoritmos
Ninguno.

### 7. Validaciones
Q14 (riesgo operacional) · regla `unsupported_requests` de B9.1 y B9.2.

### 8. Estados de error posibles
`UNSUPPORTED`.

### 9. Resultado JSON ilustrativo
```json
{
  "status": "unsupported",
  "errors": [
    { "code": "UNSUPPORTED", "message_key": "error.unsupported.exact_ignition",
      "detail": { "reason": "EXACT_IGNITION_LOCATION", "requested_horizon": { "value": 6, "unit": "month" } },
      "recoverable": false,
      "suggestions": [
        { "action": "use_phenomenon", "phenomenon_id": "B9.1", "note": "Recurrencia y estacionalidad histórica de detecciones y área quemada." },
        { "action": "use_phenomenon", "phenomenon_id": "N1.4.0", "note": "Mapa histórico de detecciones térmicas." },
        { "action": "use_phenomenon", "phenomenon_id": "B9.2", "note": "Peligro meteorológico relativo (cuando esté disponible)." }
      ] }
  ]
}
```

### 10. Presentación frontend
El asistente responde sin tecnicismos: no es posible saber dónde empezará un incendio; ofrece las tres alternativas como botones. Incluye el aviso de que la herramienta no es un sistema de alerta y la referencia a organismos oficiales.

---

## Caso 9 — Análisis fuera del catálogo

### 1. Solicitud inicial
«Compará el nivel del mar en Mar del Plata con el índice ENSO».

### 2. JSON canónico
```json
{
  "schema_version": "2.0",
  "analysis": { "kind": "multivariable", "phenomenon_ids": [] },
  "location": { "geometry": { "type": "Point", "coordinates": ["<lon>", "<lat>"] }, "spatial_mode": "entity" },
  "period": { "start": "<inicio>", "end": "<fin>" },
  "variables": [
    { "variable_id": "relative_sea_level", "role": "target" },
    { "variable_id": "oni_anomaly", "role": "explanatory" }
  ],
  "temporal": { "frequency": "monthly" },
  "scientific_params": { "lags": { "unit": "month", "candidates": [0] } }
}
```

### 3. Resolución científica
- Ningún fenómeno relaciona nivel del mar con ENSO (B6.1 es ENSO con precipitación y temperatura; B5.2 es nivel relativo con movimiento vertical). **No se fuerza ninguno** (T18).
- Modalidad general `R-GENERAL-MULTI`. Viabilidad: ambas variables tienen serie, ambas son mensuales, no hay unidad que conciliar (se correlacionan anomalías), ninguna pareja está marcada como no intercambiable → **viable**.
- Sin hipótesis de catálogo: hallazgo `exploratory: true`, sin `allowed_claims` de fenómeno, con el texto genérico de asociación.
- Desfases: solo los que declare el usuario; por defecto, 0.

**Contraejemplo de rechazo:** «compará la LST con la temperatura del aire como si fueran lo mismo» o «sumá focos y hectáreas quemadas» → `UNSUPPORTED` por `not_interchangeable_with`.

### 4. Fuentes seleccionadas
`psmsl.rlr.monthly` (mareógrafo seleccionado por puntaje) · `noaa.cpc.oni`.

### 5. DAG
`fetch(PSMSL)` → `qa` → `anomaly` ┐
`fetch(ONI)` → `qa` ┤→ `align` → `lagged_correlation(lag 0)` → `validate(Q04,Q10,Q11,Q13)` → `assemble`

### 6. Algoritmos
N01, N05, N06.

### 7. Validaciones
Q10 (ONI es media trimestral fechada en el mes central) · Q11 (nivel en referencia local RLR) · Q13 · Q04 si se prueban varios desfases.

### 8. Estados de error posibles
Sin mareógrafo con cobertura → `INSUFFICIENT_DATA` · solapamiento insuficiente tras alinear → `INSUFFICIENT_DATA` · pareja no intercambiable → `UNSUPPORTED`.

### 9. Resultado JSON ilustrativo
```json
{
  "status": "completed",
  "findings": [
    { "finding_id": "f1", "phenomenon_id": null, "finding_type": "association",
      "statement_key": "association.general",
      "values": { "r": "<r>", "p": "<p>", "n_effective": "<n>", "lag": 0 },
      "evidence_level": "association", "exploratory": true,
      "allowed_claims": ["Asociación estadística observada en este lugar y período."],
      "forbidden_claims": ["No interpretar como relación causal.", "No generalizar a otros lugares."],
      "limitations": ["Análisis general fuera del catálogo: sin hipótesis científica predefinida."] }
  ],
  "suggestions": [ { "phenomenon_id": "B6.1", "note": "Teleconexiones ENSO con precipitación y temperatura." } ]
}
```

### 10. Presentación frontend
Dos series alineadas y diagrama de dispersión; insignia «Análisis exploratorio fuera del catálogo»; sugerencia de fenómenos relacionados.

---

## Caso 10 — Paridad manual e IA

### 1. Solicitud inicial
- **Manual:** el usuario busca "San Luis" (ciudad), fija 2006–2025, elige el fenómeno N1.1.0 y la variable temperatura del aire, frecuencia mensual.
- **Conversacional:** «Analizá la tendencia de la temperatura del aire en la ciudad de San Luis entre 2006 y 2025».

### 2. JSON canónico
Ambos caminos producen el JSON del Caso 1. Difieren **solo** en `request_id`, `input_mode` y `location.name`, que están fuera de la huella.

### 3. Resolución científica
Idéntica: la calcula el backend a partir de la forma canónica.

### 4. Fuentes seleccionadas
Idénticas: la selección no depende del modo de entrada.

### 5. DAG
Mismo `plan_id`.

### 6. Algoritmos
Los mismos, mismas versiones.

### 7. Validaciones
T17. Condiciones que la arquitectura garantiza:

| Condición | Mecanismo |
|---|---|
| Mismas coordenadas | Ambos resuelven el lugar con `search_places` y envían la coordenada devuelta |
| Mismos valores por defecto | Solo el backend los aplica |
| Mismo orden y formato | `canonical.normalize` |
| Mismos datos | Caché de series por huella; el segundo análisis reutiliza la descarga del primero |
| Mismos resultados numéricos | Métodos deterministas; semilla fija donde haya aleatoriedad |

### 8. Estados de error posibles
Si la IA elige otra interpretación (p. ej. la provincia) las huellas difieren: **no es un fallo de paridad sino de interpretación**, y se detecta porque la IA muestra el resumen de lo que va a analizar antes de ejecutar.

### 9. Resultado JSON ilustrativo
```json
{
  "parity_check": {
    "manual":    { "request_hash": "sha256:9c1e…", "plan_id": "sha256:41ab…" },
    "assistant": { "request_hash": "sha256:9c1e…", "plan_id": "sha256:41ab…" },
    "equal": true
  }
}
```
*Objeto ilustrativo de la prueba automatizada; no es parte del contrato público.*

### 10. Presentación frontend
Mismas vistas. Tras aplicar la propuesta del asistente, el configurador muestra exactamente los mismos campos que el usuario habría llenado a mano; el usuario puede corregirlos antes de procesar.

---

## Qué demuestran los casos

| Capacidad de la arquitectura | Casos |
|---|---|
| De consulta a plan ejecutable | 1, 2, 10 |
| Selección de fuente con sustitución declarada | 1, 2, 6 |
| Variables que no deben mezclarse | 4, 5, 9 |
| Desfases y pruebas múltiples | 2, 9 |
| Predicción con elegibilidad y modos | 3 |
| Resultados parciales por rama | 2, 4, 6 |
| Límites temporales de una fuente | 7 |
| Límites científicos | 8 |
| Análisis general sin forzar fenómeno | 9 |
| Reproducibilidad y paridad | 10 |
