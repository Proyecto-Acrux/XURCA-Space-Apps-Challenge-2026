<script>
  import { translate } from '$lib/services/i18n.js';
  import { coordinateLabel } from '$lib/services/geography.js';

  let { cursor = null } = $props();
  let elevation = $state(null);
  let cell = $derived(cursor?.map(value => value.toFixed(3)).join(',') ?? '');
  const cache = new Map();
  const format = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

  $effect(() => {
    elevation = null;
    if (!cell) return;
    if (cache.has(cell)) {
      elevation = cache.get(cell);
      return;
    }
    const controller = new AbortController();
    const [longitude, latitude] = cell.split(',');
    const params = new URLSearchParams({ longitude, latitude });
    const timer = setTimeout(async () => {
      try {
        const response = await fetch('https://api.open-meteo.com/v1/elevation?' + params, { signal: controller.signal });
        if (!response.ok) return;
        const { elevation: values } = await response.json();
        const value = values?.[0];
        if (controller.signal.aborted || !Number.isFinite(value)) return;
        if (cache.size >= 128) cache.delete(cache.keys().next().value);
        cache.set(cell, value);
        elevation = value;
      } catch {
        // The coordinates remain available when elevation cannot be fetched.
      }
    }, 400);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  });
</script>

<div class="map-top">
  <span class="map-pill">WGS 84</span>
  <span class="map-pill">{coordinateLabel(cursor)}</span>
  <a class="map-pill" href="https://open-meteo.com/en/docs/elevation-api" target="_blank" rel="noreferrer"
    title={$translate('Elevación del terreno · Copernicus DEM / Open-Meteo')}>
    {$translate('Altitud')} · {elevation === null ? '—' : format.format(elevation) + ' m'}
  </a>
</div>
