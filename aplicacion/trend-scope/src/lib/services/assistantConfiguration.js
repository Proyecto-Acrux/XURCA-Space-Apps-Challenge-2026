import contract from '../../../src-tauri/src-python/trend_scope/services/assistant-contract.json' with { type: 'json' };
import { assistantCatalog as catalog, sourceConfig, geographicEntityRoutes } from './sources.js';
import { closedRegion, validCoordinates } from './geography.js';

function checkShape(value, schema) {
  switch (schema.type) {
    case 'object':
      return value !== null && typeof value === 'object' && !Array.isArray(value)
        && (schema.required ?? []).every(key => Object.hasOwn(value, key))
        && Object.entries(value).every(([key, item]) =>
          Object.hasOwn(schema.properties, key) && checkShape(item, schema.properties[key]));
    case 'array':
      return Array.isArray(value) && value.every(item => checkShape(item, schema.items));
    case 'string':
      return typeof value === 'string' && value.length <= 1200 && (!schema.enum || schema.enum.includes(value));
    case 'number':
      return Number.isFinite(value);
    case 'integer':
      return Number.isInteger(value);
    case 'boolean':
      return typeof value === 'boolean';
    default:
      return false;
  }
}

function isoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function bounded(value, min, max) {
  return value === undefined || (value >= min && value <= max);
}

function validate(changes) {
  if (!checkShape(changes, contract.schema.properties.changes)) throw new Error('La IA propuso campos de configuración inválidos.');
  const { point, place, polygon, sources, appearance, workspace, camera } = changes;
  if ([point, place, polygon].filter(Boolean).length > 1) throw new Error('Indicá una sola selección geográfica por mensaje.');
  if (point && !validCoordinates(point.longitude, point.latitude)) throw new Error('Las coordenadas están fuera del rango WGS 84.');
  if (polygon && (polygon.length > 100 || !polygon.every(p => p.length === 2 && validCoordinates(...p)) || !closedRegion(polygon))) {
    throw new Error('El polígono requiere vértices válidos en orden longitud, latitud.');
  }
  if (sources && (sources.length > catalog.length || new Set(sources.map(item => item.id)).size !== sources.length)) {
    throw new Error('La lista de fuentes contiene variables duplicadas o excede el catálogo.');
  }
  if (appearance?.accent !== undefined && !/^#[0-9a-f]{6}$/i.test(appearance.accent)) throw new Error('El color requiere un valor hexadecimal de seis dígitos.');
  if (appearance?.fontSize !== undefined && ![12, 13, 15].includes(appearance.fontSize)) throw new Error('El tamaño de texto debe ser 12, 13 o 15.');
  if (!bounded(workspace?.settingsWidth, 220, 450) || !bounded(workspace?.assistantWidth, 265, 600)) {
    throw new Error('El ancho propuesto está fuera del rango de los paneles.');
  }
  if (!bounded(camera?.longitude, -180, 180) || !bounded(camera?.latitude, -90, 90) || !bounded(camera?.zoom, 0.65, 1024)) {
    throw new Error('La posición o el zoom del mapa están fuera de rango.');
  }
}

function configureSource(item, points, newPoint, existing) {
  const entry = catalog.find(source => source.id === item.id);
  if (!entry) throw new Error('Una variable propuesta no está en el catálogo: ' + item.id);
  const config = sourceConfig(item.id);
  const { upstream } = config;
  const compatible = geographicEntityRoutes.has(config.access)
    ? points : points.filter(item => item.geometry.type === 'Point');
  const preferred = item.pointId || newPoint?.id || existing?.upstream.geometryId;
  const selection = compatible.find(item => item.id === preferred) ?? (compatible.length === 1 ? compatible[0] : null);
  if (!selection) throw new Error('Elegí una selección geográfica para ' + entry.label + '.');
  upstream.geometryId = selection.id;
  return config;
}

export async function configureWorkspace(snapshot, changes, invoke, language) {
  validate(changes);
  const next = JSON.parse(JSON.stringify(snapshot));
  const { data, visual } = next;
  for (const key of ['title', 'objective', 'description']) if (key in changes) data[key] = changes[key];
  if (changes.time) {
    const { start, end } = { ...data.time, ...changes.time };
    if (!isoDate(start) || !isoDate(end) || start > end) throw new Error('Ingresá fechas válidas en orden.');
    Object.assign(data.time, { start, end });
  }

  const selection = data.geography.selection;
  if (changes.clearSelection) {
    selection.features = [];
    for (const source of data.sources) source.upstream.geometryId = null;
  }
  let point = changes.point;
  if (changes.place) {
    const { name, kind } = changes.place;
    if (name.trim().length < 2 || name.length > 100) throw new Error('Indicá un nombre de lugar válido.');
    const matches = JSON.parse(await invoke('search_places', { query: name, kind, language }));
    if (matches.length !== 1) {
      const names = matches.slice(0, 4).map(match => [match.name, match.province, match.country].filter(Boolean).join(', '));
      throw new Error(names.length ? 'Hay varios lugares posibles. Indicá cuál: ' + names.join(' / ') : 'No encontré ese lugar. Indicá la ciudad, provincia o coordenadas.');
    }
    const [{ coordinates: [longitude, latitude], name: label }] = matches;
    if (!validCoordinates(longitude, latitude)) throw new Error('El lugar no tiene coordenadas válidas.');
    point = { longitude, latitude, name: label };
  }
  let feature;
  if (point || changes.polygon) {
    feature = {
      type: 'Feature', id: crypto.randomUUID(), properties: { name: point?.name ?? '' },
      geometry: point ? { type: 'Point', coordinates: [point.longitude, point.latitude] }
        : { type: 'Polygon', coordinates: closedRegion(changes.polygon) }
    };
    selection.features.push(feature);
    if (point) Object.assign(visual.map.camera, { longitude: point.longitude, latitude: point.latitude });
  }
  if (changes.sources || point) {
    const points = selection.features;
    const requests = changes.sources ?? data.sources.filter(item => catalog.some(entry => entry.id === item.id))
      .map(item => ({ id: item.id }));
    const configured = requests.map(item => configureSource(item, points, feature, data.sources.find(source => source.id === item.id)));
    if (changes.sources) data.sources = configured;
    else data.sources = data.sources.map(item => configured.find(source => source.id === item.id) ?? item);
  }
  if (changes.sources || changes.time || point) {
    const cadences = await Promise.all(data.sources.map(async source => {
      const entry = catalog.find(item => item.id === source.id);
      if (!entry) return null;
      const scope = source.access === 'noaa.ncei.station' ? 'station'
        : entry.featureType === 'Reach' ? 'river' : entry.featureType === 'PriorLake' ? 'lake' : 'land';
      const { matches } = await invoke('evaluate_coverage', { variable: entry.variable, scope, start: data.time.start, end: data.time.end });
      const match = matches.find(row => row.access === source.access && row.variables.includes(entry.code)
        && (!entry.featureType || row.selection === entry.featureType));
      if (!match || !['compatible', 'unverified'].includes(match.status)) {
        throw new Error('El período o la selección no son compatibles con ' + entry.label + '.');
      }
      return match.cadence;
    }));
    if (cadences.includes('monthly')) data.time.resolution = 'Mensual';
    else if (cadences.includes('daily')) data.time.resolution = 'Diaria';
    else if (cadences.includes('overpass')) data.time.resolution = 'Por pasada';
  }
  for (const key of ['theme', 'language', 'chartResolution']) if (key in changes) visual[key] = changes[key];
  Object.assign(visual.appearance, changes.appearance);
  Object.assign(visual.workspace, changes.workspace);
  Object.assign(visual.map.camera, changes.camera);
  Object.assign(visual.map.layers, changes.mapLayers);
  return next;
}
