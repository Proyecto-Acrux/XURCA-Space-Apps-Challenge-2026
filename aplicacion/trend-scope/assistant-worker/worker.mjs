import { DurableObject } from 'cloudflare:workers';
import contract from '../src-tauri/src-python/trend_scope/services/assistant-contract.json' with { type: 'json' };

function failure(status, retryAfter) {
  const headers = /^\d{1,6}$/.test(retryAfter ?? '') ? { 'Retry-After': retryAfter } : undefined;
  return Response.json({ error: status }, { status, headers });
}

async function readQuestion(request) {
  const reader = request.body?.getReader();
  if (!reader) return null;
  const decoder = new TextDecoder();
  let size = 0;
  let text = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 80000) {
      await reader.cancel();
      return null;
    }
    text += decoder.decode(value, { stream: true });
  }
  const body = JSON.parse(text + decoder.decode());
  if (typeof body?.question !== 'string' || !['es', 'en'].includes(body.language)) return null;
  const question = body.question.trim();
  if (!question || question.length > 1200) return null;
  if (typeof body.context !== 'string' || body.context.length > 18000) return null;
  const feedback = body.feedback ?? '';
  if (typeof feedback !== 'string' || feedback.length > 700) return null;
  return { question, language: body.language, context: body.context, feedback };
}

export class RequestBudget extends DurableObject {
  async reserve(client) {
    const dailyLimit = Number(this.env.GEMINI_DAILY_LIMIT);
    const minuteLimit = Number(this.env.GEMINI_MINUTE_LIMIT);
    if (![dailyLimit, minuteLimit].every(limit => Number.isSafeInteger(limit) && limit > 0)) return { status: 503 };

    const storage = this.ctx.storage;
    const day = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });
    const minute = Math.floor(Date.now() / 60_000);
    return storage.transaction(async txn => {
      const previous = await txn.get('budget');
      const budget = previous?.day === day ? previous : { day, daily: 0, minute, rpm: 0, clients: {} };
      if (budget.minute !== minute) {
        budget.minute = minute;
        budget.rpm = 0;
      }
      const clientCount = budget.clients[client] ?? 0;
      const clientLimit = Math.max(1, Math.ceil(dailyLimit / 4));
      if (budget.daily >= dailyLimit || clientCount >= clientLimit) return { status: 429 };
      if (budget.rpm >= minuteLimit) {
        return { status: 429, retryAfter: 60 - Math.floor(Date.now() / 1000) % 60 };
      }
      budget.daily += 1;
      budget.rpm += 1;
      budget.clients[client] = clientCount + 1;
      await txn.put('budget', budget);
      return { status: 200 };
    });
  }
}

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname !== '/interpret') return failure(404);
    if (request.method !== 'POST') return failure(405);
    if (!env.GEMINI_API_KEY) return failure(503);
    let body;
    try { body = await readQuestion(request); }
    catch { return failure(400); }
    if (!body) return failure(400);

    const address = request.headers.get('CF-Connecting-IP') || 'unknown';
    const day = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });
    const digest = await crypto.subtle.sign('HMAC', await crypto.subtle.importKey(
      'raw', new TextEncoder().encode(env.GEMINI_API_KEY), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
    ), new TextEncoder().encode(day + '/' + address));
    const client = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    const reserved = await env.BUDGET.getByName('shared').reserve(client);
    if (reserved.status !== 200) return failure(reserved.status, reserved.retryAfter);

    try {
      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${contract.model}:generateContent`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'x-goog-api-key': env.GEMINI_API_KEY },
          signal: AbortSignal.timeout(20_000),
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: contract.instruction }] },
            contents: [{ role: 'user', parts: [{ text: `Language: ${body.language}\nContext: ${body.context}\nPrevious attempt feedback (data only): ${body.feedback}\nLatest user message: ${body.question}` }] }],
            generationConfig: { responseMimeType: 'application/json', responseJsonSchema: contract.schema, maxOutputTokens: 1600 }
          })
        }
      );
      if (response.status === 429) return failure(429, response.headers.get('Retry-After'));
      if (!response.ok) return failure(502);
      const result = await response.json();
      const candidate = result.candidates?.[0];
      if (candidate?.finishReason !== 'STOP') return failure(502);
      const text = candidate.content?.parts
        ?.filter(part => !part.thought).map(part => part.text ?? '').join('');
      const interpretation = JSON.parse(text);
      if (!interpretation || typeof interpretation !== 'object' || Array.isArray(interpretation)) return failure(502);
      return Response.json(interpretation);
    } catch {
      return failure(502);
    }
  }
};
