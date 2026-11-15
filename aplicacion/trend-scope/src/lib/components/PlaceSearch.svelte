<script>
  import { translate } from '$lib/services/i18n.js';
  import { Search } from '@lucide/svelte';
  import { pyInvoke } from 'tauri-plugin-pytauri-api';
  import { selectGeometry, editVisual, workspace } from '$lib/stores/workspace.js';

  let query = $state('');
  let kind = $state('localidades');
  let places = $state([]);
  let busy = $state(false);
  let message = $state('');

  async function search(event) {
    event.preventDefault();
    if (busy) return;
    busy = true;
    places = [];
    message = '';
    try {
      places = JSON.parse(await pyInvoke('search_places', { query, kind, language: $workspace.visual.language }));
      if (!places.length) message = 'No se encontraron coincidencias.';
    } catch (error) {
      message = String(error.message ?? error);
    } finally {
      busy = false;
    }
  }

  function select(place) {
    const label = [...new Set([place.name, place.province, place.country].filter(Boolean))].join(' · ');
    const [longitude, latitude] = place.coordinates;
    if (!$workspace.data.geography.selection.features.some(item =>
      item.geometry.type === 'Point' && item.geometry.coordinates[0] === longitude && item.geometry.coordinates[1] === latitude
    )) selectGeometry('Point', [longitude, latitude], label);
    editVisual(visual => {
      visual.map.camera = { longitude, latitude, zoom: 7 };
      visual.map.layers.selection = true;
    });
    places = [];
    message = label + ' · ' + $translate('centroide seleccionado');
  }
</script>

<form class="place-search" onsubmit={search}>
  <label>{$translate('Buscar lugar')}
    <input bind:value={query} placeholder={$translate("Ciudad o provincia")} minlength="2" maxlength="100" required/>
  </label>
  <div class="input-row">
    <select aria-label={$translate("Tipo de lugar")} bind:value={kind}>
      <option value="localidades">{$translate("Ciudad")}</option>
      <option value="provincias">{$translate("Provincia (Argentina)") }</option>
    </select>
    <button class="outlined icon-button" aria-label={$translate("Buscar lugar")} disabled={busy}><Search size={16}/></button>
  </div>
  {#each places as place (place.id)}
    <button type="button" class="outlined" onclick={() => select(place)}>{[...new Set([place.name, place.province, place.country].filter(Boolean))].join(' · ')}</button>
  {/each}
  <small>Photon · © OpenStreetMap</small>
  {#if message}<small role="status">{$translate(message)}</small>{/if}
</form>
