<script>
  import { translate } from '$lib/services/i18n.js';
  import { Search } from '@lucide/svelte';
  import { pyInvoke } from 'tauri-plugin-pytauri-api';
  import { selectGeometry, editVisual, workspace } from '$lib/stores/workspace.js';

  let { scope = '' } = $props();
  let query = $state('');
  let kind = $state('');
  let effectiveKind = $derived(scope === 'area'
    ? (kind === 'provincias' ? kind : 'localidades-censales')
    : kind === 'provincias' || (scope === 'both' && kind === 'localidades-censales') ? kind : 'localidades');
  let resultKind = $state('');
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
      const current = effectiveKind;
      const results = JSON.parse(await pyInvoke('search_places', { query, kind: current, language: $workspace.visual.language }));
      if (effectiveKind !== current) return;
      places = results;
      resultKind = current;
      if (!places.length) message = 'No se encontraron coincidencias.';
    } catch (error) {
      message = String(error.message ?? error);
    } finally {
      busy = false;
    }
  }

  async function select(place) {
    if (busy) return;
    const label = [...new Set([place.name, place.province, place.country].filter(Boolean))].join(' · ');
    const [longitude, latitude] = place.coordinates;
    const regional = effectiveKind !== 'localidades' && (scope === 'area' || scope === 'both');
    if (regional) {
      const current = effectiveKind;
      const currentScope = scope;
      busy = true;
      message = '';
      try {
        const geometry = await pyInvoke('load_place_boundary', { kind: current, id: place.id });
        if (effectiveKind !== current || scope !== currentScope) return;
        selectGeometry(geometry.type, geometry.coordinates, label);
      } catch (error) {
        message = String(error.message ?? error);
        return;
      } finally { busy = false; }
    } else if (!$workspace.data.geography.selection.features.some(item =>
      item.geometry.type === 'Point' && item.geometry.coordinates[0] === longitude && item.geometry.coordinates[1] === latitude
    )) selectGeometry('Point', [longitude, latitude], label);
    editVisual(visual => {
      visual.map.camera = { longitude, latitude, zoom: regional && effectiveKind === 'provincias' ? 4 : 7 };
      visual.map.layers.selection = true;
    });
    places = [];
    message = label + ' · ' + $translate(regional ? 'límite seleccionado' : 'centroide seleccionado');
  }
</script>

<form class="place-search" onsubmit={search}>
  <label>{$translate('Buscar lugar')}
    <input bind:value={query} placeholder={$translate("Ciudad o provincia")} minlength="2" maxlength="100" required/>
  </label>
  <div class="input-row">
    <select aria-label={$translate("Tipo de lugar")} value={effectiveKind} onchange={event => { kind = event.currentTarget.value; message = ''; }}>
      {#if scope !== 'area'}<option value="localidades">{$translate("Ciudad")}</option>{/if}
      {#if scope === 'area' || scope === 'both'}
        <option value="localidades-censales">{$translate("Ciudad o localidad censal (Argentina)")}</option>
      {/if}
      <option value="provincias">{$translate("Provincia (Argentina)") }</option>
    </select>
    <button class="outlined icon-button" aria-label={$translate("Buscar lugar")} disabled={busy}><Search size={16}/></button>
  </div>
  {#if resultKind === effectiveKind}
    {#each places as place (place.id)}
      <button type="button" class="outlined" disabled={busy} onclick={() => select(place)}>{[...new Set([place.name, place.province, place.country].filter(Boolean))].join(' · ')}</button>
    {/each}
  {/if}
  <small>{effectiveKind === 'localidades' ? 'Photon · © OpenStreetMap' : 'Georef Argentina'}</small>
  {#if message}<small role="status">{$translate(message)}</small>{/if}
</form>
