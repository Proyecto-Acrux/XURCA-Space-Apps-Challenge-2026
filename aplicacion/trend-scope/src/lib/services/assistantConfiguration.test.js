import { test } from 'node:test';
import assert from 'node:assert/strict';
import data from '../../../config/cfg_data.json' with { type: 'json' };
import visual from '../../../config/cfg_visual.json' with { type: 'json' };
import { configureWorkspace } from './assistantConfiguration.js';
import { prepareInvestigation } from './acquisition.js';

const snapshot = () => structuredClone({ data, visual });
const coverage = async (command) => {
  assert.equal(command, 'evaluate_coverage');
  return { matches: [{ access: 'nasa.power.monthly', variables: ['T2M'], status: 'compatible', cadence: 'monthly' }] };
};

test('two-turn configuration preserves the point, variable and visual preferences', async () => {
  const initial = snapshot();
  const first = await configureWorkspace(initial, { point: { longitude: -66.33, latitude: -33.3 },
    sources: [{ id: 'power-temperature' }], time: { start: '2000-01-01', end: '2024-12-31' } }, coverage, 'es');
  const second = await configureWorkspace(first, { time: { start: '2010-01-01' } }, coverage, 'es');
  assert.equal(second.data.time.start, '2010-01-01');
  assert.equal(second.data.time.end, '2024-12-31');
  assert.deepEqual(second.data.sources, first.data.sources);
  assert.deepEqual(second.data.geography, first.data.geography);
  assert.deepEqual(second.visual, first.visual);
  assert.deepEqual(initial, snapshot());
});

test('invalid source and ambiguous place do not mutate existing configuration', async () => {
  const initial = snapshot();
  await assert.rejects(configureWorkspace(initial, { sources: [{ id: 'invented' }] }, coverage, 'es'), /catálogo/);
  await assert.rejects(configureWorkspace(initial, { place: { name: 'San Luis', kind: 'localidades' } },
    async () => JSON.stringify([{ name: 'San Luis', country: 'Argentina' }, { name: 'San Luis', country: 'México' }]), 'es'), /varios lugares/);
  assert.deepEqual(initial, snapshot());
});

test('incompatible coverage rejects the entire proposal, including title and theme', async () => {
  const initial = snapshot();
  await assert.rejects(configureWorkspace(initial, { title: 'New', theme: 'light',
    point: { longitude: -66, latitude: -33 }, sources: [{ id: 'power-temperature' }] },
    async () => ({ matches: [{ access: 'nasa.power.monthly', variables: ['T2M'], status: 'partial' }] }), 'es'), /compatibles/);
  assert.deepEqual(initial, snapshot());
});

const locations = [
  ['San Luis', 'San Luis', -66.335, -33.302],
  ['9 de Julio', 'Buenos Aires', -60.884, -35.445],
  ['El Volcán', 'San Luis', -66.183, -33.259]
];
const multiple = {
  places: locations.map(([name, province]) => ({ name: `${name}, ${province}, Argentina`, kind: 'localidades' })),
  sources: [{ id: 'power-precipitation' }, { id: 'noaa-precipitation' }],
  time: { start: '2005-01-01', end: '2024-12-31' }
};
const resolveLocations = async (command, args) => {
  if (command === 'search_places') {
    const [name, province, longitude, latitude] = locations.find(([name]) => args.query.startsWith(name));
    return JSON.stringify([{ name, province, country: 'Argentina', coordinates: [longitude, latitude] },
      { name, province: 'Otra provincia', country: 'Argentina', coordinates: [0, 0] }]);
  }
  return { matches: [
    { access: 'nasa.power.monthly', variables: ['PRECTOTCORR'], status: 'compatible', cadence: 'monthly' },
    { access: 'noaa.ncei.station', variables: ['PRCP'], status: 'unverified', cadence: 'monthly' }
  ] };
};

test('three named towns create six distinct source-point series and survive follow-ups', async () => {
  const initial = snapshot();
  initial.data.geography.selection.features = [];
  const configured = await configureWorkspace(initial, multiple, resolveLocations, 'es');
  assert.equal(configured.data.geography.selection.features.length, 3);
  assert.equal(configured.data.sources.length, 6);
  assert.equal(new Set(configured.data.sources.map(source => source.id)).size, 6);
  for (const point of configured.data.geography.selection.features) {
    assert.equal(configured.data.sources.filter(source => source.upstream.geometryId === point.id).length, 2);
  }
  const again = await configureWorkspace(configured, multiple, resolveLocations, 'es');
  assert.deepEqual(again.data, configured.data);
  const later = await configureWorkspace(configured, { time: { start: '2010-01-01' } }, resolveLocations, 'es');
  assert.deepEqual(later.data.sources, configured.data.sources);
});

test('an unresolved place rejects the entire multi-place proposal', async () => {
  const initial = snapshot();
  await assert.rejects(configureWorkspace(initial, multiple, async (command, args) =>
    args?.query?.startsWith('El Volcán') ? '[]' : resolveLocations(command, args), 'es'), /No encontré/);
  assert.deepEqual(initial, snapshot());
});

test('explicit missing point references are rejected instead of silently reassigned', async () => {
  await assert.rejects(configureWorkspace(snapshot(), { point: { longitude: -66, latitude: -33 },
    sources: [{ id: 'power-temperature', pointId: 'missing' }] }, coverage, 'es'), /no existe/);
});

const ring = [[-61, -36], [-60, -36], [-60, -35], [-61, -35], [-61, -36]];
const polygon = { type: 'Polygon', coordinates: [ring] };
const rainfall = { access: 'ucsb.chirps.monthly', variables: ['precipitation'], status: 'unverified', cadence: 'monthly' };

test('a drawn polygon is reused from the chat, applied to scope, and passed to acquisition', async () => {
  const initial = snapshot();
  initial.data.geography.scope = 'point';
  initial.data.geography.selection.features = [
    { id: 'p', geometry: { type: 'Point', coordinates: [-60.5, -35.5] } },
    { id: 'drawn', properties: { name: 'Polígono manual' }, geometry: polygon }
  ];
  const result = await configureWorkspace(initial, { sources: [{ id: 'chirps-monthly-precipitation', geometryId: 'drawn' }] },
    async (command, args) => {
      assert.equal(command, 'evaluate_coverage');
      assert.equal(args.scope, 'area');
      return { matches: [rainfall] };
    }, 'es');
  assert.equal(result.data.geography.scope, 'area');
  assert.equal(result.data.sources[0].upstream.geometryId, 'drawn');
  assert.equal(result.data.geography.selection.features.length, 2);
  const payload = prepareInvestigation(result.data);
  assert.deepEqual(payload.geography.selection.features.map(item => item.geometry), [polygon]);
  assert.equal(payload.sources[0].upstream.geometryId, 'drawn');
});

test('a named Argentine locality uses its published boundary', async () => {
  const result = await configureWorkspace(snapshot(), {
    place: { name: '9 de Julio, Buenos Aires, Argentina', kind: 'localidades-censales' },
    sources: [{ id: 'chirps-monthly-precipitation' }]
  }, async (command, args) => {
    if (command === 'search_places') {
      assert.equal(args.query, '9 de Julio');
      return JSON.stringify([{ id: '006', name: '9 de Julio', province: 'Buenos Aires', country: 'Argentina', coordinates: [-60.88, -35.44] }]);
    }
    if (command === 'load_place_boundary') {
      assert.deepEqual(args, { kind: 'localidades-censales', id: '006' });
      return { type: 'MultiPolygon', coordinates: [[ring]] };
    }
    assert.equal(command, 'evaluate_coverage');
    assert.equal(args.scope, 'area');
    return { matches: [rainfall] };
  }, 'es');
  const [feature] = result.data.geography.selection.features;
  assert.equal(feature.geometry.type, 'MultiPolygon');
  assert.equal(prepareInvestigation(result.data).sources[0].upstream.geometryId, feature.id);
});

test('a polygon does not become a point for a point-only source', async () => {
  await assert.rejects(configureWorkspace(snapshot(), {
    polygon: ring, sources: [{ id: 'power-temperature' }]
  }, async () => { throw new Error('Must reject before checking provider coverage'); }, 'es'), /selección geográfica/);
});
