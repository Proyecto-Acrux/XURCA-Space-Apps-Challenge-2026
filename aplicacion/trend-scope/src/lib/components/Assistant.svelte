<script>
  import { tick } from 'svelte';
  import { Send } from '@lucide/svelte';
  import { isTauri } from '@tauri-apps/api/core';
  import { pyInvoke } from 'tauri-plugin-pytauri-api';
  import { workspace } from '$lib/stores/workspace.js';
  import { assistantCatalog as catalog } from '$lib/services/sources.js';
  import { configureWorkspace } from '$lib/services/assistantConfiguration.js';
  import AssistantConnection from './AssistantConnection.svelte';

  let { series = [], processing = false, onprocess = () => {} } = $props();
  let connected = $state(false);

  let draft = $state('');
  let messages = $state([]);
  let busy = $state(false);
  let thread;
  const tr = (es, en) => $workspace.visual.language === 'en' ? en : es;
  const sourceOptions = catalog.map(item => ({ id: item.id, label: item.label,
    variable: item.variable, access: item.route.id, code: item.code, selection: item.featureType ?? (item.route.id === 'noaa.ncei.station' ? 'Station' : 'Point') }));

  function contextFor(snapshot) {
    const { data, visual } = snapshot;
    const current = {
      title: data.title?.slice(0, 500), objective: data.objective?.slice(0, 500),
      description: data.description?.slice(0, 500), time: data.time,
      sources: data.sources.slice(0, 25).map(({ id, upstream }) => ({
        id, pointId: upstream?.geometryId, entityId: upstream?.selectors?.stationId ?? upstream?.selectors?.featureId
      })),
      selections: data.geography.selection.features.slice(-20).map(({ id, geometry, properties }) => ({
        id, type: geometry.type, name: properties?.name?.slice(0, 100),
        coordinates: geometry.type === 'Point' ? geometry.coordinates : undefined
      })),
      visual
    };
    const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Argentina/Buenos_Aires' }).format(new Date());
    const history = messages.slice(-8).map(({ role, text, status }) => ({ role, text: (text + (status ? '\n' + status : '')).slice(0, 900) }));
    const results = series.filter(item => item.summary).slice(0, 4).map(item => item.summary);
    const prefix = { today, current, sourceOptions, results, omittedResults: Math.max(0, series.length - results.length) };
    while (history.length && JSON.stringify({ ...prefix, history }).length > 18000) history.shift();
    while (results.length && JSON.stringify({ ...prefix, history }).length > 18000) {
      results.pop(); prefix.omittedResults += 1;
    }
    if (JSON.stringify({ ...prefix, history }).length > 18000) throw new Error('La investigación es demasiado grande para el chat. Reducí las selecciones o variables.');
    return JSON.stringify({ ...prefix, history });
  }

  async function scrollToLatest() {
    await tick();
    if (thread) thread.scrollTop = thread.scrollHeight;
  }

  async function send(event, suggested = '') {
    event.preventDefault();
    const question = suggested || draft.trim();
    if (busy || processing || !connected || !question) return;
    if (!isTauri()) {
      messages.push({ role: 'assistant', text: tr('Abrí la app de escritorio para usar el chat.', 'Open the desktop app to use the chat.') });
      await scrollToLatest();
      return;
    }
    const snapshot = $workspace;
    const original = JSON.stringify(snapshot);
    let context;
    try { context = contextFor(snapshot); }
    catch (error) { messages.push({ role: 'assistant', text: error.message }); return; }
    const evidenceKey = JSON.stringify(series.map(item => item.summary));
    const language = snapshot.visual.language;
    messages.push({ role: 'user', text: question });
    draft = '';
    busy = true;
    await scrollToLatest();
    try {
      const reply = await pyInvoke('interpret_question', {
        question, context, language, endpoint: import.meta.env.VITE_ASSISTANT_ENDPOINT || null
      });
      let status = '';
      let applied = null;
      if (JSON.stringify($workspace) !== original || JSON.stringify(series.map(item => item.summary)) !== evidenceKey) {
        throw new Error('La investigación o sus resultados cambiaron durante la respuesta. Enviá el pedido de nuevo.');
      }
      if (Object.keys(reply.changes).length) {
        try {
          const next = await configureWorkspace(snapshot, reply.changes, pyInvoke, language);
          if (JSON.stringify($workspace) !== original) {
            throw new Error(tr('La configuración cambió durante la consulta. Pedime el cambio de nuevo.', 'Settings changed during this reply. Ask me again.'));
          }
          if (JSON.stringify(next) !== original) {
            workspace.set(next);
            applied = reply.changes;
            status = tr('Configuración actualizada. Pulsá Procesar para ejecutar la consulta.', 'Settings updated. Select Process to run the query.');
          }
        } catch (error) {
          status = tr('No se aplicaron cambios. ', 'No settings were applied. ') + String(error.message ?? error);
        }
      }
      messages.push({ role: 'assistant', text: reply.message, status, applied,
        evidence: series.length && !Object.keys(reply.changes).length ? original : null });
    } catch (error) {
      messages.push({ role: 'assistant', text: String(error.message ?? error) });
      if (!draft) draft = question;
    } finally {
      busy = false;
      await scrollToLatest();
    }
  }
</script>

<div class="chat">
  <AssistantConnection onstatus={value => connected = value}/>
  <div class="thread" role="log" aria-label={tr('Conversación con la IA', 'AI conversation')} bind:this={thread}>
    {#if !messages.length}
      <p>{tr('¿Qué querés conocer de este lugar?', 'What would you like to know about this place?')}</p>
      <p class="quiet">{tr('Contame con tus palabras. Te ayudo a elegir los datos y preparar la consulta; no necesitás programar.', 'Describe it in your own words. I will help choose data and prepare the query; no programming needed.')}</p>
      <button class="example" onclick={() => draft = 'Quiero ver cómo cambió la temperatura en el punto seleccionado entre 2000 y 2024.'}>¿Cómo cambió la temperatura?</button>
      <button class="example" onclick={() => draft = 'Quiero investigar si llueve menos en San Luis.'}>¿Está lloviendo menos en San Luis?</button>
    {/if}
    {#each messages as message}
      <article class:user={message.role === 'user'}>
        <strong>{message.role === 'user' ? tr('Vos', 'You') : tr('Asistente', 'Assistant')}</strong>
        <p>{message.text}</p>
        {#if message.status}<p class="quiet">{message.status}</p>{/if}
        {#if message.evidence && message.evidence !== JSON.stringify($workspace)}<p class="quiet">Esta explicación corresponde a una configuración anterior. Procesá la actual para actualizarla.</p>{/if}
        {#if message.applied}<details><summary>Cambios aplicados (JSON)</summary><pre>{JSON.stringify(message.applied, null, 2)}</pre></details>{/if}
      </article>
    {/each}
    {#if busy}<p class="quiet">{tr('Preparando respuesta…', 'Preparing a reply…')}</p>{/if}
  </div>
  <div class="actions">
    <button onclick={onprocess} disabled={busy || processing}>{processing ? 'Procesando…' : 'Procesar investigación'}</button>
    <button onclick={event => send(event, 'Explicame los resultados actuales en lenguaje sencillo, con sus fuentes, unidades y limitaciones.')} disabled={!connected || busy || processing || !series.length}>Explicar resultados</button>
  </div>
  <form onsubmit={send}>
    <textarea aria-label={tr('Mensaje', 'Message')} placeholder={tr('Escribí un mensaje…', 'Write a message…')}
      maxlength="1200" rows="2" bind:value={draft}
      onkeydown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }}></textarea>
    <button type="submit" class="primary" disabled={!connected || busy || processing || !draft.trim()} aria-label={tr('Enviar mensaje', 'Send message')}>
      <Send size={16}/>
    </button>
  </form>
</div>

<style>
  .chat { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  .thread { flex: 1; overflow: auto; min-height: 0; padding: 12px; scrollbar-width: thin; }
  article { padding: 8px 10px; margin: 0 10% 10px 0; border: 1px solid var(--line); border-radius: 7px; background: var(--surface); overflow-wrap: anywhere; }
  article.user { margin: 0 0 10px 10%; background: var(--raised); }
  article p { margin: 4px 0 0; white-space: pre-wrap; }
  form { flex: none; display: flex; align-items: end; gap: 8px; padding: 10px; border-top: 1px solid var(--line); }
  textarea { resize: none; }
  .actions { display: flex; gap: 6px; padding: 8px; flex-wrap: wrap; border-top: 1px solid var(--line); }
  .actions button, .example { font-size: 12px; }
  .example { display: block; margin: 8px 0; text-align: left; width: 100%; white-space: normal; }
  pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; }
  details { margin-top: 8px; font-size: 12px; }
</style>
