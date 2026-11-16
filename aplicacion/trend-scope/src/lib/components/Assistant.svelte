<script>
  import { tick } from 'svelte';
  import { Send } from '@lucide/svelte';
  import { isTauri } from '@tauri-apps/api/core';
  import { pyInvoke } from 'tauri-plugin-pytauri-api';
  import { workspace } from '$lib/stores/workspace.js';
  import { assistantCatalog as catalog } from '$lib/services/sources.js';
  import { providerGeometries } from '$lib/services/sources.js';
  import { configureWorkspace } from '$lib/services/assistantConfiguration.js';
  import { prepareInvestigation } from '$lib/services/acquisition.js';
  import idleMascot from '$lib/assets/mascot/reposo.png';
  import thinkingMascot from '$lib/assets/mascot/pensando.png';
  import analyzingMascot from '$lib/assets/mascot/analizando.png';
  import discoveryMascot from '$lib/assets/mascot/descubrimiento.png';
  import errorMascot from '$lib/assets/mascot/error.png';
  import restingMascot from '$lib/assets/mascot/descansando.png';

  let { series = [], running = false, storageBusy = false, acquisitionError = '',
    onprocess = () => {}, onresults = () => {} } = $props();
  let failedQuestion = $state('');
  let recovering = $state(false);

  let draft = $state('');
  let messages = $state([]);
  let busy = $state(false);
  let configured = $state(false);
  let thread;
  const tr = (es, en) => $workspace.visual.language === 'en' ? en : es;
  let processing = $derived(running || storageBusy);
  let mascot = $derived.by(() => {
    if (busy) return { image: thinkingMascot, status: tr('Preparando respuesta…', 'Preparing a reply…') };
    if (running) return { image: analyzingMascot, status: tr('Consultando las fuentes…', 'Fetching data…') };
    if (failedQuestion || acquisitionError) return { image: errorMascot, status: tr('La consulta no pudo completarse.', 'The request could not be completed.') };
    if (series.length) return { image: discoveryMascot, status: tr('Resultados disponibles', 'Results available') };
    if (messages.length) return { image: restingMascot, status: tr('Esperando tu mensaje', 'Waiting for your message') };
    return { image: idleMascot, status: '' };
  });
  const sourceOptions = catalog.map(item => ({ id: item.id, label: item.label,
    geometries: providerGeometries(item.route) }));
  let prepared = $derived.by(() => {
    try { return { investigation: prepareInvestigation($workspace.data) }; }
    catch (error) { return { error: error.message }; }
  });
  let configuredSources = $derived(prepared.investigation?.sources.map(source => {
    const feature = prepared.investigation.geography.selection.features.find(item => item.id === source.upstream.geometryId);
    const label = catalog.find(item => item.id === source.id.split('::')[0])?.label ?? source.variable;
    const place = feature?.properties?.name || (feature?.geometry.type === 'Point' ? tr('Punto del mapa', 'Map point')
      : feature ? tr('Área del mapa', 'Map area') : '');
    return { id: source.id, label, place };
  }) ?? []);

  function contextFor(snapshot, retryQuestion) {
    const { data, visual } = snapshot;
    const current = {
      title: data.title?.slice(0, 500), objective: data.objective?.slice(0, 500),
      description: data.description?.slice(0, 500), time: data.time,
      geographicScope: data.geography.scope,
      sources: data.sources.slice(0, 25).map(({ id, upstream }) => ({
        id, geometryId: upstream?.geometryId
      })),
      selections: data.geography.selection.features.slice(-20).map(({ id, geometry, properties }) => ({
        id, type: geometry.type, name: properties?.name?.slice(0, 100),
        coordinates: geometry.type === 'Point' ? geometry.coordinates : undefined
      })),
      visual
    };
    const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Argentina/Buenos_Aires' }).format(new Date());
    const history = messages.filter(message => !message.temporary).slice(-8).map(({ role, text, status }) => ({ role, text: (text + (status ? '\n' + status : '')).slice(0, 900) }));
    if (retryQuestion && history.at(-1)?.role === 'user' && history.at(-1)?.text === retryQuestion.slice(0, 900)) history.pop();
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

  async function send(event, suggested = '', retry = false) {
    event.preventDefault();
    const question = suggested || draft.trim();
    if (busy || processing || !question) return;
    if (!isTauri()) {
      messages.push({ role: 'assistant', text: tr('Abrí la app de escritorio para usar el chat.', 'Open the desktop app to use the chat.') });
      await scrollToLatest();
      return;
    }
    const snapshot = $workspace;
    const hasPoint = snapshot.data.geography.selection.features.some(feature => feature.geometry.type === 'Point');
    if (!hasPoint && /\b(punto seleccionado|selected point)\b/i.test(question)) {
      if (!retry) messages.push({ role: 'user', text: question });
      messages.push({ role: 'assistant', text: tr(
        'Todavía no hay un punto seleccionado. Escribí el nombre de la localidad o marcá un punto en el mapa.',
        'There is no selected point yet. Enter the town name or mark a point on the map.'
      ) });
      failedQuestion = '';
      if (!retry) draft = '';
      await scrollToLatest();
      return;
    }
    const original = JSON.stringify(snapshot);
    let context;
    try { context = contextFor(snapshot, retry ? question : null); }
    catch (error) { messages.push({ role: 'assistant', text: error.message }); return; }
    const evidenceKey = JSON.stringify(series.map(item => item.summary));
    const language = snapshot.visual.language;
    if (!retry) messages.push({ role: 'user', text: question });
    failedQuestion = '';
    draft = '';
    busy = true;
    await scrollToLatest();
    try {
      const ensureCurrent = () => {
        if (JSON.stringify($workspace) !== original || JSON.stringify(series.map(item => item.summary)) !== evidenceKey) {
          throw new Error(tr('La investigación cambió. Volvé a enviar la consulta.', 'The investigation changed. Please resend the question.'));
        }
      };
      let feedback = '';
      for (let attempt = 0; attempt < 2; attempt++) {
        let reply;
        let next;
        try {
          reply = await pyInvoke('interpret_question', { question, context, language, feedback });
        } catch (error) {
          const reason = String(error.message ?? error);
          if (attempt || /HTTP 4[0-9]{2}/.test(reason)) throw error;
          feedback = reason.includes('propuesta inválida')
            ? 'The previous reply violated the response schema. Return a valid proposal for the original question.'
            : '';
          recovering = true;
          await new Promise(resolve => setTimeout(resolve, 2000));
          continue;
        }
        ensureCurrent();
        try {
          if (Object.keys(reply.changes).length) next = await configureWorkspace(snapshot, reply.changes, pyInvoke, language);
          if (reply.readyToProcess === true) prepareInvestigation((next ?? snapshot).data);
        } catch (error) {
          const reason = String(error.message ?? error);
          if (/^(Hay varios lugares|No encontré|No pude confirmar)/.test(reason)) {
            messages.push({ role: 'assistant', text: reason });
            return;
          }
          if (attempt) throw error;
          feedback = 'The app could not apply the proposal. Correct the configuration, or ask a simple question if essential information is missing. Do not invent data. Validation detail: ' + reason.slice(0, 400);
          recovering = true;
          continue;
        }
        ensureCurrent();
        const applied = next && JSON.stringify(next) !== original ? reply.changes : null;
        if (applied) {
          const changedInvestigation = JSON.stringify(next.data) !== JSON.stringify(snapshot.data);
          workspace.set(next);
          if (changedInvestigation) {
            configured = true;
          }
        }
        messages.push({ role: 'assistant', text: reply.message,
          status: applied ? tr('Configuración aplicada.', 'Settings applied.') : '',
          evidence: series.length && !reply.readyToProcess && !Object.keys(reply.changes).length ? original : null });
        if (reply.readyToProcess === true) {
          configured = true;
          onprocess();
        }
        return;
      }
    } catch (error) {
      const reason = String(error.message ?? error);
      const quota = reason.includes('HTTP 429');
      const retryAfter = reason.match(/Retry-After: (\d+)/)?.[1];
      const message = quota
        ? (retryAfter
          ? tr(`El asistente alcanzó su límite. Reintentá en ${retryAfter} segundos.`, `The assistant reached its limit. Retry in ${retryAfter} seconds.`)
          : tr('El asistente alcanzó su límite de consultas. Probá más tarde.', 'The assistant reached its request limit. Try again later.'))
        : tr('No pude completar tu consulta. Podés reintentar sin perder la conversación.', 'I could not complete your request. You can retry without losing the conversation.');
      messages.push({ role: 'assistant', text: message, temporary: true });
      failedQuestion = question;
    } finally {
      busy = false;
      recovering = false;
      await scrollToLatest();
    }
  }
</script>

<div class="chat">
  <div class="mascot" role="status">
    <img src={mascot.image} alt="" width="56" height="56" draggable="false"/>
    {#if busy && recovering}
      <span>{tr('Volviendo a intentar…', 'Trying again…')}</span>
    {:else if mascot.status}
      <span>{mascot.status}</span>
    {/if}
  </div>
  <div class="thread" role="log" aria-label={tr('Conversación con la IA', 'AI conversation')} bind:this={thread}>
    {#if !messages.length}
      <p>{tr('¿Qué querés investigar?', 'What would you like to investigate?')}</p>
      <p class="quiet">{tr('Contame qué querés estudiar. Te voy a preguntar por el lugar o el período si hace falta. También puedo usar un polígono que ya dibujaste.', 'Tell me what you want to study. I will ask for the place or period if needed. I can also use a polygon you already drew.')}</p>
      <button class="example" onclick={() => draft = 'Quiero ver cómo cambió la temperatura en el punto seleccionado entre 2000 y 2024.'}>¿Cómo cambió la temperatura?</button>
      <button class="example" onclick={() => draft = 'Quiero investigar si llueve menos en San Luis.'}>¿Está lloviendo menos en San Luis?</button>
      <button class="example" onclick={() => draft = tr('Quiero ver la lluvia mensual en el polígono que dibujé.', 'Show monthly precipitation in the polygon I drew.')}>{tr('Estudiar el área dibujada', 'Study the drawn area')}</button>
    {/if}
    {#each messages as message}
      <article class:user={message.role === 'user'}>
        <strong>{message.role === 'user' ? tr('Usuario', 'User') : tr('Asistente', 'Assistant')}</strong>
        <p>{message.text}</p>
        {#if message.status}<p class="quiet">{message.status}</p>{/if}
        {#if message.evidence && message.evidence !== JSON.stringify($workspace)}<p class="quiet">Esta explicación corresponde a una configuración anterior. Procesá la actual para actualizarla.</p>{/if}
      </article>
    {/each}
  </div>
  {#if configured}
    <div class="query-summary">
      {#if prepared.investigation}
        <strong>{tr('Investigación', 'Investigation')}</strong>
        <small>{prepared.investigation.time.start} – {prepared.investigation.time.end}</small>
        <ul>
          {#each configuredSources as source (source.id)}
            <li>{source.label}{source.place ? ' · ' + source.place : ''}</li>
          {/each}
        </ul>
      {:else}
        <small>{prepared.error}</small>
      {/if}
    </div>
  {/if}
  <div class="actions">
    {#if failedQuestion}
      <button onclick={event => send(event, failedQuestion, true)} disabled={busy || processing}>{tr('Reintentar consulta', 'Retry request')}</button>
    {/if}
    {#if acquisitionError}
      <button onclick={onprocess} disabled={busy || processing || !prepared.investigation}>{tr('Reintentar procesamiento', 'Retry processing')}</button>
    {/if}
    {#if series.length}
      <button onclick={onresults} disabled={busy || processing}>{tr('Ver resultados', 'View results')}</button>
      <button onclick={event => send(event, 'Explicame los resultados actuales en lenguaje sencillo, con sus fuentes, unidades y limitaciones.')} disabled={busy || processing}>{tr('Explicar resultados', 'Explain results')}</button>
    {/if}
  </div>
  <form onsubmit={send}>
    <textarea aria-label={tr('Mensaje', 'Message')} placeholder={tr('Escribí un mensaje…', 'Write a message…')}
      maxlength="1200" rows="2" bind:value={draft}
      onkeydown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }}></textarea>
    <button type="submit" class="primary" disabled={busy || processing || !draft.trim()} aria-label={tr('Enviar mensaje', 'Send message')}>
      <Send size={16}/>
    </button>
  </form>
</div>

<style>
  .chat { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  .mascot { display: flex; flex: none; align-items: center; gap: 8px; min-height: 58px; padding: 2px 12px; color: var(--muted); font-size: 12px; }
  .mascot img { flex: none; object-fit: contain; }
  .thread { flex: 1; overflow: auto; min-height: 0; padding: 12px; scrollbar-width: thin; }
  article { padding: 8px 10px; margin: 0 10% 10px 0; border: 1px solid var(--line); border-radius: 7px; background: var(--surface); overflow-wrap: anywhere; }
  article.user { margin: 0 0 10px 10%; background: var(--raised); }
  article p { margin: 4px 0 0; white-space: pre-wrap; }
  form { flex: none; display: flex; align-items: end; gap: 8px; padding: 10px; border-top: 1px solid var(--line); }
  textarea { resize: none; }
  .actions { display: flex; gap: 6px; padding: 8px; flex-wrap: wrap; border-top: 1px solid var(--line); }
  .actions button, .example { font-size: 12px; }
  .example { display: block; margin: 8px 0; text-align: left; width: 100%; white-space: normal; }
  .query-summary { display: grid; gap: 4px; margin: 0 8px 8px; padding: 8px; border: 1px solid var(--line); border-radius: 7px; max-height: 120px; overflow: auto; }
  .query-summary ul { margin: 0; padding-left: 18px; font-size: .88em; }
</style>
