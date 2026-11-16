# 02 — Auditoría del repositorio y de la documentación

Fecha de auditoría: 2026-11-15. Commit auditado: `c8f6555` (rama `main`). Auditoría de **solo lectura**: no se ejecutaron tests ni benchmarks; las cifras de "tests passed" son las que declaran los documentos del repo.

Convenciones de este documento:

- **[HECHO]** comprobado leyendo código o documento.
- **[DECLARADO]** lo afirma un documento del repo; no fue re-ejecutado.
- **[FALTA]** se buscó y no existe.
- **[CONTRADICCIÓN]** dos fuentes no coinciden; queda para decisión (ver `21_RIESGOS_Y_DECISIONES.md`).

Rutas abreviadas: `TS/` = `aplicacion/trend-scope/`, `PY/` = `TS/src-tauri/src-python/trend_scope/`, `M/` = `PY/models/`.

---

## 1. Resumen ejecutivo

1. **[HECHO] El motor científico existe pero no está conectado a la aplicación.** `M/` contiene ~31 métodos registrados, contratos, validación y ejecución con cancelación; ningún comando que use la interfaz los invoca. Lo que el usuario ve hoy es `PY/services/evidence.py`: media, mínimo, máximo y una pendiente por mínimos cuadrados en Python puro.
2. **[HECHO] El catálogo de 73 fenómenos no aparece en ningún archivo de código.** No hay mapeo fenómeno → variable → fuente → método.
3. **[HECHO] No hay API HTTP.** Frontend y Python se comunican por comandos PyTauri (`PY/desktop.py`, 12 comandos). Todo "endpoint" del plan es un comando PyTauri nuevo.
4. **[HECHO] 10 de 16 conectores devuelven series normalizadas; 6 son parciales** (5 solo descargan archivos crudos; FIRMS funciona en código pero su acceso autenticado no fue verificado en campo).
5. **[HECHO] La selección automática de estaciones sigue con el problema documentado**: gana el primer candidato con al menos un valor.
6. **[HECHO] No hay modelos predictivos ambientales.** Hay funciones de pronóstico estadístico genéricas (naive, Holt-Winters, ARIMA/SARIMA) con un único holdout, sin incertidumbre ni backtesting rodante, y ningún modelo entrenado o persistido.
7. **[FALTA] `ANEXO_MATEMATICO.md`, `FUENTES_Y_CONECTORES.csv`, la hoja `Ruteo_Competencia_73` y la imagen del esquema conceptual.** Consecuencia: no existe en ningún documento disponible una matriz numérica de mínimos históricos ni de horizontes por modelo.

---

## 2. Estructura del repositorio

| Ruta | Contenido | Estado |
|---|---|---|
| `README.md`, `AGENTS.md`, `LICENSE` | Organización y reglas de arquitectura (SvelteKit, PyTauri, store único, `cfg_*.json`) | Versionado |
| `CLAUDE.md` (raíz) | Vacío (0 bytes) | Versionado |
| `CATALOGO_V9_73.json`, `Trend_Detective_*.txt`, `Trend_Detective_v9_*(1).xlsx`, `SUPERPROMPT_MAESTRO.md` (+ copia idéntica), `EARTH_DETECTIVE_VARIABLES_Y_RECURSOS.txt`, `Importante.md` | Documentos científicos | **Sin versionar** (untracked) |
| `Memoria/` | Notas, enlaces y recursos del desafío | Versionado |
| `web app/` | Landing estática para Vercel; sin relación con la app | Versionado |
| `TS/` | Aplicación de escritorio | Versionado |
| `TS/src/` | Frontend SvelteKit: 1 ruta, 9 componentes, 10 servicios, 1 store | |
| `TS/src-tauri/` | Rust mínimo (arranque del intérprete), `pyproject.toml`, `Cargo.toml` | |
| `PY/` | Backend Python: `desktop.py`, `services/`, `handlers/`, `models/` | |
| `TS/config/` | `cfg_data.json`, `cfg_visual.json`, muestras de cobertura | |
| `TS/docs/` | `fuentes-de-datos.md`, `chat-ia.md`, `asistente-gemini.md`, `SOUL.md`, copia del inventario | |
| `TS/assistant-worker/` | Proxy opcional de Gemini en Cloudflare Workers | |
| `TS/.github/workflows/publish.yaml` | Empaquetado para 6 plataformas; no corre tests; al no estar en la raíz, GitHub probablemente no lo detecta | |

### Tecnologías existentes

| Capa | Tecnología | Nota |
|---|---|---|
| Frontend | SvelteKit ^2.9 (adapter-static, SPA), Svelte ^5 (runes), Vite ^6.3 | **JavaScript, no TypeScript** (`typescript` solo para `svelte-check`) |
| Mapa | MapLibre GL 5 (globo) + respaldo d3-geo sin conexión | |
| Gráficos | Chart.js 4 | |
| Puente | PyTauri 0.8 sobre Tauri 2.8.3 (pyo3 0.25) | Intérprete Python embebido; sin sidecar ni HTTP local |
| Backend | Python ≥3.9 declarado (probado en 3.11.9), Pydantic 2, jsonschema, anyio 4 | |
| Numérico | NumPy, Numba, SciPy (núcleo); statsmodels, scikit-learn, PyWavelets, ruptures, river, pymannkendall, tslearn (**opcionales, fuera de `pyproject.toml`**) | |
| Tests | pytest (131 funciones de test en 18 archivos); `node:test` (1 archivo, 3 tests) | Sin script `test` en `package.json`, sin CI de tests |

### Ramas

`main` contiene a todas las demás (`ema_workspace`, `eze_w`, `API`, `Primeros_pasos_Appweb`): ninguna tiene commits que `main` no tenga.

---

## 3. Comunicación y comandos existentes

`TS/src-tauri/src/main.rs` arranca Python embebido → `PY/__main__.py` → `PY/desktop.py:main()` → `commands.generate_handler(portal)`. El frontend llama con `pyInvoke(nombre, body)`.

| Comando (`PY/desktop.py`) | Entrada | Salida | ¿Lo usa la UI? |
|---|---|---|---|
| `load_configuration` | `{name}` | JSON crudo | Sí |
| `save_configuration` | `{data, visual}` (exige `schemaVersion 1`) | `bool` | Sí |
| `acquire_data` | `{investigation}` (= `cfg_data`) | JSON: lista de series con `summary` | Sí |
| `list_appeears` | `{product?}` | productos o capas | Sí |
| `list_ina_variables` | `{}` | variables INA | Sí |
| `search_places` | `{query, kind, language}` | lugares con coordenadas | Sí |
| `execute_regression` | `{algorithm, x[], y[], options?}` | `{success, data|error}` | **No** |
| `evaluate_coverage` | `{variable, start, end, scope}` | `{matches}` | Sí (asistente) |
| `interpret_question` | `{question, language, endpoint?, context}` | `{message, changes}` | Sí |
| `assistant_status` / `configure_assistant` / `disconnect_assistant` | conexión del proveedor | estado | Sí |

Todos los errores salen como `InvokeException(str(ValueError))`: **no hay códigos de error estructurados**.

---

## 4. Pipeline actual de punta a punta

1. `+page.svelte: run()` → `acquireData(investigation)` → `pyInvoke('acquire_data')`.
2. `services/acquisition.validate_investigation`: `schemaVersion 1`, fechas, 1–25 fuentes; **si `methods` no está vacío lanza «Los métodos personalizados todavía no están conectados»**.
3. `services/acquisition.acquire`: POWER en lote → cada fuente por tabla de rutas (con `fetch_for_selection` si resuelve estación) → Open-Meteo.
4. `services/evidence.with_evidence` agrega `summary` (`method: "descriptive-v1"`, tendencia `ordinary-least-squares`, `confidenceInterval: null`).
5. UI: pestañas por serie → `Results.svelte` → `ChartView.svelte` (Chart.js, decimación min/max).

**No existen**: orquestador, jobs, colas, progreso, cancelación en el flujo real, caché de series, persistencia de resultados, promedios por polígono, pronóstico.

**Bug probable (inferido, no ejecutado):** con la opción por defecto «Usar la única selección compatible», `geometryId` queda `null` y las rutas de entidad (NOAA, SWOT, INA, PSMSL) no pasan `validate_investigation`; `run()` solo completa `geometryId` para POWER y Open-Meteo.

---

## 5. Motor científico (`M/`)

Detalle completo y clasificación en `06_MATRIZ_ALGORITMOS.md`. Hechos estructurales:

- **Contratos v1** (`M/contracts.py`, dataclasses congeladas): `ScientificDataset`, `VariableData`, `TimeCoordinate`, `Coordinate`, `Provenance`, `Transformation`, `AnalysisRequest(analysis_id, method_id, variable, parameters)`, `AnalysisResult`, `ODEProblem`.
- **Registro** (`M/registry.py`, `M/extended_registry.py`): `MethodSpec` + `MethodRegistry`; `scientific_registry()` registra 21 métodos fijos y hasta 10 condicionados a dependencias opcionales.
- **Ejecución** (`M/execution.py`): `analyze(data, request, registry, context)` valida límites (256 MiB, 1e6 observaciones), dimensiones, n mínimo, parámetros desconocidos, y soporta cancelación cooperativa y checkpoints de progreso vía `ExecutionContext`.
- **Rejilla** (`M/adapters/grid.py`): `analyze_grid` aplica un método por celda de `(time,y,x)`, con tope por defecto de 100 celdas.
- **Serialización estricta** (`M/serialization.py`).
- **Dos sistemas de despacho que no se comunican**: `PY/handlers/analysis.py` (cadena de `if`, salida `FitOutput` TypedDict, 7 regresiones) y `MethodRegistry` + `analyze` (salida `AnalysisResult`).
- **[DECLARADO]** `M/ENGINE_STATUS.md`: estado *candidate, no aprobado*; sin auditoría independiente; sin prueba nativa ni end-to-end; 94 tests pasados con imports normales.
- **[CONTRADICCIÓN]** `M/PRESERVATION.json` registra SHA-256 de 36 archivos protegidos; normalizando finales de línea coinciden 35. **`M/dynamical/multi_ode.py` no coincide** con su hash, aunque `ENGINE_STATUS.md` afirma que la preservación coincide.
- **[HECHO]** Documentación desactualizada: `SCIENTIFIC_CORE.md` y `stats/LINEAR_REGRESSION.md` describen como roto un dispatcher ya corregido.

---

## 6. Conectores de datos

Detalle en `07_MATRIZ_FUENTES.md`. Hechos transversales:

- **Sin esquema formal de serie**: dict *ad hoc* `{id, provider, product?, variable, unit, points:[{month, value, ...}], coordinates?, url, retrievedAt, cadence?, selectedEntity?, ...}`. El campo de fecha se llama `month` aunque contenga días o timestamps.
- **Sin reintentos ni backoff.** Timeouts fijos de 25–90 s. Toda excepción se vuelve `ValueError` con texto en español.
- **Fallo en cadena**: si una fuente falla, falla toda la adquisición.
- **Caché**: solo `lru_cache` de catálogos de estaciones por proceso; las descargas crudas se guardan en `%LOCALAPPDATA%\com.xurca.trend-scope\downloads\`. FIRMS re-descarga siempre.
- **Tres registros parciales de fuentes** que no coinciden entre sí: `services/catalog.py` (18 rutas, 3 sin implementación), `services/source-coverage.json` (7 productos), `src/lib/services/sources.js` (16 proveedores, 35 variables predefinidas).
- **Credenciales** por variables de entorno: `FIRMS_MAP_KEY`, `APPEEARS_TOKEN` o `EARTHDATA_USERNAME/PASSWORD`, `EARTHDATA_TOKEN`, `CDSE_ACCESS_TOKEN`, `CDSAPI_KEY`. Ninguna descarga autenticada fue verificada en campo.

### Selección de estaciones (`PY/services/station_catalogs.py:151-204`)

| Aspecto | Comportamiento actual |
|---|---|
| Candidatos | Orden por distancia; radio 150 km (NOAA, INA, PSMSL), 20 km (tramos SWOT), 10 km (lagos SWOT); máximo 12 |
| Polígono | Punto-en-polígono, orden desde el centro del rectángulo envolvente |
| Elección | El **primer** candidato con ≥1 valor no nulo |
| Cobertura temporal previa | Solo INA; NOAA usa `ghcnd-stations.txt` (sin períodos) |
| Errores | Una excepción en un candidato **aborta** el recorrido |
| Corrección manual | Se retiraron los campos de ID manual |

---

## 7. IA conversacional

- **Vive en Python + frontend**; Rust no participa. Proveedores: Gemini (`generateContent` con `responseJsonSchema`) y OpenAI (`/v1/responses` con `json_schema strict`), más un proxy opcional en Cloudflare.
- **Contrato estático** `PY/services/assistant-contract.json`: prompt del sistema en inglés + esquema de salida `{message, changes{...}}`.
- **Hace dos cosas**: proponer cambios de configuración (validados en servidor con jsonschema y en cliente; aplicados al mismo store que los controles manuales) y explicar los `summary` vigentes. **No ejecuta análisis ni hay tool calling.**
- **Conocimiento limitado**: `assistantCatalog` cubre solo POWER, NOAA mensual, SWOT y Open-Meteo.
- Claves en memoria de proceso o variables de entorno; no se persisten.
- `TS/docs/SOUL.md` describe el comportamiento deseado como "futura integración".

---

## 8. Frontend

- Una sola vista (`src/routes/+page.svelte`, 363 líneas) con menús, herramientas de mapa, paneles y diálogos.
- `Settings.svelte`: secciones Investigación, Fuentes, Período, Geografía. El estado incluye `methods` pero **no hay sección de métodos renderizada**.
- Estado único: `stores/workspace.js` (`{data: cfg_data, visual: cfg_visual}`).
- Sin tipos formales: las formas son las de `TS/config/cfg_data.json` (`schemaVersion 1`).
- i18n casera (`services/i18n.js`, diccionario es→en); varios textos fijos en español.

---

## 9. Documentos científicos

| Documento | Verificación |
|---|---|
| `CATALOGO_V9_73.json` | 73 fenómenos (36 N1 + 37 N2), sin ids duplicados; `status = SPECIFIED_NOT_IMPLEMENTED` en los 73; no contiene prioridad |
| `Trend_Detective_..._SIMPLIFICADO_PARA_IA.txt` | Coincide campo a campo con la planilla en los 73 ids (omite "fuentes opcionales" en 6 fenómenos N2) |
| Planilla `.xlsx` | 8 hojas leídas; 27 columnas por fenómeno; 13 MVP / 33 P2 / 27 P3; 8 líneas PRED; 18 QA; 21 pruebas |
| `SUPERPROMPT_MAESTRO.md` y copia `(1)` | **Idénticos** (mismo hash) |
| `EARTH_DETECTIVE_VARIABLES_Y_RECURSOS.txt` | 16 conectores; idéntico a la copia en `TS/docs/` |
| `Importante.md` | Lista los 5 documentos como referencia de implementación |

### Faltantes y qué condicionan

| Faltante | Qué se esperaba | Parte del diseño condicionada |
|---|---|---|
| `ANEXO_MATEMATICO.md` | Ecuaciones y matriz de mínimos históricos y horizontes por modelo | Umbrales del registro de elegibilidad: quedan como valores iniciales propuestos, marcados como pendientes |
| `FUENTES_Y_CONECTORES.csv` | Tabla producto ↔ conector | Se reemplaza por la matriz de `07_MATRIZ_FUENTES.md`, derivada del código y del inventario |
| Hoja `Ruteo_Competencia_73` | Ruteo recurso de competencia → producto por fenómeno | El ruteo se reconstruye desde las columnas S–W de la planilla |
| Imagen del esquema conceptual | Diagrama de bloques original | Se usó la descripción textual del pedido (usuario/IA → JSON → Handler → bibliotecas/modelos/fuentes → resultados → interfaz) |
| Documentación de integración numérica y regresiones | — | Sí existe: `M/dynamical/RK4.md`, `M/stats/LINEAR_REGRESSION.md`, `POLYNOMIAL_REGRESSION.md`, `STAGE1A.md` |
| Informes de validación / seguimiento | `VALIDATION_REPORT.md`, `IMPLEMENTATION_STATUS.json` | No existen; el seguimiento real está en `M/ENGINE_STATUS.md` |

---

## 10. Contradicciones entre fuentes

Se listan para revisión; **ninguna se resolvió en silencio**. Las decisiones propuestas están en `21_RIESGOS_Y_DECISIONES.md`.

| # | Contradicción |
|---|---|
| C01 | **Vocabularios de modo distintos**: catálogo (`historical_only / direct_forecast / derived_from_forecast / conditional_scenario`), superprompt en respuesta (`validated_forecast / conditional_scenario / exploratory_extrapolation`), en pedido (`auto|forecast|scenario|extrapolation`), y estados `UNSUPPORTED / NOT_AUTOMATABLE / UNAVAILABLE / EXPERIMENTAL` |
| C02 | **Nomenclatura de modelos**: el superprompt define F2=M5, F3=M6A, F4=M6B; el catálogo mezcla M5/M6A/M6B con F1/F5 |
| C03 | **Familia vs modo en el catálogo**: N1.8.0, B8.1, N1.3A y B8.3 tienen familia predictiva pero modo `historical_only`; siete fenómenos son `conditional_scenario` sin familia |
| C04 | **PRED-07 (nivel de agua)** propone pronóstico, pero N1.9.0/N1.9A/N1.9B/B3.4 son históricos o escenario y el superprompt no define modelo hidrológico |
| C05 | **PRED-08 (SST y clorofila)** propone pronóstico, pero N1.1.1 es `historical_only` y ningún modelo M cubre SST ni clorofila |
| C06 | **PRED-06** es P3 y "escenario exploratorio", pero N1.4C es MVP con modo `direct_forecast` |
| C07 | **Métodos distintos para el mismo objetivo**: lluvia (SARIMA + ridge con ENSO vs logística + Gamma/Tweedie), área quemada (zero-inflated vs hurdle Gamma/lognormal), T2m (SARIMA/ETS vs ARX regularizado) |
| C08 | **Horizontes**: PRED-01 dice 1–3 meses sin condición; el superprompt los condiciona a reforecasts con skill |
| C09 | **Piloto 2015–2025 (11 años)** frente a Q05 (SPI con <20 años = baja robustez) y Q02 (base 1991–2020) |
| C10 | **Intervalos**: IC95 para tendencias (planilla) vs PI 90% por defecto (superprompt); PRED-02/03 dicen "cobertura IC" para pronósticos |
| C11 | **Presión**: glosario en hPa; NASA POWER entrega `PS` en kPa y no es presión reducida al nivel del mar |
| C12 | **B6.3 mal ruteado**: variables radiación/AOD/nube con productos requeridos ENSO/IMERG/ERA5 |
| C13 | **Columna G vs S** en N1.4A (texto de temperatura en un fenómeno FIRMS) y N1.1C |
| C14 | **Recursos de competencia sin conector**: Giovanni figura en los 73 fenómenos; KNMI en 22; Hydrology TS en 21. A la inversa, Open-Meteo, INA, PSMSL y Planetary Computer no figuran en la planilla |
| C15 | **ERA5 (X02, 24 fenómenos)** se propone vía CDS, pero la app lo consume como serie solo vía Open-Meteo (8 variables fijas) |
| C16 | **Productos X sin ficha** en `FUENTES_Y_ENLACES_v8`: X22, X24, X26, X27, X29 |
| C17 | **Glosario duplicado**: SPI, FRP, dNBR, T2m y WSE con definición heredada v4 y definición nueva |
| C18 | **Estados**: catálogo (todo `SPECIFIED_NOT_IMPLEMENTED`), planilla (13 "Implementar"), superprompt (estados finos que nadie rellena) |
| C19 | **`dschg_c` de SWOT** (caudal, requerido por B3.4 y PRED-07) no devolvió valores válidos en pruebas |
| C20 | **`PRESERVATION.json` vs `multi_ode.py`** (ver §5) |
| C21 | **Estado del motor**: el pedido habla de algoritmos "validados"; `ENGINE_STATUS.md` los declara *candidate, no aprobado* |
| C22 | **Python**: `pyproject.toml` declara ≥3.9; el superprompt pide ≥3.11; los opcionales se probaron en 3.11.9 |

---

## 11. Qué reutiliza el plan y qué no existe

| Se reutiliza tal cual | Se envuelve con adaptador | Hay que construir |
|---|---|---|
| `M/` completo (métodos, contratos v1, `analyze`, `ExecutionContext`, `analyze_grid`, serialización) | Conectores de `PY/services/` (aislamiento de fallos, reintentos, caché, serie normalizada) | Paquete `handler/` (contratos v2, intención, planificador, ejecutor, validadores, hallazgos, capacidades) |
| Comandos PyTauri existentes | `evidence.summarize_series` (queda como resumen descriptivo) | Capa de conocimiento `knowledge/` (73 fenómenos, variables, fuentes, QA, modelos) |
| Chat (transporte, proveedores, validación) | `assistant-contract.json` (nueva versión del esquema) | Algoritmos faltantes del MVP: climatología/anomalías, SPI, IC de Sen, eventos por percentil, correlación con lags + FDR, backtesting, intervalos |
| Mapa, gráficos, store, i18n | `Settings.svelte` (nuevas secciones) | Parseo de AppEEARS a serie; estadística zonal; selección de estaciones por puntaje |
