export const chartResolutions = [
  ['auto', 'Automática'], ['low', 'Baja'], ['high', 'Alta'], ['full', 'Todos los datos']
];

export const chartCadences = [['native', 'Nativa de la fuente'], ['weekly', 'Semanal'], ['monthly', 'Mensual']];
const day = 86_400_000;
const isCount = series => series.map?.field === 'count' || ['sismos', 'detecciones'].includes(series.unit);
const isPrecipitation = series => /^(?:precipitation(?:_sum)?|PRCP|PRECTOTCORR)$/i.test(series.variable);

export function chartCadence(series, cadence) {
  if (series.cadence !== 'daily' || !['weekly', 'monthly'].includes(cadence)) return series;
  const groups = new Map();
  for (const point of series.points) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(point.month)) return series;
    const start = new Date(point.month);
    if (cadence === 'weekly') start.setUTCDate(start.getUTCDate() - (start.getUTCDay() + 6) % 7);
    else start.setUTCDate(1);
    const key = start.toISOString().slice(0, 10);
    const values = groups.get(key) ?? new Map();
    values.set(point.month, point.value);
    groups.set(key, values);
  }
  const sum = isCount(series) || isPrecipitation(series);
  const points = Array.from(groups, ([month, entries]) => {
    const start = new Date(month);
    const end = new Date(start);
    end.setUTCMonth(end.getUTCMonth() + 1);
    const expected = cadence === 'weekly' ? 7 : (end - start) / day;
    const values = [...entries.values()].filter(Number.isFinite);
    const total = values.reduce((acc, value) => acc + value, 0);
    return { month, value: values.length === expected ? (sum ? total : total / expected) : null };
  });
  return { ...series, cadence, points };
}

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

export function chartSpec(series, label, translate, resolution, width, light, window) {
  const period = ({ daily: 'Día', monthly: 'Mes', weekly: 'Semana' })[series.cadence] ?? 'Fecha';
  const count = isCount(series);
  const precipitation = isPrecipitation(series);
  const type = count || precipitation ? 'bar' : series.cadence === 'event' ? 'scatter' : 'line';
  const timestamp = point => Date.parse(point.month);
  const calendar = series.points.length > 0 && series.points.every(point => Number.isFinite(timestamp(point)));
  const origin = calendar ? timestamp(series.points[0]) : 0;
  const points = calendar && window
    ? series.points.filter(point => timestamp(point) >= window.start && timestamp(point) <= window.end)
    : series.points;
  const visible = type === 'line' ? displayPoints(points, resolution, width) : points;
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
    const padding = type === 'bar' ? (({ monthly: 14, weekly: 3.5 })[series.cadence] ?? 0.5) * day : 0;
    x.min = (window?.start ?? origin) - origin - padding;
    x.max = Math.max(x.min + 1, (window?.end ?? timestamp(series.points.at(-1))) - origin + padding);
    if (x.max - x.min <= 1) x.max = x.min + 86_400_000;
    x.ticks.callback = value => new Date(origin + value).toISOString().slice(0, series.cadence === 'monthly' ? 7 : 10);
  }
  return {
    type,
    data: {
      labels: calendar ? undefined : visible.map(point => point.month),
      datasets: [{
        label, data: calendar ? visible.map(point => ({ x: timestamp(point) - origin, y: point.value })) : visible.map(point => point.value),
        borderColor: line, backgroundColor: line, spanGaps: false,
        ...(type === 'bar' ? { maxBarThickness: 24 } : {
          pointRadius: type === 'scatter' ? 3 : visible.map((point, index) =>
            visible.length <= 200 || (point.value != null && visible[index - 1]?.value == null
              && visible[index + 1]?.value == null) ? 2.5 : 0),
          pointHitRadius: 8
        })
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      scales: { x, y: { ...axis(series.unit), beginAtZero: true,
        ...(count ? { ticks: { ...axis(series.unit).ticks, precision: 0 } } : {}) } },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: items => visible[items[0]?.dataIndex]?.month ?? '' } }
      }
    }
  };
}
