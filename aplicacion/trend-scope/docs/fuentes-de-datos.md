# Fuentes de datos de Earth Detective

## Consultas y descargas desde Configuración

Agregá una fuente en **Fuentes de información**, elegí un punto o polígono cuando la fuente lo pida y pulsá **Procesar**. Las series muestran valores en la app. Las descargas muestran la ruta del archivo en el resultado. Los archivos van al subdirectorio `downloads` del directorio de datos de Earth Detective. En Windows está bajo `%LOCALAPPDATA%\com.xurca.trend-scope`.

| Fuente | Selección | Resultado |
|---|---|---|
| NOAA NCEI diario | Punto o área del mapa y código de variable, por ejemplo `TMAX`, `TMIN` o `PRCP` | Serie diaria. Los días sin observación quedan vacíos. |
| NOAA OISST | Punto marino. Códigos `sst`, `anom`, `err` e `icec` | Serie diaria de la celda NOAA. |
| NOAA ENSO / ONI | Fechas. Anomalía ONI o temperatura móvil de Niño 3.4 | Serie de medias móviles trimestrales con fechas del mes central. |
| USGS sismos | Polígono y magnitud mínima opcional | Conteo diario, magnitud o profundidad por evento. |
| INA y PSMSL | Punto o área del mapa. En INA elegí la variable del catálogo; en PSMSL seleccioná nivel relativo del mar. | Observaciones hidrológicas o nivel relativo mensual RLR, respectivamente. |
| NASA FIRMS | Polígono, sensor oficial y columna, `count` o `all` | CSV con todas las columnas y las detecciones dentro del polígono. `count` grafica el conteo y un código numérico como `frp` grafica su media diaria. |
| NASA AppEEARS | Producto con versión y capa exacta. **Buscar capas** consulta el catálogo del proveedor. | ZIP de la extracción appEEARS por punto o área. Si sigue en curso, volvé a pulsar **Procesar** para recuperar el mismo trabajo. |
| NASA Earthdata CMR | ID de colección, como `C2723754864-GES_DISC` para IMERG diario V07, y punto o área | ZIP con gránulos originales y manifiesto. Admite productos con enlaces HTTPS directos compatibles, por ejemplo colecciones de lluvia, humedad, aerosoles o color oceánico. `all` conserva todas las variables del gránulo. El área filtra por extensión rectangular. |
| Copernicus Data Space | Colección, por ejemplo `SENTINEL-2`, tipo de producto como `S2MSI2A` o `all`, y punto o área | Escenas originales que intersectan la selección. El área se busca por su extensión rectangular. |
| Copernicus CDS | ERA5, ERA5-Land o niveles de presión con polígono y código oficial. Para otros productos CDS pegá el objeto JSON que muestra el proveedor en **Show API request code**, con fechas, variables y filtros. | ZIP con NetCDF de ERA5 en el rectángulo de la selección, o archivos originales de la solicitud CDS. La ruta JSON sirve para productos con campos propios, como FireCCI o temperatura superficial de lagos. |
| Planetary Computer STAC | Colección y clave del activo. Por ejemplo `landsat-c2-l2` y `red`. Usá `all` para los activos marcados como datos. | ZIP con bandas o archivos originales y manifiesto de los ítems encontrados. |

Las credenciales se configuran antes de abrir la aplicación. FIRMS usa `FIRMS_MAP_KEY`. AppEEARS usa `APPEEARS_TOKEN` o `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD`. Las descargas protegidas de CMR usan `EARTHDATA_TOKEN`. Las escenas Sentinel de Copernicus Data Space usan `CDSE_ACCESS_TOKEN`. CDS usa `CDSAPI_KEY` o `.cdsapirc` y requiere aceptar los términos del producto desde el portal.

Los ZIP de grillas y escenas conservan el material para análisis posteriores. La aplicación todavía requiere un paso de procesamiento científico para aplicar máscaras de calidad, derivar índices, estimar área quemada o reducir grillas a series por polígono.

## Inventario de cobertura

[source-coverage.json](../src-tauri/src-python/trend_scope/services/source-coverage.json) describe las 19 opciones iniciales que tienen evaluación de cobertura en el asistente. Los límites por colección sirven para una evaluación previa. La disponibilidad efectiva depende del punto, la estación o la entidad solicitada.

### Selección automática de estaciones y entidades

Para NOAA diario y mensual, PSMSL, INA y SWOT, marcá un punto o dibujá un área y elegí la variable. Si hay varias selecciones, indicá cuál debe usar la fuente. Al pulsar **Procesar**, Earth Detective consulta los catálogos y prueba hasta 12 candidatos por orden de cercanía. Para puntos busca NOAA, PSMSL e INA hasta 150 km, tramos SWOT hasta 20 km y lagos SWOT hasta 10 km. Para áreas, busca estaciones dentro del polígono y entidades SWOT que lo intersectan, ordenadas por distancia al centro de su extensión. Elige el primer candidato con al menos un dato de la variable en las fechas solicitadas. El resultado indica la entidad elegida, su ID y la distancia.

### Comprobaciones directas del 14 de noviembre de 2026

| Ruta | Selección y período | Resultado |
|---|---|---|
| NASA POWER | Punto en San Luis, lon −66.34 y lat −33.30, enero de 2000 a diciembre de 2025 | 312 meses con valor en cada una de las seis variables predefinidas |
| Open-Meteo ERA5 / ERA5-Land | Mismo punto, 1–3 de enero de 2000 y 29–31 de diciembre de 2025 | Tres días con valor por ventana en las ocho variables predefinidas. La solicitud del intervalo completo no devolvió una respuesta válida |
| NOAA GSOM | Estación `ARM00087436`, enero de 2000 a diciembre de 2025 | Precipitación `PRCP` con 11 meses con valor, entre diciembre de 2002 y junio de 2005. Temperatura media `TAVG` sin valores en la ventana solicitada |
| SWOT RiverSP D | Tramo `78340600051`, agosto de 2023 a diciembre de 2025 | 120 observaciones con altura de agua |
| SWOT LakeSP D | Lago `6350036102`, agosto de 2023 a diciembre de 2025 | 80 observaciones con valor por variable, altura de agua y superficie |

Las comprobaciones usaron los conectores Python de la app y conservaron solo conteos y metadatos. Los ejemplos de NOAA y SWOT corresponden a los identificadores indicados. Las pruebas de Open-Meteo en los extremos sustentan la disponibilidad en esos días, mientras que la continuidad completa queda por comprobar.

### Muestreo geográfico de Argentina

El [registro de muestras](../config/argentina-coverage-samples.json) usa un punto aproximado en cada una de las 23 provincias y en CABA, más tres puntos mar adentro frente al norte, centro y sur. Se pidió un mes de NASA POWER y un día de Open-Meteo. Cada resultado registra qué variables devolvieron un valor y, en Open-Meteo, la celda devuelta. Las muestras indican disponibilidad puntual en esas fechas.

En los 24 puntos terrestres, NASA POWER devolvió seis variables, ERA5 devolvió dos y ERA5-Land devolvió seis. En los tres puntos marinos, POWER devolvió las cinco variables atmosféricas y de radiación y dejó sin valor la humedad radicular. ERA5 devolvió precipitación y ET₀ con ambas preferencias de celda. ERA5-Land dejó las seis variables sin valor en los tres puntos marinos.

El conector de Open-Meteo usa `cell_selection=land`. El muestreo marino de ERA5 incluye una prueba separada con `cell_selection=sea`, disponible en el proveedor y pendiente de integrar en la app. ERA5-Land es un producto terrestre. Las variables de NASA POWER y ERA5 probadas en el mar describen condiciones atmosféricas o radiación, con la humedad radicular y la ET₀ sujetas a sus propias limitaciones de uso.

NOAA GSOM requiere una estación con observaciones de la variable elegida. SWOT Hydrocron usa las colecciones de tramos fluviales y lagos. La selección automática usa el catálogo GHCN de NOAA y los catálogos SWORD v17b y PLD para los identificadores de Hydrocron. Las variables oceanográficas, como temperatura superficial del mar y altura de ola, requieren productos marinos específicos.

El inventario se basa en `Memoria/General/Recursos_Earth_System_Trend_Detective.txt`. Las rutas utilizables se registran en `trend_scope/services/catalog.py`. Cada ruta identifica un mecanismo de acceso. Una misma colección puede aparecer por varias rutas.

## Recursos del desafío

| Recurso | Datos y requisitos | Estado |
|---|---|---|
| AppEEARS | Producto con versión, capa, período y punto o área. Earthdata Login para crear trabajos, consultar estado y descargar. El formato y la proyección dependen de la extracción. | Catálogo y descarga integrados |
| NOAA CDO / NCEI | Separar API CDO v2 con token y Data Access Service. Para series de estación, usar ID de colección, códigos de variable, IDs de estación y fechas. | Data Access Service integrado para series mensuales y diarias |
| KNMI Climate Explorer | Portal de series y grillas. Identificar archivo, producto, período y unidad antes de automatizar. | Página accesible. Descarga programática pendiente. |
| RADARSAT RCM | Ficha de misión con distribución por EODMS. Requiere identificar colección, escena o filtros de búsqueda y permisos para el producto. | Ficha pública consultada. Acceso a imágenes pendiente. |
| GEO.ca | Catálogo. Para la ruta STAC, elegir colección, geometría o filtros espaciales según el producto, período y clave del archivo. Registrar el ID del ítem devuelto. | Catálogo STAC consultado |
| SWOT | La ficha canadiense describe la misión. Para series en Hydrocron, elegir colección, tipo e ID del río o lago, campos y fechas. El ID de la entidad corresponde a la versión del producto. | Integrado para altura del agua y superficie de lago |
| PDF SeaWiFS, dos artículos estadísticos, ecosistemas y tutorial SAR | Referencias científicas, metodológicas o didácticas. | Consultar el proveedor original si se identifica un producto de interés. |

CMR complementa los accesos NASA. Permite resolver el ID de colección y buscar gránulos de productos como FLDAS o GLDAS. La descarga se determina por los enlaces y permisos de la colección.

## Fuentes complementarias

- **NASA POWER mensual** admite un punto, años inicial y final, código de variable (por ejemplo, `PRECTOTCORR`) y comunidad (por ejemplo, `AG`). Integrado en la app para precipitación y temperatura del aire a 2 m.
- **Meteomatics** requiere cuenta, marcas de tiempo e intervalo, parámetro con unidad, coordenadas y, cuando se fija, modelo. La cuenta del equipo tiene acceso temporal. Confirmar cobertura y condiciones de uso antes de depender de sus datos.
- **Planetary Computer** ofrece catálogo STAC. La descarga requiere seleccionar colección, ítem y archivo, y seguir el mecanismo de acceso del activo.

## Contrato de configuración

`cfg_data.json` ya tiene fechas, resolución, unidades, geometrías GeoJSON WGS 84, datos básicos del producto y procedencia. Para ejecutar una consulta falta identificar la ruta en `sources[].access` y registrar los IDs del proveedor en `sources[].upstream`. El catálogo valida presencia de los campos básicos de cada ruta. Cada futura implementación debe validar cobertura, resoluciones, fechas y opciones particulares.

| Campo dentro de la fuente | Uso |
|---|---|
| `access` | ID estable de la ruta, por ejemplo `openmeteo.archive.daily`. |
| `upstream.productId` | Código exacto que espera el servicio. La versión del producto se guarda en `version` cuando exista. |
| `upstream.variableId` | ID o código oficial de variable, capa o campo solicitado. `variable` conserva su significado dentro de la app. |
| `upstream.geometryId` | ID de una geometría en la selección compartida. GeoJSON mantiene longitud antes de latitud. El conector traduce el orden al formato del proveedor. |
| `upstream.selectors` | Parámetros de selección propios de la ruta, como `stationIds`, `featureType`, `featureId`, `collectionId`, `assetKey` o `community`. |
| `reference` y `provenance.references` | Referencias a datos usados, como IDs de gránulos, ítems, versiones o archivos descargados. |

El campo `upstream` es opcional al leer proyectos de esquema 1. Para POWER, la app toma el único punto seleccionado y resuelve su ID al consultar. Al sumar un proveedor, agregá su ruta y requisitos al catálogo y colocá su cliente en `services/`. El cliente convierte los campos de la investigación a la solicitud del proveedor. Credenciales, respuestas crudas, datos descargados y cachés se mantienen fuera del repositorio.

## Variables por código oficial

En los conectores activos se puede elegir una variable habitual o introducir su código oficial desde el selector. La disponibilidad depende del producto y la resolución: POWER mensual (comunidad AG en la interfaz), NOAA Global Summary of the Month y SWOT RiverSP/LakeSP D. Para NOAA, las variables con unidades todavía sin identificar se muestran como tales.


## Reanálisis histórico vía Open-Meteo

La ruta diaria agrupa las variables por punto y modelo. ERA5-Land sirve humedad del suelo en cuatro capas y temperaturas extremas diarias. ERA5 aporta precipitación acumulada y ET₀ de referencia. Las fechas se interpretan en UTC y los resultados conservan el punto solicitado, la celda, unidades y URL. ET₀ expresa demanda evaporativa de referencia. La evapotranspiración real requiere otro producto.

El acceso público de Open-Meteo está sujeto a sus condiciones de uso no comercial y cuotas. La atribución incluye ECMWF y Open-Meteo. Consultá https://open-meteo.com/en/docs/historical-weather-api.
