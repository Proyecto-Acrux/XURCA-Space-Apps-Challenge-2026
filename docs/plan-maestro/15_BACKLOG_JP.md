# 15 — Backlog de JP · Inteligencia artificial conversacional

**Rol:** arquitectura de interacción con IA; interpretación de consultas; identificación de intenciones; resolución de variables y fenómenos; generación de JSON; integración con capacidades; aclaraciones; interpretación de resultados; explicación de evidencia e incertidumbre; control de afirmaciones no sustentadas; pruebas de comportamiento.

**Propiedad de archivos:** `TS/src/lib/components/Assistant.svelte`, `AssistantConnection.svelte`, `TS/src/lib/services/assistantConfiguration.js`, `TS/assistant-worker/`, `PY/services/assistant.py`, `assistant_providers.py`, `gemini.py`, `assistant-contract.json` (los cuatro últimos según D-15, con revisión obligatoria de Ema).

**Límite:** JP no implementa lógica del motor científico ni comandos del Handler. Lo que necesite del servidor se pide como cambio de contrato a Ema o Eze.

Rutas: `TS/` = `aplicacion/trend-scope/`, `PY/` = `TS/src-tauri/src-python/trend_scope/`.

## Resumen

| ID | Título | Prior. | Compl. | Fase | Depende de |
|---|---|---|---|---|---|
| JP-01 | Contrato de salida del asistente v2 | P0 | M | F1 | EMA-01 |
| JP-02 | Contexto dinámico desde capacidades | P1 | L | 6b | EMA-27 (o simulación) |
| JP-03 | Interpretación de intención y de fenómeno | P1 | L | 6b | JP-01, JP-02 |
| JP-04 | Flujo de aclaraciones | P1 | M | 6b | JP-03 |
| JP-05 | Explicación de resultados | P1 | L | R4 | EMA-10 (o ejemplos fijos) |
| JP-06 | Guardia de afirmaciones | P1 | M | R4 | JP-05 |
| JP-07 | Suite de comportamiento | P0 | L | 6b | JP-01 |
| JP-08 | Paridad manual e IA | P1 | M | R4 | JOSE-01, EMA-02 |
| JP-09 | Independencia del proveedor | P1 | S | 6b | JP-01 |
| JP-10 | Respuestas ante límites científicos | P1 | S | R4 | JP-03 |
| JP-11 | Proxy de Cloudflare: nuevo esquema | P2 | S | F7 | JP-01 |
| JP-12 | Plantillas deterministas de hallazgos | P1 | M | R1 | EMA-10 |

---

## Tareas

### JP-01 — Contrato de salida del asistente v2
- **Descripción:** nueva versión de `assistant-contract.json`: salida `{message, intent, request_patch, clarifications, ui_changes}` (ver `11` §A4). `request_patch` referencia el JSON Schema de `AnalysisRequest` exportado por el backend, **no una copia**. Validación en servidor (`assistant.validate_proposal`) y en cliente (`assistantConfiguration.validate`). El `changes` visual actual pasa a `ui_changes` sin cambios de comportamiento.
- **Colaboradores:** Ema (esquema), José (aplicación al store).
- **Archivos:** `PY/services/assistant-contract.json`, `assistant.py`, `TS/src/lib/services/assistantConfiguration.js`.
- **Interfaces:** comando `interpret_question` (misma firma; cambia el contenido de la respuesta, con campo de versión).
- **Criterios de aceptación:** una propuesta con un `phenomenon_id` inexistente se rechaza; los cambios visuales siguen funcionando; las pruebas existentes de `test_chat_workflow.py` se actualizan y pasan.
- **Pruebas:** unitarias de validación en ambos lados con propuestas válidas, inválidas y maliciosas.
- **Entregable:** asistente que emite solicitudes, no configuraciones de fuente.

### JP-02 — Contexto dinámico desde capacidades
- **Descripción:** reemplazar `assistantCatalog` y el `source-coverage.json` embebido por `get_capabilities`. Índice compacto de los 73 fenómenos siempre presente (una línea: id, título, variables, disponibilidad); segundo turno con el detalle de los candidatos (`get_capabilities({phenomenon_ids})`). Presupuesto de caracteres medido y con prueba.
- **Colaboradores:** Ema (forma del índice compacto).
- **Archivos:** `Assistant.svelte` (`contextFor`), `assistant.py`.
- **Criterios de aceptación:** el contexto no supera el límite vigente con el catálogo completo; al cambiar el estado de un fenómeno en el backend, el asistente lo refleja sin tocar el prompt; con capacidades simuladas funciona igual.
- **Pruebas:** de tamaño de contexto; de frescura (capacidades distintas → respuestas coherentes con ellas).
- **Entregable:** asistente que conoce el estado real del sistema.

### JP-03 — Interpretación de intención y de fenómeno
- **Descripción:** instrucciones del sistema para: clasificar `intent`; mapear la pregunta a fenómenos **solo** de la lista; preferir modalidad general cuando ningún fenómeno encaja de forma confiable (no forzar); distinguir variables cercanas (temperatura del aire vs superficial; focos vs área quemada; humedad superficial vs radicular); no proponer valores por defecto científicos.
- **Archivos:** `assistant-contract.json` (instrucción).
- **Criterios de aceptación:** los 10 casos de uso producen el `intent` y los ids esperados; "comparar nivel del mar con ENSO" → modalidad general, sin fenómeno; "temperatura del suelo" no se convierte en T2m.
- **Pruebas:** JP-07.
- **Entregable:** interpretación alineada con el catálogo.

### JP-04 — Flujo de aclaraciones
- **Descripción:** una pregunta por turno; opciones cuando existen (candidatos de `search_places`, variables del fenómeno, horizontes habilitados); `missing[]` de `validate_request` como fuente de las preguntas; conservación de lo ya respondido en el historial.
- **Colaboradores:** José (los mismos faltantes se marcan en el formulario).
- **Criterios de aceptación:** "San Luis" → pregunta ciudad o provincia con las opciones del buscador; sin período → propone uno y lo declara como supuesto; nunca inventa coordenadas.
- **Pruebas:** diálogos de varios turnos en JP-07.
- **Entregable:** conversación que converge a una solicitud válida.

### JP-05 — Explicación de resultados
- **Descripción:** extracto del `AnalysisResult` para el modelo (hallazgos, validaciones, procedencia resumida, pronósticos, advertencias; sin series completas); instrucciones de `11` §A7; enlaces desde la explicación a la vista y a «Cómo se calculó».
- **Colaboradores:** Ema (campos de hallazgos), Juan (anclas en las vistas).
- **Archivos:** `Assistant.svelte`, `assistant-contract.json`.
- **Criterios de aceptación:** con un hallazgo `inconclusive` la explicación dice "no hay evidencia suficiente"; con `association` menciona alternativas; con pronóstico nombra el modo y, si corresponde, que no supera a la referencia; no aparece ningún número ausente del resultado.
- **Pruebas:** con resultados sintéticos de cada tipo.
- **Entregable:** explicaciones fieles al resultado.

### JP-06 — Guardia de afirmaciones
- **Descripción:** verificación determinista posterior al modelo (ver `11` §A8): números respaldados, léxico causal, términos prohibidos por contexto, modo predictivo presente. Una regeneración; si persiste, plantilla determinista (JP-12). Listas de términos en datos, en es y en.
- **Archivos:** `PY/services/assistant_guard.py`, `PY/services/assistant_guard_rules.json`.
- **Criterios de aceptación:** un texto que diga "3 incendios" con variable de detecciones es bloqueado; "debido a" con evidencia asociativa es bloqueado; una explicación correcta no es bloqueada (tasa de falsos positivos medida sobre el conjunto de pruebas).
- **Pruebas:** conjunto de textos correctos e incorrectos por regla.
- **Entregable:** control de afirmaciones independiente del modelo.

### JP-07 — Suite de comportamiento
- **Descripción:** conjunto de consultas con resultado esperado estructural (ver `11` §A9): 10 casos, paráfrasis, ambigüedad, límites, trampas semánticas, inyección, explicación. Proveedor simulado determinista para CI; ejecución opcional contra proveedores reales con informe comparativo.
- **Archivos:** `PY/services/test_assistant_behavior.py`, `PY/services/fixtures/assistant/`.
- **Criterios de aceptación:** corre en CI sin claves ni red; el informe contra un proveedor real muestra tasa de acierto por grupo.
- **Entregable:** red de seguridad del asistente y base de comparación entre modelos.

### JP-08 — Paridad manual e IA
- **Descripción:** prueba automatizada T17: para cada caso, la solicitud armada por `requestBuilder` desde una configuración manual y la producida por el asistente (proveedor simulado) dan la misma `request_hash` y el mismo `plan_id`.
- **Colaboradores:** José, Ema.
- **Criterios de aceptación:** T17 en verde para los casos 1, 2 y 9.
- **Entregable:** evidencia de paridad.

### JP-09 — Independencia del proveedor
- **Descripción:** documentar y probar la interfaz `Provider`; verificar que no se usa ninguna función exclusiva de un proveedor; comportamiento con `configured: false` (chat deshabilitado, resto intacto).
- **Criterios de aceptación:** agregar un tercer proveedor simulado no requiere tocar `assistant.py` ni el frontend.
- **Entregable:** asistente intercambiable.

### JP-10 — Respuestas ante límites científicos
- **Descripción:** uso de `capabilities.unsupported_examples` y de los `suggestions` de los errores para responder con alternativas viables y lenguaje llano.
- **Criterios de aceptación:** Casos 7 y 8.
- **Entregable:** rechazos útiles.

### JP-11 — Proxy de Cloudflare
Actualizar `worker.mjs` al esquema v2 y revisar el límite de tokens de salida.

### JP-12 — Plantillas deterministas de hallazgos
- **Descripción:** texto base es/en por cada `statement_key`, rellenado con `values`. Sirve como explicación sin IA y como respaldo de la guardia.
- **Colaboradores:** Ema (lista de claves), José (i18n).
- **Criterios de aceptación:** todo `statement_key` emitido por el backend tiene plantilla (prueba que lo verifica); el resultado se entiende con el asistente desconectado.
- **Entregable:** explicación mínima garantizada.

---

## Orden recomendado

`JP-01 → JP-07 (esqueleto) → JP-09 → JP-02 → JP-03 → JP-04 → JP-12 → JP-05 → JP-06 → JP-10 → JP-08 → JP-11`.

## Verificación propia antes de pedir revisión

1. `pytest` y `node --test` en verde; la suite de comportamiento corre sin red.
2. Prueba manual con un proveedor real en los casos 1, 8 y 9, anotada en el PR.
3. Ninguna clave en registros ni en el contexto enviado al modelo.
4. Con el asistente desconectado, la aplicación sigue siendo usable.
