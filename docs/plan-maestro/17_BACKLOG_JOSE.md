# 17 — Backlog de José · Configuración avanzada y experiencia de usuario

**Rol:** configurador manual; selección de variables y fenómenos; formularios avanzados; parámetros científicos; navegación; validaciones de interfaz; experiencia de usuario; presentación de errores y advertencias; integración del flujo de configuración con la IA y el frontend; pruebas funcionales de interfaz.

**Propiedad de archivos:** `TS/src/lib/components/Settings.svelte`, `PlaceSearch.svelte`, `TS/src/lib/components/config/` (nuevo), `TS/src/lib/services/requestBuilder.js`, `configuration.js`, `sources.js`, `i18n.js`, `TS/src/lib/stores/workspace.js`, `TS/config/cfg_data.json`, `TS/src/routes/+page.svelte` (estructura y navegación).

**Límite:** el formulario no aplica valores por defecto científicos ni decide viabilidad: muestra lo que devuelve el backend.

Rutas: `TS/` = `aplicacion/trend-scope/`.

## Resumen

| ID | Título | Prior. | Compl. | Fase | Depende de |
|---|---|---|---|---|---|
| JOSE-01 | `requestBuilder`: del espacio de trabajo a `AnalysisRequest` | P0 | M | F1 | EMA-01 |
| JOSE-02 | Selector de fenómenos | P1 | L | R1 | JUAN-01 |
| JOSE-03 | Selección de variables y fuentes | P1 | L | R1 | JOSE-02 |
| JOSE-04 | Opciones científicas | P1 | M | R2 | JOSE-03 |
| JOSE-05 | Predicción: horizonte, modo y supuestos | P1 | M | R3 | JOSE-03 |
| JOSE-06 | Validación en vivo y vista de plan | P1 | L | R1 | JOSE-01 |
| JOSE-07 | Presentación de errores y advertencias | P1 | M | R1 | JUAN-01 |
| JOSE-08 | Migración de `cfg_data` a la versión 2 | P0 | M | F1 | EMA-01 |
| JOSE-09 | Propuesta del asistente en el formulario | P1 | M | R4 | JP-01 |
| JOSE-10 | Internacionalización de textos nuevos | P1 | M | Continuo | — |
| JOSE-11 | Pruebas funcionales de interfaz | P1 | M | Continuo | — |
| JOSE-12 | Modos básico y avanzado; navegación | P1 | M | R2 | JOSE-02 |
| JOSE-13 | Estado de fuentes y credenciales | P2 | S | R2 | EZE-15 |

---

## Tareas

### JOSE-01 — `requestBuilder`
- **Descripción:** función pura `buildRequest(cfgData) → AnalysisRequest` (parcial: sin valores por defecto científicos). Convierte la selección geográfica del espacio de trabajo en `location.geometry`, el período, los fenómenos, las variables con rol y preferencia de fuente, las opciones científicas que el usuario cambió explícitamente y la sección de predicción. Marca `input_mode`.
- **Colaboradores:** Ema (forma canónica), JP (misma función para la propuesta del asistente).
- **Archivos:** `TS/src/lib/services/requestBuilder.js`, `requestBuilder.test.js`.
- **Interfaces:** entrada `cfg_data` v2; salida validable con el JSON Schema de `AnalysisRequest`.
- **Criterios de aceptación:** para cada caso de uso, la configuración manual equivalente produce una solicitud que valida contra el esquema; los campos no tocados por el usuario **no** se envían (para que el backend aplique su valor por defecto); la función no accede a red ni a stores.
- **Pruebas:** `node:test` con una configuración por caso; validación contra esquema.
- **Entregable:** única vía de armado de solicitudes (base de T17).

### JOSE-02 — Selector de fenómenos
- **Descripción:** sección «Análisis»: tipo de análisis y lista de los 73 fenómenos desde `get_capabilities`, con búsqueda y filtros por nivel, familia, prioridad y disponibilidad. Ficha del fenómeno: objetivo, variables, qué puede afirmarse y qué no, disponibilidad por rama con su motivo. Opción explícita «Análisis general (sin fenómeno)».
- **Colaboradores:** Ema (contenido de capacidades), Juan (cliente).
- **Archivos:** `TS/src/lib/components/config/PhenomenonPicker.svelte`, `PhenomenonCard.svelte`.
- **Criterios de aceptación:** los 73 aparecen; los no disponibles se muestran deshabilitados **con motivo**, no ocultos; no hay ninguna lista de fenómenos escrita en el frontend.
- **Pruebas:** con capacidades simuladas (disponible, parcial, bloqueado, no soportado).
- **Entregable:** entrada al catálogo científico.

### JOSE-03 — Selección de variables y fuentes
- **Descripción:** sección «Variables»: variables del fenómeno con su rol; agregar variables en modalidad general; atributos (profundidad, pasada día o noche, sensor). Sección «Fuentes» ampliada: preferencia por variable entre las fuentes compatibles, estado de conexión, fijar estación o entidad a partir de `candidates[]`. Sustituye progresivamente el catálogo fijo de `sources.js`.
- **Colaboradores:** Eze (descriptores y candidatos).
- **Archivos:** `config/VariablePicker.svelte`, `config/SourcePreference.svelte`, `Settings.svelte`.
- **Criterios de aceptación:** al elegir LST no se ofrece una fuente de T2m; la interfaz impide combinar en una misma comparación dos variables marcadas como no intercambiables y explica por qué; la estación elegida por el sistema puede reemplazarse por otra candidata.
- **Pruebas:** con capacidades y plan simulados.
- **Entregable:** configuración de variables y fuentes.

### JOSE-04 — Opciones científicas
- **Descripción:** sección plegada con base climatológica, cobertura mínima, nivel de significación, niveles de intervalo, desfases y escalas de SPI; cada control con rango tomado de `params_schema` de la receta y con el valor sugerido por el backend rotulado como tal. Aviso cuando un cambio vuelve exploratorio el análisis (p. ej. editar los desfases).
- **Criterios de aceptación:** no se puede ingresar un valor fuera del rango de la receta; al modificar los desfases se muestra que el resultado podrá quedar como exploratorio.
- **Entregable:** control fino para usuarios técnicos.

### JOSE-05 — Predicción: horizonte, modo y supuestos
- **Descripción:** sección «Predicción»: horizonte (limitado a lo que `get_capabilities.models` habilita, con el resto visible y explicado), modo pedido, editor de supuestos de escenario.
- **Colaboradores:** Ema (elegibilidad), Juan (vista).
- **Criterios de aceptación:** un fenómeno `historical_only` no muestra controles de predicción sino la explicación; pedir un horizonte mayor al validado muestra de antemano que el tramo extra será exploratorio.
- **Entregable:** configuración predictiva honesta.

### JOSE-06 — Validación en vivo y vista de plan
- **Descripción:** llamada a `validate_request` con espera tras la última edición; campos faltantes marcados; valores por defecto aplicados visibles; botón «Ver plan» que muestra `AnalysisPlan`: fuentes elegidas y alternativas, pasos, controles, lo bloqueado y por qué. «Procesar» habilitado solo con solicitud válida.
- **Colaboradores:** Juan (grafo, JUAN-14).
- **Archivos:** `config/PlanPreview.svelte`, `+page.svelte` (`run()`).
- **Criterios de aceptación:** el usuario ve qué fuente se usará **antes** de ejecutar; un fenómeno parcial indica qué rama se ejecuta y cuál no; el defecto de `geometryId` nulo deja de ser alcanzable porque la geometría se resuelve en `requestBuilder`.
- **Pruebas:** con respuestas simuladas (válida, con faltantes, con bloqueos).
- **Entregable:** el usuario entiende qué va a pasar.

### JOSE-07 — Presentación de errores y advertencias
- **Descripción:** catálogo código de error → texto es/en, gravedad y acciones (`suggestions` como botones: usar otra fuente, acortar el período, usar otro fenómeno, configurar credencial). Distinción visual entre error definitivo, error recuperable y advertencia.
- **Colaboradores:** Juan (advertencias junto a gráficos), JP (mismo vocabulario en el chat).
- **Archivos:** `TS/src/lib/services/errors.js`, `config/ErrorPanel.svelte`.
- **Criterios de aceptación:** los 15 códigos de `09` §9 tienen texto y acción; Caso 7 muestra los dos botones de alternativa; no se muestra nunca un texto técnico crudo de excepción.
- **Pruebas:** `node:test` de cobertura del catálogo (falla si aparece un código sin texto).
- **Entregable:** errores accionables.

### JOSE-08 — Migración de `cfg_data` a la versión 2
- **Descripción:** nueva sección `analysis` en `cfg_data` (fenómenos, variables canónicas con rol, opciones científicas, predicción); migración v1 → v2 en `configuration.js: loadWorkspace`, donde ya viven las migraciones; `sources[]` actual se conserva como preferencia de fuente.
- **Colaboradores:** Ema o Eze (el guardado en `configuration.py` exige hoy `schemaVersion 1`: cambio de servidor a coordinar).
- **Archivos:** `TS/src/lib/services/configuration.js`, `TS/config/cfg_data.json`, `stores/workspace.js`.
- **Criterios de aceptación:** un espacio de trabajo v1 guardado se abre sin pérdida; la vía heredada sigue funcionando con un archivo v2.
- **Pruebas:** `node:test` de migración con archivos v1 reales.
- **Entregable:** estado del espacio de trabajo listo para el nuevo flujo.

### JOSE-09 — Propuesta del asistente en el formulario
- **Descripción:** `request_patch` del asistente se aplica al store mediante las mismas funciones que usa el formulario; los campos cambiados se resaltan; el usuario confirma o corrige antes de procesar.
- **Colaboradores:** JP.
- **Archivos:** `assistantConfiguration.js` (con JP), `Settings.svelte`.
- **Criterios de aceptación:** tras aplicar una propuesta, el formulario muestra exactamente lo que el usuario habría completado a mano; T17 pasa.
- **Entregable:** convergencia de los dos modos.

### JOSE-10 — Internacionalización
Claves es/en para todos los textos nuevos; eliminación de textos fijos en español en componentes tocados; decisión D-26 sobre traducción de afirmaciones normativas.

### JOSE-11 — Pruebas funcionales de interfaz
- **Descripción:** guiones de prueba manual por caso de uso (pasos, resultado esperado, captura), ejecutables en modo simulado y en la aplicación de escritorio; pruebas automáticas de `requestBuilder`, migración y catálogo de errores.
- **Criterios de aceptación:** los 10 guiones se ejecutan antes de cada integración a `main` de la Fase 7 en adelante.
- **Entregable:** verificación funcional repetible.

### JOSE-12 — Modos básico y avanzado; navegación
- **Descripción:** modo básico (ubicación, período, fenómeno) y avanzado (todo); reorganización de `+page.svelte` para alojar las secciones nuevas sin romper menús, herramientas de mapa ni paneles.
- **Criterios de aceptación:** un usuario sin formación técnica completa el Caso 1 en modo básico sin abrir opciones científicas.
- **Entregable:** experiencia graduada.

### JOSE-13 — Estado de fuentes y credenciales
Vista de qué fuentes están listas, cuáles requieren credencial y cómo configurarla (sin mostrar las claves).

---

## Orden recomendado

`JOSE-08 → JOSE-01 → JOSE-07 → JOSE-02 → JOSE-03 → JOSE-06` (R1) → `JOSE-12 → JOSE-04 → JOSE-13` (R2) → `JOSE-05` (R3) → `JOSE-09` (R4); `JOSE-10` y `JOSE-11` continuos.

## Verificación propia antes de pedir revisión

1. `pnpm check` y `node --test` en verde.
2. Guion funcional del caso afectado ejecutado en modo simulado.
3. Un espacio de trabajo guardado antes del cambio se abre correctamente.
4. Ningún valor por defecto científico escrito en el frontend.
