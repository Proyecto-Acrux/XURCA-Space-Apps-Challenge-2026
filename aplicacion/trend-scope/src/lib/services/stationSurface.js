const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);

export function stationHull(points) {
  const sorted = [...points].sort(([x1, y1], [x2, y2]) => x1 - x2 || y1 - y2);
  const half = points => {
    const boundary = [];
    for (const point of points) {
      while (boundary.length >= 2 && cross(boundary.at(-2), boundary.at(-1), point) <= 0) boundary.pop();
      boundary.push(point);
    }
    return boundary.slice(0, -1);
  };
  return [...half(sorted), ...half(sorted.reverse())];
}

export function stationSnapshots(samples, precision) {
  const byDate = new Map();
  for (const sample of samples) {
    if (!Number.isFinite(sample.value)) continue;
    const date = sample.date.slice(0, 10);
    if (!byDate.has(date)) byDate.set(date, new Map());
    const coordinates = sample.geometry.coordinates;
    byDate.get(date).set(coordinates.join(','), sample);
  }
  const windows = new Map();
  for (const date of [...byDate.keys()].sort().reverse()) {
    const key = date.slice(0, precision);
    const previous = windows.get(key);
    if (previous?.canEstimate) continue;
    const events = [...byDate.get(date).values()];
    const canEstimate = events.length >= 3 && stationHull(events.map(event => event.geometry.coordinates)).length >= 3;
    if (canEstimate || !previous || events.length > previous.events.length) {
      windows.set(key, { date, events, canEstimate });
    }
  }
  return windows;
}

export function stationValue(x, y, samples, hull) {
  if (hull.length < 3 || hull.some((point, i) => cross(point, hull[(i + 1) % hull.length], [x, y]) < 0)) {
    return null;
  }
  let sum = 0;
  let weights = 0;
  for (const { position: [px, py], value } of samples) {
    const squaredDistance = (x - px) ** 2 + (y - py) ** 2;
    if (squaredDistance === 0) return value;
    const weight = 1 / squaredDistance;
    sum += weight * value;
    weights += weight;
  }
  return sum / weights;
}

export function stationImage(samples, width, height, palette, thresholds, outline) {
  if (!width || !height || !outline) return null;
  const hull = stationHull(samples.map(sample => sample.position));
  if (hull.length < 3) return null;
  const resolution = Math.min(1, 384 / Math.max(width, height));
  const canvas = document.createElement('canvas');
  const columns = canvas.width = Math.ceil(width * resolution);
  const rows = canvas.height = Math.ceil(height * resolution);
  const context = canvas.getContext('2d');
  if (!context) return null;
  context.setTransform(columns / width, 0, 0, rows / height, 0, 0);
  context.fill(new Path2D(outline), 'evenodd');
  const image = context.getImageData(0, 0, columns, rows);
  const rgb = palette.map(color => [1, 3, 5].map(index => parseInt(color.slice(index, index + 2), 16)));
  let painted = false;
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < columns; col++) {
      const offset = (row * columns + col) * 4;
      if (!image.data[offset + 3]) continue;
      const value = stationValue((col + 0.5) * width / columns, (row + 0.5) * height / rows, samples, hull);
      if (value === null) {
        image.data[offset + 3] = 0;
        continue;
      }
      const index = thresholds.findIndex(limit => value < limit);
      const channels = rgb[thresholds.length ? (index < 0 ? rgb.length - 1 : index) : 0];
      image.data.set(channels, offset);
      image.data[offset + 3] = Math.min(198, image.data[offset + 3]);
      painted = true;
    }
  }
  if (!painted) return null;
  context.putImageData(image, 0, 0);
  return canvas.toDataURL();
}
