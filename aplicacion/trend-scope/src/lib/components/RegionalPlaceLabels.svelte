<script module>
  let placeStyle;

  function loadPlaceStyle() {
    placeStyle ??= fetch('https://tiles.openfreemap.org/styles/dark')
      .then(response => {
        if (!response.ok) throw new Error('OpenFreeMap style unavailable');
        return response.json();
      })
      .then(style => ({
        version: 8,
        glyphs: style.glyphs,
        sources: { openmaptiles: style.sources.openmaptiles },
        layers: style.layers.filter(layer => layer.type === 'symbol' && layer['source-layer'] === 'place')
          .map(layer => {
            const layout = Object.fromEntries(Object.entries(layer.layout ?? {})
              .filter(([name]) => !name.startsWith('icon-')));
            return { ...layer, layout, paint: {
              'text-color': '#fff',
              'text-halo-color': '#172238',
              'text-halo-width': 1.5
            } };
          })
      }))
      .catch(error => { placeStyle = undefined; throw error; });
    return placeStyle;
  }
</script>

<script>
  import { onMount } from 'svelte';
  import { Map } from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';

  let { center, zoom, width, height } = $props();
  let container;
  let map = $state.raw(null);

  onMount(() => {
    let disposed = false;
    loadPlaceStyle().then(style => {
      if (disposed) return;
      map = new Map({
        container, style, center, zoom, interactive: false, attributionControl: false,
        renderWorldCopies: false, fadeDuration: 0
      });
    }).catch(() => { /* Relief remains visible when the labels are unavailable. */ });
    return () => {
      disposed = true;
      map?.remove();
    };
  });

  $effect(() => {
    if (map && width && height) {
      map.resize();
      map.jumpTo({ center, zoom });
    }
  });
</script>

<div class="place-labels" bind:this={container} aria-hidden="true"></div>

<style>
  .place-labels { position: absolute; inset: 0; pointer-events: none; }
</style>
