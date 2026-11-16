# AGENTS.md — `trend_scope/handlers/` · Orquestación del análisis

Instrucciones para **Codex**. Este paquete conecta la aplicación con el motor científico: recibe `request.json`, obtiene y prepara los datos, ejecuta los algoritmos registrados y devuelve `response.json`.

**Especificación completa (leer antes de escribir código):** `docs/plan-maestro/23_ARQUITECTURA_HANDLERS.md` en la raíz del repositorio. Este archivo es el orden de trabajo; ante una diferencia, manda el documento 23.

Rutas: `PY/` = `trend_scope/` · `M/` = `PY/models/`.

## Estado de implementación (2026-11-15)

**Fase 0 y fase 1: implementadas, sin ejecutar ni verificar** (por decisión del equipo: ninguna prueba ni benchmark). Lo primero que debe hacer quien continúe es arrancar la app y probar `run_analysis` / `list_analyses`; cualquier error de ejecución es esperable y se corrige sin rediseñar.

| Hecho | Archivos |
|---|---|
| Fase 0 | `M/climate/climatology.py` (`robust_z` con 1,4826), `M/tests/test_climatology.py` y `M/W01_REPORT.md` ajustados al nuevo valor |
| Fase 1 · cálculo | `M/stats/diagnostics.py` (W17), `M/stats/descriptive.py` (W18), registro `describe` en `M/catalog_registry.py` |
| Fase 1 · handlers | `contracts.py`, `analysis_structs.py`, `analysis_handler.py`, `preparation.py`, `algorithm_handler.py`, `decision.py`, `data_handler.py` |
| Fase 1 · comandos | `desktop.py`: `run_analysis`, `list_analyses` |

**Fases 3 y 4 (2026-11-15), también sin ejecutar ni verificar:**

| Hecho | Archivos |
|---|---|
| Fase 3 · pronóstico | `M/forecasting/` (`baselines.py` W07, `backtest.py` W08, `intervals.py` W09, `prob_metrics.py` W13, `forecasters.py` W20, `pipeline.py` = método registrado `forecast_backtest`), `M/stats/multiple_testing.py` (W06) |
| Fase 3 · handlers | structs `forecast` y `spatial_pattern`; `spatial.py` (muestreo de puntos en un polígono); bloque `forecast` y veredicto `forecast_threshold` en `decision.py`; `_analyze_pattern` (tendencia por punto + FDR) en `data_handler.py`; topes provisionales de horizonte en `analysis_handler.check` |
| Fase 4 · librerías sin registrar | W19 `signal/convolution2d.py`, W10 `climate/etccdi.py`, W11 `stats/bootstrap.py`, W12 `fire/fwi.py`, W14 `vegetation/burn_indices.py`, W15 `landcover/transitions.py`, W16 `atmosphere/hypsometric.py` |

Structs disponibles: `describe`, `trend_significance`, `anomaly`, `drought_spi`, `regression_fit`, `forecast`, `spatial_pattern`. Los de la fase 2 (`seasonality`, `change_point`, `smoothing`, `extreme_events`, `relationship`) siguen declarados con `planned=True` y `list_analyses` los informa `available: false`. **La fase 2 no se hizo**: faltan W05 (correlación con desfases), W04 (percentiles y eventos) y los structs que las usan.

Las librerías de la fase 4 son API de Python: no están registradas en `catalog_registry` (necesitan adaptadores de contrato propio: rejillas 2D, series diarias con etiquetas) ni las usa ningún struct todavía. `fire/fwi.py` rechaza latitudes con |lat| < 30° (no se inventaron factores de duración del día tropicales) y no se comparó contra tablas publicadas.

Desvíos respecto del documento 23: no se implementó el paso opcional `lttb` de `describe` (los arreglos largos se omiten y se avisa); `lag1_autocorrelation` recibe un `groups` opcional para quitar el ciclo estacional; se agregó el código de error `CADENCE_INCOMPATIBLE`; no se generaron archivos de schema ni fixtures (`contracts.export_schemas()` los produce bajo demanda).

## 0. Regla de trabajo

**Una fase por solicitud** (§6). Por decisión del equipo (2026-11-15) no se escriben pruebas ni benchmarks: la verificación la hace el equipo. Dentro de una fase, seguí el orden de archivos indicado. Los algoritmos nuevos de `M/` siguen el protocolo de `M/AGENTS.md` (una función por solicitud, estado `candidate`).

## 1. Qué no se toca

1. `PY/services/**`, el frontend (`src/`), `assistant-worker/`, Rust (`src-tauri/src/`) y `web app/`.
2. `handlers/analysis.py`, `PY/main.py` y los comandos existentes de `desktop.py`: quedan como vía heredada.
3. Todo lo listado en `M/PRESERVATION.json` y las funciones de `M/` que ya tienen pruebas.
4. Dependencias, `git commit` y `git push`: solo con pedido expreso.

Único archivo existente que se edita en este paquete de trabajo: `desktop.py`, para **agregar** `run_analysis` y `list_analyses`.

## 2. Qué se reutiliza (no reescribir)

| Necesidad | Usar |
|---|---|
| Descargar series | `services.acquisition.acquire(investigation)` |
| Resumen descriptivo heredado | `services.evidence.with_evidence(series)` |
| Familia de una variable (precipitación, temperatura…) | `services.coverage.VARIABLES` |
| Registro de métodos | `models.catalog_registry.catalog_registry()` (construirlo una vez por proceso) |
| Ejecutar un método | `models.execution.analyze(dataset, request, registry, context)` |
| Contratos del motor | `models.contracts` (`ScientificDataset`, `VariableData`, `TimeCoordinate`, `Provenance`, `Transformation`, `AnalysisRequest` como `MethodRequest`) |
| Análisis por celda | `models.adapters.grid.analyze_grid` |
| JSON estricto | `models.serialization.to_jsonable` / `dumps` |
| Validar escalares | `models.numeric.integer` / `scalar` |

## 3. Módulos y firmas

| Archivo | Responsabilidad | Entrada → salida |
|---|---|---|
| `contracts.py` | Modelos Pydantic v2 (`extra="forbid"`): `RequestDocument`, `AnalysisSpec`, `Hypothesis`, `ResponseDocument`, `AnalysisBlock`, `StepBlock`, `Finding`, `Verdict`, `ErrorItem`; códigos de error; `request_hash` | `dict` ↔ modelos |
| `analysis_structs.py` | `ParamSpec`, `Requirements`, `Candidate`, `Step`, `AnalysisStruct` (dataclasses congeladas) y la tupla `STRUCTS` | datos declarativos, sin lógica |
| `analysis_handler.py` | `resolve(spec) -> AnalysisStruct` · `check(struct, profile) -> list` · `capabilities() -> dict` | valida struct, targets, params, hipótesis |
| `preparation.py` | `prepare(series, struct, params) -> Prepared` (`dataset`, `profile`, `transformations`, `issues`) | serie del conector → `ScientificDataset` |
| `algorithm_handler.py` | `execute(struct, prepared, params, context) -> list[StepResult]` | selección por reglas + `analyze()` |
| `decision.py` | `build(struct, steps, prepared, hypothesis) -> (findings, verdict)` | reglas deterministas |
| `data_handler.py` | `run(raw: dict) -> dict` (única entrada pública) | `request.json` → `response.json` |
| (en `contracts.py`) | `export_schemas()` devuelve los JSON Schema de request y response | contrato para frontend y chat |

Reglas de diseño:

- **Los handlers no contienen fórmulas.** Toda estadística sale de un método registrado en `M/`. Si falta una, es una tarea de `M/` (W17–W20 o la cola existente), no un cálculo local.
- **Lista blanca:** un `request.json` solo puede nombrar `struct_id` de `STRUCTS` e ids de `investigation.sources`. Nada de rutas, URLs, nombres de función ni expresiones.
- **Los valores por defecto los aplica solo el backend** y se devuelven en `parameters_effective`.
- **Nunca abortar por un análisis:** cada fallo se convierte en `ErrorItem` con alcance; el resto continúa (`status: "partial"`).
- **Sin interpolación, ordenamiento ni conversión de unidades implícitos.** Toda transformación queda en `transformations`.
- **Idioma:** `code` de error en inglés (constantes); `message` en español, como en `services/`.
- **Decisión:** p ≥ α o intervalo que incluye 0 → `inconclusive` («no hay evidencia suficiente»), nunca «sin cambios». Multivariable → «asociación», nunca causa. No se emite ningún «porcentaje de certeza».

## 4. Trampas del código existente (verificadas al leerlo)

Series de los conectores:

- La clave `month` contiene **cualquier** marca temporal: `YYYY-MM`, `YYYY-MM-DD` o ISO con hora (INA, USGS).
- `cadence` puede faltar (NASA POWER): tratarlo como `monthly`. Valores existentes: `monthly`, `daily`, `overpass`, `observation`, `event`.
- Los faltantes llegan como `value: null`.
- Las descargas crudas (AppEEARS, CDS, Earthdata, Copernicus, Planetary) devuelven `message`/`downloadPath` y no una serie analizable → `UNSUPPORTED_SPATIAL`.
- `acquire()` exige `schemaVersion == 1`, `methods` vacío y entre 1 y 25 fuentes. NASA POWER exige además `time.resolution == "Mensual"` y que el año final sea anterior al actual.
- NASA POWER `PRECTOTCORR` es una **tasa** (mm/día, media mensual): para SPI hay que pasarla a total mensual (× días del mes) y registrarlo.

Motor (`execution.analyze` y registro):

- Rechaza parámetros que no estén en `MethodSpec.parameters` y variables cuya dimensión no esté en `MethodSpec.dimensions`.
- Los tiempos deben ser numéricos, estrictamente crecientes y sin NaN; los valores, finitos y sin máscara.
- `sen`, `sen_interval`, `mann_kendall`, `seasonal_mann_kendall`: presupuesto de pares 2 000 000 → **n ≤ 2000**. Una serie diaria de 25 años no entra: agregar antes.
- `modified_mann_kendall`: serie regular, 4 ≤ n ≤ 2000.
- `seasonal_mann_kendall`: `seasons` es una lista de etiquetas enteras del largo de la serie, pasada como parámetro.
- `climatology`, `anomalies`, `spi`: `groups`, `baseline` y `calibration` son **ids de otras variables del mismo dataset**, con unidad `"1"`; `baseline`/`calibration` codificadas 0/1. `min_count`, `kind` y `scale` son obligatorios.
- `spi`: `time.unit` debe ser `month`/`months` con paso exacto 1; unidad de la variable `mm`, `cm` o `m`; mínimo 24 observaciones.
- `harmonic` por registro no tiene valor por defecto de `period`: pasarlo siempre.
- `stl`: ≥ 2 ciclos y `seasonal` impar. `pelt` exige `penalty`; `cusum` exige `baseline`, `allowance`, `threshold`.
- `forecast` y derivados: serie regular, n ≥ 4, `validation_size < n − 1`.
- `serialization.to_jsonable`: tope de 100 000 elementos. Decimar arreglos largos antes de armar la respuesta.
- La pendiente de Sen sale en `unidad/unidad de tiempo`: usar años decimales como tiempo para informar «por año» y «por década».


## 5. Structs de la primera versión

`describe`, `trend_significance`, `anomaly`, `drought_spi`, `regression_fit` (fase 1); `seasonality`, `change_point`, `smoothing`, `extreme_events`, `relationship` (fase 2); `forecast`, `spatial_pattern` (fase 3). Pasos, métodos y reglas de selección: documento 23, §4 y §6.

Un struct cuyo requisito todavía no existe se declara igual y `capabilities()` lo informa `available: false` con el motivo. No se simula ningún resultado.

## 6. Fases

| Fase | Entrega | Cierre |
|---|---|---|
| 0 | En `M/`: corrección de `robust_z` (factor 1.4826, ver `M/AGENTS.md` W01) | Aplicada |
| 1 | `contracts.py` → `analysis_structs.py` → `analysis_handler.py` → W17 y W18 en `M/` → `preparation.py` → `algorithm_handler.py` → `decision.py` → `data_handler.py` → comandos en `desktop.py`. Structs de fase 1 | Recorrido request → response implementado |
| 2 | W06, W05, W04 en `M/`; structs de fase 2 | Structs de fase 2 implementados |
| 3 | W07, W08, W09, W20, W13 en `M/forecasting/`; struct `forecast`; muestreo de área y `spatial_pattern` | Se entrega el baseline cuando no hay habilidad |
| 4 | W19 y W10–W16 | Cola de `M/AGENTS.md` |

## 7. Entrega de cada fase

```text
FASE: <n> — <nombre>
ARCHIVOS CREADOS:
ARCHIVOS EXISTENTES MODIFICADOS (solo los autorizados):
STRUCTS DISPONIBLES / NO DISPONIBLES (con motivo):
VALORES PROVISIONALES INTRODUCIDOS (parámetro y valor):
DESVÍOS RESPECTO DEL DOCUMENTO 23 (y por qué):
PENDIENTE PARA LA FASE SIGUIENTE:
```
