<script>
  import { geoMercator, geoPath } from 'd3-geo';
  import { feature } from 'topojson-client';
  import atlas from 'world-atlas/countries-110m.json';
  import { featurePath } from '$lib/services/geography.js';
  import { densityColors, densityImage } from '$lib/services/densityMap.js';
  import { stationImage, stationSnapshots } from '$lib/services/stationSurface.js';
  import { translate } from '$lib/services/i18n.js';
  import RegionalPlaceLabels from './RegionalPlaceLabels.svelte';

  let { layer, unit, label } = $props();
  let frame = $state(0);
  let selected = $state(null);
  let width = $state(0);
  let height = $state(0);
  let reliefLoaded = $state('');
  let heatmap = $state(null);
  const land = feature(atlas, atlas.objects.land);
  const eventColors = ['#36739d', '#468fb7', '#60bdce', '#c5f2ef'];
  let colors = $derived(layer.kind === 'events' ? eventColors : densityColors);
  const densityLabels = ['Muy baja', 'Baja', 'Media', 'Alta'];
  const discreteColors = ['#4da5c8', '#efaa66', '#b6a3e5', '#77c498', '#d77794', '#d6ca63', '#c0c7d2'];
  let categories = $derived(Object.entries(layer.categories ?? {}));
  let categoryColors = $derived(new Map(categories.map(([value], i) => [value, discreteColors[i % discreteColors.length]])));
  const clipId = 'regional-map-area-' + crypto.randomUUID();
  let earthquake = $derived(layer.eventType === 'earthquake' || (layer.kind === 'events' && !layer.eventType));
  let fire = $derived(layer.eventType === 'fire');
  let featureLabel = $derived($translate(earthquake ? 'Sismo registrado' : fire ? 'Foco detectado' : 'Observación'));
  let magnitude = $derived(layer.field === 'magnitude');
  let count = $derived(layer.field === 'count');
  const format = value => new Intl.NumberFormat(undefined, {maximumSignificantDigits: 5}).format(value);
  let range = $derived.by(() => {
    let min = Infinity, max = -Infinity;
    for (const event of layer.events) {
      const value = event[layer.field];
      if (!Number.isFinite(value)) continue;
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
    return Number.isFinite(min) ? [min, max] : null;
  });
  let thresholds = $derived(earthquake ? (magnitude ? [3, 4, 5] : [35, 70, 300])
    : fire && layer.field === 'frp' ? [10, 50, 100]
    : range && range[0] !== range[1] ? [1, 2, 3].map(index => range[0] + (range[1] - range[0]) * index / 4) : []);
  let classes = $derived(categories.length ? categories.map(([value, label]) => ({label, color: categoryColors.get(value)}))
    : count ? [{ label: featureLabel, color: colors[0] }] : thresholds.length ?
    [{ label: '< ' + format(thresholds[0]), color: colors[0] },
     { label: format(thresholds[0]) + ' – < ' + format(thresholds[1]), color: colors[1] },
     { label: format(thresholds[1]) + ' – < ' + format(thresholds[2]), color: colors[2] },
     { label: '≥ ' + format(thresholds[2]), color: colors[3] },
     { label: $translate('Sin valor'), color: '#a0aec0' }]
    : [{ label: range ? format(range[0]) : $translate('Sin valor'), color: range ? colors[0] : '#a0aec0' }]);

  let precision = $derived({ daily: 10, monthly: 7, yearly: 4 }[layer.cadence]);
  let windows = $derived.by(() => {
    const first = new Date(layer.start + 'T00:00:00Z');
    const last = new Date(layer.end + 'T00:00:00Z');
    if (precision === 4) first.setUTCMonth(0, 1);
    if (precision === 7) first.setUTCDate(1);
    const result = [];
    while (first <= last) {
      const date = first.toISOString().slice(0, 10);
      if (precision === 4) first.setUTCFullYear(first.getUTCFullYear() + 1);
      else if (precision === 7) first.setUTCMonth(first.getUTCMonth() + 1);
      else first.setUTCDate(first.getUTCDate() + 1);
      const end = new Date(first.getTime() - 86400000).toISOString().slice(0, 10);
      result.push({ key: date.slice(0, precision), start: date < layer.start ? layer.start : date,
                    end: end > layer.end ? layer.end : end });
    }
    return result;
  });
  let groups = $derived.by(() => {
    const result = new Map();
    if (layer.stationSurface) return result;
    for (const event of layer.events) {
      const key = event.date.slice(0, precision);
      if (!result.has(key)) result.set(key, []);
      result.get(key).push(event);
    }
    if (layer.kind === 'entities') {
      for (const [key, samples] of result) {
        const latest = new Map();
        for (const sample of samples) {
          if (!latest.has(sample.entityId) || latest.get(sample.entityId).date <= sample.date) latest.set(sample.entityId, sample);
        }
        result.set(key, [...latest.values()]);
      }
    }
    return result;
  });
  let window = $derived(windows[frame] ?? windows[0]);
  let stationWindows = $derived(layer.stationSurface ? stationSnapshots(layer.events, precision) : null);
  let snapshot = $derived(stationWindows?.get(window?.key));
  let events = $derived(snapshot?.events ?? groups.get(window?.key) ?? []);
  let projection = $derived.by(() => {
    const polygons = layer.area.type === 'Polygon' ? [layer.area.coordinates] : layer.area.coordinates;
    const bounds = polygons.flatMap(polygon => polygon[0]);
    return geoMercator().fitExtent([[18, 18], [Math.max(width - 18, 19), Math.max(height - 18, 19)]],
      { type: 'MultiPoint', coordinates: bounds }).clipExtent([[0, 0], [width, height]]);
  });
  let projected = $derived(events.map(event => {
    const coordinates = event.coordinates ?? (event.geometry?.type === 'Point' ? event.geometry.coordinates : null);
    return { ...event, coordinates, position: coordinates && projection(coordinates),
             path: !coordinates && event.geometry ? featurePath(projection, event) : null };
  }));
  let mapCenter = $derived(projection.invert([width / 2, height / 2]));
  let mapZoom = $derived(Math.log2(2 * Math.PI * projection.scale() / 512));
  $effect(() => {
    if (layer.kind === 'events') {
      heatmap = densityImage(projected.map(event => event.position).filter(Boolean), width, height);
    } else if (snapshot?.canEstimate) {
      heatmap = stationImage(projected.filter(event => event.position?.every(Number.isFinite)), width, height, colors, thresholds, outline);
    } else {
      heatmap = null;
    }
  });
  let outline = $derived(featurePath(projection, { geometry: layer.area }));
  let landPath = $derived(geoPath(projection)(land));
  let relief = $derived.by(() => {
    if (!width || !height) return null;
    const origin = projection([0, 0]);
    const metresPerPixel = 6378137 / projection.scale();
    const limit = Math.PI * 6378137;
    const left = Math.max(0, origin[0] - limit / metresPerPixel);
    const top = Math.max(0, origin[1] - limit / metresPerPixel);
    const right = Math.min(width, origin[0] + limit / metresPerPixel);
    const bottom = Math.min(height, origin[1] + limit / metresPerPixel);
    if (right <= left || bottom <= top) return null;
    const bbox = [(left - origin[0]) * metresPerPixel, (origin[1] - bottom) * metresPerPixel,
                  (right - origin[0]) * metresPerPixel, (origin[1] - top) * metresPerPixel];
    const params = new URLSearchParams({
      SERVICE: 'WMS', VERSION: '1.3.0', REQUEST: 'GetMap', FORMAT: 'image/png', STYLES: '',
      CRS: 'EPSG:3857', BBOX: bbox.map(value => value.toFixed(2)).join(','),
      WIDTH: String(Math.min(1600, Math.ceil(right - left))),
      HEIGHT: String(Math.min(1200, Math.ceil(bottom - top))),
      LAYERS: 'ASTER_GDEM_Greyscale_Shaded_Relief', TRANSPARENT: 'true'
    });
    return { url: 'https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi?' + params,
             x: left, y: top, width: right - left, height: bottom - top };
  });

  function color(event) {
    if (count) return colors[0];
    const value = event[layer.field];
    if (value == null) return '#a0aec0';
    if (categories.length) return categoryColors.get(String(value)) ?? '#a0aec0';
    if (!thresholds.length) return colors[0];
    const index = thresholds.findIndex(limit => value < limit);
    return colors[index < 0 ? colors.length - 1 : index];
  }

  function eventLabel(event) {
    const value = event[layer.field];
    const display = count ? featureLabel : value == null ? $translate('Sin valor')
      : layer.categories?.[value] ?? (format(value) + ' ' + unit);
    return [display, event.date.slice(0, 19).replace('T', ' ') + ' UTC', event.location].filter(Boolean).join(' · ');
  }
</script>

<section class="event-map" aria-label={label}>
  {#if layer.label}<strong>{layer.label}</strong>{/if}
  <div class="event-map-viewport" bind:clientWidth={width} bind:clientHeight={height}>
    <svg {width} {height} aria-label={$translate('Mapa de eventos')} role="group">
      <path d={landPath} class="event-map-land"/>
      {#if relief}
        {#key relief.url}
          {@const url = relief.url}
          <image href={url} x={relief.x} y={relief.y} width={relief.width} height={relief.height}
            preserveAspectRatio="none" opacity="0.8" aria-hidden="true" onload={() => reliefLoaded = url}/>
        {/key}
      {/if}
      <path d={outline} class="event-map-area"/>
      <defs><clipPath id={clipId}><path d={outline} clip-rule="evenodd"/></clipPath></defs>
      {#if heatmap}
        <image href={heatmap} x="0" y="0" {width} {height} preserveAspectRatio="none"
          clip-path={'url(#' + clipId + ')'} pointer-events="none" aria-hidden="true"/>
      {/if}
      {#each projected as event (event.id)}
        {#if event.position}
        <circle cx={event.position[0]} cy={event.position[1]} r="4.5" fill={color(event)}
          clip-path={'url(#' + clipId + ')'}
          stroke="#142033" stroke-width="1" role="button" tabindex="0" aria-label={eventLabel(event)}
          onclick={() => selected = event}
          onkeydown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selected = event; } }}>
          <title>{eventLabel(event)}</title>
        </circle>
        {:else if event.path}
          <path d={event.path} fill={event.geometry.type.includes('LineString') ? 'none' : color(event)} fill-opacity={layer.kind === 'grid' ? 0.82 : 1}
            clip-path={'url(#' + clipId + ')'} stroke={color(event)} stroke-width={layer.kind === 'grid' ? 0 : 2}
            role="button" tabindex={layer.kind === 'grid' ? -1 : 0} aria-label={eventLabel(event)}
            onclick={() => selected = event}
            onkeydown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selected = event; } }}>
            <title>{eventLabel(event)}</title>
          </path>
        {/if}
      {/each}
    </svg>
    {#if width && height && mapCenter?.every(Number.isFinite) && mapZoom >= 0 && mapZoom <= 22 && Math.abs(mapCenter[1]) <= 85}
      <RegionalPlaceLabels center={mapCenter} zoom={mapZoom} {width} {height}/>
    {/if}
    <details class="map-credits">
      <summary aria-label={$translate('Créditos del mapa')} title={$translate('Créditos del mapa')}>ⓘ</summary>
      <div>
        {#if relief && reliefLoaded === relief.url}
          <a href="https://earthdata.nasa.gov/gibs" target="_blank" rel="noreferrer">NASA EOSDIS GIBS · ASTER GDEM</a> (NASA/METI)
        {/if}
        <a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a>
      </div>
    </details>
  </div>
  {#if layer.kind === 'events'}
    <div class="event-map-legend" aria-label={$translate('Concentración de eventos')}>
      <strong>{$translate('Concentración de eventos')}</strong>
      {#each densityColors as color, index}
        <span><i style:background={color}></i>{$translate(densityLabels[index])}</span>
      {/each}
    </div>
    <small class="quiet">{$translate('La concentración se estima a partir de los puntos de esta ventana.')}</small>
  {/if}
  <div class="event-map-legend" aria-label={$translate('Leyenda')}>
    {#if !count}<strong>{unit}</strong>{/if}
    {#each classes as entry}
      <span><i style:background={entry.color}></i>{entry.label}</span>
    {/each}
  </div>
  <label class="event-map-time">
    <span>{$translate('Fecha del mapa')} ·
      {#if layer.kind === 'grid' && layer.cadence === 'yearly' && events.length}
        {events[0].date.slice(0, 7)}
      {:else if layer.kind === 'grid' && layer.nativeCadence === 'daily' && layer.cadence !== 'daily' && events.length}
        {events[0].date} UTC
      {:else}
        {window?.start}{window?.end !== window?.start ? ' – ' + window?.end : ''} UTC
      {/if}
    </span>
    <input type="range" min="0" max={windows.length - 1} value={frame} disabled={windows.length < 2}
      oninput={event => { frame = Number(event.currentTarget.value); selected = null; }}/>
  </label>
  {#if !events.length}<p class="quiet">{$translate(earthquake ? 'Sin sismos registrados en esta ventana' : fire ? 'Sin focos detectados en esta ventana' : 'No hay datos para esta ventana')}</p>{/if}
  {#if layer.stationSurface && snapshot}
    <p class="quiet">
      {snapshot.date} · {events.length} {$translate('estaciones con mediciones ese día')}.
      {#if heatmap}
        {$translate('Superficie estimada entre estaciones, recortada a la selección.')}
      {:else}
        {$translate('Cobertura insuficiente para estimar una superficie. Se requieren al menos tres estaciones que cubran parte de la selección.')}
      {/if}
    </p>
    <details>
      <summary>{$translate('Mediciones de estación')}</summary>
      <ul>
        {#each events as event (event.id)}
          <li>{event.location} · {format(event.value)} {unit}</li>
        {/each}
      </ul>
    </details>
  {:else if layer.kind === 'entities' && !layer.stationSurface && precision < 10}
    <p class="quiet">{$translate('Última medición disponible por entidad en cada ventana.')}</p>
  {/if}
  {#if selected}
    <p role="status">{eventLabel(selected)}
      {#if selected.coordinates || selected.center} · {(selected.coordinates ?? selected.center).map(value => value.toFixed(3)).join(', ')}{/if}
      {#if selected.magnitudeType} · {selected.magnitudeType}{/if}
      {#if selected.quality} · {$translate('Estado del catálogo')}: {selected.quality}{/if}</p>
  {/if}
</section>

<style>
  .map-credits {position:absolute;right:.5rem;bottom:.5rem;text-align:right}
  .map-credits summary {list-style:none;cursor:pointer;background:var(--panel,#101a28);padding:.2rem .45rem;border-radius:4px}
  .map-credits div {position:absolute;right:0;bottom:100%;width:max-content;max-width:min(75vw,24rem);padding:.4rem;background:var(--panel,#101a28)}
</style>
