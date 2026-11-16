function reply(body, status = 200, retryAfter) {
  const headers = { 'Cache-Control': 'no-store' };
  if (retryAfter) headers['Retry-After'] = retryAfter;
  return Response.json(body, { status, headers });
}

export default {
  async fetch(request, env) {
    if (request.method !== 'POST') return reply({ error: 'Usar POST' }, 405);

    let body;
    try {
      body = await request.json();
    } catch {
      return reply({ error: 'JSON inválido' }, 400);
    }
    const prompt = body?.prompt;
    if (typeof prompt !== 'string' || !prompt.trim() || prompt.length > 30_000) {
      return reply({ error: 'El prompt debe tener entre 1 y 30.000 caracteres' }, 400);
    }
    if (!env.GEMINI_API_KEY) {
      console.error('Falta el secreto GEMINI_API_KEY');
      return reply({ error: 'Asistente temporalmente no disponible' }, 503);
    }

    try {
      const response = await fetch(
        'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'x-goog-api-key': env.GEMINI_API_KEY },
          signal: AbortSignal.timeout(25_000),
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { maxOutputTokens: 4096 }
          })
        }
      );
      const data = await response.json();
      if (!response.ok) {
        console.error('Gemini rechazó la solicitud', {
          httpStatus: response.status,
          status: data?.error?.status,
          reason: data?.error?.details?.find(detail => detail?.reason)?.reason
        });
        const status = [429, 503].includes(response.status) ? response.status : 502;
        return reply({ error: 'Error de Gemini' }, status, response.headers.get('Retry-After'));
      }

      const candidate = data.candidates?.[0];
      const answer = candidate?.content?.parts
        ?.filter(part => !part.thought)
        .map(part => part.text ?? '').join('').trim();
      if (candidate?.finishReason !== 'STOP' || !answer) {
        console.error('Gemini no completó la respuesta', { finishReason: candidate?.finishReason });
        return reply({ error: 'Respuesta incompleta de Gemini' }, 502);
      }
      return reply({ answer });
    } catch (error) {
      console.error('Falló la conexión con Gemini', { type: error?.name });
      return reply({ error: 'No se pudo consultar Gemini' }, 502);
    }
  }
};
