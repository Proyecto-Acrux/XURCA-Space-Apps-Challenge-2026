# 03 — Diseño interno del Algorithm Handler

Rutas: `PY/` = `aplicacion/trend-scope/src-tauri/src-python/trend_scope/`, `M/` = `PY/models/`.

## 1. Qué es y qué no es

El Algorithm Handler es el **orquestador científico**: recibe una solicitud canónica, decide qué análisis corresponde, qué datos hacen falta, de qué fuente, con qué preparación, con qué métodos **ya registrados**, en qué orden, y con qué controles; ejecuta y devuelve un resultado trazable.

| No es | Por qué importa |
|---|---|
| Una biblioteca de ecuaciones | Toda la matemática vive en `M/`. El Handler no contiene fórmulas |
| Un modelo de lenguaje | No interpreta texto libre; recibe JSON validado |
| El frontend | No conoce componentes gráficos; emite metadatos de visualización |
| Un intérprete de configuraciones | Un JSON solo puede **referenciar** ids registrados (fenómenos, variables, fuentes, recetas, métodos, modelos). Nunca hay `eval`, importación dinámica ni nombres de función en la solicitud |

## 2. Ubicación y principio de no intrusión

- Paquete nuevo **`PY/handler/`**, fuera de `M/`. `M/` no se modifica: el Handler **importa** `scientific_registry`, `analyze`, `ExecutionContext` y los contratos v1.
- Datos declarativos en **`PY/knowledge/`** (JSON versionado).
- Preparación de datos en **`PY/dataprep/`**.
- Los conectores de `PY/services/` se envuelven, no se reescriben.
- Los algoritmos nuevos van en `M/` como **archivos nuevos**, uno por solicitud, y se registran de forma aditiva (como ya hace `extended_registry.py`).

```
PY/
├─ desktop.py                  (+ comandos nuevos; los 12 existentes se conservan)
├─ handler/
│  ├─ contracts.py             Ema   Modelos Pydantic v2 de todos los contratos públicos
│  ├─ errors.py                Ema   Códigos de error y excepciones tipadas
│  ├─ canonical.py             Ema   Valores por defecto, normalización y huella canónica
│  ├─ knowledge.py             Ema   Carga y verificación de integridad de knowledge/*.json
│  ├─ intent.py                Ema   Resolución de intención científica
│  ├─ algorithm_registry.py    Ema   AlgorithmDescriptor sobre scientific_registry()
│  ├─ model_registry.py        Ema   ModelDescriptor + registro de elegibilidad
│  ├─ planner.py               Ema   Recetas → DAG (AnalysisPlan)
│  ├─ executor.py              Ema   Recorrido del DAG, memoización, propagación de estados
│  ├─ validators.py            Ema   Controles científicos (Q03, Q04, Q12, Q13, Q14, Q16)
│  ├─ findings.py              Ema   Construcción de ScientificFinding y afirmaciones
│  ├─ capabilities.py          Ema   Respuesta de get_capabilities
│  ├─ service.py               Ema   Fachada: validate / plan / submit
│  ├─ adapters/                Ema   series_to_dataset, method_call, method_result
│  ├─ ops/                     Ema+Eze  Una función por tipo de nodo
│  ├─ source_registry.py       Eze   DataSourceDescriptor + SourceSelector
│  ├─ jobs.py                  Eze   JobManager
│  ├─ cache.py                 Eze   Caché de series y de resultados de nodos
│  └─ retry.py                 Eze   Reintentos, timeouts, clasificación de fallos
├─ dataprep/                   Eze   series, units, calendar, aggregate, align, qa, zonal, stations
├─ knowledge/
│  ├─ phenomena.json           Ema   73 fenómenos
│  ├─ variables.json           Ema   Variables canónicas y compatibilidades
│  ├─ recipes.json             Ema   Recetas de análisis
│  ├─ qa_rules.json            Ema+Eze  Q01–Q18 parametrizados
│  ├─ models.json              Ema   ModelRegistry + elegibilidad
│  └─ sources.json             Eze   16 conectores + productos
└─ models/                     (existente; solo archivos nuevos)
```

---

## 3. Flujo interno

```
solicitud JSON
   │
   ▼
[1] contracts.AnalysisRequest.model_validate      → INVALID_REQUEST
   │
   ▼
[2] canonical.normalize  (defaults + orden + huella)  → CanonicalRequest
   │
   ▼
[3] intent.resolve  (fenómenos / modalidad general / no soportado)  → ResolvedIntent
   │
   ▼
[4] planner.build   (recetas → nodos; fuentes; elegibilidad; controles)  → AnalysisPlan
   │                       ← aquí termina plan_analysis (sin descargar nada)
   ▼
[5] jobs.submit → executor.run  (DAG, caché, reintentos, cancelación)
   │
   ▼
[6] validators.run + findings.build
   │
   ▼
[7] AnalysisResult (JSON)
```

Los pasos 1–4 son **deterministas y sin red**: dada la misma solicitud canónica y la misma versión de `knowledge/`, producen el mismo plan. Esa es la base de la paridad manual/IA (T17) y de la reproducibilidad.

---

## 4. Recepción y normalización (`contracts.py`, `canonical.py`)

### 4.1 Validación

Pydantic v2 en modo estricto, con `extra="forbid"`. Se valida: tipos, enumeraciones, rangos (latitud/longitud, fechas, `start < end ≤ hoy`), geometría GeoJSON bien formada, CRS admitido (`EPSG:4326` en v2.0), ids existentes en `knowledge/`, y combinaciones permitidas (p. ej. `forecast.horizon` solo si `analysis.kind ∈ {forecast, scenario, composite, auto}`).

### 4.2 Valores por defecto científicamente justificados

| Campo | Valor por defecto | Fundamento | ¿Sujeto a decisión? |
|---|---|---|---|
| `scientific_params.baseline_period` | 1991–2020 si la fuente lo cubre; si no, el mayor período disponible, **rotulado** | Q02 | No |
| `scientific_params.min_coverage` | 0.8 | Q01, T06 | Configurable por producto |
| `scientific_params.significance_alpha` | 0.05 | T01 | No |
| `uncertainty.confidence_level` | 0.95 (intervalos de confianza de parámetros) | Planilla (IC95) | No |
| `uncertainty.interval_level` | 0.90 (intervalos predictivos) | Superprompt | No |
| `scientific_params.spi_scales` | [1, 3, 6, 12] | N1.2.0, N1.2C | No |
| `temporal.frequency` | La de la receta del fenómeno; en modalidad general, mensual | Planilla | No |
| `scientific_params.lags` | Los desfases **predefinidos** en la receta del fenómeno | Q04, T09 | Valores por fenómeno: D-03 |
| `location.spatial_mode` | `point` para punto; `entity` si la variable es de estación o tramo; `area_mean` para polígono solo si existe procesador zonal | Q09, Q18 | D-20 |
| `forecast.mode` | `auto` | Superprompt | No |
| `issue_time` | Instante de la solicitud, truncado al día UTC | Q15 | No |
| Período histórico mínimo para tendencia | **Sin valor en los documentos disponibles** | Falta `ANEXO_MATEMATICO.md` | **D-03** |

### 4.3 Información faltante

`validate_request` devuelve `missing[]` (campo, motivo, opciones sugeridas) en lugar de fallar cuando lo que falta se puede preguntar. La IA lo usa para pedir aclaraciones; el configurador, para marcar campos.

| Situación | Respuesta |
|---|---|
| Falta ubicación | `missing: location` |
| Nombre de lugar ambiguo | `missing: location` con candidatos de `search_places` |
| Fenómeno con varias variables objetivo y ninguna elegida | `missing: variables` con las opciones del fenómeno |
| Período ausente | Se propone el mayor período cubierto por la fuente preferida; queda como `assumption` |
| Pronóstico sin horizonte | `missing: forecast.horizon` con los horizontes habilitados |

### 4.4 Forma canónica y huella

`canonical.normalize` produce una `CanonicalRequest`:

1. aplica valores por defecto;
2. ordena listas sin orden semántico (variables, fenómenos, preferencias);
3. redondea coordenadas a 6 decimales y normaliza el sentido de los anillos;
4. resuelve alias de variables a ids canónicos;
5. **excluye de la huella** los campos no científicos: `request_id`, `input_mode`, nombres visibles, idioma.

`request_hash = sha256(JSON canónico)`. Dos solicitudes con los mismos parámetros científicos tienen la misma huella sin importar si vinieron del formulario o del asistente.

---

## 5. Resolución de intención científica (`intent.py`)

**Entrada:** `CanonicalRequest`. **Salida:** `ResolvedIntent`. Es un conjunto de reglas deterministas, no un clasificador.

```python
class ResolvedIntent(BaseModel):
    operations: list[Operation]           # qué hacer, en orden lógico
    phenomena: list[PhenomenonResolution] # un elemento por fenómeno pedido
    mode: Literal["catalog", "general", "unsupported"]
    assumptions: list[str]
    blocked: list[BlockedItem]            # lo que no se puede hacer y por qué
```

### 5.1 Tipos de operación

| `Operation.kind` | Qué hace | Recetas típicas |
|---|---|---|
| `descriptive` | Caracteriza lo observado | `R-DESCRIBE`, `R-COUNT`, `R-AREA` |
| `trend` | Cambio a lo largo del tiempo | `R-TREND`, `R-BREAK` |
| `anomaly` | Desvío respecto de una referencia; eventos | `R-ANOM`, `R-SPI`, `R-EXTREMES` |
| `multivariable` | Relaciones, desfases, asociaciones | `R-LAGREG`, `R-PARTIAL`, `R-PAIRED`, `R-COMPOSITE` |
| `forecast` | Estima valores futuros con modelo habilitado | `R-FORECAST` |
| `scenario` | Resultado condicionado a supuestos | `R-SCENARIO` |
| `composite` | Varias de las anteriores, ordenadas por dependencia | — |

### 5.2 Reglas

1. **Con `phenomenon_ids`:** cada id se busca en `phenomena.json`. Sus recetas determinan las operaciones. `analysis.kind` solo **restringe** (p. ej. `trend` descarta la parte predictiva).
2. **Sin fenómeno y con variables** → **modalidad general**:
   - una variable → `R-GENERAL-UNI` (descriptivo + anomalía + tendencia si hay datos suficientes);
   - dos o más → `R-GENERAL-MULTI` (alineación + correlación con lag 0 y desfases declarados por el usuario, FDR), **rotulado exploratorio**, sin hipótesis ni afirmaciones de fenómeno.
3. **Viabilidad de la modalidad general:** se verifica que cada variable tenga fuente utilizable, que las unidades y escalas sean comparables o agregables, y que ninguna pareja esté marcada `not_interchangeable` *para el uso pedido*. Si no → `UNSUPPORTED` con motivo.
4. **Nunca se fuerza un fenómeno** (T18): el Handler no infiere `phenomenon_ids` a partir de las variables. Puede **sugerir** fenómenos relacionados en `suggestions[]`, pero el plan sigue siendo general.
5. **Solicitudes fuera de los límites científicos** (p. ej. ubicación exacta de una ignición futura): cada fenómeno declara `unsupported_requests[]`; se devuelve `UNSUPPORTED` más `viable_alternatives[]`.
6. **Predicción:** se planifica solo si el modo del fenómeno lo admite **y** hay un modelo elegible (§8). Si no, la operación se degrada explícitamente (§8.3) y queda registrada.

### 5.3 Estado por fenómeno

```python
class PhenomenonResolution(BaseModel):
    phenomenon_id: str
    status: Literal["PLANNED", "PARTIAL", "HISTORICAL_ONLY", "UNSUPPORTED", "NOT_AUTOMATABLE",
                    "INSUFFICIENT_DATA", "SOURCE_UNAVAILABLE"]
    planned_branches: list[str]     # p. ej. ["T2m"]
    blocked_branches: list[BlockedItem]  # p. ej. LST: producto MOD11A2 sin procesador
    prediction_mode_catalog: str    # el del catálogo, sin alterar
    prediction_mode_effective: str | None
```

`PARTIAL` es frecuente y legítimo: N1.1.0 puede ejecutar la rama de temperatura del aire aunque la rama LST esté bloqueada.

---

## 6. Capa de conocimiento (`knowledge/`)

### 6.1 `phenomena.json`

Una entrada por fenómeno, **generada a partir de** `CATALOGO_V9_73.json` y de las columnas E–M de la planilla, con una sección de integración redactada por el equipo. Los textos científicos se copian **literalmente**.

```json
{
  "id": "B2.2",
  "level": "N2",
  "family": "B2",
  "title": "Estrés vegetal asociado a déficit de agua",
  "priority": "MVP",
  "evidence_level": "association",
  "source_text": {
    "preprocessing": "Anomalías estacionales, desfases ecológicamente plausibles y tipo de cobertura",
    "method": "Regresión dinámica con lags; sensibilidad; controles",
    "allowed_claim": "Disminución vigor coincide/precedida por déficit hídrico; hipótesis explícita",
    "forbidden_claim": "No declarar causalidad mediante correlación simple"
  },
  "variables": [
    { "variable_id": "ndvi", "role": "target", "required": true },
    { "variable_id": "precipitation_total", "role": "explanatory", "required": true },
    { "variable_id": "soil_moisture_rootzone", "role": "explanatory", "required": false },
    { "variable_id": "air_temperature_2m_mean", "role": "confounder", "required": false }
  ],
  "products": { "required": ["X06", "X01", "X09", "X02"], "optional": [] },
  "hypothesis": "El vigor disminuye durante o después de un déficit hídrico.",
  "recipes": ["R-LAGREG"],
  "recipe_params": {
    "lags": { "unit": "month", "candidates": [0, 1, 2, 3], "status": "proposed" },
    "anomaly": "seasonal",
    "frequency": "monthly"
  },
  "confounders_to_report": ["cambio de uso del suelo", "cosecha", "incendio", "temperatura"],
  "qa_checks": ["Q01", "Q02", "Q04", "Q06", "Q09", "Q10", "Q13", "Q17"],
  "prediction": { "catalog_mode": "derived_from_forecast", "families": ["M2", "M3"], "pred_lines": ["PRED-02"] },
  "unsupported_requests": [],
  "implementation_state": "specified"
}
```

`knowledge.py` verifica al cargar: 73 ids, 36 N1 + 37 N2, sin duplicados, ids idénticos a los del catálogo, toda variable/receta/control/producto referenciado existe. Si falla, el Handler no arranca.

### 6.2 `variables.json`

```json
{
  "variable_id": "land_surface_temperature_day",
  "label": { "es": "Temperatura superficial terrestre (día)", "en": "Land surface temperature (day)" },
  "quantity": "surface_skin_temperature",
  "unit": "degC",
  "aliases": ["LST", "lst_day"],
  "not_interchangeable_with": [
    { "variable_id": "air_temperature_2m_mean", "reason": "LST es temperatura radiométrica de la superficie; T2m es temperatura del aire a 2 m." }
  ],
  "attributes": { "requires": ["sensor", "overpass"] },
  "default_aggregation": "period_mean",
  "valid_range": [-90, 90]
}
```

Así el sistema **sabe** qué variables no deben mezclarse: no por una regla escrita en código, sino por un dato revisable por la ingeniera química.

### 6.3 `recipes.json`

Una receta es una plantilla de sub-grafo. Es la pieza que conecta los 73 fenómenos con las bibliotecas: **los fenómenos referencian recetas; las recetas referencian métodos registrados.**

| Receta | Propósito | Pasos (nodos) | Métodos del motor |
|---|---|---|---|
| `R-DESCRIBE` | Resumen descriptivo | fetch → normalize → qa → describe | — (estadísticos básicos) |
| `R-TREND` | Tendencia univariable | … → climatology → anomaly → `sen` → `seasonal_mann_kendall` / `modified_mann_kendall` → sen_interval | `sen`, `seasonal_mann_kendall`, `modified_mann_kendall`, N01, N02 |
| `R-ANOM` | Anomalías, percentiles, eventos | … → climatology → anomaly → events | N01, N04 |
| `R-SPI` | Déficit y exceso pluviométrico | … → to_monthly_total → spi(escalas) → events(estados) | N03, N04 |
| `R-EXTREMES` | Extremos por índice | … → etccdi(índice) → `sen` + MK por índice | N10, `sen`, `mann_kendall` |
| `R-COUNT` | Conteos y frecuencia por temporada | … → count_by(season, sensor) → describe / trend | — |
| `R-AREA` | Área por producto | fetch(raster) → mask_qa → geodesic_area → aggregate | dataprep |
| `R-BREAK` | Rupturas | … → `stl` → `pelt` (o `cusum`) | `stl`, `pelt`, `cusum` |
| `R-PREPOST` | Comparación antes/después | … → window(pre) / window(post) → difference | N14 |
| `R-PAIRED` | Diferencial pareado | … → pair(match) → difference → bootstrap | N11 |
| `R-LAGREG` | Asociación con desfases predefinidos | fetch×k → normalize → anomaly → align → lagged_correlation → fdr → `multivariable`(diseño con lags) → sensitivity | N05, N06, `multivariable` |
| `R-PARTIAL` | Correlación parcial | … → align → partial_correlation → fdr | N05, N06 |
| `R-COMPOSITE` | Estudio de eventos | … → events(driver) → composite(response) | N04 |
| `R-TRANSITION` | Cambio de cobertura | fetch(clases) → transition_matrix | N15 |
| `R-PHYS` | Fórmula física | … → formula | N12, N16 |
| `R-FORECAST` | Pronóstico | … → eligibility → backtest → fit → predict → intervals | `forecast`, N07, N08, N09 |
| `R-SCENARIO` | Escenario condicionado | … → predict(supuestos) | modelo + supuestos |
| `R-GENERAL-UNI`, `R-GENERAL-MULTI` | Modalidad fuera de catálogo | Subconjuntos de las anteriores | — |

Una receta declara `inputs` (roles de variables), `steps` (con dependencias entre sí), `params_schema` (qué parámetros admite y sus límites) y `checks` (qué Q aplican).

---

## 7. `AlgorithmRegistry` (`algorithm_registry.py`)

**Problema:** `MethodSpec` describe cómo llamar a un método, pero no **qué problema científico resuelve**, qué roles de entrada exige, ni su estado de validación. Y no se puede modificar.

**Solución:** un `AlgorithmDescriptor` por método, almacenado junto al registro del Handler, que **referencia** un `method_id` de `scientific_registry()`.

```python
class AlgorithmDescriptor(BaseModel):
    algorithm_id: str               # == method_id del motor
    solves: list[str]               # p. ej. ["trend.magnitude"], ["trend.significance"]
    category: str
    input_roles: list[InputRole]    # target, time, second_variable, features, seasons…
    dimensions: list[tuple[str, ...]]
    requires_regular_time: bool
    min_observations_scientific: int | None   # mínimo científico; None = pendiente (D-03)
    parameters: dict[str, ParamSpec]          # tipo, rango, obligatorio, valor por defecto
    units: UnitRule                 # cómo se derivan las unidades de la salida
    output_kind: str
    assumptions: list[str]          # p. ej. "independencia serial"
    limitations: list[str]
    validation_state: Literal["specified", "implemented", "unit_tested",
                              "numerically_validated", "approved"]
    evidence: list[str]             # rutas a tests y documentos
    optional_dependency: str | None
    protected: bool                 # está en PRESERVATION.json
    available: bool                 # calculado al arrancar
```

Reglas:

- El registro se construye al arrancar: `scientific_registry(include_optional=True)` + descriptores. Un método del motor **sin descriptor no es invocable** por el Handler (lista blanca).
- `available = False` cuando falta la dependencia opcional → el planificador elige la alternativa declarada o devuelve `METHOD_NOT_AVAILABLE`.
- Agregar un algoritmo = archivo nuevo en `M/`, registro aditivo, descriptor nuevo, y (si aplica) referencia desde una receta. **El núcleo del Handler no se toca.**

### Selección de método

La selección no es libre: la determina la receta. Donde hay alternativas, la regla está escrita:

| Decisión | Regla | Origen |
|---|---|---|
| Magnitud de la tendencia | `sen` (no OLS) | Planilla: "Sen" en 10 fenómenos; Q03 |
| Significación | Serie con estacionalidad → `seasonal_mann_kendall`; con autocorrelación significativa en los residuales → `modified_mann_kendall`; si falta la dependencia → MK estacional con advertencia | Q03 |
| Ruptura | `stl` + `pelt`; sin `ruptures` → `cusum` con advertencia | Planilla ("ruptura"); D-09 |
| Asociación | Correlación con desfases **predefinidos** + FDR; luego regresión con los mismos desfases | Q04, T09 |
| Serie irregular (SWOT) | Métodos que no exigen paso constante (`sen`, `mann_kendall`); los que lo exigen quedan excluidos | `requires_regular_time` |
| Pronóstico | El modelo lo decide el `ModelRegistry`, no la receta | §8 |

---

## 8. `ModelRegistry` y elegibilidad (`model_registry.py`, `knowledge/models.json`)

Se mantiene **separado** del `AlgorithmRegistry`: `sarima` es una función matemática; "SARIMA de T2m mensual para un punto, validado a 3 meses" es un modelo ambiental con evidencia. La existencia de la primera no implica la del segundo.

```python
class ModelDescriptor(BaseModel):
    model_id: str                 # p. ej. "pred03.t2m_monthly.sarima"
    version: str
    family: str                   # M1, M0, M2, M3, M4, M5, M6A, M6B, F1, F5
    pred_line: str | None         # PRED-01..08
    target_variable: str
    predictors: list[PredictorSpec]      # con available_at_rule (Q15)
    algorithm_id: str             # método del AlgorithmRegistry que lo implementa
    baseline_ids: list[str]       # climatología, persistencia…
    training_scope: Literal["per_series", "regional"]
    region_validity: RegionRule
    spatial_scale: str
    frequency: str
    depends_on: list[str]         # otros model_id (M0←M1, M3←M1+M2 …)
    requirements: DataRequirements       # historia mínima, cobertura; valores "proposed" hasta D-03
    horizons: list[HorizonRecord]        # evidencia por horizonte
    calibration_state: Literal["none", "intervals_checked", "calibrated"]
    state: Literal["specified", "implemented", "unit_tested", "backtested",
                   "calibrated", "validated_operationally"]
    limitations: list[str]

class HorizonRecord(BaseModel):
    horizon: Horizon
    scope: EligibilityScope       # variable, región/ubicación, frecuencia, estación del año
    backtest_id: str | None
    skill_vs_baseline: float | None
    interval_coverage: float | None
    n_origins: int | None
    status: Literal["not_evaluated", "passed", "failed"]
```

### 8.1 Entrenamiento e inferencia separados

| Etapa | Dónde ocurre | Cuándo |
|---|---|---|
| Preparación de datos de entrenamiento | Nodos `fetch/normalize/qa` del DAG | En la consulta, con caché |
| Entrenamiento | Nodo `fit` | Modelos `per_series`: bajo demanda, **cacheado** por huella de (serie, modelo, versión). Modelos `regional`: fuera de línea, artefacto versionado |
| Validación | Nodo `backtest` (rolling-origin) | Bajo demanda y cacheada, o fuera de línea |
| Calibración | Nodo `intervals` | A partir de residuales fuera de muestra |
| Registro | `models.json` + almacén de artefactos | Al aprobar evidencia |
| Inferencia | Nodo `predict` | En la consulta |
| Seguimiento | Registro de pronósticos emitidos para verificación posterior | Fase 9 |

**Un modelo no se reentrena en cada consulta**: la huella de la serie de entrenamiento decide si el ajuste y el backtest cacheados siguen siendo válidos.

### 8.2 Puerta de elegibilidad

Se evalúa en el planificador (lo que se puede saber sin datos) y otra vez en ejecución (lo que depende de los datos).

1. ¿El modo del fenómeno en el catálogo admite predicción? Si es `historical_only` → no se planifica.
2. ¿Existe un `ModelDescriptor` para (variable objetivo, frecuencia, escala)? Si no → `MODEL_NOT_ELIGIBLE`.
3. ¿La ubicación está dentro de `region_validity`?
4. ¿Hay historia suficiente y con cobertura (`requirements`)?
5. ¿Los predictores están disponibles **a la fecha de emisión** (`available_at ≤ issue_time`)? Si no → se bloquea el predictor (`LEAKAGE_BLOCKED`, T10).
6. ¿El horizonte pedido ≤ máximo horizonte con `status = passed` para este alcance?
7. ¿El backtest muestra `skill_vs_baseline > 0` en el bloque de prueba final y la cobertura de intervalos dentro de tolerancia (D-21)?

### 8.3 Qué pasa cuando no se cumple

| Situación | Resultado |
|---|---|
| Todo se cumple | `mode: validated_forecast`, con horizonte, skill y cobertura |
| Horizonte pedido > horizonte validado | Se entrega el tramo validado; el resto, si el usuario lo acepta, como `exploratory_extrapolation` **sin intervalo nominal** |
| El modelo no supera al baseline | Se muestra el **baseline** con la bandera "no superior a la referencia" (T11, Q16) |
| Historia insuficiente | Solo análisis descriptivo, o baseline rotulado; se informa cuánto falta |
| Faltan predictores futuros legítimos | `conditional_scenario` si el usuario aporta supuestos; si no, modelo reducido o rechazo |
| Sin modelo | `MODEL_NOT_ELIGIBLE` + alternativa histórica |

### 8.4 Predicción encadenada

- Las dependencias M1 → M0, M1 → M2, M1+M2 → M3, M1+M2+M3 → M4, M1 → M5, M5+M2+M3+F1 → M6A, M6A/F1 → M6B, M3 + área quemada → F5 se declaran en `depends_on` y el planificador las ordena. No hay ciclos (no existe realimentación fuego → clima).
- **Coherencia de trayectorias:** cuando hay ensembles, cada miembro lleva un `member_id`. El modelo aguas arriba genera los miembros **conjuntamente** (temperatura y precipitación del mismo miembro provienen de la misma trayectoria), y los modelos aguas abajo consumen los mismos `member_id`. Está prohibido muestrear entradas de forma independiente por variable.
- El resultado registra `inputs_from_models[]` en cada pronóstico y `uncertainty.propagation` (`ensemble_members` | `residual_based` | `not_propagated`).

---

## 9. Planificador (`planner.py`)

**Entrada:** `CanonicalRequest` + `ResolvedIntent`. **Salida:** `AnalysisPlan` (ver `09_CONTRATOS_JSON_API.md`).

### 9.1 Tipos de nodo

| `op` | Función | Responsable | ¿Red? | ¿Cacheable en disco? |
|---|---|---|---|---|
| `fetch` | Llama a un conector envuelto | Eze | Sí | Sí |
| `normalize` | Unidades, calendario, serie normalizada | Eze | No | No |
| `qa` | Cobertura, flags, máscaras | Eze | No | No |
| `transform` | Agregación, climatología, anomalía, SPI, desfase, conteo | Ema (matemática) / Eze (agregación) | No | No |
| `align` | Alineación temporal y espacial de varias series | Eze | No | No |
| `analyze` | Método del `AlgorithmRegistry` vía `analyze()` | Ema | No | No |
| `eligibility` | Puerta predictiva con datos reales | Ema | No | No |
| `backtest`, `fit`, `predict`, `intervals` | Línea predictiva | Ema | No | Sí (por huella de serie) |
| `validate` | Controles Q sobre resultados | Ema | No | No |
| `assemble` | Hallazgos y resultado final | Ema | No | No |

### 9.2 Construcción

1. Expandir cada operación en los pasos de su receta.
2. Para cada variable requerida, pedir al `SourceSelector` la fuente; insertar `fetch → normalize → qa`.
3. **Extender el período de descarga** cuando una transformación lo exige (p. ej. climatología 1991–2020 aunque el análisis sea 2006–2025) y registrarlo.
4. Insertar `align` cuando un paso consume más de una serie.
5. Insertar los controles Q declarados por receta y fenómeno.
6. **Deduplicar:** `node_id = sha256(op, parámetros canónicos, node_id de las entradas)`. Dos operaciones que piden la misma precipitación del mismo punto y período comparten el nodo `fetch` y todo lo que cuelga de él.
7. Verificar que el grafo es acíclico (orden topológico de Kahn); un ciclo es error de receta, no de usuario.
8. Estimar costo y decidir `execution_mode`: `sync` si todos los `fetch` están en caché o son de fuentes rápidas y no hay nodos predictivos; `async` en otro caso.

### 9.3 Garantías

- Una variable no se descarga dos veces en la misma ejecución.
- Una transformación no se recalcula si su nodo ya existe.
- El plan es **inspeccionable antes de ejecutar** (`plan_analysis`): muestra fuentes elegidas, alternativas, pasos, controles y lo bloqueado.

---

## 10. Ejecutor y gestión de ejecución (`executor.py`, `jobs.py`, `cache.py`, `retry.py`)

### 10.1 Modelo

Un solo proceso (el intérprete embebido). Sin colas externas ni base de datos. Es la solución más simple que cubre los requisitos: aplicación de escritorio, un usuario, pocas ejecuciones simultáneas.

- `JobManager`: diccionario en memoria `job_id → Job`, protegido con `Lock`; máximo de jobs simultáneos configurable (2 por defecto); los demás quedan `queued`.
- Cada job corre en un hilo vía `anyio.to_thread.run_sync` (el patrón que ya usa `desktop.py`).
- Dentro del job, los nodos listos (todas sus entradas completas) se ejecutan con un grupo de hilos acotado: en paralelo los `fetch` de **distintos** proveedores; en serie los del mismo proveedor (respeto de cuotas).
- Los nodos numéricos se ejecutan en serie (Numba y NumPy ya usan varios núcleos).

### 10.2 Estados de nodo

`pending → ready → running → completed | failed | skipped | cancelled | waiting_external`

Propagación: si un nodo falla, sus descendientes pasan a `skipped` con `blocked_by`. **Las ramas independientes continúan** → resultado `partial`.

### 10.3 Fallos

| Clase | Ejemplos | Tratamiento |
|---|---|---|
| Recuperable | Timeout, HTTP 429/5xx, error de red | Reintento con espera exponencial y variación aleatoria (3 intentos por defecto); respeta `Retry-After` |
| Definitivo | HTTP 4xx, credencial ausente, producto inexistente, datos insuficientes | Sin reintento; código de error tipado |
| Espera externa | Tarea AppEEARS en curso | `waiting_external` con sondeo de espera creciente y tiempo máximo |

### 10.4 Cancelación, tiempos y recursos

- Cancelación cooperativa: `cancel_job` marca el `ExecutionContext` (el del motor ya existe); se comprueba entre nodos, entre ventanas de descarga y dentro de `analyze()`.
- Timeout por nodo (según fuente) y por job (`constraints.max_runtime_s`).
- Límites: los del motor (256 MiB, 1e6 observaciones) + tamaño máximo de descarga por nodo + tope de celdas en análisis por rejilla.

### 10.5 Caché

| Nivel | Clave | Contenido | Vida útil | Ubicación |
|---|---|---|---|---|
| Memoria (por job) | `node_id` | Salida de cualquier nodo | El job | RAM |
| Disco: series | huella de (fuente, producto, variable, geometría/entidad, período, versión del conector) | `NormalizedSeries` + metadatos | Período cerrado: larga. Período que incluye datos recientes: según latencia del producto | `<datos de la app>/cache/series/` |
| Disco: predictivo | huella de (serie de entrenamiento, modelo, versión, horizonte) | Ajuste, backtest, residuales | Hasta que cambie la serie o la versión | `<datos de la app>/cache/models/` |
| Disco: resultados | `result_id` | `AnalysisResult` | Últimos N (configurable) | `<datos de la app>/results/` |

Todo acierto de caché queda registrado en el resultado (`cache_status` por nodo), con la fecha original de obtención: la reproducibilidad exige saber **cuándo** se bajó cada dato.

### 10.6 Progreso y resultados parciales

`job_status` devuelve `done_nodes / total_nodes`, el nodo en curso con una etiqueta legible y el estado por nodo. `job_result` puede pedirse con el job en curso: devuelve los bloques ya completos (`status: "partial"`). El frontend sondea; no se introduce un canal de eventos nuevo.

---

## 11. Validadores y hallazgos (`validators.py`, `dataprep/qa.py`, `findings.py`)

### 11.1 Reparto de los 18 controles

| Control | Dónde se evalúa | Responsable |
|---|---|---|
| Q01 cobertura, Q05 precipitación, Q06 QA óptico, Q07 sensor térmico, Q08 área quemada, Q09 compatibilidad espacial, Q10 compatibilidad temporal, Q11 unidades y datum, Q18 validación espacial | Nodos `qa` / `align` | Eze |
| Q02 climatología | Nodo `transform(climatology)` | Ema (cálculo) + Eze (cobertura de la base) |
| Q03 tendencia, Q04 pruebas múltiples, Q12 anomalía/tendencia/evento, Q13 causalidad, Q14 riesgo operacional, Q16 incertidumbre predictiva, Q17 línea base y uso del suelo | Nodo `validate` | Ema |
| Q15 sin fuga | Planificador + nodo `eligibility` | Ema |

Cada control produce un `ValidationStatus` con `status ∈ {pass, warn, block, not_applicable}`, lo medido, el umbral usado y su origen. **Los umbrales viven en `qa_rules.json`**, con el texto original de la planilla al lado, y son parametrizables por producto y método (como pide Q01).

Un `block` no aborta el job: bloquea **el hallazgo** que depende de ese control y produce en su lugar un hallazgo `data_gap` con la "salida ante falla" de la planilla (p. ej. "Datos insuficientes").

### 11.2 Construcción de hallazgos

`findings.build` convierte resultados numéricos en `ScientificFinding`. Reglas fijas:

| Regla | Origen |
|---|---|
| Una tendencia con p ≥ α o con IC que incluye 0 se emite como `conclusiveness: "inconclusive"` con el texto "no hay evidencia suficiente"; **nunca** "sin cambios" ni "variabilidad natural" | Q03, T01 |
| Anomalía, tendencia y evento son `finding_type` distintos y pueden coexistir (sequía actual sin tendencia significativa) | Q12, T07 |
| Todo hallazgo N2 lleva `evidence_level: "association"` (como máximo `"consistent_with_hypothesis"`), `alternatives[]` y nunca `"causal"` | Q13 |
| Si los desfases se eligieron por máxima correlación, o no se aplicó control de pruebas múltiples, el hallazgo es `exploratory: true` | Q04, T09 |
| `allowed_claims` y `forbidden_claims` se copian del fenómeno | Planilla, columnas J y K |
| Hallazgos de fuego e hidrología llevan el aviso "no operativo" y la referencia a organismos oficiales | Q14 |
| Un pronóstico que no supera al baseline lleva `not_superior_to_baseline: true` | Q16, T11 |

El enumerado `evidence_level` **incluye** `causal` para que el contrato pueda expresarlo algún día, pero ningún camino del código lo emite: requeriría un diseño de inferencia causal que hoy no existe.

---

## 12. Fachada y capacidades (`service.py`, `capabilities.py`)

```python
def get_capabilities(scope: CapabilityScope | None = None) -> Capabilities: ...
def validate_request(raw: dict) -> ValidationReport: ...        # pasos 1–3, sin red
def plan_analysis(raw: dict) -> AnalysisPlan: ...               # pasos 1–4, sin red
def submit_analysis(raw: dict, wait_ms: int = 0) -> JobStatus: ...
def job_status(job_id: str) -> JobStatus: ...
def job_result(job_id: str) -> AnalysisResult: ...
def cancel_job(job_id: str) -> JobStatus: ...
```

`get_capabilities` es la **única fuente de verdad** para la IA y para el configurador: fenómenos con su estado real, variables, recetas, parámetros permitidos, fuentes con estado de conexión y credenciales, modelos con horizontes habilitados, y la versión de `knowledge/`. Admite `scope` para pedir un recorte (p. ej. solo MVP, solo una familia), de modo que el contexto de la IA quepa en su presupuesto.

---

## 13. Reproducibilidad y trazabilidad

Cada `AnalysisResult` incluye: `request` canónica y su huella, `plan_id`, versión de `knowledge/`, versión de cada método (`method_version` del motor) y de cada modelo, fuente/producto/versión/fecha de obtención/URL por serie, entidad seleccionada y candidatos, todas las `transformations` en orden, parámetros efectivos (incluidos los valores por defecto aplicados), semilla donde haya aleatoriedad, y el estado de caché por nodo.

Con eso, repetir un análisis significa reenviar la misma solicitud canónica; si las fuentes no cambiaron (o se usa la caché), el plan y el resultado numérico son los mismos.

---

## 14. Seguridad

| Riesgo | Medida |
|---|---|
| Ejecución arbitraria desde JSON | Listas blancas: solo ids registrados; `extra="forbid"`; sin `eval`, sin importación dinámica, sin rutas de archivo en la solicitud |
| Salida de la IA maliciosa o malformada | Se valida con el mismo esquema que la entrada manual; la IA no tiene acceso a comandos de ejecución sin pasar por `validate_request` |
| Abuso de recursos | Límites de período, de fuentes por solicitud, de tamaño de descarga, de celdas y de tiempo |
| Fuga de credenciales | Las claves nunca entran en resultados, planes, huellas ni registros; `source_status` solo informa presencia |
| Solicitudes del lado servidor | Las URL las construye el conector a partir de ids validados; la solicitud no puede aportar URL |
| Datos de terceros como instrucciones | El texto que devuelven las fuentes se trata como dato y nunca se inserta en el prompt como instrucción |
