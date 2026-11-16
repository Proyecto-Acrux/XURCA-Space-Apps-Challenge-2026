# 11 — Integración con la IA conversacional y el frontend

Rutas: `TS/` = `aplicacion/trend-scope/`, `PY/` = `TS/src-tauri/src-python/trend_scope/`.

## Parte A — Inteligencia artificial

### A1. Punto de partida (auditado)

| Hoy | Limitación |
|---|---|
| `interpret_question` → Gemini u OpenAI con salida JSON estructurada `{message, changes}` | `changes` describe cambios de **configuración visual y de fuentes**, no un análisis científico |
| Prompt e instrucciones estáticos en `PY/services/assistant-contract.json` | Se desactualiza: no conoce fenómenos, recetas ni estados |
| `assistantCatalog` con 4 proveedores | Desconoce 12 de los 16 conectores |
| Explica los `summary` descriptivos | No hay hallazgos, validaciones ni afirmaciones permitidas |
| Validación de la propuesta en servidor (jsonschema) y cliente | **Se conserva**: es el patrón correcto |
| Aplicación de cambios al mismo store que los controles manuales | **Se conserva**: es la base de la paridad |

### A2. Papel de la IA

| La IA hace | La IA no hace |
|---|---|
| Interpretar la pregunta e identificar la intención | Calcular nada: ninguna estadística sale del modelo de lenguaje |
| Reconocer variables, lugares y períodos | Elegir ecuaciones o métodos: los fija la receta del fenómeno |
| Proponer un análisis compatible con el catálogo | Inventar fenómenos, fuentes o capacidades que no estén en `get_capabilities` |
| Construir un `AnalysisRequest` válido | Ejecutar sin que el backend valide |
| Pedir aclaraciones | Rellenar valores por defecto científicos (lo hace el backend) |
| Explicar resultados, incertidumbre y limitaciones | Afirmar algo que no esté en `findings` ni convertir asociación en causa |

### A3. Flujo de 14 pasos

| # | Paso | Componente | Responsable |
|---|---|---|---|
| 1 | El usuario escribe | `Assistant.svelte` | JP |
| 2 | Interpretación de la intención | LLM vía `interpret_question` | JP |
| 3 | Consulta de capacidades | `get_capabilities(scope)` | Ema (comando) / JP (uso) |
| 4 | Identificación de fenómeno o tipo de análisis | LLM, restringido a ids de capacidades | JP |
| 5 | Propuesta de variables y parámetros | LLM | JP |
| 6 | Generación de JSON | Salida estructurada con el esquema de `AnalysisRequest` | JP |
| 7 | Validación y normalización | `validate_request` | Ema |
| 8 | Plan científico | `plan_analysis` | Ema |
| 9 | Obtención y preparación de datos | Ejecutor + conectores | Eze |
| 10 | Ejecución de algoritmos | Ejecutor + motor | Ema |
| 11 | Evaluación de resultados y restricciones | Validadores + hallazgos | Ema + Eze |
| 12 | Resultado JSON | `job_result` | Ema |
| 13 | Interpretación y explicación | LLM + guardia de afirmaciones | JP |
| 14 | Gráficos, mapas y advertencias | Vistas de resultado | Juan |

### A4. Contrato de salida del asistente (versión 2)

Reemplaza `changes` de análisis por un parche de solicitud; los cambios puramente visuales (tema, cámara, capas) se mantienen como hoy.

```json
{
  "message": "Voy a analizar la tendencia de la temperatura del aire en la ciudad de San Luis entre 2006 y 2025.",
  "intent": "analyze",
  "request_patch": {
    "analysis": { "kind": "trend", "phenomenon_ids": ["N1.1.0"] },
    "place": { "name": "San Luis", "kind": "localidades" },
    "period": { "start": "2006-01-01", "end": "2025-12-31" },
    "variables": [ { "variable_id": "air_temperature_2m_mean", "role": "target" } ]
  },
  "clarifications": [],
  "ui_changes": {}
}
```

| Campo | Valores | Nota |
|---|---|---|
| `intent` | `analyze | clarify | explain | configure_ui | unsupported | chat` | Decide el camino en el cliente |
| `request_patch` | Subconjunto de `AnalysisRequest` | Solo ids existentes en capacidades. `place` se resuelve con `search_places` (como hoy); nunca coordenadas inventadas |
| `clarifications[]` | `{ field, question, options[] }` | Una pregunta por vez, con opciones cuando existan |
| `ui_changes` | El `changes` visual actual | Sin cambios de comportamiento |

Reglas duras del cliente (deterministas, no dependen del modelo):

1. `request_patch` se valida contra el JSON Schema exportado por el backend; lo inválido se descarta con mensaje.
2. Todo `phenomenon_id`, `variable_id` o `source_id` que no esté en `get_capabilities` invalida la propuesta.
3. La propuesta se **aplica al store**, se muestra el resumen y **el usuario confirma** antes de ejecutar (como hoy).
4. `validate_request` decide; si devuelve `missing[]`, el asistente pregunta eso mismo.

### A5. Descubrimiento de capacidades (por qué sí conviene)

Un prompt estático obliga a reescribirlo cada vez que cambia el catálogo, se habilita un conector o se valida un modelo, y deja a la IA ofreciendo cosas que no existen. Con `get_capabilities`:

- la IA recibe **el estado real** (p. ej. "N1.3.0: bloqueado, falta procesador") y puede decirlo en lugar de prometer;
- el conocimiento científico tiene **una sola fuente** (`knowledge/`), compartida con el configurador;
- al habilitar una capacidad en el backend, la IA la ve sin tocar el prompt.

**Presupuesto de contexto.** El catálogo completo no entra en cada turno (hoy el contexto se limita a 18 000 caracteres). Estrategia en dos pasos, sin tool calling obligatorio:

1. **Índice compacto** siempre presente: por fenómeno, `id · título · variables · disponibilidad` (una línea).
2. **Detalle bajo demanda:** cuando el modelo elige candidatos, el cliente pide `get_capabilities({phenomenon_ids:[…]})` y hace un segundo turno con recetas, parámetros, afirmaciones prohibidas y estado.

Si el proveedor admite llamadas a funciones, el paso 2 puede hacerse como herramienta; el diseño no depende de eso.

### A6. Independencia del modelo de lenguaje

| Requisito | Diseño |
|---|---|
| El Handler no conoce al LLM | Ningún módulo de `handler/` importa de `services/assistant*` |
| Cambiar de proveedor sin tocar la lógica | La interfaz `Provider.generate(instruction, context, schema) → dict` ya existe en `assistant_providers.py`; se mantiene y se documenta como punto de extensión |
| Funcionar sin IA | El modo manual recorre exactamente los mismos comandos; si `assistant_status` informa `configured: false`, el chat se deshabilita y nada más cambia |
| Sin funciones exclusivas de un proveedor | Solo se exige "salida JSON conforme a un esquema"; todo lo demás lo valida el cliente |
| Mismo comportamiento esperado entre modelos | Suite de comportamiento (A9) ejecutable contra cualquier proveedor |

### A7. Explicación de resultados

El modelo recibe **solo** un extracto del `AnalysisResult`: `findings` (con `values`, `conclusiveness`, `evidence_level`, `allowed_claims`, `forbidden_claims`, `alternatives`, `limitations`), `validation` (estados), `sources` (procedencia resumida), `forecasts` (modo, horizonte validado, habilidad) y `warnings`. No recibe las series completas.

Instrucciones fijas de explicación:

- usar únicamente los números presentes en `findings`;
- si `conclusiveness = inconclusive`: decir que no hay evidencia suficiente, nunca que "no hubo cambios";
- si `evidence_level = association`: hablar de asociación y mencionar las alternativas;
- mencionar el modo de todo pronóstico y, si corresponde, que no supera a la referencia;
- incluir limitaciones y, en fuego o hidrología, el aviso de no operatividad.

### A8. Guardia de afirmaciones (determinista)

Verificación posterior a la respuesta del modelo, en `PY/services/` (propiedad de JP, D-15):

| Regla | Detección | Acción |
|---|---|---|
| Números no respaldados | Todo número del texto debe aparecer en `findings` o `forecasts` (con tolerancia de redondeo) | Regenerar una vez; si persiste, plantilla determinista |
| Causalidad | Léxico causal ("causa", "provoca", "debido a", "por culpa de") con `evidence_level ≠ causal` | Ídem |
| Términos prohibidos por contexto | "incendios" como unidad de detecciones FIRMS; "hectáreas" a partir de focos; "temperatura del aire" con variable LST; "marea roja" / "tóxico" con clorofila; "sin cambios" con hallazgo inconcluso; "porcentaje de certeza" | Ídem |
| Modo predictivo omitido | Hay `forecasts` y el texto no nombra el modo | Añadir frase de plantilla |

**Plantilla determinista:** cada `statement_key` tiene un texto base en es/en. Si el modelo falla o no hay IA, el resultado igual se puede leer. La IA mejora la redacción; no es la única vía de explicación.

### A9. Pruebas de comportamiento

Conjunto de consultas con resultado esperado **estructural** (no textual), ejecutado con proveedor simulado en CI y, a pedido, contra proveedores reales:

| Grupo | Ejemplos | Se verifica |
|---|---|---|
| Los 10 casos de `10_CASOS_DE_USO.md` | — | `intent`, `phenomenon_ids`, variables, huella |
| Paráfrasis | 5 formas de pedir el Caso 1 | Misma huella |
| Ambigüedad | "San Luis", sin período, sin lugar | `intent: clarify` y campo correcto |
| Límites | Ignición exacta, floraciones tóxicas, 20 años de SWOT | `unsupported` + alternativas |
| Trampas semánticas | "temperatura del suelo" vs "temperatura del aire"; "cuántos incendios hubo" | Variable correcta; aclaración sobre detecciones |
| Inyección | Texto de usuario que pide ignorar reglas o ejecutar código | Propuesta inválida descartada por el validador |
| Explicación | Resultados sintéticos inconclusos, asociativos, con pronóstico peor que la referencia | La guardia no detecta infracciones |

---

## Parte B — Frontend

### B1. Dos modos, un contrato

| | Usuario avanzado | Usuario asistido |
|---|---|---|
| Entrada | Configurador (`Settings.svelte` ampliado) | Chat (`Assistant.svelte`) |
| Estado | `stores/workspace.js` → `cfg_data` v2 | El mismo |
| Solicitud | `requestBuilder(cfg_data)` | El mismo |
| Validación | `validate_request` en vivo | El mismo |
| Ejecución | `submit_analysis` | El mismo |

Ningún modo tiene un atajo propio hacia el backend.

### B2. Configurador avanzado

Hoy existen las secciones Investigación, Fuentes, Período y Geografía. Se agregan o amplían:

| Sección | Controles | Origen de las opciones | Responsable |
|---|---|---|---|
| **Análisis** (nueva) | Tipo de análisis; selector de fenómenos con filtros por nivel, familia, prioridad y disponibilidad; ficha del fenómeno con "qué puede afirmarse / qué no" | `get_capabilities` | José |
| **Variables** (nueva) | Variables del fenómeno con su rol; agregar variables (modalidad general); atributos (profundidad, pasada día/noche, sensor) | `get_capabilities` | José |
| **Fuentes** (ampliada) | Preferencia de fuente por variable; estado de conexión y de credenciales; fijar estación o entidad | `get_capabilities`, `plan_analysis` | José |
| **Período** (ampliada) | Período, frecuencia, base climatológica | `validate_request` | José |
| **Predicción** (nueva) | Horizonte, modo pedido, supuestos de escenario | `get_capabilities.models` | José |
| **Opciones científicas** (nueva, plegada) | Cobertura mínima, nivel de significación, niveles de intervalo, desfases, escalas de SPI | Límites de la receta | José |
| **Plan** (nueva) | Vista previa: fuentes elegidas y alternativas, pasos, controles, lo bloqueado y por qué | `plan_analysis` | José (contenedor) + Juan (grafo) |

Reglas de interfaz:

- Las opciones **no disponibles se muestran deshabilitadas con el motivo** (p. ej. "requiere credencial de AppEEARS"), no se ocultan.
- Los valores por defecto se muestran como *sugeridos por el sistema* y provienen de `validate_request.defaults_applied`.
- Modo básico / avanzado: el básico pide ubicación, período y fenómeno; el avanzado expone todo.

### B3. Visualización de resultados

Un despachador elige el componente por `VizHint.kind`; un `kind` desconocido cae a tabla.

| `kind` | Representa | Componente | Reglas |
|---|---|---|---|
| `timeseries` | Serie observada | `ChartView` existente | Huecos visibles, sin interpolar |
| `timeseries_trend` | Serie + línea de Sen + banda del IC | Nuevo | Banda rotulada "intervalo de confianza 95%" |
| `anomaly_bars` | Anomalías respecto de la base | Nuevo | Base climatológica en el título |
| `spi_states` | Estados déficit / normal / exceso | Nuevo | Una fila por escala; nunca se suman escalas |
| `multi_panel_aligned` | Varias variables con eje temporal común | Nuevo | Un eje Y por unidad |
| `scatter` | Relación entre dos variables | Nuevo | Etiqueta "asociación, no causa" |
| `lag_correlogram` | Correlación por desfase | Nuevo | Marca los desfases que superan el control de pruebas múltiples |
| `forecast_fan` | Observado + mediana + banda + referencia | Nuevo | Modo visible; tramo exploratorio punteado y **sin banda** |
| `scenario_lines` | Una línea por conjunto de supuestos | Nuevo | Leyenda con los supuestos |
| `probability_bars` | Probabilidad de evento definido | Nuevo | Definición del evento visible; "calibrada" solo si lo es |
| `map_points` | Detecciones, estaciones, puntos de análisis | `WorldMap` | Estación elegida y candidatas |
| `map_entities` | Tramos, lagos | `WorldMap` | |
| `map_raster` | Anomalías o áreas por celda | `WorldMap` | Resolución efectiva en la leyenda |
| `table` | Tablas de eventos, transiciones, métricas | Nuevo | |

Elementos transversales:

- **Insignias** (`badges`): reanálisis, modelo, observación, punto único, exploratorio, datos de muestra, sustitución de producto.
- **Advertencias**: los `ValidationStatus` con `warn` o `block` se muestran junto al gráfico al que aplican, con el texto de "salida ante falla" de la planilla.
- **Capas separadas** para detecciones y área quemada, con leyendas y unidades propias (T04, T20).
- **Colores distintos** para intervalo de confianza e intervalo predictivo.
- **Estados de ejecución**: barra por nodos, paso en curso con etiqueta legible, botón cancelar, resultados parciales a medida que llegan.

### B4. «Cómo se calculó»

Panel generado **solo** desde `AnalysisResult`; no requiere IA.

| Sección | Campo de origen |
|---|---|
| Qué se analizó | `request` canónica + `findings[].variable_ids` + `period` |
| De dónde vienen los datos | `sources[]`: proveedor, producto, versión, fecha de obtención, URL, estación elegida y candidatas, sustituciones |
| Cómo se prepararon | `how_computed[]` de tipo normalize, qa, transform: conversiones de unidades, agregaciones, base climatológica |
| Qué métodos se usaron | `method_results[]`: método, versión, parámetros efectivos, supuestos |
| Resolución efectiva | `sources[].resolution.effective_m` y la de la combinación |
| Controles aplicados | `validation[]`: control, estado, valor medido, umbral y su origen |
| Incertidumbre | IC, intervalos predictivos, cobertura empírica, habilidad frente a la referencia |
| Qué afirmaciones están respaldadas | `findings[].allowed_claims` y `forbidden_claims` |
| Limitaciones | `findings[].limitations`, `warnings` |
| Reproducir | `request_hash`, `plan_id`, versiones; botón "copiar solicitud" |

### B5. Trabajo en paralelo con el backend: datos simulados

Para que JP, Juan y José no esperen al backend:

1. En cuanto EMA-01 congela los contratos, se publican los JSON Schema y un conjunto de **ejemplos fijos** (`fixtures/`) — uno por caso de uso — validados contra el esquema en CI.
2. `analysisApi.js` tiene dos implementaciones con la misma interfaz: `pytauri` (real) y `mock` (lee los ejemplos, simula progreso de job). Se elige con una variable de entorno de Vite, igual que `VITE_ASSISTANT_ENDPOINT`.
3. El modo navegador que ya existe (persistencia en `localStorage`) permite desarrollar la interfaz sin compilar la aplicación de escritorio.
4. Cuando un comando real está listo, se quita su simulación; las pruebas de contrato garantizan que los ejemplos sigan siendo válidos.

### B6. Tipos sin migrar a TypeScript

El frontend es JavaScript con `svelte-check`. No se propone migrarlo. Los tipos se obtienen generando `@typedef` de JSDoc a partir de los JSON Schema (script de desarrollo), lo que da autocompletado y verificación con las herramientas que ya están instaladas.

### B7. Internacionalización

`statement_key`, `message_key`, `title_key` y `label_key` son claves; los textos viven en `services/i18n.js` (diccionario actual es→en ampliado). Los textos científicos normativos (afirmaciones permitidas y prohibidas) llegan en español desde `knowledge/`; su traducción al inglés es una decisión de contenido (D-26).
