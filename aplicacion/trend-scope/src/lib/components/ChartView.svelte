<script>
  import { Chart, registerables } from 'chart.js';
  import { chartSpec } from '$lib/services/charts.js';
  import { translate } from '$lib/services/i18n.js';
  import { workspace } from '$lib/stores/workspace.js';
  Chart.register(...registerables);
  let { series, label, resolution } = $props();
  let light = $derived($workspace.visual.theme === 'light');
  let width = $state(400);
  let canvas = $state();
  $effect(() => {
    if (!canvas) return;
    const graph = new Chart(canvas, chartSpec(series, label, $translate, resolution, width, light));
    return () => graph.destroy();
  });
</script>
<div class="chart-canvas" bind:clientWidth={width} role="img" aria-label={label}><canvas bind:this={canvas}></canvas></div>
