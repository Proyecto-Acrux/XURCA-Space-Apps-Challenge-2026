import { isTauri } from '@tauri-apps/api/core';
import { pyInvoke } from 'tauri-plugin-pytauri-api';

export async function acquireData(investigation) {
  if (!isTauri()) throw new Error('Abrí Earth Detective con pnpm tauri dev para consultar las fuentes.');
  const response = await pyInvoke('acquire_data', { investigation });
  return JSON.parse(response);
}
