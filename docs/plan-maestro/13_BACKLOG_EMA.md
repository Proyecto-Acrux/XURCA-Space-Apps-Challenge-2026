# 13 — Backlog de Ema · Arquitectura y núcleo científico del backend

**Rol:** coordinación técnica del backend; Algorithm Handler; registros; resolución de fenómenos; planificación; integración de algoritmos y modelos; elegibilidad; contratos científicos; corrección matemática.

**Propiedad de archivos:** `PY/handler/` (salvo `source_registry.py`, `jobs.py`, `cache.py`, `retry.py`), `PY/knowledge/` (salvo `sources.json`), todo `PY/models/`, comandos del Handler en `PY/desktop.py`.

Rutas: `PY/` = `aplicacion/trend-scope/src-tauri/src-python/trend_scope/`, `M/` = `PY/models/`.
Prioridad: P0 bloquea a otros · P1 MVP · P2 después del MVP. Complejidad: S, M, L (relativa, sin horas).
Regla del repositorio (`M/CLAUDE.md`): **un algoritmo por solicitud**, con pruebas sintéticas y casos extremos, sin tocar archivos protegidos.

## Resumen

| ID | Título | Prior. | Compl. | Fase | Depende de |
|---|---|---|---|---|---|
| EMA-01 | Contratos Pydantic, JSON Schema y ejemplos fijos | P0 | L | F1 | — |
| EMA-02 | Forma canónica y huella | P0 | M | F1 | EMA-01 |
| EMA-03 | `phenomena.json` con los 73 fenómenos | P0 | L | F1 | EMA-01 |
| EMA-04 | `variables.json` y compatibilidades | P0 | M | F1 | EMA-01 |
| EMA-05 | AlgorithmRegistry | P1 | M | R1 | EMA-01 |
| EMA-06 | Adaptadores al motor | P1 | M | R1 | EMA-05, EZE-02 |
| EMA-07 | Resolución de intención y recetas | P1 | L | R1 | EMA-03, EMA-04 |
| EMA-08 | Planificador DAG | P1 | L | R1 | EMA-07, EZE-10 |
| EMA-09 | Ejecutor | P1 | L | R1 | EMA-08, EZE-05 |
| EMA-10 | Validadores científicos base y hallazgos | P1 | L | R1 | EMA-09 |
| EMA-11 | Comandos PyTauri del Handler | P0 | M | R1 | EMA-01 |
| EMA-12 | Algoritmo: climatología y anomalías | P1 | M | R1 | — |
| EMA-13 | Algoritmo: intervalo de confianza de Theil-Sen | P1 | M | R1 | — |
| EMA-14 | Algoritmo: SPI | P1 | L | R2 | EMA-12 |
| EMA-15 | Algoritmo: percentiles y eventos | P1 | M | R2 | EMA-12 |
| EMA-16 | Algoritmos: correlación con desfases y FDR | P1 | M | R2 | — |
| EMA-17 | Receta multivariable `R-LAGREG` | P1 | M | R2 | EMA-16, EZE-16 |
| EMA-18 | ModelRegistry y puerta de elegibilidad | P1 | L | R3 | EMA-01 |
| EMA-19 | Baselines y backtesting rolling-origin | P1 | L | R3 | — |
| EMA-20 | Intervalos predictivos | P1 | M | R3 | EMA-19 |
| EMA-21 | Receta `R-FORECAST` y línea PRED-03 | P1 | L | R3 | EMA-18–20 |
| EMA-22 | Validadores Q04, Q13, Q17 | P1 | M | R2 | EMA-10, EMA-16 |
| EMA-23 | Recetas `R-COUNT` y `R-AREA` | P1 | M | Fuego | EZE-13, EZE-14 |
| EMA-24 | Semántica de fuego y control Q14 | P1 | S | Fuego | EMA-10 |
| EMA-25 | Algoritmo: Fire Weather Index | P2 | L | O6 | EZE-21 |
| EMA-26 | Modalidad general fuera de catálogo | P1 | M | R2 | EMA-07 |
| EMA-27 | Capacidades (`get_capabilities`) | P0 | M | R1 | EMA-03, EMA-05, EZE-01 |
| EMA-28 | Algoritmos de segunda prioridad (uno por PR) | P2 | L | O6 | — |
| EMA-29 | Línea PRED-01 (precipitación y SPI) | P2 | L | O5 | EMA-14, EMA-21 |
| EMA-30 | Línea PRED-02 (NDVI) | P2 | L | O5 | EMA-21, EZE-12 |
| EMA-31 | Retiro controlado de código duplicado | P2 | S | F9 | D-05 |
| EMA-32 | Actualización de documentación del motor | P2 | S | F9 | — |

---

## Tareas

### EMA-01 — Contratos Pydantic, JSON Schema y ejemplos fijos
- **Descripción:** implementar en `handler/contracts.py` los modelos `AnalysisRequest`, `ValidationReport`, `AnalysisPlan`, `PlanNode`, `JobStatus`, `AnalysisResult`, `ScientificFinding`, `ValidationStatus`, `SeriesBlock`, `SourceUse`, `VizHint`, `ForecastBlock`, `Capabilities`, `Error`, tal como se especifican en `09_CONTRATOS_JSON_API.md`. `extra="forbid"`. Script que exporta JSON Schema a `handler/schemas/` y valida `handler/fixtures/*.json` (un ejemplo por caso de uso).
- **Colaboradores:** Eze (campos de fuente y serie), JP, Juan y José (revisión antes de congelar).
- **Archivos:** `PY/handler/contracts.py`, `errors.py`, `schemas/`, `fixtures/`.
- **Interfaces:** es la interfaz de todo el sistema.
- **Criterios de aceptación:** los 10 ejemplos validan; un campo desconocido es rechazado; los esquemas exportados son deterministas (dos ejecuciones dan el mismo archivo); revisión aprobada por una persona de cada equipo.
- **Pruebas:** unitarias de validación (válidos, inválidos, límites); prueba de contrato que falla si un ejemplo deja de validar.
- **Entregable:** contratos v2.0 congelados y publicados.

### EMA-02 — Forma canónica y huella
- **Descripción:** `canonical.normalize(request) → CanonicalRequest` y `request_hash`. Aplica valores por defecto (tabla de `03` §4.2), ordena, redondea coordenadas, resuelve alias, excluye campos de presentación.
- **Colaboradores:** José (verifica que `requestBuilder` no aplique valores por defecto).
- **Archivos:** `PY/handler/canonical.py`.
- **Criterios de aceptación:** solicitudes equivalentes con distinto orden, `request_id`, `input_mode` o nombre de lugar dan la misma huella; cambiar un parámetro científico la cambia; `defaults_applied` lista cada valor por defecto con su motivo.
- **Pruebas:** unitarias por propiedad (permutaciones, idempotencia: normalizar dos veces da lo mismo).
- **Entregable:** base de T17.

### EMA-03 — `phenomena.json` con los 73 fenómenos
- **Descripción:** generar el archivo a partir de `CATALOGO_V9_73.json` y de las columnas E–M de la planilla (script de desarrollo en `tools/`, no en producción), copiando literalmente método, afirmación permitida y prohibida. Completar a mano la sección de integración: variables canónicas con rol, recetas, parámetros, controles, líneas predictivas. Los 13 MVP completos; los otros 60 con texto de planilla, receta asignada y `recipe_params.status: "proposed"`. `knowledge.py` carga y verifica integridad.
- **Colaboradores:** ingeniera química (revisión de roles y desfases), Eze (productos).
- **Archivos:** `PY/knowledge/phenomena.json`, `PY/handler/knowledge.py`, `tools/build_phenomena.py`.
- **Criterios de aceptación:** 73 ids idénticos a los del catálogo, 36 N1 + 37 N2, sin duplicados; toda referencia a variable, receta, control o producto resuelve; el texto de las tres columnas normativas coincide carácter por carácter con la planilla.
- **Pruebas:** de integridad; de regresión contra el catálogo (falla si un id cambia).
- **Entregable:** capa de conocimiento de fenómenos.

### EMA-04 — `variables.json` y compatibilidades
- **Descripción:** variables canónicas (id, magnitud física, unidad, alias, atributos requeridos, agregación por defecto, rango válido) y relaciones `not_interchangeable_with` con su motivo: LST ↔ T2m, detecciones ↔ área quemada, ET₀ ↔ ET real, humedad volumétrica ↔ fracción de saturación, presión de superficie ↔ reducida al mar, SST ↔ temperatura de lago.
- **Colaboradores:** Eze (mapeo a códigos nativos), ingeniera química.
- **Archivos:** `PY/knowledge/variables.json`.
- **Criterios de aceptación:** toda variable usada por los 73 fenómenos existe; las seis parejas anteriores están declaradas; ningún alias es ambiguo.
- **Pruebas:** integridad; unitarias de resolución de alias.
- **Entregable:** vocabulario de variables.

### EMA-05 — AlgorithmRegistry
- **Descripción:** `AlgorithmDescriptor` por cada método de `scientific_registry()` que el catálogo usa (`sen`, `mann_kendall`, `seasonal_mann_kendall`, `modified_mann_kendall`, `multivariable`, `harmonic`, `stl`, `pelt`, `cusum`, `linear`, `forecast` y derivados). Lista blanca: sin descriptor, no invocable. Cálculo de `available` según dependencias opcionales. Mínimo científico y parámetros obligatorios declarados aquí (no en `MethodSpec`).
- **Archivos:** `PY/handler/algorithm_registry.py`, `PY/knowledge/algorithms.json`.
- **Interfaces:** `get(algorithm_id)`, `find(solves=…)`, `is_available(id)`.
- **Criterios de aceptación:** cada descriptor resuelve a un `method_id` existente; un método no listado produce error al planificar; con una dependencia ausente el descriptor queda `available: false`; **ningún archivo de `M/` cambia**.
- **Pruebas:** de contrato sobre la ruta `analyze()` para cada método descrito (cubre el hueco detectado en la auditoría); simulación de dependencia ausente.
- **Entregable:** registro de algoritmos consultable.

### EMA-06 — Adaptadores al motor
- **Descripción:** `series_to_dataset` (`NormalizedSeries` → `ScientificDataset` con `TimeCoordinate`, unidad, `Provenance`, máscara, transformaciones), `method_call` (nodo → `MethodRequest` → `analyze`), `method_result_to_block` (completa unidades de salida, p. ej. °C/década), `time_numeric` (fechas ↔ años decimales).
- **Colaboradores:** Eze (`NormalizedSeries`, política de huecos).
- **Archivos:** `PY/handler/adapters/`.
- **Criterios de aceptación:** una serie mensual sintética con pendiente conocida produce, vía `sen`, la pendiente esperada en unidades por década; los huecos se excluyen y se registran, nunca se interpolan; la procedencia llega intacta al bloque de resultado.
- **Pruebas:** unitarias con series sintéticas; de ida y vuelta de tiempos.
- **Entregable:** puente entre datos y motor.

### EMA-07 — Resolución de intención y recetas
- **Descripción:** `recipes.json` con `R-DESCRIBE` y `R-TREND` (R1); `intent.resolve` con las reglas de `03` §5: fenómeno → recetas; restricción por `analysis.kind`; estado por fenómeno y por rama; `unsupported_requests`.
- **Archivos:** `PY/handler/intent.py`, `PY/knowledge/recipes.json`.
- **Criterios de aceptación:** N1.1.0 con variable T2m → `PARTIAL` con rama T2m planificada; una solicitud sin fenómeno **no** recibe uno inferido; la solicitud del Caso 8 → `UNSUPPORTED` con alternativas.
- **Pruebas:** tabla de casos (solicitud → intención esperada) que incluye los 10 casos de uso.
- **Entregable:** resolutor determinista.

### EMA-08 — Planificador DAG
- **Descripción:** expansión de recetas a nodos; integración con `SourceSelector`; extensión del período de descarga para la base climatológica; inserción de `align` y de controles; `node_id` por huella y deduplicación; verificación de aciclicidad; decisión `sync`/`async`.
- **Colaboradores:** Eze (`SourceSelector`).
- **Archivos:** `PY/handler/planner.py`.
- **Interfaces:** `build(canonical, intent) → AnalysisPlan`.
- **Criterios de aceptación:** el plan del Caso 1 coincide con el ejemplo de `09` §4; dos operaciones sobre la misma variable comparten el nodo `fetch`; misma entrada ⇒ mismo `plan_id`; **no hay acceso a red** durante la planificación.
- **Pruebas:** unitarias de deduplicación y orden; de determinismo; prueba que falla si el planificador abre una conexión.
- **Entregable:** `plan_analysis` funcional.

### EMA-09 — Ejecutor
- **Descripción:** recorrido topológico; nodos listos en paralelo acotado (un proveedor a la vez por fuente); memoización por `node_id`; propagación de `failed` → `skipped` con `blocked_by`; cancelación entre nodos; ensamblado parcial.
- **Colaboradores:** Eze (JobManager, caché, reintentos — interfaz acordada antes de empezar).
- **Archivos:** `PY/handler/executor.py`, `PY/handler/ops/analyze.py`, `ops/transform.py`.
- **Criterios de aceptación:** con un `fetch` que falla, las ramas independientes terminan y el estado es `partial`; cancelar detiene el job antes del siguiente nodo; un nodo compartido se ejecuta una sola vez.
- **Pruebas:** con conectores simulados (éxito, fallo definitivo, fallo recuperable, lentitud); de cancelación.
- **Entregable:** ejecución de planes.

### EMA-10 — Validadores científicos base y hallazgos
- **Descripción:** `validators.py` con Q03 (tendencia y significación) y Q12 (anomalía, tendencia y evento como salidas distintas); `qa_rules.json` con texto original, umbral y parametrización; `findings.build` con las reglas de `03` §11.2; `VizHint` por tipo de hallazgo; `how_computed`.
- **Colaboradores:** Eze (controles de datos), Juan (qué necesita cada vista).
- **Archivos:** `PY/handler/validators.py`, `findings.py`, `PY/knowledge/qa_rules.json`.
- **Criterios de aceptación:** una tendencia con p ≥ α produce `inconclusive` y el texto de "evidencia insuficiente" (T01); un control en `block` reemplaza el hallazgo por `data_gap` con la "salida ante falla" de la planilla; `evidence_level: "causal"` no es alcanzable por ningún camino.
- **Pruebas:** T01, T07 con datos sintéticos; prueba de que ningún hallazgo N2 sale sin `alternatives`.
- **Entregable:** resultados con semántica científica.

### EMA-11 — Comandos PyTauri del Handler
- **Descripción:** registrar en `desktop.py` `get_capabilities`, `validate_request`, `plan_analysis`, `submit_analysis`, `job_status`, `job_result`, `cancel_job`, `list_results`, cada uno con modelo Pydantic de entrada y respuesta `{…} | {error}`. Primero como esqueletos que devuelven los ejemplos fijos (desbloquea al frontend); luego conectados a `service.py`.
- **Colaboradores:** Eze (`job_*`), Juan (cliente).
- **Archivos:** `PY/desktop.py`, `PY/handler/service.py`.
- **Criterios de aceptación:** los 12 comandos existentes siguen funcionando sin cambios; los nuevos nunca lanzan `InvokeException` por errores de negocio.
- **Pruebas:** de contrato por comando (entrada y salida contra esquema).
- **Entregable:** API del Handler.

### EMA-12 — Algoritmo: climatología y anomalías (N01)
- **Descripción:** climatología por mes o período sobre una base fija; anomalías absoluta, porcentual, estandarizada y z robusto; reporte de años válidos por mes de la base.
- **Archivos:** `M/climate/climatology.py`, `M/tests/test_climatology.py`; registro aditivo en `extended_registry` solo si no implica tocar archivo protegido — en caso contrario, registro desde el Handler (decisión a tomar al implementar, con Eze como revisor).
- **Criterios de aceptación:** sobre una serie sintética estacional + tendencia, la anomalía recupera la tendencia; base con cobertura insuficiente → error explícito; unidades correctas (% vs unidad original).
- **Pruebas:** sintéticas; extremos (base de un año, mes sin datos, valores constantes).
- **Entregable:** método `climatology` / `anomaly`.

### EMA-13 — Algoritmo: intervalo de confianza de Theil-Sen (N02)
- **Descripción:** función nueva que calcula el IC de la pendiente de Sen al nivel pedido (**no** se modifica `sen_slope`, D-22).
- **Archivos:** `M/stats/sen_interval.py`, tests.
- **Criterios de aceptación:** coincide con `scipy.stats.theilslopes` en casos de referencia; el IC contiene la pendiente verdadera en simulación con la frecuencia esperada; documenta el supuesto de independencia.
- **Pruebas:** contra SciPy; simulación de cobertura; empates y n pequeño.
- **Entregable:** método `sen_interval`.

### EMA-14 — Algoritmo: SPI (N03)
- **Descripción:** acumulación a escalas 1/3/6/12; ajuste por mes con masa en cero; **calibración en un período explícito** separado del de aplicación (requisito de Q15 para uso predictivo); transformación a normal estándar con límites.
- **Archivos:** `M/climate/spi.py`, tests.
- **Criterios de aceptación:** sobre datos sintéticos de distribución conocida recupera valores esperados; base < 20 años → advertencia de baja robustez (Q05); nunca usa datos fuera del período de calibración para ajustar.
- **Pruebas:** sintéticas; meses con muchos ceros; prueba de no fuga (cambiar datos posteriores a la calibración no cambia los parámetros).
- **Entregable:** método `spi`.

### EMA-15 — Algoritmo: percentiles y eventos (N04)
- **Descripción:** umbrales por percentil (global o por período del año); detección de eventos por rachas con duración mínima; duración, intensidad y frecuencia.
- **Archivos:** `M/climate/events.py`, tests.
- **Criterios de aceptación:** eventos sintéticos insertados se recuperan con sus fechas; el umbral se calcula solo con la base.
- **Pruebas:** sintéticas; huecos dentro de un evento; serie sin eventos.
- **Entregable:** método `events`.

### EMA-16 — Algoritmos: correlación con desfases y FDR (N05, N06)
- **Descripción (dos PR):** (a) correlación para una lista **dada** de desfases, con tamaño efectivo de muestra por autocorrelación y variante parcial; (b) Benjamini-Hochberg por familia.
- **Archivos:** `M/stats/lagged.py`, `M/stats/multiple_testing.py`, tests.
- **Criterios de aceptación:** la función **no** ofrece "mejor desfase" como salida principal; series independientes autocorrelacionadas no producen significación espuria a la tasa nominal; BH coincide con una referencia.
- **Pruebas:** simulación de falsos positivos; T09 (24 desfases, uno significativo → no confirmatorio).
- **Entregable:** métodos `lagged_correlation`, `partial_correlation`, `fdr_bh`.

### EMA-17 — Receta multivariable `R-LAGREG`
- **Descripción:** receta que encadena anomalías → `align` → correlación con desfases del fenómeno → FDR → `multivariable` con diseño de rezagos → sensibilidad (variar base y período). Genera un `align` por subconjunto analizable.
- **Archivos:** `PY/knowledge/recipes.json`, `PY/handler/ops/`.
- **Criterios de aceptación:** Caso 2 produce el hallazgo `association` con `lag_selection: "predefined"`; si falta una variable opcional, las demás parejas se analizan.
- **Pruebas:** integración con series sintéticas con desfase conocido.
- **Entregable:** B3.5 y B2.2 ejecutables.

### EMA-18 — ModelRegistry y puerta de elegibilidad
- **Descripción:** `ModelDescriptor`, `HorizonRecord`, `models.json` (inicialmente con los descriptores de PRED-03 y sus baselines, todos `state: specified`); función `eligibility(model, request, data) → decisión` con los siete pasos de `03` §8.2.
- **Archivos:** `PY/handler/model_registry.py`, `PY/knowledge/models.json`.
- **Criterios de aceptación:** un fenómeno `historical_only` nunca planifica predicción; sin `backtest_id` el modo no puede ser `validated_forecast`; un predictor con `available_at > issue_time` se bloquea (T10).
- **Pruebas:** tabla de decisiones; T10.
- **Entregable:** elegibilidad predictiva.

### EMA-19 — Baselines y backtesting rolling-origin (N09, N07)
- **Descripción (dos PR):** climatología mensual y persistencia como pronósticos; backtesting con ventana expansiva que **envuelve** a `forecast` sin modificarlo, con transformaciones ajustadas dentro de cada pliegue, bloque final reservado y métricas por horizonte.
- **Archivos:** `M/forecasting/baselines.py`, `M/forecasting/backtest.py`, tests.
- **Criterios de aceptación:** un proceso sintético predecible da habilidad positiva; ruido blanco da habilidad ≈ 0 frente a la climatología; modificar datos posteriores a un origen no cambia la predicción de ese origen.
- **Pruebas:** sintéticas; de no fuga; T11.
- **Entregable:** evidencia de validación fuera de muestra.

### EMA-20 — Intervalos predictivos (N08)
- **Descripción:** cuantiles por horizonte a partir de residuales fuera de muestra; cobertura empírica en el bloque final; `calibrated` solo si está dentro de la tolerancia (D-21).
- **Archivos:** `M/forecasting/intervals.py`, tests.
- **Criterios de aceptación:** en simulación la cobertura empírica se acerca a la nominal; con pocos residuales devuelve "sin intervalo calibrado".
- **Pruebas:** simulación de cobertura.
- **Entregable:** incertidumbre predictiva con evidencia.

### EMA-21 — Receta `R-FORECAST` y línea PRED-03
- **Descripción:** nodos `eligibility → backtest → fit → predict → intervals`; `ForecastBlock` con modo, baseline, habilidad, cobertura; división validado / exploratorio; `VizHint: forecast_fan`. Primer modelo: T2m mensual.
- **Colaboradores:** Eze (caché de ajustes), Juan (gráfico).
- **Criterios de aceptación:** Caso 3 (con T2m) corre; si el modelo no supera al baseline se muestra el baseline con la bandera; el tramo exploratorio no lleva intervalo.
- **Pruebas:** integración con serie sintética; T10, T11.
- **Entregable:** recorrido 3.

### EMA-22 — Validadores Q04, Q13, Q17
- **Descripción:** Q04 (familia de pruebas, FDR, exploratorio si hubo selección a posteriori); Q13 (techo de `evidence_level`, alternativas obligatorias); Q17 (comparación por clase y estación; advertencia de cosecha o quema cuando haya cobertura del suelo).
- **Criterios de aceptación:** T09 y T16 pasan con datos sintéticos.
- **Entregable:** controles de N2.

### EMA-23 — Recetas `R-COUNT` y `R-AREA`
- **Descripción:** conteos por temporada y sensor; área por producto a partir de la salida zonal de Eze; tendencia sobre ambos, **como hallazgos separados**.
- **Criterios de aceptación:** T03, T04, T20.
- **Entregable:** N1.4.0, N1.4C, B9.1, B9.4.

### EMA-24 — Semántica de fuego y control Q14
- **Descripción:** unidad "detecciones"; `operational_disclaimer`; ningún `statement_key` de fuego usa "incendios" como conteo.
- **Criterios de aceptación:** T03; revisión de plantillas con JP.
- **Entregable:** hallazgos de fuego correctos.

### EMA-25 — Algoritmo: Fire Weather Index (N12)
- **Descripción:** FFMC, DMC, DC, ISI, BUI, FWI diarios según la formulación oficial, con ajuste de hemisferio sur, estado persistente y spin-up. Validación contra valores de referencia publicados. **Sin** versión mensual.
- **Depende de:** variables diarias de humedad relativa y viento (EZE-21).
- **Entregable:** B9.2 histórico.

### EMA-26 — Modalidad general fuera de catálogo
- **Descripción:** `R-GENERAL-UNI` y `R-GENERAL-MULTI`; chequeo de viabilidad; `exploratory: true`; sugerencia de fenómenos relacionados sin forzarlos.
- **Criterios de aceptación:** Caso 9 corre; una pareja no intercambiable → `UNSUPPORTED`; T18.
- **Entregable:** análisis general.

### EMA-27 — Capacidades
- **Descripción:** `capabilities.build(scope)` desde `knowledge/` + registros + estado de fuentes; `availability` y `branches` por fenómeno calculados, no escritos a mano; `fingerprint`.
- **Colaboradores:** Eze (`source_status`), JP (recorte para el contexto de la IA).
- **Criterios de aceptación:** al cambiar el estado de un conector, la disponibilidad de los fenómenos que dependen de él cambia sin editar otro archivo; el índice compacto de los 73 cabe en el presupuesto acordado con JP.
- **Entregable:** `get_capabilities`.

### EMA-28 — Algoritmos de segunda prioridad (uno por PR)
ETCCDI (N10) · bootstrap por bloques (N11) · métricas probabilísticas (N13). Cada uno con el mismo patrón que EMA-12.

### EMA-29 / EMA-30 — Líneas PRED-01 y PRED-02
Repiten EMA-21 con SPI calibrado dentro de cada pliegue (PRED-01) y predictores rezagados (PRED-02).

### EMA-31 — Retiro controlado de código duplicado
Según D-05: `evidence.summarize_series` deja de rotular "trend"; `execute_regression` y `handlers/analysis.py` quedan marcados como heredados. Sin borrar hasta la Fase 9.

### EMA-32 — Actualización de documentación del motor
`ENGINE_STATUS.md`, `SCIENTIFIC_CORE.md`, `LINEAR_REGRESSION.md`; resolución documentada de la discrepancia de `multi_ode.py` (D-07).

---

## Orden recomendado

`EMA-01 → 02 → 11 (esqueletos) → 03 → 04 → 27 → 05 → 06 → 12 → 13 → 07 → 08 → 09 → 10` (cierra R1) → `16 → 14 → 15 → 17 → 22 → 26` (R2) → `23 → 24` (fuego) → `18 → 19 → 20 → 21` (R3) → resto.

## Verificación propia antes de pedir revisión

1. `pytest` desde `src-tauri/` en verde, incluidos los tests existentes.
2. Ningún archivo listado en `M/PRESERVATION.json` aparece en el diff.
3. Los ejemplos fijos siguen validando contra los esquemas.
4. El caso de uso de la tarea corre con conectores simulados.
