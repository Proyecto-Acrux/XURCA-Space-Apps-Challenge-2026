# 14 — Backlog de Eze · Datos e infraestructura del backend

**Rol:** conectores; disponibilidad de fuentes; selección de estaciones y entidades; normalización; compatibilidad espacial y temporal; preprocesamiento; QA de datos; caché; descargas; persistencia; trabajos asíncronos; control de fallos; pruebas de infraestructura y datos.

**Propiedad de archivos:** `PY/services/` (conectores; no `assistant*.py`), `PY/dataprep/`, `PY/handler/source_registry.py`, `jobs.py`, `cache.py`, `retry.py`, `PY/knowledge/sources.json`, flujos de CI.

Rutas: `PY/` = `aplicacion/trend-scope/src-tauri/src-python/trend_scope/`.
Principio: **los conectores existentes se envuelven; no se reescriben** salvo donde la tarea lo indica.

## Resumen

| ID | Título | Prior. | Compl. | Fase | Depende de |
|---|---|---|---|---|---|
| EZE-01 | `sources.json`: los 16 descriptores y los productos | P0 | L | F1 | EMA-01 |
| EZE-02 | `NormalizedSeries` y adaptador desde los conectores | P0 | M | F1 | EMA-01 |
| EZE-03 | Aislamiento de fallos, clasificación de errores y reintentos | P1 | M | R1 | EZE-02 |
| EZE-04 | Caché en disco | P1 | M | R1 | EZE-02 |
| EZE-05 | JobManager | P0 | L | R1 | EMA-01 |
| EZE-06 | Selección de estaciones y entidades por puntaje | P1 | L | R2 | EZE-02 |
| EZE-07 | Unidades y conversiones | P1 | M | R1 | EZE-02 |
| EZE-08 | Calendario, agregación temporal y faltantes | P1 | M | R1 | EZE-07 |
| EZE-09 | QA de datos: Q01, Q05, Q10, Q11 | P1 | M | R1 | EZE-08 |
| EZE-10 | SourceSelector | P1 | L | R1 | EZE-01 |
| EZE-11 | Troceo temporal de descargas largas | P1 | M | R2 | EZE-03 |
| EZE-12 | AppEEARS por punto → serie con QA | P0 | L | Línea AppEEARS | EZE-19 |
| EZE-13 | AppEEARS por área → estadística zonal y área geodésica | P1 | L | Línea AppEEARS | EZE-12, D-10 |
| EZE-14 | FIRMS: caché, sensores, confianza (Q07) | P1 | M | Fuego | EZE-04 |
| EZE-15 | Estado de fuentes, credenciales y datos de muestra | P1 | M | R1 | EZE-01 |
| EZE-16 | Alineación temporal y espacial (Q09, Q10) | P1 | M | R2 | EZE-08 |
| EZE-17 | Persistencia de resultados y limpieza | P2 | S | F7 | EZE-05 |
| EZE-18 | CI de pruebas | P0 | S | F1 | — |
| EZE-19 | Verificación en campo de conectores autenticados | P0 | M | F1 | Credenciales |
| EZE-20 | Empaquetado de dependencias opcionales | P1 | M | F1 | D-06 |
| EZE-21 | Variables diarias adicionales y conector de pronóstico | P2 | L | O6 | D-19 |
| EZE-22 | Procesadores para Earthdata (IMERG, SMAP) | P2 | L | O7 | EZE-13 |

---

## Tareas

### EZE-01 — `sources.json`
- **Descripción:** un `DataSourceDescriptor` por cada uno de los 16 conectores, más las tres rutas declaradas sin implementación (`not_implemented`) y los recursos de competencia que son portales o documentos (`not_automatable`). Mapeo `variable_id` canónico ↔ código nativo, unidad nativa y normalizada, conversión, semántica de agregación, resolución nativa y efectiva, período, latencia, autenticación, estado de conexión, `last_verified`, referencias X y COMP. Contenido base en `07_MATRIZ_FUENTES.md` §2–3.
- **Colaboradores:** Ema (ids de variables), José (qué muestra el configurador).
- **Archivos:** `PY/knowledge/sources.json`, `PY/handler/source_registry.py`.
- **Interfaces:** `get(source_id)`, `for_variable(variable_id) → descriptores`.
- **Criterios de aceptación:** los 16 ids de `acquisition.py` tienen descriptor; toda variable del MVP tiene al menos un descriptor o queda explícitamente sin vía; `PRECTOTCORR` declara `mm/day` y la conversión por días del mes; `PS` declara kPa y "presión de superficie"; SWOT declara su fecha de inicio; ningún portal figura como `series_ready`.
- **Pruebas:** integridad (ids, variables, conversiones existentes); T21 (Giovanni → `NOT_AUTOMATABLE`).
- **Entregable:** registro único de fuentes. Los tres registros actuales (`catalog.py`, `source-coverage.json`, `sources.js`) quedan hasta que el frontend migre a `get_capabilities`.

### EZE-02 — `NormalizedSeries`
- **Descripción:** modelo de serie normalizada (ver `07` §7) y adaptador `from_legacy(dict)` que convierte la salida actual (`month` → `time`, unidad, cadencia, entidad seleccionada, URL, fecha de obtención). Añade `observed_at` / `available_at` y `time_bounds` para valores agregados.
- **Colaboradores:** Ema (lo consume `series_to_dataset`).
- **Archivos:** `PY/dataprep/series.py`.
- **Criterios de aceptación:** la salida de los 10 conectores que dan serie se convierte sin pérdida; los valores nulos quedan `valid: false`, no desaparecen; la vía heredada (`acquire_data`) no cambia.
- **Pruebas:** un caso por conector con respuestas grabadas.
- **Entregable:** contrato de serie.

### EZE-03 — Aislamiento de fallos, clasificación y reintentos
- **Descripción:** envoltorio `fetch_node(source_id, params)` que ejecuta un conector, captura sus excepciones y las traduce a `Error` tipado (`SOURCE_UNAVAILABLE`, `CREDENTIALS_MISSING`, `TIMEOUT`, `INSUFFICIENT_DATA`…). Reintentos con espera exponencial y variación aleatoria solo para fallos recuperables; respeto de `Retry-After`; timeout por fuente; límite de tamaño de descarga. **Una fuente que falla no afecta a las demás.**
- **Archivos:** `PY/handler/retry.py`, `PY/handler/ops/fetch.py`.
- **Criterios de aceptación:** HTTP 503 → reintenta; HTTP 404 o credencial ausente → no reintenta; con dos fuentes y una caída, la otra entrega su serie.
- **Pruebas:** con servidor simulado (códigos 200, 404, 429, 500, tiempo agotado, respuesta truncada); T19.
- **Entregable:** descargas robustas.

### EZE-04 — Caché en disco
- **Descripción:** caché de series por huella de (fuente, producto, variable, geometría o entidad, período, versión del conector); vida útil según si el período está cerrado y según la latencia del producto; caché de artefactos predictivos por huella de serie; escritura atómica (el patrón ya existe en `configuration.py`); tamaño máximo con expulsión por antigüedad.
- **Colaboradores:** Ema (claves de nodo).
- **Archivos:** `PY/handler/cache.py`.
- **Criterios de aceptación:** una segunda ejecución idéntica no hace llamadas de red; el resultado registra `cache_status` y la fecha original de obtención; un archivo corrupto se descarta y se vuelve a bajar.
- **Pruebas:** acierto, fallo, vencimiento, corrupción, concurrencia de dos jobs sobre la misma clave.
- **Entregable:** reutilización de datos.

### EZE-05 — JobManager
- **Descripción:** registro de jobs en memoria con `Lock`; estados `queued → running → waiting_external → completed | partial | failed | cancelled`; hilo por job (`anyio.to_thread`); máximo de jobs simultáneos; progreso por nodo; cancelación cooperativa mediante el `ExecutionContext` del motor; tiempo máximo por job; `submit(plan, wait_ms)`.
- **Colaboradores:** Ema (el ejecutor corre dentro del job), Juan (sondeo).
- **Archivos:** `PY/handler/jobs.py`.
- **Interfaces:** `submit`, `status`, `result`, `cancel`.
- **Criterios de aceptación:** la interfaz no se bloquea durante un job largo; cancelar un job en descarga lo detiene en el siguiente punto de control; `job_result` de un job en curso devuelve lo parcial; cerrar la aplicación no deja archivos a medio escribir.
- **Pruebas:** con ejecutor simulado (lento, que falla, que se cancela); límite de simultaneidad.
- **Entregable:** ejecución asíncrona.

### EZE-06 — Selección de estaciones y entidades por puntaje
- **Descripción:** rediseño descrito en `07` §6. Puntaje por distancia, fracción de cobertura del período pedido y completitud; uso de `ghcnd-inventory.txt` para filtrar NOAA por período **antes** de descargar; `try` por candidato; ampliación progresiva del radio; centroide real del polígono; salida `{selected, candidates, rejected, representativeness_note}`; respeto de `location.entity_id`. Corrección del defecto de `geometryId` nulo en rutas de entidad.
- **Archivos:** `PY/dataprep/stations.py` (lógica nueva), `PY/services/station_catalogs.py` (mínimos cambios para delegar).
- **Criterios de aceptación:** con una estación cercana de un solo dato y otra algo más lejana con serie completa, se elige la segunda; un error HTTP en el primer candidato no impide probar el resto; si ningún candidato alcanza la cobertura mínima → `INSUFFICIENT_DATA` con la lista; el caso documentado de San Luis mensual se reproduce y queda como prueba de regresión.
- **Pruebas:** con catálogos y respuestas simulados; prueba del caso reportado.
- **Entregable:** selección representativa y explicable.

### EZE-07 — Unidades y conversiones
- **Descripción:** tabla de conversiones registradas por id (`rate_per_day_times_days_in_month`, `mm_per_hour_to_interval`, `kelvin_to_celsius`, `kpa_to_hpa`, `fraction_to_percent`, `identity`); aplicación en el nodo `normalize`; registro en `transformations`. Combinación sin conversión registrada → `UNIT_INCOMPATIBLE`.
- **Archivos:** `PY/dataprep/units.py`.
- **Criterios de aceptación:** `PRECTOTCORR` de un mes de 30 días a 2 mm/día → 60 mm; febrero bisiesto correcto; T14 (tasas de media hora → suma mensual conservadora).
- **Pruebas:** unitarias por conversión; T14.
- **Entregable:** unidades trazables.

### EZE-08 — Calendario, agregación temporal y faltantes
- **Descripción:** todo a UTC; agregación de fina a gruesa según `aggregation_semantics` (suma para acumulados, media para estados, integración para tasas); `n_valid / n_expected` por período agregado; período bajo el umbral → inválido; **sin interpolación**.
- **Archivos:** `PY/dataprep/calendar.py`, `aggregate.py`.
- **Criterios de aceptación:** un mes con el 70% de días nublados queda inválido con umbral 0.8 (T06); la suma mensual de precipitación diaria coincide con el total esperado; no se puede agregar de mensual a diario.
- **Pruebas:** sintéticas con huecos; meses de distinta longitud; T06.
- **Entregable:** series comparables.

### EZE-09 — QA de datos: Q01, Q05, Q10, Q11
- **Descripción:** nodo `qa` que emite `ValidationStatus` para cobertura y faltantes (Q01), precipitación (Q05: tasa vs acumulado, ventana, base de SPI), compatibilidad temporal (Q10) y unidades y datum (Q11). Umbrales desde `qa_rules.json`.
- **Colaboradores:** Ema (formato de `ValidationStatus`, `qa_rules.json`).
- **Archivos:** `PY/dataprep/qa.py`.
- **Criterios de aceptación:** cobertura < 0.8 → `block` para tendencia; dos series de nivel con datum distinto → `block` (T15).
- **Pruebas:** T06, T15.
- **Entregable:** controles de datos.

### EZE-10 — SourceSelector
- **Descripción:** filtros excluyentes y ordenamiento de `07` §5; salida con elegido, alternativas y descartados con motivo; `source_substitution`; respeto de la preferencia del usuario. Absorbe la lógica de `coverage.evaluate_coverage`.
- **Colaboradores:** Ema (lo llama el planificador).
- **Archivos:** `PY/handler/source_registry.py`.
- **Criterios de aceptación:** 20 años de SWOT → `TEMPORAL_INCOMPATIBLE` con INA como alternativa, **sin tocar la red** (T12); T2m nunca se ofrece como sustituto de LST; una fuente sin credencial se descarta con `CREDENTIALS_MISSING`.
- **Pruebas:** tabla de decisiones; T12, T19, T21.
- **Entregable:** selección de fuentes explicable.

### EZE-11 — Troceo temporal de descargas largas
- **Descripción:** división de pedidos largos en ventanas (Open-Meteo, CDS), ensamblado, verificación de continuidad y de solapamientos; progreso por ventana; cancelación entre ventanas.
- **Criterios de aceptación:** el pedido histórico largo que falló según el inventario se completa por ventanas; una ventana fallida se reintenta sin repetir las demás.
- **Pruebas:** con servidor simulado; prueba real marcada como de red (no corre en CI).
- **Entregable:** series largas de reanálisis.

### EZE-12 — AppEEARS por punto → serie con QA
- **Descripción:** envío de tarea de punto, espera como nodo `waiting_external` con sondeo de espera creciente, descarga, lectura del CSV de resultados, aplicación de las capas de calidad del producto (MOD13Q1, MOD11A2, MOD16A2GF), conversión de factores de escala y salida como `NormalizedSeries` con `quality_flag` y fracción de cobertura. LST día y noche como variables separadas.
- **Colaboradores:** Ema (variables canónicas), José (estado en la interfaz).
- **Archivos:** `PY/services/appeears.py` (ampliar), `PY/dataprep/satellite_qa.py`.
- **Criterios de aceptación:** una serie de NDVI de un punto llega con máscara aplicada; los valores marcados por nubes quedan inválidos, no interpolados (Q06); una tarea ya enviada se reutiliza.
- **Pruebas:** con archivos de respuesta grabados; T06; prueba real marcada como de red.
- **Entregable:** NDVI, EVI, LST y ET real como series. **Camino crítico del MVP.**

### EZE-13 — AppEEARS por área → estadística zonal y área geodésica
- **Descripción:** lectura del archivo de área (formato y biblioteca según D-10), máscara QA, promedio ponderado por área sobre el polígono con `valid_area_fraction` (Q18), salida por celda para análisis en rejilla con tope de celdas, y área geodésica por píxel para MCD64A1 (Q08) y MCD12Q1.
- **Criterios de aceptación:** el área total de un polígono de referencia se conserva dentro de la tolerancia; el área quemada sale en hectáreas a partir de píxeles, nunca de focos; la resolución efectiva queda registrada.
- **Pruebas:** con ráster sintético de área conocida; T04, T13, T20.
- **Entregable:** LST por celda, área quemada, cobertura.

### EZE-14 — FIRMS: caché, sensores y confianza
- **Descripción:** dejar de re-descargar; separar VIIRS y MODIS en la salida; filtro de confianza; eliminación de duplicados; unidad "detecciones"; control Q07.
- **Criterios de aceptación:** tres detecciones del mismo fuego se cuentan como tres **detecciones** (T03); los sensores nunca se suman sin declararlo.
- **Entregable:** N1.4.0.

### EZE-15 — Estado de fuentes, credenciales y datos de muestra
- **Descripción:** `source_status()` por fuente: credencial presente (sin exponerla), última verificación, estado de conexión. Conjunto pequeño de datos de muestra rotulados `demo: true`, usados solo si `constraints.allow_sample_data` es verdadero.
- **Criterios de aceptación:** T19: conector sin credencial → error explícito y oferta de datos de muestra etiquetados; las claves no aparecen en ningún resultado, plan ni registro.
- **Entregable:** transparencia de disponibilidad.

### EZE-16 — Alineación temporal y espacial
- **Descripción:** nodo `align`: intersección de períodos válidos, misma frecuencia, resolución efectiva = la más gruesa; informe de pasos perdidos; controles Q09 y Q10.
- **Criterios de aceptación:** T13 (una fuente gruesa y otra fina → se agrega a la gruesa y se rotula); solapamiento insuficiente → `INSUFFICIENT_DATA`.
- **Entregable:** series listas para el análisis multivariable.

### EZE-17 — Persistencia de resultados y limpieza
Guardado de los últimos N `AnalysisResult`; `list_results`; limpieza de descargas y caché antiguas.

### EZE-18 — CI de pruebas
- **Descripción:** flujo de GitHub Actions **en la raíz del repositorio** que ejecute `pytest` (sin pruebas de red), `pnpm check`, las pruebas `node:test` y la validación de ejemplos contra esquemas. Mover o duplicar el flujo de publicación existente, que hoy está en una subcarpeta donde GitHub no lo detecta.
- **Criterios de aceptación:** un PR con un test roto no puede integrarse.
- **Entregable:** puerta de calidad.

### EZE-19 — Verificación en campo de conectores autenticados
- **Descripción:** con credenciales reales, verificar FIRMS, AppEEARS, Earthdata, CDS y Copernicus Data Space; registrar fecha y alcance en `last_verified`; documentar cuotas y tiempos observados.
- **Criterios de aceptación:** cada conector autenticado tiene `last_verified` con fecha, o un motivo documentado de por qué no se pudo verificar.
- **Entregable:** estado real de los conectores. **Hacer primero:** condiciona la línea AppEEARS.

### EZE-20 — Empaquetado de dependencias opcionales
Según D-06: incorporar `statsmodels`, `pymannkendall` y `ruptures` al paquete, verificar la compilación en las plataformas objetivo y el tamaño resultante.

### EZE-21 — Variables diarias adicionales y conector de pronóstico
Ampliar las variables diarias (humedad relativa, viento) necesarias para FWI; evaluar e integrar un conector de pronóstico meteorológico con sus fechas de emisión (D-19).

### EZE-22 — Procesadores para Earthdata
IMERG y SMAP como series, para dejar de depender de las sustituciones por reanálisis.

---

## Orden recomendado

`EZE-18 → EZE-19 → EZE-02 → EZE-01 → EZE-05 → EZE-03 → EZE-07 → EZE-08 → EZE-09 → EZE-10 → EZE-04 → EZE-15` (cierra R1), con **EZE-12 en paralelo desde que EZE-19 lo permita** → `EZE-06 → EZE-11 → EZE-16` (R2) → `EZE-13 → EZE-14` (fuego) → resto.

## Verificación propia antes de pedir revisión

1. `pytest` en verde sin acceso a red.
2. Prueba manual con datos reales del conector tocado, anotada en el PR con fecha.
3. Ninguna credencial en registros, resultados ni capturas.
4. `acquire_data` (vía heredada) sigue funcionando.
