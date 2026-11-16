# 06 — Matriz de algoritmos existentes y faltantes

Rutas: `PY/` = `aplicacion/trend-scope/src-tauri/src-python/trend_scope/`, `M/` = `PY/models/`.

## 1. Criterio de clasificación

El pedido define cinco clases. La auditoría obliga a precisar la clase A: **ningún algoritmo del repositorio tiene aprobación independiente** (`M/ENGINE_STATUS.md` declara todo como *candidate, no aprobado*). Por eso:

| Clase | Definición usada en este plan |
|---|---|
| **A** | Completado, con tests, con **documento de validación numérica propio** y listado en `M/PRESERVATION.json`. Protegido: no se modifica. *No equivale a auditoría independiente.* |
| **B** | Implementado y con tests de corrección; sin informe de validación propio. Protegido si está en `PRESERVATION.json`. No se declara "validado". |
| **C** | Parcialmente implementado: falta una parte necesaria para el uso científico previsto. |
| **D** | No implementado y requerido por el catálogo. |
| **E** | Duplicado o incompatible. |

**Regla de protección (todas las clases A y B):** el Handler los invoca solo a través de `scientific_registry()` + `analyze()`. Cualquier cambio a un archivo listado en `PRESERVATION.json` es una decisión pendiente de aprobación, nunca una tarea de backlog.

**Benchmarks de rendimiento:** existen para regresión lineal, polinómica y RK4 (`M/stats/stage1a_results.json`, `stage1b_results.json`, `M/benchmarks/`). **No se replanifican.**

---

## 2. Clase A — completados con validación numérica documentada

| Método (`method_id`) | Ubicación | Método matemático | Entradas → salida | Restricciones | Evidencia | Integración |
|---|---|---|---|---|---|---|
| `linear` | `M/stats/regression.py:166` (kernel `linear_kernel.py:16`) | OLS centrado/escalado con sumas compensadas | `(x, y)` → `LinearFitOutput` (pendiente en unidad y/x, r², RMSE, MAE, AIC) | n≥2; x no constante; sin NaN | `STAGE1A.md`: error ≤7.4e-14 vs referencia; ~20 tests | En `default_registry`; sin uso desde la UI |
| `polynomial` | `M/stats/polynomial.py:65` | Vandermonde en base escalada + `lstsq`; coeficientes con `Decimal` | `(x, y, degree=2)` → `PolynomialFitOutput` con `stable_basis` | n≥grado+1; rango completo; límites de memoria | `POLYNOMIAL_REGRESSION.md`: coincide con `Polynomial.fit` dentro de 6.5e-12; ~16 tests | En `default_registry` |
| `rk4` (servicio `simulate_rk4`) | `M/dynamical/rk4.py:49`, `rk4_service.py:80` | Runge-Kutta clásico de orden 4, un paso por intervalo | `(rhs, y0, t)` → matriz de estados; servicio → `AnalysisResult` | RHS compilado en nopython; sin modelos registrados por defecto | `RK4.md`: orden 4 verificado, comparado con SciPy DOP853; 21 tests | Registro propio (`ODEModelRegistry`); no está en `scientific_registry` |

## 3. Clase B — implementados con tests, sin informe de validación propio

### 3.1 Tendencia e inferencia

| `method_id` | Ubicación | Método | Salida | Restricciones | Tests | Uso en el catálogo |
|---|---|---|---|---|---|---|
| `sen` | `M/stats/trends.py:17` | Theil-Sen (mediana de pendientes de todos los pares) | `{slope, intercept_at_reference, n_pairs, uncertainty}` | O(n²); **sin intervalo de confianza** | vs `scipy.stats.theilslopes` | 10 fenómenos (N1.1.0, N1.2.0, N1.3.0…) |
| `mann_kendall` | `trends.py:48` | S con corrección por empates, Z con continuidad, p bilateral | `{score, variance, z, p_value, tau_a}` | Asume independencia | S y Var exactos | 5 fenómenos |
| `seasonal_mann_kendall` | `extended_registry.py:81` | Suma S y Var por estrato estacional | ídem + `seasonal` | Etiquetas de estación | Sí | N1.1.0 y Q03 |
| `modified_mann_kendall` *(opcional: pymannkendall)* | `M/optional_methods.py:17` | Hamed-Rao o Yue-Wang (autocorrelación) | — | Serie regular; 4≤n≤2000 | Sí | Q03 ("control de autocorrelación") |
| `multivariable` | `trends.py:78` | OLS con intercepto, diseño escalado, SVD | coeficientes, residuales, r², rango, condición | n≥p+1; rango completo | Sí | Base de la regresión con lags de N2 |

### 3.2 Regresiones (API heredada, despacho por `handlers/analysis.py` y por registro)

`ridge`, `exponential`, `logarithmic`, `power`, `harmonic` — `M/stats/regression.py:248-315`. Con tests de corrección (`test_legacy_completion`). Uso en catálogo: `harmonic` para amplitud y fase estacional (N1.3.0); `ridge` como base de PRED-01/02.

### 3.3 Cambios, anomalías y patrones

| `method_id` | Ubicación | Método | Restricciones | Uso |
|---|---|---|---|---|
| `cusum` | `M/change_detection/cusum.py:27` | CUSUM tabular bilateral | Requiere `baseline`, `allowance`, `threshold` | Cambios de régimen |
| `pelt` *(opcional: ruptures)* | `optional_methods.py:88` | PELT con costo L2 | Serie regular | Rupturas (N1.3A, N1.3C, N1.9A, N1.3D, B2.5) |
| `adwin` *(opcional: river)* | `:104` | ADWIN | Valores en [0,1] | Sin uso asignado en el catálogo |
| `isolation_forest` *(opcional: scikit-learn)* | `:120` | Isolation Forest, semilla fija | Anomalías in-sample | Sin uso asignado |
| `matrix_profile` | `M/similarity/matrix_profile.py:10` | Auto-join exacto por fuerza bruta | Pares ≤1e5 | Sin uso asignado |
| `dtw` | `M/similarity/dtw.py:19` | DTW exacto con banda Sakoe-Chiba | Misma unidad en ambas series | Sin uso asignado |

### 3.4 Señal, descomposición y reducción

`moving_average`, `fir` (modo coeficientes), `iir`, `fft`, `ssa`, `paa`, `lttb` (`M/signal/processing.py`, `M/data_reduction/reduction.py`); `stl` y `wavelet` opcionales (`optional_methods.py:61,72`). Uso en catálogo: `stl` para desestacionalizar antes de rupturas; `lttb` para decimación de gráficos; `fft` para estacionalidad exploratoria.

### 3.5 Sin registrar en `scientific_registry`

`dtw_kmeans` (tslearn), `kleinberg`, `CountMinSketch`, `MisraGries`, `SpaceSaving`, `rk45`, `rk4_multi`, `diffusion_1d`. Con tests. **Ninguno es requerido por los 73 fenómenos**; quedan disponibles sin integración planificada.

---

## 4. Clase C — parcialmente implementados

| Componente | Qué existe | Qué falta | Tarea |
|---|---|---|---|
| Pronóstico (`naive_forecast`, `seasonal_naive_forecast`, `holt_winters`, `arima`, `sarima`, `forecast`) — `optional_methods.py:178` | Ajuste y predicción; un único holdout cronológico; comparación con naive; error por horizonte | Backtesting rolling-origin, baseline climatológico, intervalos predictivos, cobertura empírica, persistencia de ajustes. Devuelve `uncertainty: 'not_estimated'` | EMA-19, EMA-20 (código nuevo que **envuelve** a `forecast`, sin modificarlo) |
| `sen` | Pendiente e intercepto | Intervalo de confianza (la planilla exige IC95 y Q03 exige IC) | EMA-13 (función nueva) |
| `fir` | Modo con coeficientes | Modo de diseño (`numtaps`/`cutoff`) sin test | Sin tarea: no lo requiere el catálogo |
| Rutas por registro de métodos extendidos | Funciones probadas directamente | Tests de la ruta `analyze()` para ridge, exponential, logarithmic, power, harmonic, dtw, matrix_profile, iir y opcionales | EMA-05 (tests de contrato del registro) |
| `MethodSpec.min_observations` | Todos los métodos extendidos declaran 2 | El mínimo real está dentro de cada función | EMA-05: el descriptor del Handler declara el mínimo científico sin tocar `MethodSpec` |
| `rk4_multi_independent` | Implementado | Sin tests ni guardas de finitud; archivo con hash discrepante | Decisión pendiente D-07 |
| Integración con la UI | `execute_regression` (nadie lo llama) | Todo el recorrido | EMA-06, EMA-11 |

---

## 5. Clase D — no implementados y requeridos

Solo se listan los que exige el catálogo. La columna "Ola" remite a `12_ROADMAP.md`.

| ID | Algoritmo | Requerido por | Entradas → salida | Ubicación propuesta | Ola | Tarea |
|---|---|---|---|---|---|---|
| N01 | Climatología de referencia y anomalías (absoluta, %, estandarizada, z robusto) | 14 fenómenos; Q02 | serie + período base → climatología por mes/período, anomalías, cobertura de la base | `M/climate/climatology.py` | 1 | EMA-12 |
| N02 | Intervalo de confianza de Theil-Sen | N1.1.0, N1.1A, N1.2A; Q03 | tiempos, valores, nivel → `{slope, ci_low, ci_high}` | `M/stats/sen_interval.py` | 1 | EMA-13 |
| N03 | SPI (escalas 1/3/6/12, ajuste por mes con masa en cero, **calibración solo en entrenamiento**) | N1.2.0, N1.2A, N1.2C, B3.5; Q05; PRED-01 | precipitación mensual + período de calibración → SPI por escala, parámetros, n de calibración | `M/climate/spi.py` | 2 | EMA-14 |
| N04 | Percentiles, umbrales y eventos (duración, frecuencia, intensidad por rachas) | 9 fenómenos (N1.3B, N1.5A/B, N1.1D, B5.3…) | serie + percentil/umbral por período → eventos `{inicio, fin, duración, intensidad}` | `M/climate/events.py` | 2 | EMA-15 |
| N05 | Correlación con desfases predefinidos, tamaño efectivo de muestra y correlación parcial | B2.2, B5.4, B6.1, B9.1, B1.4, B6.2 | dos series alineadas + lista de lags → r, p, n efectivo por lag | `M/stats/lagged.py` | 2 | EMA-16 |
| N06 | Control de tasa de falsos descubrimientos (Benjamini-Hochberg) | Q04; T09 | p-valores + familia → q-valores | `M/stats/multiple_testing.py` | 2 | EMA-16 |
| N07 | Backtesting rolling-origin y métricas (MAE, RMSE, sesgo, skill vs baseline, cobertura) | PRED-01..08; Q15, Q16; T10, T11 | serie + modelo + horizonte → métricas por horizonte, residuales fuera de muestra | `M/forecasting/backtest.py` | 5 | EMA-19 |
| N08 | Intervalos predictivos por residuales fuera de muestra (conformal temporal) | Q16 | residuales del backtest + nivel → cuantiles por horizonte | `M/forecasting/intervals.py` | 5 | EMA-20 |
| N09 | Baselines: climatología mensual y persistencia | PRED-01..08 | serie → pronóstico base | `M/forecasting/baselines.py` | 5 | EMA-19 |
| N10 | Índices ETCCDI (RX1day, RX5day, R95pTOT, SDII, CDD; olas de calor por umbral calendarizado) | N1.1B, N1.2B | serie diaria → índice anual | `M/climate/etccdi.py` | 6 | EMA-28 |
| N11 | Bootstrap por bloques para IC | N1.1C, B2.6, B3.4 | serie(s) + estadístico → IC | `M/stats/bootstrap.py` | 6 | EMA-28 |
| N12 | Fire Weather Index (FFMC, DMC, DC, ISI, BUI, FWI; hemisferio sur; estado y spin-up) | B9.2; PRED-05 | meteorología diaria → componentes diarios | `M/fire/fwi.py` | 6 | EMA-25 |
| N13 | Métricas probabilísticas (Brier, fiabilidad, CRPS) | PRED-01, 05; Q16 | probabilidades + observaciones → métricas | `M/forecasting/prob_metrics.py` | 6 | EMA-28 |
| N14 | dNBR / RdNBR y trayectorias de recuperación | N1.4D, B9.3, B2.6 | bandas pre/post → índice; serie NDVI → tiempo de recuperación | `M/vegetation/` | 7 | Backlog P2 |
| N15 | Matriz de transición de cobertura | B1.1, B2.1, N1.3A, B8.3 | clasificaciones multifecha → matriz y áreas | `M/landcover/` | 7 | Backlog P2 |
| N16 | Ecuación hipsométrica | N1.8.1 | presión, temperatura, elevación → presión esperada | `M/atmosphere/` | 7 | Backlog P3 |

**No son algoritmos matemáticos sino preparación de datos** (responsable Eze, ver `07_MATRIZ_FUENTES.md`): conversión de unidades, agregación temporal con control de faltantes, alineación de series, estadística zonal ponderada por área, área geodésica de píxel, máscaras QA satelitales.

**Explícitamente fuera de alcance v1** (requieren procesamiento especializado; los fenómenos que dependen de ellos quedan `UNSUPPORTED` o `NOT_AUTOMATABLE` con justificación): BFAST completo, detección de cambios SAR, interferometría diferencial, índices de bloqueo atmosférico, seguimiento de ciclones, modelos de susceptibilidad a deslizamientos, balance de masa glaciar.

> **Sustitución que requiere aprobación (D-09):** la planilla nombra BFAST para rupturas. El repositorio no lo tiene; sí tiene `stl` + `pelt`/`cusum`. El plan propone `stl → pelt` como aproximación **rotulada como tal**, no como BFAST.

---

## 6. Clase E — duplicados e incompatibilidades

| # | Caso | Evidencia | Propuesta | Estado |
|---|---|---|---|---|
| E1 | Mínimos cuadrados lineal en 4 lugares | `regression.linear_regression`, `linear_reference.linear_regression` (oráculo de tests), `services/evidence.summarize_series` (lo que ve la UI), `trends.multivariable_ols` | La tendencia científica pasa a salir de `sen` + `mann_kendall` vía Handler. `evidence.summarize_series` queda **solo como resumen descriptivo** y deja de rotularse "trend" cuando exista un resultado del Handler. No se borra hasta completar el recorrido 1 | Decisión D-05 |
| E2 | Dos despachadores y dos contratos de salida | `handlers/analysis.py` + `FitOutput` vs `MethodRegistry` + `AnalysisResult` | El Handler usa **solo** el registro. `execute_regression` queda como comando heredado sin nuevos usos | Decisión D-05 |
| E3 | RK4 en 3 implementaciones | `rk4.rk4`, `benchmarks/rk4_reference.rk4`, lazo de `multi_ode.rk4_multi_independent` | Sin acción: la referencia es oráculo; `multi_ode` queda fuera del Handler | — |
| E4 | Validación de entradas repetida en 6 sitios | `numeric.array`, `polynomial._vector`, etc. | Sin acción (tocar esto es modificar archivos protegidos) | — |
| E5 | `metric_units` genéricas para ridge/exponential/logarithmic/power/harmonic vía registro | `extended_registry._run` | El adaptador de resultados del Handler completa unidades a partir del descriptor, sin tocar `_run` | EMA-06 |
| E6 | `harmonic` sin valor por defecto de `period` por registro (da `TypeError`) | `extended_registry` | El `AlgorithmDescriptor` marca `period` como obligatorio y el planificador lo completa desde la frecuencia | EMA-05 |
| E7 | Tres registros de fuentes en el frontend y backend | `catalog.py`, `source-coverage.json`, `sources.js` | Un único `knowledge/sources.json` expuesto por `get_capabilities` | EZE-01 |
| E8 | Código muerto en producción | `_jit_poly_fit`, `_jit_compute_metrics` (solo benchmark) | Sin acción | — |

---

## 7. Adaptadores que necesita el Handler

| Adaptador | Problema que resuelve | Entrada → salida | Responsable |
|---|---|---|---|
| `series_to_dataset` | Los conectores devuelven dicts; el motor exige `ScientificDataset` | `NormalizedSeries` (una o varias, ya alineadas) → `ScientificDataset` con `TimeCoordinate`, unidades, `Provenance`, máscara `invalid`, `transformations` | Ema (EMA-06) |
| `method_call` | Traducir un nodo del plan a una llamada al motor | nodo `analyze` → `models.contracts.AnalysisRequest` (importado como `MethodRequest`) → `analyze(...)` | Ema (EMA-06) |
| `method_result_to_block` | `AnalysisResult` interno → bloque JSON del resultado público, con unidades completas | `AnalysisResult` → `MethodResultBlock` | Ema (EMA-06) |
| `time_numeric` | Los métodos reciben tiempos numéricos; el resultado debe expresarse en unidades interpretables | fechas → años decimales (pendientes "por año/década") y vuelta | Ema (EMA-06) |
| `gap_policy` | Los métodos rechazan NaN; las series tienen faltantes | serie con huecos → serie válida + registro de qué se excluyó (nunca interpolación silenciosa; Q01) | Eze (EZE-08) + Ema |
| `optional_dependency_gate` | Métodos opcionales ausentes en la instalación | `method_id` → disponible / `METHOD_NOT_AVAILABLE` con alternativa | Ema (EMA-05) |

---

## 8. Dependencias

| Paquete | Estado | Métodos que habilita | Nota |
|---|---|---|---|
| numpy, numba, scipy | En `pyproject.toml` | Núcleo | |
| pydantic 2, jsonschema, anyio | En `pyproject.toml` | Contratos y ejecución del Handler | No se agregan dependencias nuevas para el Handler |
| statsmodels | **Opcional, fuera de `pyproject.toml`** | `stl`, `arima`, `sarima`, `holt_winters` | Necesario para rupturas con STL y para toda la línea predictiva → decisión D-06 |
| pymannkendall | Opcional | `modified_mann_kendall` | Necesario para Q03 con autocorrelación → D-06 |
| ruptures | Opcional | `pelt` | Necesario para rupturas → D-06 |
| scikit-learn, PyWavelets, river, tslearn | Opcionales | `isolation_forest`, `wavelet`, `adwin`, `dtw_kmeans` | Sin uso asignado en el catálogo; no se empaquetan por ahora |
