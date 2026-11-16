# 16 — Backlog de Juan · Visualización y frontend científico

**Rol:** interfaz geográfica; mapas y capas; series temporales; gráficos; visualización multivariable; predicciones e incertidumbre; resultados científicos; estados de ejecución; integración del frontend con la API.

**Propiedad de archivos:** `TS/src/lib/services/analysisApi.js`, `TS/src/lib/stores/analysis.js`, `TS/src/lib/components/results/` (nuevo), `ChartView.svelte`, `Results.svelte`, `WorldMap.svelte`, `Globe.svelte`, `TS/src/lib/services/charts.js`, `chartExport.js`, `geography.js`.

**Límite:** Juan no implementa cálculos científicos en el navegador. Toda cifra mostrada viene del `AnalysisResult`; el frontend solo decima para dibujar.

Rutas: `TS/` = `aplicacion/trend-scope/`.

## Resumen

| ID | Título | Prior. | Compl. | Fase | Depende de |
|---|---|---|---|---|---|
| JUAN-01 | Cliente de API, modo simulado y tipos | P0 | M | F1 | EMA-01 |
| JUAN-02 | Store de jobs y resultados | P0 | M | R1 | JUAN-01 |
| JUAN-03 | Despachador de vistas por `VizHint` | P1 | M | R1 | JUAN-02 |
| JUAN-04 | Serie temporal con tendencia e intervalo | P1 | M | R1 | JUAN-03 |
| JUAN-05 | Vistas multivariables | P1 | L | R2 | JUAN-03 |
| JUAN-06 | Gráfico de abanico para pronósticos y escenarios | P1 | M | R3 | JUAN-03 |
| JUAN-07 | Mapas: capas de resultado | P1 | L | Fuego | JUAN-03 |
| JUAN-08 | Panel de estado de ejecución | P1 | M | R1 | JUAN-02 |
| JUAN-09 | Panel «Cómo se calculó» | P1 | M | R1 | JUAN-03 |
| JUAN-10 | Insignias, advertencias y controles | P1 | M | R2 | JUAN-03 |
| JUAN-11 | Exportación de resultados | P2 | S | F7 | JUAN-03 |
| JUAN-12 | Pruebas del frontend de resultados | P1 | M | Continuo | D-18 |
| JUAN-13 | Vistas de anomalías, estados de SPI y tablas | P1 | M | R2 | JUAN-03 |
| JUAN-14 | Grafo del plan | P2 | M | R2 | JOSE-06 |

---

## Tareas

### JUAN-01 — Cliente de API, modo simulado y tipos
- **Descripción:** `analysisApi.js` con `getCapabilities`, `validateRequest`, `planAnalysis`, `submitAnalysis`, `jobStatus`, `jobResult`, `cancelJob`, `listResults`. Dos implementaciones con la misma interfaz: `pytauri` y `mock` (lee los ejemplos fijos y simula el avance de un job), elegidas por variable de entorno de Vite. Normaliza `{error}` a un objeto de error único. Script que genera `@typedef` de JSDoc desde los JSON Schema.
- **Colaboradores:** Ema (esquemas y ejemplos), José y JP (lo consumen).
- **Archivos:** `TS/src/lib/services/analysisApi.js`, `analysisApi.mock.js`, `TS/src/lib/types/` (generado), `TS/scripts/gen-types.mjs`.
- **Interfaces:** comandos de `09_CONTRATOS_JSON_API.md` §10.
- **Criterios de aceptación:** la interfaz corre completa en el navegador sin backend; `pnpm check` valida los tipos generados; cambiar a `pytauri` no exige tocar ningún componente.
- **Pruebas:** `node:test` del cliente simulado y de la normalización de errores.
- **Entregable:** capa de acceso que desbloquea al equipo de frontend.

### JUAN-02 — Store de jobs y resultados
- **Descripción:** `stores/analysis.js`: envío, sondeo con intervalo creciente, resultados parciales, cancelación, historial de la sesión; marca de resultado obsoleto cuando cambia la configuración (el comportamiento que ya existe para `result.key`), usando `request_hash`.
- **Colaboradores:** Eze (semántica de estados).
- **Archivos:** `TS/src/lib/stores/analysis.js`.
- **Criterios de aceptación:** un job largo no bloquea la interfaz; cancelar detiene el sondeo; al cambiar un parámetro científico el resultado se marca obsoleto, y al cambiar solo el nombre visible no.
- **Pruebas:** `node:test` con cliente simulado (éxito, parcial, fallo, cancelación).
- **Entregable:** ciclo de vida de un análisis en la interfaz.

### JUAN-03 — Despachador de vistas por `VizHint`
- **Descripción:** componente que recibe `AnalysisResult` y, por cada `visualization[]`, instancia la vista correspondiente a `kind`; un `kind` desconocido cae a tabla. Reemplaza el flujo `Results.svelte → ChartView` para resultados del Handler, conservando el actual para la vía heredada.
- **Archivos:** `TS/src/lib/components/results/ResultView.svelte`, `results/index.js`.
- **Criterios de aceptación:** los 10 ejemplos fijos se dibujan sin errores; agregar una vista nueva es registrar una entrada, sin tocar el despachador.
- **Pruebas:** recorrido de todos los ejemplos (humo).
- **Entregable:** base de las vistas.

### JUAN-04 — Serie temporal con tendencia e intervalo
- **Descripción:** `timeseries_trend`: serie, línea de tendencia, banda del intervalo de confianza rotulada con su nivel; huecos visibles (sin unir puntos a través de datos inválidos); pendiente con unidad; estado visual distinto para hallazgo inconcluso.
- **Archivos:** `results/TrendChart.svelte`, `charts.js` (ampliar).
- **Criterios de aceptación:** con hallazgo `inconclusive` el gráfico muestra «No hay evidencia suficiente de tendencia» y no resalta la pendiente (T01); la decimación existente no altera la banda.
- **Pruebas:** ejemplos del Caso 1 en sus dos variantes (concluyente e inconcluso).
- **Entregable:** vista del recorrido 1.

### JUAN-05 — Vistas multivariables
- **Descripción:** `multi_panel_aligned` (eje temporal común, un eje Y por unidad), `lag_correlogram` (marca los desfases que superan el control de pruebas múltiples; rotula si la selección fue predefinida o exploratoria), `scatter` (con etiqueta fija «asociación, no causa»).
- **Archivos:** `results/AlignedPanels.svelte`, `LagCorrelogram.svelte`, `ScatterView.svelte`.
- **Criterios de aceptación:** dos variables con unidades distintas nunca comparten eje; un hallazgo `exploratory` lleva insignia visible (T09); la lista de explicaciones alternativas aparece junto al gráfico.
- **Entregable:** vistas del recorrido 2.

### JUAN-06 — Gráfico de abanico
- **Descripción:** `forecast_fan`: observado, estimación central, banda de cuantiles, línea de referencia (baseline); etiqueta de modo siempre visible; tramo `exploratory_extrapolation` punteado y **sin banda**; `scenario_lines` con los supuestos en la leyenda; `probability_bars` con la definición del evento.
- **Archivos:** `results/ForecastFan.svelte`, `ScenarioLines.svelte`, `ProbabilityBars.svelte`.
- **Criterios de aceptación:** `not_superior_to_baseline` muestra el aviso y destaca la referencia (T11); el color y la leyenda del intervalo predictivo difieren de los del intervalo de confianza; nunca aparece un "% de confianza".
- **Entregable:** vistas del recorrido 3.

### JUAN-07 — Mapas: capas de resultado
- **Descripción:** en `WorldMap.svelte`: punto de análisis, estación o entidad elegida con sus candidatas, detecciones (puntos) y ráster de área o anomalía como **capas independientes** con leyenda y unidad propias; resolución efectiva en la leyenda; respaldo en `Globe.svelte` para lo esencial.
- **Colaboradores:** Eze (formato de capas ráster).
- **Criterios de aceptación:** detecciones y área quemada nunca comparten leyenda ni se suman (T04, T20); una capa a 10 km no se dibuja con apariencia de mayor detalle (T13).
- **Entregable:** mapas de la ola de fuego y de rejilla.

### JUAN-08 — Panel de estado de ejecución
- **Descripción:** avance por nodos, paso actual con etiqueta legible, estado por fuente (en caché, descargando, esperando al proveedor, fallida), botón cancelar, aparición progresiva de resultados parciales.
- **Criterios de aceptación:** una tarea externa en espera se distingue de una descarga activa; una fuente fallida se muestra con su motivo sin ocultar el resto.
- **Entregable:** ejecución visible.

### JUAN-09 — Panel «Cómo se calculó»
- **Descripción:** panel generado solo desde `AnalysisResult` con las secciones de `11` §B4; botón "copiar solicitud".
- **Colaboradores:** JP (enlaces desde la explicación).
- **Criterios de aceptación:** funciona con el asistente desconectado; muestra sustituciones de producto, estación elegida y candidatas, base climatológica, versiones de métodos y origen de cada umbral.
- **Entregable:** transparencia científica.

### JUAN-10 — Insignias, advertencias y controles
- **Descripción:** componentes de insignia (reanálisis, modelo, observación, punto único, exploratorio, datos de muestra, sustitución); advertencias de `ValidationStatus` junto al gráfico al que aplican; aviso fijo de no operatividad en fuego e hidrología.
- **Colaboradores:** José (textos y errores).
- **Criterios de aceptación:** datos de muestra siempre rotulados (T19); un control en `block` muestra la "salida ante falla" de la planilla en lugar del hallazgo.
- **Entregable:** honestidad visual.

### JUAN-11 — Exportación de resultados
PNG (existente, ampliado a las vistas nuevas) y JSON del `AnalysisResult`.

### JUAN-12 — Pruebas del frontend de resultados
Pruebas de servicios y stores con `node:test`; recorrido de humo de todos los ejemplos; marco para pruebas de componentes según D-18.

### JUAN-13 — Vistas de anomalías, estados de SPI y tablas
- **Descripción:** `anomaly_bars` (base climatológica en el título), `spi_states` (una fila por escala, sin sumar escalas), `table` (eventos, transiciones, métricas).
- **Criterios de aceptación:** T02 (déficit y exceso con unidades correctas); T07 (un evento actual se muestra aunque la tendencia sea inconclusa).
- **Entregable:** vistas de O2.

### JUAN-14 — Grafo del plan
Dibujo del `AnalysisPlan` (nodos, dependencias, bloqueos) dentro de la vista de plan de José.

---

## Orden recomendado

`JUAN-01 → 02 → 03 → 04 → 08 → 09` (R1) → `13 → 05 → 10` (R2) → `07` (fuego) → `06` (R3) → `11, 14`; `JUAN-12` continuo.

## Verificación propia antes de pedir revisión

1. `pnpm check` y `node --test` en verde.
2. Los 10 ejemplos fijos se dibujan en modo simulado.
3. Captura de la vista con tema claro y oscuro en el PR.
4. Ningún cálculo estadístico agregado en el navegador.
