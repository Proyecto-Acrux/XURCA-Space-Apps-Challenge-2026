<script>
  import { chartCadences, chartResolutions } from '$lib/services/charts.js';
  import { saveChartImage } from '$lib/services/chartExport.js';
  import { catalog } from '$lib/services/sources.js';
  import { translate } from '$lib/services/i18n.js';
  import { onMount, tick } from 'svelte';
  import { Earth, Aperture, Bot, ChartNoAxesCombined, ChevronDown, CircleHelp, Crosshair, Hand, MapPin, Play, Scan, Hexagon, Settings, Settings2, Trash2, X, Save, FolderOpen } from '@lucide/svelte';
  import WorldMap from '$lib/components/WorldMap.svelte';
  import Globe from '$lib/components/Globe.svelte';
  import SettingsPanel from '$lib/components/Settings.svelte';
  import Results from '$lib/components/Results.svelte';
  import Assistant from '$lib/components/Assistant.svelte';
  import ResizeHandle from '$lib/components/ResizeHandle.svelte';
  import { workspace, defaults, editData, editVisual, selectGeometry } from '$lib/stores/workspace.js';
  import { loadWorkspace, saveWorkspace, downloadJson } from '$lib/services/configuration.js';
  import { acquireData, prepareInvestigation } from '$lib/services/acquisition.js';
  import { coordinateLabel, closedRegion, openPolygonNotice, validCoordinates } from '$lib/services/geography.js';
  import '$lib/styles/dashboard.css';

  let detailedMap = $state(true);
  $effect(() => { document.documentElement.lang = $workspace.visual.language === 'en' ? 'en' : 'es'; });
  let tool = $state('pan');
  let vertices = $state([]);
  let cursor = $state(null);
  let notice = $state('');
  let menu = $state('');
  let dialog;
  let modal = $state('');
  let latitude = $state('');
  let longitude = $state('');
  let polygonInput = $state('');
  let selectionName = $state('');
  let editingFeature = $state(null);
  let coordinateMode = $state('point');
  let modalError = $state('');
  let running = $state(false);
  let settingsOpen = $state(false);
  let acquisitionError = $state(null);
  let result = $state(null);
  let chartId = $state(null);
  let savedConfig = $state('');
  let storageBusy = $state(true);
  let panels = $derived($workspace.visual.workspace);
  let mapVisible = $derived(panels.map !== false);
  let assistantVisible = $derived(panels.assistantVisible !== false);
  let currentSeries = $derived(result?.key === configKey ? result.series : []);
  let activeChart = $derived(currentSeries.find(item => item.id === chartId));
  let exportableSeries = $derived(currentSeries.filter(item => item.points.some(point => point.value !== null)));
  let exportId = $state('');
  let exporting = $state(false);
  let dirty = $derived(JSON.stringify($workspace) !== savedConfig);
  let configKey = $derived(JSON.stringify($workspace.data));
  let savedAccent = $derived($workspace.visual.appearance.accent);
  let customAccent = $derived(savedAccent?.toLowerCase() === '#57dfc1' ? null : savedAccent);
  let resultStatus = $derived(running ? 'Procesando…' : result?.key === configKey ? 'Consulta completada' : result ? 'Configuración modificada' : 'Sin resultados');
  let selected = $derived($workspace.data.geography.selection.features.at(-1));
  const tools = [
    ['pan','Desplazar globo',Hand], ['point','Seleccionar punto',MapPin],
    ['rectangle','Selección rectangular',Scan], ['polygon','Selección poligonal',Hexagon]
  ];

  onMount(async () => {
    try {
      const saved = await loadWorkspace();
      if (saved) workspace.set({ ...defaults(), ...Object.fromEntries(Object.entries(saved).filter(([, value]) => value != null)) });
      savedConfig = JSON.stringify($workspace);
    } catch (error) {
      notify($translate('No se pudo recuperar la configuración.') + ' ' + $translate(String(error.message ?? error)));
    } finally { storageBusy = false; }
  });

  function notify(text) { notice = text; }
  function togglePanel(id, value = panels[id] === false) {
    chartId = null;
    editVisual(visual => visual.workspace[id] = value);
    if (id === 'map' && !value) cursor = null;
  }

  function toggleCharts() {
    chartId = activeChart ? null : currentSeries[0]?.id ?? null;
  }

  async function openChartExport() {
    if (!exportableSeries.length) {
      notify('Consultá datos antes de exportar una gráfica.');
      return;
    }
    exportId = exportableSeries.find(item => item.id === chartId)?.id ?? exportableSeries[0].id;
    await showDialog('chart-export');
  }

  async function exportChart(event) {
    event.preventDefault();
    if (exporting) return;
    chartId = exportId;
    await tick();
    const card = [...document.querySelectorAll('[data-series-id]')].find(item => item.dataset.seriesId === exportId);
    const canvas = card?.querySelector('canvas');
    if (!canvas) { modalError = 'La gráfica ya no está disponible.'; return; }
    modalError = '';
    exporting = true;
    try {
      if (await saveChartImage(canvas, exportId.replace(/[^a-z0-9_-]/gi, '-') + '.png', $workspace.visual.theme === 'light')) {
        dialog.close();
        notify('Gráfica guardada.');
      }
    } catch {
      modalError = 'No se pudo guardar la gráfica.';
    } finally {
      exporting = false;
    }
  }
  function chooseTool(id) { tool = id; vertices = []; if (notice === openPolygonNotice) notice = ''; }
  function clearSelection() { vertices = []; if (notice === openPolygonNotice) notice = ''; editData(data => data.geography.selection.features = []); }
  async function run({ showChart = true } = {}) {
    if (running || storageBusy) return;
    let investigation;
    try {
      investigation = prepareInvestigation($workspace.data);
    } catch (error) {
      notify($translate(error.message));
      return;
    }
    const startedWith = configKey;
    running = true;
    acquisitionError = null;
    result = null;
    chartId = null;
    notice = '';
    try {
      const acquired = await acquireData(investigation);
      const sources = new Map(investigation.sources.map(source => [source.id, source]));
      const features = new Map(investigation.geography.selection.features.map(feature => [feature.id, feature]));
      const series = acquired.map(item => {
        const source = sources.get(item.id);
        const feature = features.get(source?.upstream.geometryId);
        const name = feature?.properties?.name?.trim();
        const region = ['Polygon', 'MultiPolygon'].includes(feature?.geometry.type);
        const named = name && !['Polígono', 'Polígono manual', 'Rectángulo'].includes(name);
        const placeLabel = region
          ? named ? name + ' ' + $translate('y alrededores') : $translate('Área seleccionada')
          : name;
        return { ...item, placeLabel };
      });
      result = { key: startedWith, series };
      if (showChart && startedWith === configKey) chartId = series[0]?.id ?? null;
    } catch (error) {
      const message = String(error.message ?? error);
      acquisitionError = { key: startedWith, message };
      notify(message);
    } finally {
      running = false;
    }
  }
  async function save() {
    if (storageBusy) return;
    storageBusy = true;
    const snapshot = $workspace;
    try {
      await saveWorkspace(snapshot);
      savedConfig = JSON.stringify(snapshot);
      notify('Configuración guardada');
    } catch (error) {
      notify($translate('No se pudo guardar.') + ' ' + $translate(String(error.message ?? error)));
    } finally { storageBusy = false; }
  }
  async function restore() {
    if (storageBusy) return;
    storageBusy = true;
    try {
      const saved = await loadWorkspace();
      if (!saved) { notify('Todavía no hay una configuración guardada.'); return; }
      workspace.set({ ...defaults(), ...Object.fromEntries(Object.entries(saved).filter(([, value]) => value != null)) });
      savedConfig = JSON.stringify($workspace);
      notify('Configuración recuperada');
    } catch (error) {
      notify($translate('No se pudo recuperar.') + ' ' + $translate(String(error.message ?? error)));
    } finally { storageBusy = false; }
  }
  async function showDialog(id) {
    menu = '';
    modal = id;
    modalError = '';
    await tick();
    dialog.showModal();
  }
  function openCoordinates(feature = null) {
    editingFeature = feature;
    selectionName = feature?.properties?.name ?? '';
    coordinateMode = feature?.geometry.type === 'Polygon' ? 'polygon' : 'point';
    longitude = feature?.geometry.type === 'Point' ? String(feature.geometry.coordinates[0]) : '';
    latitude = feature?.geometry.type === 'Point' ? String(feature.geometry.coordinates[1]) : '';
    polygonInput = feature?.geometry.type === 'Polygon'
      ? feature.geometry.coordinates[0].slice(0, -1).map(point => point.join(', ')).join('\n')
      : '';
    return showDialog('coordinates');
  }

  function saveSelection(type, coordinates, name) {
    if (!editingFeature) {
      selectGeometry(type, coordinates, name);
      return;
    }
    editData(data => {
      const feature = data.geography.selection.features.find(item => item.id === editingFeature.id);
      if (feature) {
        feature.geometry = { type, coordinates };
        feature.properties.name = name;
      }
    });
  }

  function submitCoordinates(event) {
    event.preventDefault();
    let center;
    if (coordinateMode === 'point') {
      center = [Number(longitude), Number(latitude)];
      if (longitude === '' || latitude === '' || !validCoordinates(...center)) {
        modalError = 'Ingresá longitud entre −180 y 180 y latitud entre −90 y 90.';
        return;
      }
      saveSelection('Point', center, selectionName.trim());
    } else {
      const points = polygonInput.trim().split(/\r?\n/).map(line => line.trim().split(/[ ,]+/).map(Number));
      if (points.some(point => point.length !== 2 || !validCoordinates(...point))) {
        modalError = 'Ingresá un par longitud, latitud por línea.';
        return;
      }
      const ring = closedRegion(points);
      if (!ring) { modalError = 'Ingresá al menos tres vértices que delimiten un área.'; return; }
      saveSelection('Polygon', ring, selectionName.trim());
      center = points[0];
    }
    editVisual(visual => {
      visual.map.camera.longitude = center[0];
      visual.map.camera.latitude = center[1];
      visual.map.layers.selection = true;
    });
    dialog.close();
    notify('Selección geográfica actualizada');
  }
  async function menuAction(action) { menu = ''; await action(); }
  const menus = [
    ['Proyecto', [['Guardar configuración',save],['Recuperar configuración',() => dirty ? showDialog('restore') : restore()]]],
    ['Datos', [['Ingresar coordenadas',() => openCoordinates()]]],
    ['Análisis', [['Procesar',run],['Mostrar resultados',() => chartId = currentSeries[0]?.id ?? null]]],
    ['Visualización', [['Resolución gráfica',() => showDialog('chart-resolution')],['Alternar asistente',() => togglePanel('assistantVisible', !assistantVisible)]]],
    ['Capas', [
      ['Alternar fronteras', () => editVisual(visual => visual.map.layers.countries = !visual.map.layers.countries)],
      ['Alternar selecciones', () => editVisual(visual => visual.map.layers.selection = !visual.map.layers.selection)]
    ]],
    ['Exportar', [['Guardar gráfica…',openChartExport],['Descargar cfg_data.json',() => downloadJson('cfg_data.json',$workspace.data)],['Descargar cfg_visual.json',() => downloadJson('cfg_visual.json',$workspace.visual)]]]
  ];
</script>

<svelte:head><title>Earth Detective</title><meta name="description" content={$translate("Espacio de trabajo para explorar tendencias del sistema terrestre.")}/></svelte:head>
<svelte:window onkeydown={event => {
  if (tool === 'polygon' && vertices.length && !dialog?.open &&
      ['Enter', 'Escape'].includes(event.key) && !event.target?.closest?.('input, textarea, select, button, [contenteditable]')) {
    event.preventDefault();
    notify(openPolygonNotice);
  }
  if (event.key === 'Escape') menu = '';
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); save(); }
}}/>

<div class="app-shell" class:light={$workspace.visual.theme === 'light'} style:--custom-accent={customAccent} style:--base-size={$workspace.visual.appearance.fontSize + 'px'}>
  <header class="topbar">
    <div class="identity"><span class="brand-mark"><Aperture size={24} strokeWidth={1.7}/></span><strong>Earth Detective</strong></div>
    <nav aria-label={$translate("Menú principal")}>
      {#each menus as [name,actions]}
        <div class="menu-anchor">
          <button class:active={menu === name} aria-expanded={menu === name} onclick={() => menu = menu === name ? '' : name}>{$translate(name)}<ChevronDown size={12}/></button>
          {#if menu === name}<div class="dropdown">{#each actions as [label,action]}<button disabled={label === 'Mostrar resultados' && !currentSeries.length} onclick={() => menuAction(action)}>{$translate(label)}</button>{/each}</div>{/if}
        </div>
      {/each}
    </nav>
    <button class="icon-button top-icon" aria-label={$translate("Preferencias")} title={$translate("Preferencias")} onclick={() => showDialog('preferences')}><Settings2 size={17}/></button>
  </header>

  <div class="toolbar" aria-label={$translate("Herramientas")}>
    <div class="geo-tools">
      {#each tools as [id,label,Icon]}
        <button class="tool-button" class:active={id === tool} aria-pressed={id === tool} title={$translate(label)} aria-label={$translate(label)} onclick={() => chooseTool(id)}><Icon size={17}/></button>
      {/each}
      <button class="tool-button" title={$translate("Ingresar coordenadas")} aria-label={$translate("Ingresar coordenadas")} onclick={() => openCoordinates()}><Crosshair size={17}/></button>
      <button class="tool-button" title={$translate("Limpiar selecciones")} aria-label={$translate("Limpiar selecciones")} onclick={clearSelection}><Trash2 size={16}/></button>
    </div>
    <div class="panel-buttons">
      <button class="tool-button" class:active={mapVisible} aria-pressed={mapVisible}
        title={$translate('Alternar mapa')} aria-label={$translate('Alternar mapa')}
        onclick={() => togglePanel('map', !mapVisible)}><Earth size={17}/></button>
      <button class="tool-button" class:active={settingsOpen} aria-pressed={settingsOpen} title={$translate("Configuración")} aria-label={$translate("Alternar panel de configuración")} onclick={() => { chartId = null; settingsOpen = !settingsOpen; }}><Settings size={17}/></button>
      <button class="tool-button" class:active={!!activeChart} aria-pressed={!!activeChart} disabled={!currentSeries.length} title={$translate("Gráficas")} aria-label={$translate("Alternar gráficas")} onclick={toggleCharts}><ChartNoAxesCombined size={17}/></button>
      <button class="tool-button" class:active={assistantVisible} aria-pressed={assistantVisible} title={$translate("Asistente de IA")} aria-label={$translate("Alternar asistente")} onclick={() => togglePanel('assistantVisible', !assistantVisible)}><Bot size={17}/></button>
    </div>
    <div class="view-tabs" role="group" aria-label={$translate('Vistas de la consulta')}>
      <button class:active={!activeChart} aria-pressed={!activeChart} onclick={() => chartId = null}>{$translate('Espacio de trabajo')}</button>
      {#each currentSeries as item (item.id)}
        {@const label = $translate(catalog.find(source => source.id === item.id.split('::')[0])?.label ?? item.label ?? item.variable)}
        <button class:active={activeChart?.id === item.id} aria-pressed={activeChart?.id === item.id} title={item.placeLabel ? item.placeLabel + ' · ' + label : label} onclick={() => chartId = item.id}><span>{item.placeLabel ?? label}{item.placeLabel && currentSeries.some(other => other.id !== item.id && other.placeLabel === item.placeLabel) ? ' · ' + label : ''}</span></button>
      {/each}
    </div>
    <div class="run-actions">
      <button class="primary run" onclick={run} disabled={running}><Play size={15} fill="currentColor"/> {$translate(running ? 'Procesando…' : 'Procesar')}</button>
    </div>
  </div>

  <main class="view-content">
  <div class="desktop workspace-view" hidden={!!activeChart}
    style:--settings-width={panels.settingsWidth + 'px'} style:--assistant-width={(panels.assistantWidth ?? 330) + 'px'}>
    {#if settingsOpen}
      <SettingsPanel {openCoordinates}/>
      {#if mapVisible || assistantVisible}<ResizeHandle label={$translate("Ancho del panel de configuración")} value={panels.settingsWidth} min={220} max={450} resize={value => editVisual(visual => visual.workspace.settingsWidth = value)}/>{/if}
    {/if}
    {#if mapVisible && detailedMap}
      <WorldMap {tool} bind:vertices bind:cursor bind:notice fallback={() => detailedMap = false}/>
    {:else if mapVisible}
      <Globe {tool} bind:vertices bind:cursor bind:notice showDetail={() => detailedMap = true}/>
    {/if}
    {#if assistantVisible && mapVisible}<ResizeHandle label={$translate('Ancho del asistente')} value={panels.assistantWidth ?? 388} min={265} max={600} direction={-1} resize={value => editVisual(visual => visual.workspace.assistantWidth = value)}/>{/if}
    <aside class="assistant-panel" hidden={!assistantVisible}>
      <header class="panel-heading"><span><Bot size={16}/> {$translate('Asistente de IA')}</span></header>
      <Assistant series={currentSeries} {running} {storageBusy}
        acquisitionError={acquisitionError?.key === configKey ? acquisitionError.message : ''}
        onprocess={() => run({ showChart: false })} onresults={() => chartId = currentSeries[0]?.id ?? null}/>
    </aside>
  </div>
  {#if activeChart}
    <div class="chart-workspace"><Results series={[activeChart]}/></div>
  {/if}
  </main>

  <footer class="statusbar">
    <span class="status-coordinates"><Crosshair size={12}/> {cursor ? coordinateLabel(cursor) : selected?.geometry.type === 'Point' ? coordinateLabel(selected.geometry.coordinates) : $translate(selected?.properties.name || 'Sin selección')}</span>
    <span>{$workspace.data.sources.length} {$translate('variables')}</span>
    <button onclick={save} disabled={storageBusy} title={$translate("Guardar configuración (Ctrl+S)")}><Save size={13}/> {$translate(storageBusy ? 'Procesando' : dirty ? 'Sin guardar' : 'Guardado')}</button>
    <span class="status-results">{$translate(resultStatus)}</span>
  </footer>

  {#if notice}<div class="toast" role="status"><CircleHelp size={17}/><span>{$translate(notice)}</span><button aria-label={$translate("Cerrar aviso")} class="icon-button" onclick={() => notice = ''}><X size={15}/></button></div>{/if}

  <dialog bind:this={dialog} aria-labelledby="dialog-title">
    <header><strong id="dialog-title">{$translate(modal === 'coordinates' ? 'Coordenadas WGS 84' : modal === 'restore' ? 'Recuperar configuración' : modal === 'chart-resolution' ? 'Resolución gráfica' : modal === 'chart-export' ? 'Guardar gráfica…' : 'Preferencias')}</strong><button class="icon-button" aria-label={$translate("Cerrar")} onclick={() => dialog.close()}><X size={17}/></button></header>
    {#if modal === 'coordinates'}
      <form onsubmit={submitCoordinates}>
        <label>{$translate("Nombre del lugar")}<input maxlength="100" bind:value={selectionName}/></label>
        <label>{$translate("Geometría")}<select bind:value={coordinateMode}><option value="point">{$translate("Punto")}</option><option value="polygon">{$translate("Polígono")}</option></select></label>
        {#if coordinateMode === 'point'}
          <div class="field-pair"><label>{$translate("Longitud")}<input type="number" min="-180" max="180" step="any" value={longitude} oninput={event => longitude = event.currentTarget.value}/></label><label>{$translate("Latitud")}<input type="number" min="-90" max="90" step="any" value={latitude} oninput={event => latitude = event.currentTarget.value}/></label></div>
        {:else}
          <label>{$translate("Vértices (longitud, latitud)")}<textarea rows="5" bind:value={polygonInput} placeholder={'-67.1, -33.8\n-66.4, -33.8\n-66.7, -33.2'}></textarea></label>
        {/if}
        {#if modalError}<p role="alert">{$translate(modalError)}</p>{/if}
        <button class="primary"><MapPin size={16}/> {$translate(editingFeature ? 'Guardar selección' : 'Agregar selección')}</button>
      </form>
    {:else if modal === 'restore'}
      <form onsubmit={event => { event.preventDefault(); dialog.close(); restore(); }}>
        <p>{$translate("Se reemplazarán los cambios actuales con la última configuración guardada.")}</p>
        <button class="primary"><FolderOpen size={16}/> {$translate("Recuperar")}</button>
      </form>
    {:else if modal === 'chart-resolution'}
      <div class="preferences">
        <label>{$translate('Resolución gráfica')}
          <select value={$workspace.visual.chartResolution ?? 'auto'} onchange={event => editVisual(visual => visual.chartResolution = event.currentTarget.value)}>
            {#each chartResolutions as [id, label]}<option value={id}>{$translate(label)}</option>{/each}
          </select>
        </label>
        <label>{$translate('Frecuencia del gráfico')}
          <select value={$workspace.visual.chartCadence ?? 'native'} onchange={event => editVisual(visual => visual.chartCadence = event.currentTarget.value)}>
            {#each chartCadences as [id, label]}<option value={id}>{$translate(label)}</option>{/each}
          </select>
        </label>
        <small>{$translate('Las series diarias se pueden agrupar. Se muestran solo semanas o meses completos y se conserva la frecuencia de las demás fuentes.')}</small>
      </div>
    {:else if modal === 'chart-export'}
      <form onsubmit={exportChart}>
        <label>{$translate('Gráfica')}
          <select bind:value={exportId}>
            {#each exportableSeries as item (item.id)}
              <option value={item.id}>{$translate(catalog.find(source => source.id === item.id.split('::')[0])?.label ?? item.variable)}</option>
            {/each}
          </select>
        </label>
        {#if modalError}<p role="alert">{$translate(modalError)}</p>{/if}
        <button class="primary" disabled={exporting}>{$translate('Guardar como PNG…')}</button>
      </form>
    {:else}
      <div class="preferences">
        <label>{$translate('Idioma')}<select value={$workspace.visual.language} onchange={event => editVisual(visual => visual.language = event.currentTarget.value)}><option value="es">Español</option><option value="en">English</option></select></label>
        <label>{$translate("Tema")}<select value={$workspace.visual.theme} onchange={event => editVisual(visual => visual.theme = event.currentTarget.value)}><option value="dark">{$translate("Oscuro")}</option><option value="light">{$translate("Claro")}</option></select></label>
        <label>{$translate("Tamaño del texto")}<select value={$workspace.visual.appearance.fontSize} onchange={event => editVisual(visual => visual.appearance.fontSize = Number(event.currentTarget.value))}><option value="12">{$translate("Compacto")}</option><option value="13">{$translate("Normal")}</option><option value="15">{$translate("Grande")}</option></select></label>
        <label>{$translate("Color de acento")}<input type="color" value={customAccent ?? ($workspace.visual.theme === 'light' ? '#2563eb' : '#38bdf8')} oninput={event => editVisual(visual => visual.appearance.accent = event.currentTarget.value)}/></label>
      </div>
    {/if}
  </dialog>
</div>
