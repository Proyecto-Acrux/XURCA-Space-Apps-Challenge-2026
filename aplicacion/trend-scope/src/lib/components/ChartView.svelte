<script>
  import { Chart, registerables } from 'chart.js';
  import { Maximize } from '@lucide/svelte';
  import { chartCadence, chartSpec } from '$lib/services/charts.js';
  import { translate } from '$lib/services/i18n.js';
  import { workspace } from '$lib/stores/workspace.js';
  Chart.register(...registerables);
  let { series, label, resolution, cadence } = $props();
  let displayed = $derived(chartCadence(series, cadence));
  let hasValues = $derived(displayed.points.some(point => Number.isFinite(point.value)));
  let light = $derived($workspace.visual.theme === 'light');
  let width = $state(400);
  let canvas = $state();
  let windowStart = $state(0);
  let span = $state(null);
  const day = 86_400_000;
  let first = $derived(Date.parse(displayed.points[0]?.month));
  let last = $derived(Date.parse(displayed.points.at(-1)?.month));
  let duration = $derived(last - first);
  let minimumSpan = $derived(({ monthly: 31, weekly: 7 }[displayed.cadence] ?? 1) * day);
  let chartWindow = $derived(span != null ? { start: first + windowStart, end: first + windowStart + span } : undefined);
  let dragging = $state(false);
  let drag;

  function zoom(factor, anchor = 0.5) {
    const current = span ?? duration;
    const next = Math.round(Math.min(duration, Math.max(minimumSpan, current * factor)));
    if (current === next) return false;
    windowStart = clampStart(windowStart + (current - next) * anchor, next);
    span = next < duration ? next : null;
    return true;
  }

  const clampStart = (start, size) => Math.round(Math.max(0, Math.min(duration - size, start)));

  function reset() {
    span = null;
    windowStart = 0;
  }

  $effect(() => {
    displayed;
    reset();
  });

  $effect(() => {
    if (!canvas) return;
    const graph = new Chart(canvas, chartSpec(displayed, label, $translate, resolution, width, light, chartWindow));
    return () => graph.destroy();
  });

  $effect(() => {
    if (!canvas) return;
    const element = canvas;
    const signal = new AbortController();
    const options = { signal: signal.signal };
    element.addEventListener('wheel', event => {
      if (!(duration > minimumSpan) || event.deltaY === 0) return;
      const bounds = element.getBoundingClientRect();
      const area = Chart.getChart(element)?.chartArea;
      if (!area || area.width <= 0) return;
      const anchor = Math.min(1, Math.max(0, (event.clientX - bounds.left - area.left) / area.width));
      if (zoom(event.deltaY < 0 ? 0.8 : 1.25, anchor)) event.preventDefault();
    }, { ...options, passive: false });
    element.addEventListener('pointerdown', event => {
      if (span == null || event.button !== 0 || !event.isPrimary || event.pointerType === 'touch') return;
      const plotWidth = Chart.getChart(element)?.chartArea?.width;
      if (!plotWidth) return;
      drag = { id: event.pointerId, x: event.clientX, start: windowStart, unitsPerPixel: span / plotWidth };
      element.setPointerCapture(event.pointerId);
      dragging = true;
    }, options);
    element.addEventListener('pointermove', event => {
      if (drag?.id === event.pointerId && span != null) {
        windowStart = clampStart(drag.start - (event.clientX - drag.x) * drag.unitsPerPixel, span);
      }
    }, options);
    element.addEventListener('lostpointercapture', () => { drag = null; dragging = false; }, options);
    element.addEventListener('keydown', event => {
      if (!(duration > minimumSpan)) return;
      if (event.key === '+' || event.key === '=') zoom(0.8);
      else if (event.key === '-') zoom(1.25);
      else if (event.key === 'Home') reset();
      else if (span != null && ['ArrowLeft', 'ArrowRight'].includes(event.key)) {
        windowStart = clampStart(windowStart + span * (event.key === 'ArrowLeft' ? -0.2 : 0.2), span);
      } else return;
      event.preventDefault();
    }, options);
    return () => signal.abort();
  });
</script>
{#if hasValues}
<div class="chart-shell">
  {#if duration > minimumSpan}
    <button type="button" class="chart-reset" disabled={span == null} onclick={reset}
      aria-label={$translate('Centrar gráfico')} title={$translate('Centrar gráfico')}><Maximize size={15}/></button>
  {/if}
  <div class="chart-canvas" bind:clientWidth={width} class:pannable={span != null} class:dragging>
    <canvas bind:this={canvas} aria-label={label} tabindex={duration > minimumSpan ? 0 : undefined}></canvas>
  </div>
</div>
{:else}
  <p class="quiet">{$translate('No hay períodos completos para esta frecuencia.')}</p>
{/if}

<style>
  .chart-shell {position:relative}
  .chart-reset {position:absolute;right:.2rem;top:.2rem;z-index:1;padding:.3rem;background:var(--panel,#101a28)}
  .pannable canvas {cursor:grab}
  .dragging canvas {cursor:grabbing}
</style>
