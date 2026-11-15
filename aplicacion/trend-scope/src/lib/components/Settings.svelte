<script>
  import { pyInvoke } from 'tauri-plugin-pytauri-api';
  import { isTauri } from '@tauri-apps/api/core';
  import { translate } from '$lib/services/i18n.js';
  import { SlidersHorizontal, ChevronDown, Plus, X, Database, CalendarDays, MapPin, Pencil, FlaskConical } from '@lucide/svelte';
  import { workspace, editData } from '$lib/stores/workspace.js';
  import PlaceSearch from './PlaceSearch.svelte';
  import { catalog, providers, sourceConfig, customSource, geographicEntityRoutes, entityGeometries } from '$lib/services/sources.js';
  import { coordinateLabel } from '$lib/services/geography.js';

  const cdsAreaProducts = new Set(['reanalysis-era5-single-levels', 'reanalysis-era5-pressure-levels', 'reanalysis-era5-land']);
  let { openCoordinates } = $props();
  let data = $derived($workspace.data);
  let provider = $state('nasa.power.monthly');
  let sourceChoice = $state('');
  let route = $derived(providers.find(item => item.id === provider));
  let customAllowed = $derived(!['openmeteo.archive.daily', 'noaa.cpc.oni', 'usgs.earthquakes', 'argentina.ina.series', 'psmsl.rlr.monthly'].includes(provider));
  let product = $state('');
  let products = $state([]);
  let layers = $state([]);
  let inaVariables = $state([]);
  let catalogError = $state('');
  let loadingCatalog = $state(false);
  let catalogRequest = 0;

  async function loadAppEEARSCatalog(productId = null) {
    if (!isTauri()) return;
    const request = ++catalogRequest;
    catalogError = '';
    loadingCatalog = true;
    try {
      const items = await pyInvoke('list_appeears', { product: productId });
      if (request !== catalogRequest) return;
      if (productId) layers = items;
      else products = items;
    } catch (error) {
      if (request === catalogRequest) catalogError = String(error.message ?? error);
    } finally {
      if (request === catalogRequest) loadingCatalog = false;
    }
  }

  async function loadInaCatalog() {
    if (!isTauri() || inaVariables.length) return;
    const request = ++catalogRequest;
    loadingCatalog = true;
    try {
      const items = await pyInvoke('list_ina_variables', {});
      if (request === catalogRequest) inaVariables = items;
    } catch (error) {
      if (request === catalogRequest) catalogError = String(error.message ?? error);
    } finally {
      if (request === catalogRequest) loadingCatalog = false;
    }
  }

  function changeProvider() {
    catalogRequest++;
    loadingCatalog = false;
    catalogError = '';
    sourceChoice = '';
    const selected = providers.find(item => item.id === provider);
    code = selected?.defaultCode ?? '';
    product = provider === 'nasa.firms.area' ? 'VIIRS_SNPP_SP' : selected?.defaultProduct ?? '';
    layers = [];
    if (provider === 'nasa.appeears') void loadAppEEARSCatalog();
    if (provider === 'argentina.ina.series') void loadInaCatalog();
  }
  let availableVariables = $derived.by(() => {
    const presets = catalog.filter(item => item.route.id === provider);
    const extra = provider === 'argentina.ina.series' ? inaVariables
      .filter(item => !presets.some(preset => preset.code === item.id))
      .map(item => ({ ...item, code: item.id, id: provider + ':' + item.id, dynamic: true })) : [];
    return [...presets, ...extra].filter(item => !data.sources.some(selected => selected.id === item.id));
  });
  let source = $derived(
    sourceChoice === 'custom' && customAllowed ? 'custom'
      : availableVariables.some(item => item.id === sourceChoice) ? sourceChoice
      : availableVariables[0]?.id ?? (customAllowed ? 'custom' : '')
  );
  let code = $state('');
  let featureType = $state('Reach');
  let sections = $state({ sources:true, time:true, methods:true });
  function addSource() {
    const codeValue = ['nasa.appeears', 'microsoft.planetary.stac'].includes(provider) ? code.trim()
      : ['nasa.power.monthly', 'noaa.ncei.station', 'noaa.ncei.daily'].includes(provider) ? code.trim().toUpperCase()
      : code.trim().toLowerCase();
    const cdsRequest = provider === 'copernicus.cds' && !cdsAreaProducts.has(product.trim());
    const type = provider === 'nasa.swot.hydrocron' ? featureType : null;
    const known = catalog.find(item => item.route.id === provider && item.code === codeValue && (item.featureType ?? null) === type);
    const selected = availableVariables.find(item => item.id === source);
    const entry = selected?.dynamic ? { ...customSource(provider, selected.code), variable: selected.label }
      : source !== 'custom' ? sourceConfig(source)
      : known ? sourceConfig(known.id) : customSource(provider, cdsRequest ? 'all' : codeValue, type, product.trim());
    if (!data.sources.some(item => item.id === entry.id)) editData(next => next.sources.push(entry));
    sourceChoice = '';
    code = route?.defaultCode ?? '';
  }
  const set = (group, key, value) => editData(next => next[group][key] = value);
  const toggle = id => sections[id] = !sections[id];
</script>

{#snippet group(id, label, icon, contents)}
  {@const Icon = icon}
  <section class="setting-group">
    <button class="section-toggle" onclick={() => toggle(id)} aria-expanded={!!sections[id]}><Icon size={15}/><span>{$translate(label)}</span><ChevronDown class={sections[id] ? '' : 'closed'} size={14}/></button>
    {#if sections[id]}<div class="section-content">{@render contents()}</div>{/if}
  </section>
{/snippet}

<section class="settings-panel">
  <header class="panel-heading"><span><SlidersHorizontal size={16}/> {$translate("Configuración")}</span></header>
  <div class="settings-scroll">
    {@render group('objective','Investigación',FlaskConical,objective)}
    {@render group('sources','Fuentes de información',Database,sources)}
    {@render group('time','Período de análisis',CalendarDays,time)}
    {@render group('geography','Configuración geográfica',MapPin,geography)}
  </div>
</section>

{#snippet objective()}
  <label>{$translate("Nombre del proyecto")}<input value={data.title} oninput={event => editData(next => next.title = event.currentTarget.value)}/></label>
  <label>{$translate("Objetivo")}<textarea value={data.objective} oninput={event => editData(next => next.objective = event.currentTarget.value)}></textarea></label>
  <label>{$translate("Descripción")}<textarea value={data.description} oninput={event => editData(next => next.description = event.currentTarget.value)}></textarea></label>
{/snippet}

{#snippet sources()}
  {#each data.sources as item (item.id)}
    {@const entry = catalog.find(source => source.id === item.id)}
    {@const selectedRoute = providers.find(route => route.id === item.access)}
    {@const resolvesEntity = geographicEntityRoutes.has(item.access)}
    {@const geometryTypes = resolvesEntity ? entityGeometries : selectedRoute?.geometry ?? ['Point']}
    <div class="selected-item"><div><strong>{$translate(entry?.label ?? item.variable)}</strong><small>{item.product}</small></div>
    <button class="icon-button" aria-label={$translate('Quitar') + ' ' + $translate(entry?.label ?? item.variable)} onclick={() => editData(next => next.sources = next.sources.filter(source => source.id !== item.id))}><X size={14}/></button></div>
    {#if resolvesEntity || (selectedRoute?.geometry && !(item.access === 'copernicus.cds' && !cdsAreaProducts.has(item.upstream.productId))) || ['nasa.power.monthly', 'openmeteo.archive.daily'].includes(item.access)}
      {#if resolvesEntity}<small>{$translate('Identificador automático según la selección y las fechas.')}</small>{/if}
      <label>{$translate(geometryTypes.some(type => type !== 'Point') ? 'Geometría de consulta' : 'Punto de consulta')}
        <select value={item.upstream.geometryId ?? ''} onchange={event => editData(next => {
          next.sources.find(source => source.id === item.id).upstream.geometryId = event.currentTarget.value || null;
        })}>
          <option value="">{$translate("Usar la única selección compatible")}</option>
          {#each data.geography.selection.features.filter(feature => geometryTypes.includes(feature.geometry.type)) as feature (feature.id)}
            <option value={feature.id}>{$translate(feature.properties.name || (feature.geometry.type === 'Point' ? coordinateLabel(feature.geometry.coordinates) : feature.id))}</option>
          {/each}
        </select>
      </label>
    {/if}
    {#if item.access === 'copernicus.cds' && !cdsAreaProducts.has(item.upstream.productId)}
      <label>{$translate('Solicitud JSON de CDS, con fechas y filtros')}
        <textarea value={item.upstream.selectors.requestJson ?? ''} spellcheck="false"
          oninput={event => editData(next => {
            next.sources.find(source => source.id === item.id).upstream.selectors.requestJson = event.currentTarget.value;
          })}></textarea>
      </label>
    {/if}
    {#if item.access === 'copernicus.cds' && item.upstream.productId === 'reanalysis-era5-pressure-levels'}
      <label>{$translate('Niveles de presión en hPa')}
        <input placeholder="1000,925,850,700,500,300,250,200" value={item.upstream.selectors.pressureLevels ?? ''}
          oninput={event => editData(next => {
            next.sources.find(source => source.id === item.id).upstream.selectors.pressureLevels = event.currentTarget.value;
          })}/>
      </label>
    {/if}
    {#if item.access === 'usgs.earthquakes'}
      <label>{$translate('Magnitud mínima opcional')}
        <input type="number" step="any" value={item.upstream.selectors.minMagnitude ?? ''}
          oninput={event => editData(next => {
            next.sources.find(source => source.id === item.id).upstream.selectors.minMagnitude = event.currentTarget.value;
          })}/>
      </label>
    {/if}
  {/each}
  <label>{$translate('Fuente de datos')}
    <select bind:value={provider} onchange={changeProvider}>
      {#each providers as entry}<option value={entry.id}>{entry.label}</option>{/each}
    </select>
  </label>
  <small>{$translate(providers.find(entry => entry.id === provider)?.hint)}</small>
  {@const usesCdsRequest = provider === 'copernicus.cds' && !cdsAreaProducts.has(product.trim())}
  {@const validCode = usesCdsRequest || /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,159}$/.test(code.trim())}
  <div class="input-row">
    <select aria-label={$translate("Variable para agregar")} value={source} onchange={event => sourceChoice = event.currentTarget.value} disabled={!source}>
      {#if !source}<option disabled>{$translate("Sin variables disponibles")}</option>{/if}
      {#if customAllowed}<option value="custom">{$translate("Ingresar código oficial…")}</option>{/if}
      {#each availableVariables as item}
        <option value={item.id}>{$translate(item.label)}</option>
      {/each}
    </select>
    <button class="icon-button outlined" aria-label={$translate("Agregar variable")} disabled={!source || (source === 'custom' && (!validCode || (route?.product && !product.trim())))} onclick={addSource}><Plus size={16}/></button>
  </div>
  {#if provider === 'argentina.ina.series' && catalogError}<small>{catalogError}</small>{/if}
  {#if source === 'custom'}
    {#if route?.product}
      <label>{$translate(route.product)}
        <input bind:value={product} list={provider === 'nasa.appeears' ? 'appeears-products' : undefined}
          oninput={() => { catalogRequest++; loadingCatalog = false; catalogError = ''; layers = []; }}/>
      </label>
    {/if}
    {#if provider === 'nasa.appeears'}
      <datalist id="appeears-products">
        {#each products as item (item.id)}<option value={item.id}>{item.label}</option>{/each}
      </datalist>
      <button class="outlined" disabled={!product.trim() || loadingCatalog} onclick={() => loadAppEEARSCatalog(product.trim())}>
        {$translate("Buscar capas")}
      </button>
      {#if layers.length}
        <label>{$translate("Capas disponibles")}
          <select value={code} onchange={event => code = event.currentTarget.value}>
            <option value="">{$translate("Elegir capa")}</option>
            {#each layers as item (item.id)}<option value={item.id}>{item.id} · {item.label}</option>{/each}
          </select>
        </label>
      {/if}
      {#if catalogError}<small>{catalogError}</small>{/if}
    {/if}
    {#if !usesCdsRequest}
      <label>{$translate(route?.codeLabel ?? "Código oficial de variable")}<input bind:value={code} readonly={provider === 'nasa.earthdata'}/></label>
    {/if}
    {#if provider === 'nasa.swot.hydrocron'}
      <label>{$translate("Entidad SWOT")}<select bind:value={featureType}>
        <option value="Reach">{$translate("Tramo de río")}</option>
        <option value="PriorLake">{$translate("Lago")}</option>
      </select></label>
    {/if}
  {/if}
{/snippet}

{#snippet time()}
  <div class="field-pair">
    <label>{$translate("Desde")}<input type="date" value={data.time.start} oninput={event => set('time','start',event.currentTarget.value)}/></label>
    <label>{$translate("Hasta")}<input type="date" value={data.time.end} oninput={event => set('time','end',event.currentTarget.value)}/></label>
  </div>
  <small>{$translate("La frecuencia y la cobertura dependen del producto seleccionado.")}</small>
{/snippet}

{#snippet geography()}
  <PlaceSearch/>
  {#each data.geography.selection.features as item (item.id)}
    <div class="selected-item"><div><strong>{$translate(item.properties.name || coordinateLabel(item.geometry.coordinates))}</strong>
      <small>{item.geometry.type === 'Point' ? $translate('Punto WGS 84') : (item.geometry.coordinates[0].length - 1) + ' ' + $translate('vértices')}</small>
    </div><button class="icon-button" aria-label={$translate("Editar coordenadas")} onclick={() => openCoordinates(item)}><Pencil size={14}/></button><button class="icon-button" aria-label={$translate("Eliminar selección")} onclick={() => editData(next => next.geography.selection.features = next.geography.selection.features.filter(feature => feature.id !== item.id))}><X size={14}/></button></div>
  {/each}
  <button class="outlined" onclick={() => openCoordinates()}><MapPin size={14}/> {$translate("Ingresar coordenadas")}</button>
{/snippet}

{#snippet options(label,value,items,change)}
  <label>{$translate(label)}<select {value} onchange={event => change(event.currentTarget.value)}>{#each items as item}<option value={item.id ?? item}>{item.label ?? item}</option>{/each}</select></label>
{/snippet}
