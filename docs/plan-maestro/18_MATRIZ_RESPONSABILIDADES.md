# 18 — Matriz de responsabilidades

**P** = propietario principal (decide e implementa) · **C** = colaborador (aporta o es consultado) · **R** = revisor obligatorio del PR · **—** = sin participación.

Regla de equipos (obligatoria): **Ema y Eze** son responsables de todo el backend, incluidas APIs y servicios del servidor. **JP, Juan y José** son responsables de IA conversacional, frontend y experiencia de usuario; ninguno implementa el motor científico.

## 1. Componentes

| Componente | Ubicación | Ema | Eze | JP | Juan | José |
|---|---|---|---|---|---|---|
| Contratos públicos y JSON Schema | `PY/handler/contracts.py`, `schemas/`, `fixtures/` | **P** | C | R | R | R |
| Errores tipados | `handler/errors.py` | **P** | C | — | C | C |
| Forma canónica y huella | `handler/canonical.py` | **P** | — | C | — | C |
| Capa de conocimiento: fenómenos, variables, recetas | `PY/knowledge/` | **P** | C | C | — | — |
| Reglas QA | `knowledge/qa_rules.json` | **P** | **P** (controles de datos) | — | — | — |
| Registro de fuentes | `knowledge/sources.json`, `handler/source_registry.py` | R | **P** | — | — | C |
| Resolución de intención | `handler/intent.py` | **P** | — | C | — | — |
| AlgorithmRegistry | `handler/algorithm_registry.py` | **P** | R | — | — | — |
| ModelRegistry y elegibilidad | `handler/model_registry.py`, `knowledge/models.json` | **P** | R | — | — | — |
| Planificador | `handler/planner.py` | **P** | C | — | — | — |
| Ejecutor | `handler/executor.py` | **P** | C | — | — | — |
| JobManager | `handler/jobs.py` | C | **P** | — | C | — |
| Caché | `handler/cache.py` | C | **P** | — | — | — |
| Reintentos y fallos | `handler/retry.py` | R | **P** | — | — | — |
| Operaciones de nodo: `fetch`, `normalize`, `qa`, `align` | `handler/ops/` | R | **P** | — | — | — |
| Operaciones de nodo: `transform`, `analyze`, `predict`, `validate`, `assemble` | `handler/ops/` | **P** | R | — | — | — |
| Adaptadores al motor | `handler/adapters/` | **P** | C | — | — | — |
| Validadores científicos y hallazgos | `handler/validators.py`, `findings.py` | **P** | C | C | C | — |
| Capacidades | `handler/capabilities.py` | **P** | C | C | — | C |
| Comandos PyTauri del Handler | `PY/desktop.py` | **P** | C | — | C | — |
| Motor matemático existente | `PY/models/` | **P** (custodia) | R | — | — | — |
| Algoritmos nuevos | `PY/models/` (archivos nuevos) | **P** | R | — | — | — |
| Línea predictiva: baselines, backtesting, intervalos | `PY/models/forecasting/` | **P** | R | — | — | — |
| Conectores | `PY/services/` (no `assistant*`) | R | **P** | — | — | — |
| Selección de estaciones | `PY/dataprep/stations.py` | R | **P** | — | — | — |
| Preparación de datos | `PY/dataprep/` | R | **P** | — | — | — |
| Procesadores de AppEEARS y ráster | `services/appeears.py`, `dataprep/` | C | **P** | — | — | — |
| Persistencia de configuración (servidor) | `PY/configuration.py` | C | **P** | — | — | C |
| CI y empaquetado | `.github/workflows/`, `pyproject.toml` | C | **P** | — | C | — |
| Transporte y proveedores del asistente | `PY/services/assistant*.py`, `gemini.py` | R | — | **P** | — | — |
| Contrato e instrucciones del asistente | `services/assistant-contract.json` | R | — | **P** | — | C |
| Guardia de afirmaciones | `services/assistant_guard.py` | R | — | **P** | — | — |
| Chat | `Assistant.svelte`, `AssistantConnection.svelte` | — | — | **P** | C | C |
| Aplicación de propuestas del asistente | `assistantConfiguration.js` | — | — | **P** | — | **P** |
| Proxy de Cloudflare | `TS/assistant-worker/` | — | — | **P** | — | — |
| Plantillas de hallazgos | `i18n` + `statement_key` | C | — | **P** | C | C |
| Cliente de API y modo simulado | `analysisApi.js` | C | C | C | **P** | C |
| Store de jobs y resultados | `stores/analysis.js` | — | C | — | **P** | C |
| Vistas de resultado | `components/results/` | C | — | — | **P** | — |
| Gráficos | `ChartView.svelte`, `charts.js` | — | — | — | **P** | — |
| Mapas y capas | `WorldMap.svelte`, `Globe.svelte` | — | C | — | **P** | C |
| «Cómo se calculó» | `components/results/` | C | — | C | **P** | — |
| Estado de ejecución | `components/results/` | — | C | — | **P** | — |
| Armado de solicitudes | `requestBuilder.js` | C | — | C | — | **P** |
| Configurador | `Settings.svelte`, `components/config/` | — | — | — | C | **P** |
| Vista de plan | `config/PlanPreview.svelte` | C | — | — | C | **P** |
| Errores y advertencias en la interfaz | `errors.js`, `ErrorPanel.svelte` | C | C | C | C | **P** |
| Estado del espacio de trabajo y migraciones | `stores/workspace.js`, `configuration.js` | — | C | C | C | **P** |
| Página principal y navegación | `routes/+page.svelte` | — | — | C | C | **P** |
| Internacionalización | `i18n.js` | — | — | C | C | **P** |

## 2. Entregables transversales

| Entregable | Propietario | Colaboradores |
|---|---|---|
| Decisiones pendientes (`21`) | Ema convoca; deciden los cinco | Ingeniera química en las científicas |
| Revisión científica de `phenomena.json` y de resultados | Ingeniera química | Ema |
| Ejemplos fijos de los 10 casos | Ema | Juan (los consume), JP |
| Matriz de aceptación T01–T21 | Ema (científicas) y Eze (datos) | JP (T17, T18), Juan (T03, T04, T20), José (T17) |
| Prueba de paridad T17 | JP | José, Ema |
| Guiones funcionales de interfaz | José | Juan |
| Verificación en campo de conectores | Eze | — |
| Integración final a `main` | Ema (backend), José (frontend) | Los cinco |

## 3. Reglas contra la propiedad ambigua

1. **Un archivo, un propietario.** Las dos excepciones declaradas son `qa_rules.json` (dividido por control, ver tabla de `03` §11.1) y `assistantConfiguration.js` (JP: validación y contexto; José: aplicación al store).
2. **`handler/ops/` se reparte por archivo**, no por líneas: `fetch.py`, `normalize.py`, `qa.py`, `align.py` son de Eze; `transform.py`, `analyze.py`, `predict.py`, `validate.py`, `assemble.py` son de Ema.
3. **`desktop.py`** es de Ema; Eze agrega comandos de datos mediante PR con Ema como revisora.
4. **Los archivos listados en `M/PRESERVATION.json` no se modifican** sin una decisión aprobada.
5. **Un cambio de contrato** lo implementa Ema, pero requiere la aprobación de una persona del equipo IA/frontend antes de integrarse.
6. **Quien necesita algo de un archivo ajeno** abre una solicitud a su propietario; no lo edita por su cuenta.

## 4. Zonas de conflicto y cómo evitarlas

| Archivo | Quiénes lo tocan | Mitigación |
|---|---|---|
| `PY/desktop.py` | Ema, Eze | Los comandos nuevos van en un bloque propio al final; la lógica vive en `handler/service.py` |
| `TS/src/routes/+page.svelte` | José, Juan, JP | José extrae primero los paneles a componentes; después cada uno trabaja en el suyo |
| `Settings.svelte` | José, JP | Las secciones nuevas son componentes en `components/config/` |
| `stores/workspace.js` | José, JP | Solo José cambia la forma del estado; JP usa las funciones de edición |
| `i18n.js` | Todos los de frontend | Un bloque de claves por área; José integra |
| `knowledge/*.json` | Ema, Eze | Un archivo por propietario; PR pequeños |
| `pyproject.toml` | Ema, Eze | Solo Eze lo edita |

## 5. Mecanismo de coordinación

Simple y sin herramientas nuevas:

- **Tablero único** (GitHub Projects o Issues) con una tarjeta por ID de tarea de los backlogs, en columnas Pendiente · En curso · En revisión · Hecho. El ID va en el título del PR.
- **Sincronización breve y periódica** de los cinco: qué terminó cada uno, qué lo bloquea, qué contrato quiere cambiar. La frecuencia la decide el equipo.
- **Canal de contratos:** todo cambio a `contracts.py`, a los esquemas o a los ejemplos se anuncia antes de integrarse, con etiqueta propia en el PR.
- **Demostración por recorrido:** cada recorrido (R1–R4) se cierra con una demostración en la aplicación de escritorio ante los cinco.
- **Decisiones registradas:** lo que se decide se anota en `21_RIESGOS_Y_DECISIONES.md` con fecha y responsables.
