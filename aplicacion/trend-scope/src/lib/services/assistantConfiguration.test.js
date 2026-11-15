import { test } from 'node:test';
import assert from 'node:assert/strict';
import data from '../../../config/cfg_data.json' with { type: 'json' };
import visual from '../../../config/cfg_visual.json' with { type: 'json' };
import { configureWorkspace } from './assistantConfiguration.js';

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
