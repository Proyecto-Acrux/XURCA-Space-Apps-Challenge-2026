import { providers } from './sources.js';
import dataDefaults from '../../../config/cfg_data.json';
import { isTauri } from '@tauri-apps/api/core';
import { pyInvoke } from 'tauri-plugin-pytauri-api';

const files = { data: 'cfg_data.json', visual: 'cfg_visual.json' };
const browserKey = 'earth-detective.workspace';

export async function loadWorkspace() {
  let snapshot;
  if (isTauri()) {
    const entries = await Promise.all(Object.entries(files).map(async ([key, name]) => {
      const raw = await pyInvoke('load_configuration', { name });
      return [key, raw ? JSON.parse(raw) : null];
    }));
    snapshot = Object.fromEntries(entries);
  } else {
    snapshot = JSON.parse(localStorage.getItem(browserKey) ?? 'null');
  }
  for (const key of Object.keys(files)) {
    if (snapshot?.[key] && snapshot[key].schemaVersion !== 1) {
      throw new Error('Versión de esquema incompatible en ' + files[key]);
    }
  }
  if (snapshot?.data?.provenance?.simulated) {
    const data = snapshot.data;
    data.sources = structuredClone(dataDefaults.sources);
    data.methods = [];
    data.time = { ...dataDefaults.time, start: data.time.start, end: data.time.end };
    data.geography.selection.features = data.geography.selection.features.filter(feature => !feature.properties?.approximate);
    data.id = data.id === 'investigacion-demo' ? dataDefaults.id : data.id;
    delete data.provenance.simulated;
  }
  if (snapshot?.data?.sources) {
    snapshot.data.sources = snapshot.data.sources.filter(source =>
      providers.some(provider => provider.id === source.access)
    );
  }
  const geography = snapshot?.data?.geography;
  if (geography && !Object.hasOwn(geography, 'scope')) {
    const features = geography.selection?.features ?? [];
    const point = features.some(feature => feature.geometry?.type === 'Point');
    const area = features.some(feature => ['Polygon', 'MultiPolygon'].includes(feature.geometry?.type));
    geography.scope = point && area ? 'both' : point ? 'point' : area ? 'area' : null;
  }
  if (snapshot?.visual) {
    const layout = snapshot.visual.workspace;
    if (layout) {
      if (layout.assistantVisible === undefined) {
        layout.assistantVisible = true;
        layout.assistantWidth = layout.resultsWidth ?? 388;
      }
      delete layout.results;
      delete layout.resultsWidth;
      delete layout.assistant;
    }
    delete snapshot.visual.charts;
    delete snapshot.visual.expandedChart;
  }
  return snapshot;
}

export async function saveWorkspace(snapshot) {
  if (isTauri()) {
    await pyInvoke('save_configuration', {
      data: JSON.stringify(snapshot.data, null, 2), visual: JSON.stringify(snapshot.visual, null, 2)
    });
  } else {
    localStorage.setItem(browserKey, JSON.stringify(snapshot));
  }
}

export function downloadJson(name, value) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
