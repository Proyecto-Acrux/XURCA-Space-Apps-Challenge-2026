import { isTauri } from '@tauri-apps/api/core';
import { save } from '@tauri-apps/plugin-dialog';
import { writeFile } from '@tauri-apps/plugin-fs';

export async function saveChartImage(canvas, filename, light) {
  const image = document.createElement('canvas');
  image.width = canvas.width;
  image.height = canvas.height;
  const context = image.getContext('2d');
  context.fillStyle = light ? '#ffffff' : '#101b2a';
  context.fillRect(0, 0, image.width, image.height);
  context.drawImage(canvas, 0, 0);
  const png = await new Promise((resolve, reject) => image.toBlob(
    blob => blob ? resolve(blob) : reject(new Error('Could not encode PNG.')), 'image/png'
  ));
  if (!isTauri()) throw new Error('Open Earth Detective in desktop mode to export charts.');
  const path = await save({
    defaultPath: filename,
    filters: [{ name: 'PNG', extensions: ['png'] }]
  });
  if (!path) return false;
  await writeFile(path, new Uint8Array(await png.arrayBuffer()));
  return true;
}
