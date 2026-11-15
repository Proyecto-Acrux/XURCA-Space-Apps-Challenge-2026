<script>
  import { ChartNoAxesCombined } from '@lucide/svelte';
  import ChartView from './ChartView.svelte';
  import { catalog } from '$lib/services/sources.js';
  import { translate } from '$lib/services/i18n.js';

  import { workspace } from '$lib/stores/workspace.js';

  let resolution = $derived($workspace.visual.chartResolution ?? 'auto');
  let { series } = $props();

  function location(item, t) {
    const value = item.location ?? item.coordinates.join(', ') + ' (lon, lat)';
    return value.replace(/^(Estación|Tramo de río|Lago|Punto) /, (_, kind) => t(kind) + ' ')
      .replace(' · celda ', ' · ' + t('Celda').toLocaleLowerCase() + ' ');
  }
</script>

<section class="results-panel">
  <header class="panel-heading"><span><ChartNoAxesCombined size={16}/> {$translate('Resultados')}</span>
  </header>
  <div class="results-scroll">
    {#each series as item (item.id)}
      {@const available = item.points.filter(point => point.value !== null).length}
      {@const label = $translate(catalog.find(source => source.id === item.id)?.label ?? item.label ?? item.variable)}
      {@const period = item.cadence === 'daily' ? 'días con datos' : item.cadence && item.cadence !== 'monthly' ? 'observaciones con datos' : 'meses con datos'}
      <article class="chart-card" data-series-id={item.id}>
        <header><strong>{label}</strong></header>
        <p class="quiet">{item.provider} · {$translate(item.unit)} · {location(item, $translate)}</p>
        {#if item.message}<p>{item.message}</p>{/if}
        {#if item.downloadPath}<p class="quiet"><code>{item.downloadPath}</code></p>{/if}
        {#if !item.message}<p class="quiet">{available} {$translate('de')} {item.points.length} {$translate(period)}</p>{/if}
        {#if available}
          <ChartView series={item} {label} {resolution}/>
        {:else if !item.message}
          <p>{$translate('No hay valores para el período seleccionado.')}</p>
        {/if}
        {#if item.product}<p class="quiet">{item.product}</p>{/if}
        {#if item.summary?.validCount}
          <details>
            <summary>Resumen calculado sobre la serie completa</summary>
            <p>Promedio de observaciones: {item.summary.mean.toPrecision(5)} {item.unit} · mínimo: {item.summary.minimum.toPrecision(5)} · máximo: {item.summary.maximum.toPrecision(5)}</p>
            {#if item.summary.trend}
              <p>Tendencia lineal descriptiva: {item.summary.trend.perYear.toPrecision(4)} {item.unit}/año.</p>
            {/if}
            <p class="quiet">Sin ajuste estacional ni intervalo de confianza. No demuestra causalidad ni significancia estadística. El promedio corresponde a observaciones disponibles, no a un acumulado anual ni a un promedio regional.</p>
          </details>
        {/if}
        {#if item.url}<a href={item.url} target="_blank" rel="noreferrer">{$translate('Consulta original')}</a>{/if}
      </article>
    {:else}
      <p class="quiet">{$translate('Elegí un punto en el mapa y consultá la serie para ver los resultados.')}</p>
    {/each}
  </div>
</section>
