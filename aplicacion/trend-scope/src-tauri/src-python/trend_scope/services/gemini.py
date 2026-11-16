"""Gemini transport and a local connectivity check."""

import json
import os
from getpass import getpass
from importlib.resources import files
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CONTRACT = json.loads(files(__package__).joinpath("assistant-contract.json").read_text("utf-8"))
MODEL = CONTRACT["model"]
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def generate_text(prompt: str, api_key: str) -> str:
    return gemini_text({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 512},
    }, api_key)


def gemini_text(payload, api_key):
    data = post_json(ENDPOINT, payload, {"x-goog-api-key": api_key}, provider="Gemini")
    candidates = data.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    reply = "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
    if not reply:
        raise ValueError("Gemini no devolvió texto.")
    return reply


def open_assistant_request(request, retry_unavailable):
    try:
        return urlopen(request, timeout=60)
    except HTTPError as error:
        if error.code != 503 or not retry_unavailable:
            raise
        error.close()
    sleep(2)
    return urlopen(request, timeout=60)


def post_json(url, payload, headers=None, provider="Servicio de IA"):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with open_assistant_request(request, retry_unavailable=provider == "Gemini") as response:
            data = json.load(response)
            if not isinstance(data, dict):
                raise ValueError()
            return data
    except HTTPError as error:
        hints = {
            400: "Revisá la clave y la configuración del proyecto.",
            401: "Revisá la clave de API.",
            403: "Revisá los permisos y restricciones de la clave.",
            404: "Revisá que el modelo esté disponible para tu proyecto.",
            429: "Se alcanzó la cuota del proveedor. Revisá el saldo o intentá más tarde.",
            503: "El servicio no está disponible en este momento. Volvé a intentar más tarde.",
        }
        hint = hints.get(error.code, "Volvé a intentar más tarde.")
        retry_after = error.headers.get("Retry-After", "") if error.headers else ""
        if error.code == 429 and retry_after.isascii() and retry_after.isdecimal() and len(retry_after) <= 6:
            hint = f"Retry-After: {retry_after}"
        raise ValueError(f"{provider} devolvió HTTP {error.code}. {hint}") from None
    except (URLError, TimeoutError):
        raise ValueError(f"No se pudo conectar con {provider}.") from None
    except (ValueError, UnicodeError):
        raise ValueError(f"{provider} devolvió una respuesta ilegible.") from None

def main() -> int:
    api_key = (os.getenv("GEMINI_API_KEY") or getpass("Clave de Gemini: ")).strip()
    if not api_key:
        print("Ingresá una clave de Google AI Studio.")
        return 1
    try:
        reply = generate_text("Respondé en una frase breve: ¿qué es una serie temporal?", api_key)
    except ValueError as error:
        print(error)
        return 1
    print(f"Conexión con {MODEL} confirmada.")
    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
