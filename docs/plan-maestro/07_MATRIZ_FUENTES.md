# 07 — Matriz de fuentes, conectores y preparación de datos

Rutas: `PY/` = `aplicacion/trend-scope/src-tauri/src-python/trend_scope/`.

## 1. Distinciones obligatorias

El plan separa siete conceptos que la documentación a veces mezcla:

| Concepto | Ejemplo | Cómo lo representa el sistema |
|---|---|---|
| **Portal de consulta** | Giovanni, KNMI Climate Explorer, Hydrology Time Series | `access_method: "portal"`, `connection_state: "not_automatable"`. Nunca es fuente de un plan (T21) |
| **Catálogo de productos** | Earthdata CMR, STAC de Planetary Computer, catálogo de AppEEARS | `role: "catalog"` |
| **Servicio de descarga** | AppEEARS, CDS, Copernicus Data Space | `role: "download"`: entrega archivos que requieren decodificación |
| **Producto científico** | MOD13Q1 v061, MCD64A1, IMERG Final V07, ERA5-Land | `product` + `version` dentro del descriptor; es lo que se cita en la procedencia |
| **Modelo de pronóstico** | Pronóstico numérico, reforecast estacional | `kind: "forecast"`. **Hoy no hay ningún conector de pronóstico** |
| **Conector funcional** | NASA POWER mensual | `connection_state: "series_ready"` |
| **Conector parcial** | AppEEARS (descarga sin parseo) | `connection_state: "raw_only"` o `"unverified_auth"` |

---

## 2. Matriz de los 16 conectores

Estados: **SR** = serie lista; **SR\*** = serie lista con selección de entidad frágil; **RAW** = solo archivo crudo; **AUTH?** = acceso autenticado no verificado en campo.

| ID | Conector | Código | Rol real | Variables (unidad nativa) | Cobertura / resolución | Credencial | Estado | Limitaciones comprobadas |
|---|---|---|---|---|---|---|---|---|
| 01 | `nasa.power.monthly` | `services/power.py` | Serie mensual por punto | T2M (°C), PRECTOTCORR (**mm/día, media mensual**), RH2M (%), WS2M (m/s), GWETROOT (fracción 0–1), ALLSKY_SFC_SW_DWN, PS (**kPa**, presión de superficie); acepta cualquier código POWER | Global; ~0.5°×0.625°; 1981 → último año cerrado | Ninguna | **SR** | No convierte unidades; solo mensual; derivado de reanálisis, no observación |
| 02 | `noaa.ncei.station` | `services/public_sources.py` | Serie mensual de estación (GSOM) | PRCP (mm), TAVG/TMAX/TMIN (°C), SNOW/SNWD (mm) | Estaciones GHCN; cobertura desigual en Argentina | Ninguna | **SR\*** | Catálogo sin períodos; códigos fuera de tabla quedan "unidad sin verificar" |
| 03 | `nasa.swot.hydrocron` | `services/public_sources.py` | Serie por pasada de tramo o lago | wse (m), area_total (km²), width (m), slope (m/m), dschg_c | **Desde 2022**; tramos SWORD / lagos PLD | Ninguna | **SR\*** | `dschg_c` sin valores válidos en prueba; áreas grandes exceden el límite espacial; serie irregular |
| 04 | `openmeteo.archive.daily` | `services/reanalysis.py` | Serie diaria por punto | Humedad de suelo 0–7, 7–28, 28–100, 100–255 cm (m³/m³), Tmax/Tmin (°C) [ERA5-Land]; precipitation_sum (mm), ET₀ FAO (mm) [ERA5] | ERA5-Land 1950→, ERA5 1940→; ~9 km / ~25 km | Ninguna (condiciones de uso) | **SR** | 8 variables fijas; **el pedido histórico largo falló**; sin troceo temporal |
| 05 | `noaa.ncei.daily` | `services/public_sources.py` | Serie diaria de estación (GHCN-Daily) | PRCP, TMAX, TMIN (+TAVG, SNOW, SNWD) | Estaciones | Ninguna | **SR\*** | Igual que 02 |
| 06 | `noaa.oisst.daily` | `services/environmental_series.py` | Serie diaria de una celda oceánica | sst, anom, err (°C), icec (%) | Océano global; 0.25° | Ninguna | **SR** | Solo punto; una petición por año |
| 07 | `noaa.cpc.oni` | `environmental_series.py` | Índice mensual | anomaly, total (°C); media móvil trimestral fechada en el mes central | Niño 3.4; sin geografía | Ninguna | **SR** | — |
| 08 | `usgs.earthquakes` | `environmental_series.py` | Eventos por polígono | count (diario), magnitude, depth (km) | Global | Ninguna | **SR** | Solo polígono |
| 09 | `nasa.firms.area` | `services/firms.py` | Detecciones por polígono, ventanas de 5 días | count (diario), frp (MW, media diaria), brightness (K) | Según sensor (p. ej. `VIIRS_SNPP_SP`) | `FIRMS_MAP_KEY` | **SR / AUTH?** | Re-descarga siempre; no separa sensores en el resultado; sin filtro de confianza |
| 10 | `nasa.appeears` | `services/appeears.py` | Tarea asíncrona de punto o área → ZIP | 194 productos listados: MOD13Q1, MOD11A2, MCD64A1, MOD16A2GF, MCD12Q1, MOD17, MOD10A1, NASADEM… | Según producto | `APPEEARS_TOKEN` o `EARTHDATA_USERNAME/PASSWORD` | **RAW / AUTH?** | **No devuelve serie** (`points = []`); sondeo manual ("volvé a pulsar Procesar") |
| 11 | `nasa.earthdata` | `services/downloads.py` | Búsqueda CMR + descarga de gránulos completos | IMERG, SMAP, GLDAS, MERRA-2, Ocean Color | Según colección | `EARTHDATA_TOKEN` | **RAW / AUTH?** | Sin límite de tamaño ni de cantidad de gránulos |
| 12 | `copernicus.dataspace` | `downloads.py` | Búsqueda OData + escenas completas | Sentinel-1, 2, 5P | Global | `CDSE_ACCESS_TOKEN` | **RAW / AUTH?** | Sin límite de tamaño |
| 13 | `copernicus.cds` | `services/climate_store.py` | `cdsapi.retrieve` por meses → NetCDF horario | ERA5, ERA5-Land, niveles de presión; JSON libre para otros datasets | Global | `CDSAPI_KEY` + aceptación de términos | **RAW / AUTH?** | Bloqueante, sin progreso |
| 14 | `microsoft.planetary.stac` | `downloads.py` | Búsqueda STAC + assets firmados | Landsat C2 L2 (bandas, `qa_pixel`), otras colecciones | Según colección | Ninguna | **RAW** | Sin límite; requiere procesamiento de bandas |
| 15 | `argentina.ina.series` | `environmental_series.py` | Serie de observaciones de una estación | Altura hidrométrica, caudal, precipitación 12Z, 93 variables en catálogo | Argentina | Ninguna | **SR\*** | Una variable visible puede carecer de series que pasen los filtros |
| 16 | `psmsl.rlr.monthly` | `environmental_series.py` | Serie mensual de mareógrafo | Nivel relativo (mm, referencia local RLR) | Mareógrafos | Ninguna | **SR\*** | Referencia local por estación: no comparable entre estaciones sin conversión |

Rutas declaradas en `services/catalog.py` **sin implementación**: `noaa.cdo.station`, `canada.geo.stac`, `meteomatics.weather` → se registran como `not_implemented`.

---

## 3. Productos científicos de la planilla (X01–X29) ↔ conectores reales

**Hallazgo central:** la mayoría de los productos "requeridos" por la planilla no están disponibles como serie. El Handler nunca sustituye en silencio; cuando usa un producto alternativo de la **misma magnitud física** lo declara como `source_substitution` en el resultado.

| Producto | Fenómenos que lo requieren | Vía real hoy | Alternativa de la misma magnitud física ya disponible como serie | Estado |
|---|---|---|---|---|
| X01 GPM IMERG | 16 | Earthdata (RAW) | Precipitación: ERA5 vía Open-Meteo (diaria), POWER `PRECTOTCORR` (mensual), NOAA `PRCP`, INA | Sustituible con rótulo "reanálisis/estación, no IMERG" |
| X02 ERA5 / ERA5-Land | 24 | CDS (RAW); Open-Meteo (SR, 8 variables) | T2m media mensual: POWER `T2M`; Tmax/Tmin: Open-Meteo | Parcial: faltan como serie SLP, viento, humedad relativa diaria, geopotencial, PBLH |
| X03 NASA POWER | opcional | SR | — | Disponible |
| X04 FIRMS | 5 | SR / AUTH? | — | Disponible con clave |
| X05 MCD64A1 (área quemada) | 4 | AppEEARS (RAW) | **Ninguna** (los focos FIRMS no son área quemada) | Bloqueado hasta EZE-13 |
| X06 MOD13Q1 (NDVI/EVI) | 15 | AppEEARS (RAW) | Ninguna | Bloqueado hasta EZE-12 |
| X07 MOD11A2 (LST) | 4 | AppEEARS (RAW) | **Ninguna** (T2m no sustituye a LST) | Bloqueado hasta EZE-12 |
| X08 MCD12Q1 (cobertura) | 5 | AppEEARS (RAW) | Ninguna | Bloqueado hasta EZE-13 |
| X09 SMAP | 8 | Earthdata (RAW) | Humedad de suelo **modelada** ERA5-Land por capa (m³/m³). POWER `GWETROOT` es fracción de saturación: **no intercambiable** con humedad volumétrica | Sustituible con rótulo "modelo, no observación SMAP" |
| X10 GLDAS | opcional | Earthdata (RAW) | — | No disponible |
| X11 Landsat C2 L2 | 1 | Planetary (RAW) | Ninguna | Requiere procesamiento de bandas |
| X12 Sentinel-2 L2A | opcional | CDSE / Planetary (RAW) | — | No disponible |
| X13 Sentinel-1 SAR | 4 | CDSE (RAW) | Ninguna | Fuera de alcance v1 |
| X14 SWOT | 9 | SR\* (2022→) | Series largas de nivel: INA (altura hidrométrica) | Disponible con límite temporal |
| X15 Ocean Color (clorofila) | 2 | Earthdata (RAW) | Ninguna | No disponible |
| X16 ENSO ONI | 3 | SR | — | Disponible |
| X17 SRTM / NASADEM | 4 | AppEEARS (RAW) | Ninguna | Requiere EZE-13 |
| X18 GHRSST (SST) | 4 | Sin conector | OISST (X27), SST diaria 0.25° | Sustituible con rótulo |
| X19 Sentinel-5P TROPOMI | 4 | CDSE (RAW) | Ninguna | Fuera de alcance v1 |
| X20 MOD16A2 (ET real) | 4 | AppEEARS (RAW) | **Ninguna** (ET₀ de Open-Meteo es demanda de referencia, no ET real) | Bloqueado hasta EZE-12 |
| X21 MOD17 (GPP/NPP) | 1 | AppEEARS (RAW) | Ninguna | Backlog |
| X22 Mareógrafos + GNSS | 1 | PSMSL (SR\*) para mareógrafo; GNSS sin conector | — | Parcial |
| X23 USGS sismos | 1 | SR | — | Disponible |
| X24 MOD10A1 (nieve) | 3 | AppEEARS (RAW) | Ninguna | Backlog |
| X25 Estaciones nacionales (SMN) | opcional | Sin conector | NOAA GHCN, INA | No disponible |
| X26 AERONET | opcional | Sin conector | — | No disponible |
| X27 NOAA OISST | opcional | SR | — | Disponible |
| X28 MODIS/VIIRS AOD | 5 | Earthdata (RAW) | Ninguna | Fuera de alcance v1 |
| X29 ICESat-2 | 1 | Sin conector | Ninguna | Fuera de alcance v1 |

Recursos de competencia sin vía automatizable: **C01 Giovanni** (citado en los 73), **C02 Hydrology TS**, **C06 KNMI**, C05/C07/C08/C12/C13 (bibliografía y guías) → `not_automatable`; el sistema propone el producto subyacente.

---

## 4. `DataSourceDescriptor`

Archivo único: `PY/knowledge/sources.json`. Reemplaza a `catalog.py:ROUTES`, `source-coverage.json` y `sources.js` como fuente de verdad (los tres siguen existiendo hasta migrar; ver EZE-01).

```json
{
  "source_id": "nasa.power.monthly",
  "provider": "NASA LaRC POWER",
  "role": "series",
  "kind": "reanalysis",
  "access_method": "api",
  "authentication": { "type": "none", "env": [] },
  "connection_state": "series_ready",
  "products": [
    {
      "product": "POWER Monthly",
      "version": "unverified",
      "variables": [
        {
          "variable_id": "air_temperature_2m_mean",
          "native_code": "T2M",
          "unit_native": "degC",
          "unit_normalized": "degC",
          "conversion": "identity",
          "aggregation_semantics": "period_mean"
        },
        {
          "variable_id": "precipitation_total",
          "native_code": "PRECTOTCORR",
          "unit_native": "mm/day",
          "unit_normalized": "mm",
          "conversion": "rate_per_day_times_days_in_month",
          "aggregation_semantics": "period_mean_of_rate"
        }
      ],
      "temporal_resolution": "monthly",
      "spatial_resolution": { "native": "0.5x0.625 deg", "effective_m": 50000 },
      "spatial_coverage": "global",
      "period": { "start": "1981-01", "end_rule": "last_closed_year" },
      "latency_days": null,
      "format": "json",
      "quality_flags": []
    }
  ],
  "selection": { "geometry": ["point"], "entity_resolution": false },
  "restrictions": ["monthly_only", "not_an_observation"],
  "limits": { "timeout_s": 25, "max_variables_per_request": 20 },
  "provenance_url": "https://power.larc.nasa.gov/",
  "last_verified": { "date": "2026-11-14", "scope": "public request, single point", "by": "inventario" },
  "catalog_refs": ["X03"]
}
```

| Campo | Tipo | Notas |
|---|---|---|
| `source_id` | string | Igual al id de ruta existente |
| `role` | enum `series | download | catalog | portal | reference` | |
| `kind` | enum `observation | satellite | reanalysis | model | index | events | forecast` | Compatible con `Provenance.kind` del motor |
| `access_method` | enum `api | async_task | file_download | portal` | |
| `authentication.type` | enum `none | api_key | account | token` | `env` lista las variables requeridas |
| `connection_state` | enum `series_ready | series_ready_fragile_selection | raw_only | unverified_auth | not_implemented | not_automatable` | |
| `products[].variables[].variable_id` | string | Id canónico de `knowledge/variables.json` |
| `conversion` | id de conversión registrada | Nunca una expresión libre |
| `aggregation_semantics` | enum `period_mean | period_sum | period_mean_of_rate | instantaneous | composite | count` | Decide cómo agregar sin mezclar tasas y acumulados (T14) |
| `spatial_resolution.effective_m` | number | Resolución efectiva que se reporta al usuario (Q09) |
| `period.end_rule` | enum `today | last_closed_year | fixed:<fecha> | latency_days` | |
| `last_verified` | objeto | Fecha, alcance y origen de la verificación; `null` si nunca se verificó |
| `catalog_refs` | lista | Códigos X y COMP de la planilla |

---

## 5. Selección de fuentes (`SourceSelector`)

**Problema que resuelve:** hoy la fuente la elige el usuario (o el asistente entre 4 proveedores) y el sistema toma lo primero que responde.

**Entrada:** variable canónica + geometría + período + frecuencia pedida + preferencias del usuario.
**Salida:** lista ordenada de candidatos con puntaje desglosado, el elegido, las alternativas y los descartados **con motivo**.

### Filtros excluyentes (en orden)

1. **Magnitud física exacta.** La variable canónica debe coincidir; las relaciones `not_interchangeable_with` de `variables.json` impiden sustituciones (LST ↔ T2m, focos ↔ área quemada, ET₀ ↔ ET real, humedad volumétrica ↔ fracción de saturación, presión de superficie ↔ presión a nivel del mar).
2. **Estado de conexión.** `not_automatable` y `not_implemented` se descartan con `NOT_AUTOMATABLE`; `raw_only` se descarta salvo que exista un procesador registrado para ese producto.
3. **Credenciales.** Si faltan → `CREDENTIALS_MISSING` (T19), sin intentar la descarga.
4. **Geometría.** Punto, polígono o entidad según el descriptor.
5. **Cobertura temporal declarada.** Si el período pedido empieza antes del inicio del producto → `TEMPORAL_INCOMPATIBLE` con la fecha de inicio y alternativas (T12: SWOT desde 2022).

### Ordenamiento (puntaje explicable)

| Criterio | Efecto |
|---|---|
| Producto requerido por el fenómeno (columna U) | Preferencia máxima |
| Producto opcional (columna X) o alternativa de la misma magnitud | Aceptado con `source_substitution` |
| Solapamiento con el período pedido | Proporcional |
| Naturaleza | Observación > satélite > reanálisis > modelo, **salvo** que el fenómeno pida lo contrario |
| Resolución temporal | Preferir la nativa ≥ la pedida (agregar es válido; desagregar no) |
| Resolución espacial efectiva | Informativa; nunca se remuestrea a una más fina |
| Preferencia explícita del usuario | Desempata y puede forzar, quedando registrada |

Los pesos numéricos son parámetros de `knowledge/sources.json` (decisión D-11); el orden de criterios no.

### Fuentes alternativas y complementarias

- **Alternativa**: misma magnitud física; se usa si la preferida falla o no cubre. Queda en `sources[].substitution`.
- **Complementaria**: otra magnitud o producto que contrasta (p. ej. estación NOAA frente a reanálisis). Solo se agrega si el fenómeno la contempla o el usuario la pide; nunca se promedia con la principal.

---

## 6. Selección de estaciones y entidades (rediseño)

**Responsable: Eze (EZE-06).** No se asume que el problema esté resuelto.

| Problema actual | Rediseño |
|---|---|
| Gana el primer candidato con ≥1 valor | **Puntaje** = f(distancia, fracción de cobertura del período pedido, completitud, representatividad). Se evalúan los candidatos y se elige el de mayor puntaje |
| NOAA sin información de períodos | Usar `ghcnd-inventory.txt` (primer y último año por estación y elemento) para filtrar **antes** de descargar |
| Un error aborta el recorrido | `try` por candidato; el error se registra en `rejected[]` y se sigue |
| Tope fijo de 12 y radio fijo de 150 km | Parámetros con valores por defecto actuales; ampliación progresiva del radio si ningún candidato supera la cobertura mínima |
| Polígono ordenado desde el centro del rectángulo envolvente | Orden desde el centroide del polígono; para áreas grandes, **informar** que una estación no representa el área |
| Sin corrección manual | El resultado expone `candidates[]`; el configurador permite fijar `entity_id` |
| Bug de `geometryId` nulo | Corregir la asignación de geometría para rutas de entidad |

Salida de la selección (va al resultado y a «Cómo se calculó»):

```json
{
  "selected": { "id": "AR000087436", "name": "SAN LUIS AERO", "distance_km": 4.2,
                "period_coverage": 0.97, "score": 0.93 },
  "candidates": [ { "id": "…", "distance_km": 61.0, "period_coverage": 0.41, "score": 0.38 } ],
  "rejected": [ { "id": "…", "reason": "HTTP_ERROR" } ],
  "representativeness_note": "Estación puntual; no representa el promedio del área seleccionada."
}
```

*Los valores del ejemplo son ilustrativos.*

Regla de bloqueo: si el mejor candidato no alcanza `min_coverage` (Q01, 0.8 por defecto para tendencia) → `INSUFFICIENT_DATA` con la lista de candidatos, no una serie pobre.

---

## 7. Capa común de preparación (`PY/dataprep/`)

**Responsable: Eze.** Cada operación es un nodo del DAG que agrega una entrada a `transformations` del `ScientificDataset`.

| Operación | Regla | Control |
|---|---|---|
| **Serie normalizada** | `NormalizedSeries`: `time` (ISO-8601 UTC, con `time_bounds` cuando el valor es un agregado), `value`, `valid`, `quality_flag`, `unit`, `variable_id`, `source_id`, `product`, `observed_at`/`available_at` | Adaptador desde el dict actual (`month` → `time`); los conectores no se reescriben |
| **Unidades** | Tabla de conversiones registradas: mm/día→mm/mes (× días del mes), mm/h→mm por intervalo, K→°C, kPa→hPa, fracción→% | Q11, T14. Una combinación sin conversión registrada → `UNIT_INCOMPATIBLE` |
| **Tasa vs acumulado** | La agregación temporal depende de `aggregation_semantics`: los acumulados se **suman**, las tasas se integran, los estados se promedian | Q05, T14 |
| **Calendario y zona horaria** | Todo a UTC; la ventana diaria del proveedor se conserva en metadatos (p. ej. INA 12Z) | Q10 |
| **Frecuencia** | Agregación a la frecuencia pedida solo de fina a gruesa; cada período agregado guarda `n_valid / n_expected` | Q01 |
| **Faltantes** | Nunca se interpolan extremos ni huecos para el análisis; un período con cobertura bajo el umbral queda inválido | Q01, T06 |
| **Fechas de observación y disponibilidad** | `observed_at` y `available_at` separados; el segundo se deriva de la latencia del producto cuando el proveedor no lo da | Q10, Q15, T10 |
| **Alineación temporal** | Intersección de períodos válidos; se informa cuántos pasos se pierden | Q10 |
| **Compatibilidad espacial** | La resolución efectiva del conjunto es la de la **fuente más gruesa**; se agrega, nunca se remuestrea a más fino | Q09, T13 |
| **Estadística zonal** | Promedio ponderado por área sobre el polígono, con `valid_area_fraction` | Q18 |
| **Área** | Área geodésica por píxel para productos de área quemada o cobertura | Q08 |
| **QA satelital** | Máscaras por producto (nube, sombra, agua/nieve, calidad) aplicadas antes de calcular indicadores | Q06 |
| **Datum** | Las series de nivel llevan `datum`; dos series con datum distinto no se comparan ni se combinan | Q11, T15 |
| **Detecciones térmicas** | Separación por sensor; filtro de confianza; unidad "detecciones", nunca "incendios" | Q07, T03 |

### Casos que el pedido exige contemplar explícitamente

| Caso | Tratamiento |
|---|---|
| Tasa de lluvia vs acumulado | `aggregation_semantics` + conversiones registradas |
| NASA POWER `PRECTOTCORR` | Conversión `rate_per_day_times_days_in_month` antes de cualquier SPI o tendencia de totales |
| Temperatura del aire vs LST | Variables canónicas distintas, no intercambiables; leyendas y unidades separadas |
| Humedad superficial vs zona radicular | Variables distintas (`soil_moisture_surface`, `soil_moisture_rootzone`) con atributo de profundidad |
| Datums hidrométricos | Atributo `datum` obligatorio en variables de nivel |
| Detecciones FIRMS vs superficie quemada | Variables y capas distintas; ninguna conversión registrada entre ambas |
| Resolución nativa vs efectiva | Ambas en el resultado; el mapa rotula la efectiva |

---

## 8. Descargas extensas, disponibilidad y credenciales

| Problema | Diseño | Tarea |
|---|---|---|
| Pedido histórico largo de Open-Meteo falló | Troceo temporal por ventanas con ensamblado y verificación de continuidad | EZE-11 |
| CDS bloqueante sin progreso | Ejecución como nodo de job con progreso por ventana mensual y cancelación entre ventanas | EZE-05, EZE-11 |
| AppEEARS con sondeo manual | El nodo `fetch` queda en estado `waiting_external`; el job sondea con espera creciente | EZE-12 |
| Descargas sin límite de tamaño | Límite configurable por nodo; al excederlo → error definitivo con el tamaño estimado | EZE-03 |
| Credenciales ausentes | `source_status` en `get_capabilities`: por fuente, si la credencial está presente y si fue verificada | EZE-15 |
| Fuente caída | Error recuperable con reintentos y espera exponencial; agotados → `SOURCE_UNAVAILABLE` solo para esa fuente | EZE-03 |
| Datos de muestra | Solo si la solicitud lo permite (`constraints.allow_sample_data`); siempre rotulados `demo: true` en la procedencia | EZE-15 |
