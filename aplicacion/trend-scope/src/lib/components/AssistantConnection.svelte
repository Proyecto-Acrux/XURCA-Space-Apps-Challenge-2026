<script>
  import { onMount } from 'svelte';
  import { isTauri } from '@tauri-apps/api/core';
  import { pyInvoke } from 'tauri-plugin-pytauri-api';

  let { onstatus = (status) => {} } = $props();
  let provider = $state('gemini');
  let defaults = $state({ gemini: 'gemini-3.1-flash-lite', openai: 'gpt-4.1-mini' });
  let model = $state('gemini-3.1-flash-lite');
  let key = $state('');
  let busy = $state(false);
  let notice = $state('');
  let connected = $state(false);
  let expanded = $state(false);

  function update(status) {
    connected = status.configured || Boolean(import.meta.env.VITE_ASSISTANT_ENDPOINT);
    defaults = status.defaults;
    if (status.provider) { provider = status.provider; model = status.model; }
    notice = status.configured ? `Conectado: ${status.provider} · ${status.model}`
      : connected ? 'Servicio del equipo disponible' : 'Conectá una IA para empezar';
    onstatus(connected);
  }
  onMount(async () => {
    if (!isTauri()) { notice = 'Abrí la versión de escritorio para conectar la IA.'; return; }
    try { update(await pyInvoke('assistant_status', {})); expanded = !connected; }
    catch (error) { notice = String(error.message ?? error); }
  });
  async function connect(event) {
    event.preventDefault();
    busy = true;
    notice = 'Verificando conexión…';
    try {
      update(await pyInvoke('configure_assistant', { provider, model: model.trim(), apiKey: key.trim() }));
      expanded = false;
    } catch (error) { notice = String(error.message ?? error); }
    finally { key = ''; busy = false; }
  }
  async function disconnect() {
    try { update(await pyInvoke('disconnect_assistant', {})); expanded = true; }
    catch (error) { notice = String(error.message ?? error); }
  }
</script>

<div class="connection">
  <button class="toggle" onclick={() => expanded = !expanded} aria-expanded={expanded}>Conectar IA / cambiar proveedor</button>
  <p role="status">{notice}</p>
  {#if expanded}
    <form onsubmit={connect}>
      <label>Proveedor <select bind:value={provider} disabled={busy} onchange={() => model = defaults[provider]}>
        <option value="gemini">Google Gemini</option><option value="openai">OpenAI</option>
      </select></label>
      <details><summary>Opciones de modelo</summary><label>Modelo <input bind:value={model} required maxlength="100" disabled={busy}/></label></details>
      <label>API key <input type="password" bind:value={key} required maxlength="512" autocomplete="off" disabled={busy} placeholder="Pegá tu clave del proveedor"/></label>
      <button class="primary" type="submit" disabled={busy || !key.trim() || !model.trim()}>{busy ? 'Conectando…' : 'Conectar y verificar'}</button>
      <a href={provider === 'gemini' ? 'https://aistudio.google.com/apikey' : 'https://platform.openai.com/api-keys'} target="_blank" rel="noreferrer">Obtener una API key</a>
      <p>La clave dura esta sesión y no se guarda en el proyecto. Tus pedidos y resúmenes se envían al proveedor elegido. Verificar la conexión puede consumir cuota.</p>
      {#if connected}<button type="button" onclick={disconnect} disabled={busy}>Olvidar clave de esta sesión</button>{/if}
    </form>
  {/if}
</div>

<style>
  .connection { padding: 10px; border-bottom: 1px solid var(--line); max-height: 48vh; overflow: auto; flex: none; }
  .toggle { width: 100%; text-align: left; }
  p { font-size: 12px; margin: 6px 0; color: var(--muted); overflow-wrap: anywhere; }
  form, label { display: flex; flex-direction: column; gap: 6px; }
  form { gap: 9px; }
  input, select { width: 100%; min-width: 0; }
  a { font-size: 12px; }
</style>
