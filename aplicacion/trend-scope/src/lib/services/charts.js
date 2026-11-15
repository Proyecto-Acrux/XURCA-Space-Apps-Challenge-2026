export const chartResolutions = [
  ['auto', 'Automática'], ['low', 'Baja'], ['high', 'Alta'], ['full', 'Todos los datos']
];

export function displayPoints(points, resolution, width) {
  const budget = resolution === 'low' ? 180 : resolution === 'high' ? 1000
    : Math.max(240, Math.min(800, Math.round(width || 400)));
  if (resolution === 'full' || points.length <= budget) return points;

  const bucketCount = Math.max(1, Math.floor((budget - 2) / 3));
  const start = Date.parse(points[0].month);
  const end = Date.parse(points.at(-1).month);
  const buckets = new Map();
  for (let index = 1; index < points.length - 1; index++) {
    const point = points[index];
    const time = Date.parse(point.month);
    const fraction = Number.isFinite(time) && end > start
      ? (time - start) / (end - start) : index / (points.length - 1);
    const key = Math.max(0, Math.min(bucketCount - 1, Math.floor(fraction * bucketCount)));
    const bucket = buckets.get(key) ?? {};
    if (point.value === null) {
      bucket.gap ??= index;
    } else {
      if (bucket.min === undefined || point.value < points[bucket.min].value) bucket.min = index;
      if (bucket.max === undefined || point.value > points[bucket.max].value) bucket.max = index;
    }
    buckets.set(key, bucket);
  }
  const keep = new Set([0, points.length - 1]);
  for (const bucket of buckets.values()) {
    for (const index of Object.values(bucket)) keep.add(index);
  }
  return points.filter((_, index) => keep.has(index));
}

export function chartSpec(series, label, translate, resolution, width, light) {
  const period = series.cadence === 'daily' ? 'Día' : series.cadence === 'overpass' ? 'Fecha' : 'Mes';
  const visible = displayPoints(series.points, resolution, width);
  const timestamp = point => Date.parse(point.month);
  const calendar = series.points.length > 0 && series.points.every(point => Number.isFinite(timestamp(point)));
  const origin = calendar ? timestamp(series.points[0]) : 0;
  const ink = light ? "#34475a" : "#abb8c9";
  const line = light ? "#087568" : "#57dfc1";
  const axis = text => ({
    title: { display: true, text, color: ink },
    ticks: { color: ink, maxTicksLimit: 8 },
    grid: { color: light ? '#dce5ed' : '#26374b' }
  });
  const x = axis(translate(period));
  if (calendar) {
    x.type = 'linear';
    x.min = 0;
    const duration = timestamp(series.points.at(-1)) - origin;
    if (duration > 0) x.max = duration;
    else x.max = 86_400_000;
    x.ticks.callback = value => new Date(origin + value).toISOString().slice(0, series.cadence === 'monthly' ? 7 : 10);
  }
  return {
    type: 'line',
    data: {
      labels: calendar ? undefined : visible.map(point => point.month),
      datasets: [{
        label, data: calendar ? visible.map(point => ({ x: timestamp(point) - origin, y: point.value })) : visible.map(point => point.value),
        borderColor: line, backgroundColor: line, pointRadius: visible.length > 200 ? 0 : 2,
        pointHitRadius: 8
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      scales: { x, y: axis(series.unit) },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: items => visible[items[0]?.dataIndex]?.month ?? '' } }
      }
    }
  };
}
