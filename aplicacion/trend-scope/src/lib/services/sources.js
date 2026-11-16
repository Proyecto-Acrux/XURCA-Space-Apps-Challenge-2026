export const providers = [
  { id: 'nasa.power.monthly', label: 'NASA POWER', provider: 'NASA', hint: 'Usa un punto del mapa' },
  { id: 'noaa.ncei.station', label: 'NOAA NCEI', provider: 'NOAA', hint: 'Busca estaciones con datos de la variable y las fechas elegidas.' },
  { id: 'nasa.swot.hydrocron', label: 'NASA SWOT / Hydrocron', provider: 'NASA', hint: 'Busca un tramo o lago según la selección del mapa' },
  { id: 'openmeteo.archive.daily', label: 'Open-Meteo · ERA5 / ERA5-Land', provider: 'ECMWF', hint: 'Series diarias por punto, sin cuenta para uso no comercial' },
  { id: 'noaa.ncei.daily', label: 'NOAA NCEI diario', provider: 'NOAA', station: true, hint: 'Busca estaciones con datos de la variable y las fechas elegidas.' },
  { id: 'noaa.oisst.daily', label: 'NOAA OISST', provider: 'NOAA', geometry: ['Point'], hint: 'Usa un punto en el mar' },
  { id: 'noaa.cpc.oni', label: 'NOAA ENSO · ONI / RONI', provider: 'NOAA', hint: 'Índice para la región Niño 3.4' },
  { id: 'usgs.earthquakes', label: 'USGS · Sismos', provider: 'USGS', geometry: ['Polygon', 'MultiPolygon'], hint: 'Usa un polígono' },
  { id: 'nasa.firms.area', label: 'NASA FIRMS', provider: 'NASA', geometry: ['Polygon', 'MultiPolygon'], product: 'Sensor FIRMS', hint: 'Usa un polígono y requiere FIRMS_MAP_KEY' },
  { id: 'nasa.appeears', label: 'NASA AppEEARS', provider: 'NASA', geometry: ['Point', 'Polygon', 'MultiPolygon'], product: 'Producto y versión', hint: 'Extracción por punto o área con Earthdata Login' },
  { id: 'nasa.earthdata', label: 'NASA Earthdata · CMR', provider: 'NASA', geometry: ['Point', 'Polygon', 'MultiPolygon'], product: 'ID de colección CMR', codeLabel: 'Archivo completo', defaultCode: 'all', hint: 'Descarga gránulos originales por fechas y zona. Usá all para todas las variables del archivo.' },
  { id: 'copernicus.dataspace', label: 'Copernicus Data Space · Sentinel', provider: 'ESA', geometry: ['Point', 'Polygon', 'MultiPolygon'], product: 'Colección (ej. SENTINEL-2)', codeLabel: 'Tipo de producto (ej. S2MSI2A)', hint: 'Descarga escenas Sentinel con CDSE_ACCESS_TOKEN' },
  { id: 'copernicus.cds', label: 'Copernicus Climate Data Store', provider: 'ECMWF', geometry: ['Polygon', 'MultiPolygon'], product: 'Conjunto de datos CDS', defaultProduct: 'reanalysis-era5-single-levels', hint: 'ERA5 por área o solicitud JSON para otros productos CDS' },
  { id: 'microsoft.planetary.stac', label: 'Planetary Computer · STAC', provider: 'Microsoft', geometry: ['Point', 'Polygon', 'MultiPolygon'], product: 'Colección STAC (ej. landsat-c2-l2)', codeLabel: 'Clave del activo STAC', hint: 'Descarga bandas y archivos originales. Usá all para los activos de datos.' },
  { id: 'argentina.ina.series', label: 'INA · Datos hidrológicos', provider: 'INA', hint: 'Busca una serie hidrológica según el área o punto y las fechas' },
  { id: 'psmsl.rlr.monthly', label: 'PSMSL · Mareógrafos', provider: 'PSMSL', hint: 'Busca un mareógrafo para la selección y el período' },
  { id: 'ucsb.chirps.monthly', label: 'CHIRPS v3 · UCSB', provider: 'UCSB', geometry: ['Point', 'Polygon', 'MultiPolygon'], hint: 'Precipitación mensual sobre tierra entre 60° S y 60° N desde 1981.', catalogOnly: true },
  { id: 'argentina.pmra.monthly', label: 'PMRAv1 · Argentina', provider: 'Gaitán y Biancari', geometry: ['Point', 'Polygon', 'MultiPolygon'], hint: 'Precipitación mensual de Argentina en celdas de 5 km. Las fechas dependen del archivo publicado.', catalogOnly: true },
  { id: 'ucsb.chirps.daily', label: 'CHIRPS v3 diario · ERA5', provider: 'UCSB', geometry: ['Point', 'Polygon', 'MultiPolygon'], hint: 'Precipitación diaria estimada. Consultas de hasta 366 días.', catalogOnly: true }
];

export const geographicEntityRoutes = new Set([
  'noaa.ncei.station', 'noaa.ncei.daily', 'nasa.swot.hydrocron', 'argentina.ina.series', 'psmsl.rlr.monthly'
]);
export const entityGeometries = ['Point', 'Polygon', 'MultiPolygon'];

export function providerGeometries(route) {
  if (!route) return [];
  if (geographicEntityRoutes.has(route.id)) return entityGeometries;
  return route.geometry ?? (['nasa.power.monthly', 'openmeteo.archive.daily'].includes(route.id) ? ['Point'] : []);
}

export function providerMatchesScope(route, scope) {
  if (!scope || scope === 'both') return true;
  const geometries = providerGeometries(route);
  return !geometries.length || geometries.some(type => geometryMatchesScope(type, scope));
}

export function geometryMatchesScope(type, scope) {
  return !scope || scope === 'both' || (scope === 'point' ? type === 'Point' : type !== 'Point');
}

export function sourceMatchesScope(source, scope, features) {
  const route = providers.find(item => item.id === source.access);
  const geometry = features.find(item => item.id === source.upstream?.geometryId)?.geometry;
  return (!route || providerMatchesScope(route, scope)) && (!geometry || geometryMatchesScope(geometry.type, scope));
}

export const catalog = [
  ['power-precipitation', 0, 'Precipitación media diaria por mes', 'precipitation', 'PRECTOTCORR'],
  ['power-humidity', 0, 'Humedad relativa del aire', 'relative-humidity', 'RH2M'],
  ['power-wind', 0, 'Velocidad del viento a 2 m', 'wind-speed', 'WS2M'],
  ['power-soil', 0, 'Humedad de la zona radicular', 'soil-moisture', 'GWETROOT'],
  ['power-solar', 0, 'Radiación solar en superficie', 'solar-radiation', 'ALLSKY_SFC_SW_DWN'],
  ['power-temperature', 0, 'Temperatura del aire a 2 m', 'temperature', 'T2M'],
  ['noaa-precipitation', 1, 'Precipitación acumulada mensual', 'precipitation', 'PRCP'],
  ['noaa-temperature', 1, 'Temperatura media mensual', 'temperature', 'TAVG'],
  ['swot-river-elevation', 2, 'Altura del agua en río', 'water-elevation', 'wse', 'Reach'],
  ['swot-lake-elevation', 2, 'Altura del agua en lago', 'water-elevation', 'wse', 'PriorLake'],
  ['swot-lake-area', 2, 'Superficie de lago', 'water-area', 'area_total', 'PriorLake'],
  ['era5-soil-surface', 3, 'Humedad del suelo 0–7 cm (ERA5-Land)', 'soil-moisture', 'soil_moisture_0_to_7cm_mean'],
  ['era5-soil-shallow', 3, 'Humedad del suelo 7–28 cm (ERA5-Land)', 'soil-moisture', 'soil_moisture_7_to_28cm_mean'],
  ['era5-soil-root', 3, 'Humedad del suelo 28–100 cm (ERA5-Land)', 'soil-moisture', 'soil_moisture_28_to_100cm_mean'],
  ['era5-soil-deep', 3, 'Humedad del suelo 100–255 cm (ERA5-Land)', 'soil-moisture', 'soil_moisture_100_to_255cm_mean'],
  ['era5-max-temperature', 3, 'Temperatura máxima diaria (ERA5-Land)', 'temperature-max', 'temperature_2m_max'],
  ['era5-min-temperature', 3, 'Temperatura mínima diaria (ERA5-Land)', 'temperature-min', 'temperature_2m_min'],
  ['era5-precipitation', 3, 'Precipitación acumulada diaria (ERA5)', 'precipitation', 'precipitation_sum'],
  ['era5-et0', 3, 'Evapotranspiración de referencia ET₀ (ERA5)', 'reference-et', 'et0_fao_evapotranspiration'],
  ['noaa-daily-precipitation', 4, 'Precipitación diaria de estación', 'precipitation', 'PRCP'],
  ['noaa-daily-max', 4, 'Temperatura máxima diaria de estación', 'temperature-max', 'TMAX'],
  ['noaa-daily-min', 4, 'Temperatura mínima diaria de estación', 'temperature-min', 'TMIN'],
  ['oisst-sst', 5, 'Temperatura superficial del mar', 'sea-surface-temperature', 'sst'],
  ['oisst-anomaly', 5, 'Anomalía de temperatura del mar', 'sea-surface-temperature-anomaly', 'anom'],
  ['oisst-error', 5, 'Error estimado de temperatura del mar', 'sea-surface-temperature-error', 'err'],
  ['oni', 6, 'Índice oceánico de El Niño', 'oni', 'anomaly'],
  ['roni', 6, 'Índice oceánico relativo de El Niño (RONI)', 'roni', 'roni'],
  ['oni-sst', 6, 'Temperatura media móvil Niño 3.4', 'nino34-temperature', 'total'],
  ['usgs-count', 7, 'Detecciones sísmicas diarias', 'earthquake-count', 'count'],
  ['usgs-magnitude', 7, 'Magnitud de sismos', 'earthquake-magnitude', 'magnitude'],
  ['oisst-ice', 5, 'Concentración de hielo marino', 'sea-ice-concentration', 'icec'],
  ['usgs-depth', 7, 'Profundidad de sismos', 'earthquake-depth', 'depth'],
  ['ina-height', 14, 'Altura hidrométrica', 'water-level', 'var-2'],
  ['ina-discharge', 14, 'Caudal', 'river-discharge', 'var-4'],
  ['ina-precipitation', 14, 'Precipitación diaria (12Z)', 'precipitation', 'var-1'],
  ['psmsl-level', 15, 'Nivel relativo del mar (RLR mensual)', 'relative-sea-level', 'rlr'],
  ['chirps-monthly-precipitation', 16, 'Precipitación acumulada mensual (CHIRPS v3)', 'precipitation', 'precipitation'],
  ['pmra-monthly-precipitation', 17, 'Precipitación acumulada mensual (PMRAv1)', 'precipitation', 'precipitation'],
  ['chirps-daily-precipitation', 18, 'Precipitación acumulada diaria (CHIRPS v3)', 'precipitation', 'precipitation']
].map(([id, index, label, variable, code, featureType]) => ({
  id, label, variable, code, featureType, route: providers[index]
}));

export const assistantCatalog = catalog.filter(item => [
  'nasa.power.monthly', 'noaa.ncei.station', 'nasa.swot.hydrocron', 'openmeteo.archive.daily',
  'ucsb.chirps.monthly', 'ucsb.chirps.daily', 'argentina.pmra.monthly', 'noaa.cpc.oni', 'usgs.earthquakes'
].includes(item.route.id));

export function sourceConfig(id) {
  const item = catalog.find(entry => entry.id === id);
  const { route, featureType } = item;
  const selectors = route.id === 'nasa.power.monthly' ? { community: 'AG' }
    : featureType ? { featureType, featureId: '' } : (route.id === 'noaa.ncei.station' || route.station) ? { stationId: '' } : {};
  return {
    id, variable: item.variable, provider: route.provider, product: route.label, access: route.id,
    upstream: { variableId: item.code, geometryId: null, selectors }
  };
}
export function customSource(routeId, code, featureType, productId) {
  const route = providers.find(item => item.id === routeId);
  return {
    id: [routeId, featureType, productId, code].filter(Boolean).join(':'),
    variable: code, provider: route.provider, product: productId ? route.label + ' · ' + productId : route.label, access: routeId,
    upstream: {
      variableId: code, ...(productId ? { productId } : {}), geometryId: null,
      selectors: routeId === 'nasa.power.monthly' ? { community: 'AG' }
        : featureType ? { featureType, featureId: '' } : (routeId === 'noaa.ncei.station' || route.station) ? { stationId: '' } : {}
    }
  };
}
