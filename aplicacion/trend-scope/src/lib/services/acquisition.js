import { isTauri } from '@tauri-apps/api/core';
import { pyInvoke } from 'tauri-plugin-pytauri-api';
import { providers, providerGeometries, geometryMatchesScope, sourceMatchesScope } from './sources.js';

export function prepareInvestigation(data) {
  const investigation = JSON.parse(JSON.stringify(data));
  const { scope, selection } = investigation.geography;
  if (!investigation.sources.length) throw new Error('Agregá al menos una variable.');
  const { start, end } = investigation.time;
  const validDate = value => /^\d{4}-\d{2}-\d{2}$/.test(value)
    && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Argentina/Buenos_Aires' }).format(new Date());
  if (!validDate(start) || !validDate(end) || start > end || end > today) {
    throw new Error('Elegí un período histórico con las fechas en orden.');
  }
  if (investigation.methods?.length) throw new Error('Los métodos personalizados todavía no se ejecutan desde Procesar.');
  investigation.sources = investigation.sources.filter(source => sourceMatchesScope(source, scope, selection.features));
  if (!investigation.sources.length) throw new Error('En Fuentes de información, elegí una variable compatible y pulsá Agregar.');
  selection.features = selection.features.filter(feature => geometryMatchesScope(feature.geometry.type, scope));
  for (const source of investigation.sources) {
    if (source.access === 'copernicus.cds' && source.upstream.selectors?.requestJson) continue;
    const route = providers.find(route => route.id === source.access);
    const geometries = providerGeometries(route);
    if (!geometries.length) continue;
    const compatible = selection.features.filter(feature => geometries.includes(feature.geometry.type));
    const requested = source.upstream.geometryId;
    if (compatible.some(feature => feature.id === requested)) continue;
    if (!requested && compatible.length === 1) {
      source.upstream.geometryId = compatible[0].id;
      continue;
    }
    throw new Error('Elegí una geometría de consulta compatible con ' + (source.product || source.variable) + '.');
  }
  return investigation;
}

export async function acquireData(investigation) {
  if (!isTauri()) throw new Error('Abrí Earth Detective con pnpm tauri dev para consultar las fuentes.');
  const response = await pyInvoke('acquire_data', { investigation });
  return JSON.parse(response);
}
