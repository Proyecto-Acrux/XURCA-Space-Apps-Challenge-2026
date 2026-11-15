<script>
  import { translate } from '$lib/services/i18n.js';
  import { geoGraticule10, geoPath } from 'd3-geo';
  import { feature, mesh } from 'topojson-client';
  import atlas from 'world-atlas/countries-110m.json';
  import { Compass, Crosshair, Layers } from '@lucide/svelte';
  import { workspace, editVisual, selectGeometry } from '$lib/stores/workspace.js';
  import { makeProjection, positionAt, closedRegion, rectangle, featurePath, coordinateLabel, wrapLongitude, clampLatitude } from '$lib/services/geography.js';

  let { tool, vertices = $bindable([]), cursor = $bindable(null), notice = $bindable(''), showDetail } = $props();
  const land = feature(atlas, atlas.objects.land);
  const borders = mesh(atlas, atlas.objects.countries, (a, b) => a !== b);
  const grid = geoGraticule10();
  let canvas;
  let width = $state(600);
  let height = $state(500);
  let drag;
  let camera = $derived($workspace.visual.map.camera);
  let projection = $derived(makeProjection(width, height, { ...camera, zoom: Math.min(8, camera.zoom) }));
  let path = $derived(geoPath(projection));
  let center = $derived(projection.translate());
  let radius = $derived(projection.scale());
  let layers = $derived($workspace.visual.map.layers);
  let features = $derived($workspace.data.geography.selection.features);

  function setCamera(edit) { editVisual(visual => edit(visual.map.camera)); }
  function zoom(factor) { setCamera(view => view.zoom = Math.min(8, Math.max(0.65, Math.min(8, view.zoom) * factor))); }
  function pointerPosition(event) {
    const bounds = canvas.getBoundingClientRect();
    return positionAt(projection, event.clientX - bounds.left, event.clientY - bounds.top);
  }
  function down(event) {
    if (event.button !== 0) return;
    canvas.focus();
    canvas.setPointerCapture(event.pointerId);
    drag = { x: event.clientX, y: event.clientY, longitude: camera.longitude, latitude: camera.latitude };
  }
  function move(event) {
    cursor = pointerPosition(event);
    if (!drag || tool !== 'pan') return;
    const gain = 0.29 / Math.min(8, camera.zoom);
    setCamera(view => {
      view.longitude = wrapLongitude(drag.longitude - (event.clientX - drag.x) * gain);
      view.latitude = clampLatitude(drag.latitude + (event.clientY - drag.y) * gain);
    });
  }
  function up(event) {
    if (!drag) return;
    drag = null;
    if (tool === 'pan') return;
    const point = pointerPosition(event);
    if (!point) return;
    if (tool === 'point') selectGeometry('Point', point);
    if (tool === 'polygon') vertices = [...vertices, point];
    if (tool === 'rectangle') {
      if (!vertices.length) {
        vertices = [point];
        return;
      }
      const ring = rectangle(vertices[0], point);
      if (ring) selectGeometry('Polygon', ring, 'Rectángulo');
      else notice = 'Elegí esquinas distintas dentro del mismo hemisferio longitudinal.';
      vertices = [];
    }
  }
  function finishPolygon() {
    const ring = closedRegion(vertices);
    if (!ring) {
      notice = 'Elegí al menos tres vértices que delimiten un área.';
      return;
    }
    selectGeometry('Polygon', ring, 'Polígono');
    vertices = [];
  }
  function keyboard(event) {
    if (event.key === 'Escape') vertices = [];
    if (event.key === 'Enter' && tool === 'polygon') finishPolygon();
    const directions = { ArrowLeft: [-8,0], ArrowRight: [8,0], ArrowUp: [0,8], ArrowDown: [0,-8] };
    if (directions[event.key]) {
      event.preventDefault();
      const [lon, lat] = directions[event.key];
      setCamera(view => {
        view.longitude = wrapLongitude(view.longitude + lon);
        view.latitude = clampLatitude(view.latitude + lat);
      });
    }
  }
</script>

<section class="map-panel">
  <header class="panel-heading"><span><Compass size={16}/> {$translate("Exploración geográfica")}</span><button class="outlined" onclick={showDetail}>{$translate("Mapa detallado")}</button></header>
  <div class="map-view" bind:clientWidth={width} bind:clientHeight={height}>
    <canvas class:selecting={tool !== 'pan'} bind:this={canvas} tabindex="0" aria-label={$translate("Globo interactivo")}
      onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={() => drag = null}
      onpointerleave={() => cursor = null} onkeydown={keyboard} onwheel={event => zoom(event.deltaY < 0 ? 1.09 : 1 / 1.09)}></canvas>
    <svg class="earth-render" {width} {height} aria-hidden="true">
      <defs>
        <radialGradient id="ocean" cx=".37" cy=".25" r=".82">
          <stop class="globe-ocean-start" stop-color="#19415a"/><stop offset="0.72" class="globe-ocean-middle" stop-color="#112a40"/><stop offset="1" class="globe-ocean-end" stop-color="#081727"/>
        </radialGradient>
        <radialGradient id="shade" cx=".33" cy=".26" r=".74">
          <stop offset=".43" stop-color="#050d18" stop-opacity="0"/><stop offset="1" stop-color="#050d18" stop-opacity=".58"/>
        </radialGradient>
      </defs>
      <circle cx={center[0]} cy={center[1]} r={radius} fill="url(#ocean)" class="globe-edge"/>
      <path d={path(land)} class="globe-land"/>
      {#if layers.countries}<path d={path(borders)} class="globe-border"/>{/if}
      {#if layers.grid}<path d={path(grid)} class="globe-grid"/>{/if}
      <circle cx={center[0]} cy={center[1]} r={radius} class="globe-shade" fill="url(#shade)"/>
      {#if layers.selection}
        {#each features as item (item.id)}
          <path d={featurePath(projection, item)} class:map-point={item.geometry.type === 'Point'} class="map-selection"/>
        {/each}
      {/if}
      {#if vertices.length > 1}<path d={path({ type:'LineString', coordinates:vertices })} class="map-draft"/>{/if}
      {#each vertices as point}<path d={path({ type:'Point', coordinates:point })} class="map-point"/>{/each}
    </svg>
    <div class="map-top"><span class="map-pill"><span class="live-dot"></span> WGS 84</span><span class="map-pill">{coordinateLabel(cursor)}</span></div>
    <div class="map-bottom">
      <span>{$translate(tool === 'pan' ? 'Arrastrá para rotar · Rueda para acercar' : tool === 'point' ? 'Hacé clic sobre el globo para marcar un punto' : tool === 'rectangle' ? 'Marcá dos esquinas opuestas' : 'Marcá tres o más vértices')}</span>
      {#if tool === 'polygon' && vertices.length}
        <button onclick={finishPolygon} disabled={vertices.length < 3}>{$translate("Cerrar polígono")} ({vertices.length})</button>
      {/if}
    </div>
    <small class="map-credit">Natural Earth · 1:110m</small>
  </div>
  {#if $workspace.visual.workspace.layers}
    <div class="layers-bar">
      <span><Layers size={15}/> {$translate("Capas")}</span>
      {#each [['countries','Fronteras'], ['grid','Grilla'], ['selection','Selección']] as [id, label]}
        <label><input type="checkbox" checked={layers[id]} onchange={event => editVisual(visual => visual.map.layers[id] = event.currentTarget.checked)}/>{$translate(label)}</label>
      {/each}
      <span class="feature-count"><Crosshair size={14}/> {features.length}</span>
    </div>
  {/if}
</section>
