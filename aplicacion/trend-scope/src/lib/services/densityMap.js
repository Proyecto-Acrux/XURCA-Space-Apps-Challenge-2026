export const densityColors = ['#36a657', '#ecd34d', '#f28a34', '#df3c36'];
const rgb = densityColors.map(color => [1, 3, 5].map(index => parseInt(color.slice(index, index + 2), 16)));

export function densityImage(positions, width, height) {
  if (!positions.length || !width || !height) return null;
  const resolution = Math.min(1, 192 / Math.max(width, height));
  const columns = Math.ceil(width * resolution);
  const rows = Math.ceil(height * resolution);
  const radius = Math.max(2, Math.round(Math.min(columns, rows) * 0.18));
  const centers = new Map();
  for (const [x, y] of positions) {
    const col = Math.round(x * columns / width);
    const row = Math.round(y * rows / height);
    if (col < 0 || col >= columns || row < 0 || row >= rows) continue;
    const id = row * columns + col;
    centers.set(id, (centers.get(id) ?? 0) + 1);
  }
  const density = new Float32Array(columns * rows);
  for (const [id, count] of centers) {
    const x = id % columns, y = Math.floor(id / columns);
    for (let row = Math.max(0, y - radius); row <= Math.min(rows - 1, y + radius); row++) {
      for (let col = Math.max(0, x - radius); col <= Math.min(columns - 1, x + radius); col++) {
        const distance = ((row - y) ** 2 + (col - x) ** 2) / radius ** 2;
        if (distance < 1) density[row * columns + col] += count * (1 - distance) ** 2;
      }
    }
  }
  const canvas = document.createElement('canvas');
  canvas.width = columns;
  canvas.height = rows;
  const context = canvas.getContext('2d');
  if (!context) return null;
  const image = context.createImageData(columns, rows);
  for (let i = 0; i < density.length; i++) {
    const scaled = Math.min(3, density[i] * 3);
    const low = Math.min(2, Math.floor(scaled));
    for (let channel = 0; channel < 3; channel++) {
      image.data[i * 4 + channel] = rgb[low][channel] + (rgb[low + 1][channel] - rgb[low][channel]) * (scaled - low);
    }
    image.data[i * 4 + 3] = 176;
  }
  context.putImageData(image, 0, 0);
  return canvas.toDataURL();
}
