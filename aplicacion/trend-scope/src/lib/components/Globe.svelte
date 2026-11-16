<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { translate } from '$lib/services/i18n.js';
  import { geoGraticule10, geoPath } from 'd3-geo';
  import { feature, mesh } from 'topojson-client';
  import atlas from 'world-atlas/countries-110m.json';
  import { Compass } from '@lucide/svelte';
  import MapReadout from './MapReadout.svelte';
  import { workspace, editVisual, selectGeometry } from '$lib/stores/workspace.js';
  import { createGlobeTexture } from '$lib/services/globeTexture.js';
  import { makeProjection, positionAt, addPolygonVertex, closedRegion, draftGeometry, nearPolygonStart, openPolygonNotice, rectangle, featurePath, wrapLongitude, clampLatitude } from '$lib/services/geography.js';

  let { tool, vertices = $bindable([]), cursor = $bindable(null), notice = $bindable(''), showDetail } = $props();
  let draft = $derived(draftGeometry(vertices));
  const land = feature(atlas, atlas.objects.land);
  const borders = mesh(atlas, atlas.objects.countries, (a, b) => a !== b);
  const grid = geoGraticule10();
  let canvas;
  let photo;
  let renderer = $state.raw(null);
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

  onMount(() => {
    const image = new Image();
    image.onload = () => { renderer = createGlobeTexture(photo, image); };
    image.src = base + '/blue-marble.jpg';
    return () => {
      image.onload = null;
      renderer?.destroy();
    };
  });

  $effect(() => {
    renderer?.draw(width, height, center, radius, camera);
  });

  function setCamera(edit) { editVisual(visual => edit(visual.map.camera)); }
  function zoom(event) {
    if (!event.deltaY) return;
    const factor = event.deltaY < 0 ? 1.16 : 1 / 1.16;
    const next = Math.min(8, Math.max(0.65, Math.min(8, camera.zoom) * factor));
    setCamera(view => view.zoom = next);
  }
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
    if (tool === 'polygon') {
      const bounds = canvas.getBoundingClientRect();
      const first = vertices[0];
      if (vertices.length >= 3 && path({ type: 'Point', coordinates: first })
          && nearPolygonStart(projection(first), event.clientX - bounds.left, event.clientY - bounds.top)) {
        const ring = closedRegion(vertices);
        if (ring) {
          selectGeometry('Polygon', ring, 'Polígono');
          vertices = [];
          if (notice === openPolygonNotice) notice = '';
        }
        return;
      }
      vertices = addPolygonVertex(vertices, point);
    }
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
  function keyboard(event) {
    if (event.key === 'Escape' && tool !== 'polygon') vertices = [];
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
  <div class="map-view globe-view" role="group" aria-label={$translate("Exploración geográfica")} bind:clientWidth={width} bind:clientHeight={height} onpointerleave={() => cursor = null}>
    <canvas class="globe-photo" bind:this={photo} aria-hidden="true" hidden={!renderer}
      onwebglcontextlost={() => renderer = null}></canvas>
    <canvas class:selecting={tool !== 'pan'} bind:this={canvas} tabindex="0" aria-label={$translate("Globo interactivo")}
      onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={() => drag = null}
      onkeydown={keyboard} onwheel={zoom}></canvas>
    <svg class="earth-render" class:photographic={!!renderer} {width} {height} aria-hidden="true">
      <defs>
        <radialGradient id="ocean" cx=".37" cy=".25" r=".82">
          <stop class="globe-ocean-start" stop-color="#19415a"/><stop offset="0.72" class="globe-ocean-middle" stop-color="#112a40"/><stop offset="1" class="globe-ocean-end" stop-color="#081727"/>
        </radialGradient>
        <radialGradient id="shade" cx=".33" cy=".26" r=".74">
          <stop offset=".43" stop-color="#050d18" stop-opacity="0"/><stop offset="1" stop-color="#050d18" stop-opacity=".58"/>
        </radialGradient>
      </defs>
      {#if !renderer}
        <circle cx={center[0]} cy={center[1]} r={radius} fill="url(#ocean)" class="globe-edge"/>
        <path d={path(land)} class="globe-land"/>
        <circle cx={center[0]} cy={center[1]} r={radius} class="globe-shade" fill="url(#shade)"/>
      {/if}
      {#if layers.countries}<path d={path(borders)} class="globe-border"/>{/if}
      {#if layers.grid}<path d={path(grid)} class="globe-grid"/>{/if}
      {#if layers.selection}
        {#each features as item (item.id)}
          <path d={featurePath(projection, item)} class:map-point={item.geometry.type === 'Point'} class="map-selection"/>
        {/each}
      {/if}
      {#if draft}<path d={path(draft)} class="map-draft"/>{/if}
      {#each vertices as point, index}
        <path d={path({ type:'Point', coordinates:point })} class="map-point" class:polygon-start={tool === 'polygon' && index === 0}/>
      {/each}
    </svg>
    <MapReadout {cursor}/>
    <small class="map-credit globe-credit">
      {#if renderer}
        <a href="https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/" target="_blank" rel="noreferrer">Blue Marble · NASA Earth Observatory</a>
        {#if layers.countries} · Natural Earth{/if}
      {:else}
        Natural Earth · 1:110m
      {/if}
    </small>
  </div>
</section>

<style>
  .globe-photo { z-index: 0; pointer-events: none; }
  .photographic .globe-border { stroke: #cee5f0; stroke-opacity: .34; }
  .photographic .globe-grid { stroke: #b4daee; stroke-opacity: .17; }
  .globe-credit { pointer-events: auto; background: #050911c7; padding: 2px 5px; border-radius: 4px; }
  .globe-credit a { color: #c4d6e8; }
</style>
