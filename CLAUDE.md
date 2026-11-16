# CLAUDE.md — Traspaso de contexto (2026-11-15)

Proyecto: **Earth Detective / XURCA** (NASA Space Apps 2026). App de escritorio Tauri + SvelteKit + Python (PyTauri) en `aplicacion/trend-scope/`. Idioma de trabajo: español rioplatense. Lee también `AGENTS.md` (raíz) y `aplicacion/trend-scope/src-tauri/src-python/trend_scope/models/CLAUDE.md` (reglas del motor científico).

## Qué se hizo en esta sesión

Se refinó y se implementó la arquitectura del backend propuesta en `Mapa_frontend.png`:

`request.json` → **Data Handler** → **Analysis Handler** (devuelve un **Analysis Struct**) → **Algorithm Handler** (librerías de cálculo y predictivas) → Data Handler arma `response.json` → frontend / chatbot.

- Especificación completa: `docs/plan-maestro/23_ARQUITECTURA_HANDLERS.md` (formato de request y response, handlers, structs, librerías de cálculo y predictivas).
- Orden de trabajo y estado: `aplicacion/trend-scope/src-tauri/src-python/trend_scope/handlers/AGENTS.md`.
- Cola de funciones científicas (W01–W20): `.../trend_scope/models/AGENTS.md` §6.
- Todo está subido a `main` en GitHub (último commit de la sesión: ver `git log`).

## Decisión del equipo que manda sobre todo lo demás

**No hacer benchmarks ni pruebas automáticas ni verificaciones de ejecución.** Se quiere terminar la app rápido y probarla a mano. Por eso **ningún código de esta sesión se ejecutó, importó ni probó**. Es esperable encontrar errores de ejecución al arrancar: corregirlos sin rediseñar.

## Estado por fase

| Fase | Contenido | Estado |
|---|---|---|
| 0 | `robust_z` de W01 con factor 1,4826 (la MAD de la referencia queda sin escalar) | Hecha |
| 1 | `handlers/` (contracts, analysis_structs, analysis_handler, preparation, algorithm_handler, decision, data_handler), comandos `run_analysis` y `list_analyses` en `desktop.py`, W17 y W18 | Hecha |
| 2 | W05 (correlación con desfases), W04 (percentiles y eventos) + structs `seasonality`, `change_point`, `smoothing`, `extreme_events`, `relationship` | **Pendiente** (declarados con `planned=True`) |
| 3 | Pronóstico: W07–W09, W13, W20 + `forecast_backtest`; W06; structs `forecast` y `spatial_pattern`; `spatial.py` | Hecha |
| 4 | W19, W10, W11, W12, W14, W15, W16 como API de Python | Hecha (sin registrar ni usar desde structs) |

Structs disponibles hoy: `describe`, `trend_significance`, `anomaly`, `drought_spi`, `regression_fit`, `forecast`, `spatial_pattern`.

## Mapa de archivos (PY = `aplicacion/trend-scope/src-tauri/src-python/trend_scope/`)

- `PY/handlers/contracts.py` — Pydantic del request/response, códigos de error, `request_hash`, `export_schemas()`.
- `PY/handlers/analysis_structs.py` — catálogo declarativo de análisis (`STRUCTS`, `BY_ID`); agregar un análisis = agregar una entrada.
- `PY/handlers/analysis_handler.py` — `resolve`, `check`, `capabilities`, topes provisionales de horizonte.
- `PY/handlers/preparation.py` — series → `ScientificDataset` (fechas, agregación, huecos, tiempo numérico, etiquetas de mes, período de referencia).
- `PY/handlers/algorithm_handler.py` — ejecuta los pasos de un struct con `catalog_registry()` + `analyze()`; sin fórmulas.
- `PY/handlers/decision.py` — hallazgos (qué / dónde / cuánto / significativo) y veredicto de la hipótesis; reglas deterministas.
- `PY/handlers/data_handler.py` — `run(request) -> response`; reutiliza `services.acquisition.acquire` y `services.evidence.with_evidence`.
- `PY/handlers/spatial.py` — muestreo de puntos dentro de un polígono (nunca un promedio zonal).
- `PY/models/` — motor científico (registro de 39 métodos en `catalog_registry.py`). Archivos nuevos: `stats/{diagnostics,descriptive,multiple_testing,bootstrap}.py`, `forecasting/*`, `climate/etccdi.py`, `signal/convolution2d.py`, `fire/fwi.py`, `vegetation/burn_indices.py`, `landcover/transitions.py`, `atmosphere/hypsometric.py`.

## Reglas que hay que respetar

- No tocar `web app/`. No tocar `services/` ni el frontend sin pedido. No modificar archivos de `models/PRESERVATION.json`.
- Los handlers **no contienen fórmulas**: todo cálculo sale de un método del motor.
- Nada de interpolación, orden ni conversión de unidades implícitos; toda transformación va en `transformations`.
- Nunca un «porcentaje de certeza»; p ≥ α o intervalo con 0 → «no hay evidencia suficiente», jamás «sin cambios».
- Valores provisionales (no vienen de la investigación): `min_points` 10, topes de horizonte (mensual 12, diario 14, anual 5), `max_origins` 24, `min_residuals` 10, `baseline_min_count` 3, `mk_lag` 1, `n_points` 9. Decisiones D-03 y D-21 pendientes (`docs/plan-maestro/21_RIESGOS_Y_DECISIONES.md`).
- Git: no hacer commit ni push sin pedido. El usuario autorizó subir a `main` en esta sesión.

## Pendientes y riesgos conocidos

1. **Probar la app a mano** (`pnpm tauri dev` desde `aplicacion/trend-scope`): `run_analysis` con `trend_significance` sobre `power-temperature` (San Luis, 2000–2024) y `list_analyses`. Ante errores, corregir el módulo afectado.
2. **Frontend sin conectar:** no hay botón ni servicio que llame a `run_analysis`; falta `runAnalysis(request)` en `src/lib/services/acquisition.js` y mostrar hallazgos/veredicto. El chatbot (`assistant.py`, `assistant-contract.json`) sigue con su contrato anterior; el plan es que reciba `response.assistant_digest` y arme `request.json` desde `list_analyses`.
3. **Fase 2** sin hacer (ver tabla).
4. **Dependencias opcionales** (`statsmodels`, `pymannkendall`, `ruptures`) están en el venv pero no declaradas en `src-tauri/pyproject.toml` (decisión D-06: pedir visto bueno antes de tocarlo). Sin ellas el pronóstico solo usa `seasonal_naive` y no hay Mann-Kendall modificado.
5. **Sin generar** los JSON Schema ni fixtures: `contracts.export_schemas()` los produce bajo demanda.
6. **Auditoría independiente** pendiente de W01–W03 y de todo lo nuevo; todo está en estado `candidate`.
7. `fire/fwi.py`: rechaza |lat| < 30° y no se comparó con tablas de referencia. `catalog_registry.py` no registra las librerías de la fase 4.
8. `tests/test_climatology.py` se ajustó a mano al nuevo `robust_z` sin correrlo; si la suite vuelve a usarse, empezar por ahí. Tests que cuenten métodos del registro pueden fallar (se agregaron `describe` y `forecast_backtest`).
9. Avisos de Git sobre LF/CRLF al hacer commit: inofensivos.
10. Desvíos respecto del plan 23: sin paso `lttb` en `describe` (arreglos largos se omiten con aviso); `lag1_autocorrelation` acepta `groups`; código de error nuevo `CADENCE_INCOMPATIBLE`; el pronóstico es un único método registrado (`forecast_backtest`) que compone W07–W09 y W20.

## Cómo seguir

Si el usuario pide continuar: primero confirmar que la app arranca y que `run_analysis` responde; después fase 2 (W05, W04 y sus structs), conexión del frontend y del chat, y por último auditoría. Respetar el protocolo de una función por solicitud de `models/AGENTS.md`.
