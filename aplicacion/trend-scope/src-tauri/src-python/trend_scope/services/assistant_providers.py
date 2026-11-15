"""Provider adapters and process-local credentials (never part of a project)."""

import json
import os
from copy import deepcopy
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from .gemini import CONTRACT, post_json

DEFAULTS = {"gemini": CONTRACT["model"], "openai": "gpt-4.1-mini"}
_connection = None
_lock = Lock()


class Connection(BaseModel):
    provider: Literal["gemini", "openai"]
    model: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    apiKey: SecretStr


def current_connection():
    with _lock:
        if _connection:
            return _connection.model_copy(deep=True)
    for provider in DEFAULTS:
        key = os.getenv(provider.upper() + "_API_KEY", "").strip()
        if key:
            return Connection(provider=provider, model=DEFAULTS[provider], apiKey=key)
    return None


def connection_status():
    connection = current_connection()
    return {"configured": connection is not None, "provider": connection.provider if connection else None,
            "model": connection.model if connection else None, "defaults": DEFAULTS}


def configure_connection(connection):
    global _connection
    key = connection.apiKey.get_secret_value().strip()
    if not key or len(key) > 512 or any(char.isspace() for char in key):
        raise ValueError("Ingresá una clave API válida, sin espacios.")
    # Verify before replacing a working connection. Do not return the key or provider response.
    from .assistant import validate_proposal
    validate_proposal(generate(connection.model_copy(update={"apiKey": SecretStr(key)}),
                              "Return message 'Conexión verificada' and empty changes.", CONTRACT["instruction"]))
    with _lock:
        _connection = connection.model_copy(update={"apiKey": SecretStr(key)})
    return connection_status()


def forget_connection():
    global _connection
    with _lock:
        _connection = None
    return connection_status()


def strict_schema(schema):
    """Represent omitted patch fields as null for OpenAI's strict schema."""
    result = deepcopy(schema)
    if result.get("type") == "object":
        required = result.get("required", [])
        result["properties"] = {
            key: strict_schema(value) if key in required else {"anyOf": [strict_schema(value), {"type": "null"}]}
            for key, value in result["properties"].items()
        }
        result["required"] = list(result["properties"])
        result["additionalProperties"] = False
    elif result.get("type") == "array":
        result["items"] = strict_schema(result["items"])
    return result


def without_nulls(value):
    if isinstance(value, dict):
        return {key: without_nulls(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [without_nulls(item) for item in value]
    return value


def generate(connection, prompt, instruction):
    key = connection.apiKey.get_secret_value()
    if connection.provider == "gemini":
        data = post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{connection.model}:generateContent",
            {"systemInstruction": {"parts": [{"text": instruction}]},
             "contents": [{"role": "user", "parts": [{"text": prompt}]}],
             "generationConfig": {"responseMimeType": "application/json",
                                  "responseJsonSchema": CONTRACT["schema"], "maxOutputTokens": 4096}},
            {"x-goog-api-key": key}, provider="Gemini")
        candidates = data.get("candidates") or []
        candidate = candidates[0] if candidates else {}
        if candidate.get("finishReason") != "STOP":
            raise ValueError("Gemini no completó la respuesta. Probá reformular el pedido.")
        reply = "".join(part.get("text", "") for part in candidate.get("content", {}).get("parts", [])
                        if not part.get("thought"))
    else:
        data = post_json("https://api.openai.com/v1/responses", {
            "model": connection.model, "instructions": instruction, "input": prompt, "store": False,
            "max_output_tokens": 4096,
            "text": {"format": {"type": "json_schema", "name": "earth_configuration",
                                "strict": True, "schema": strict_schema(CONTRACT["schema"])}}},
            {"Authorization": f"Bearer {key}"}, provider="OpenAI")
        if data.get("status") != "completed":
            raise ValueError("OpenAI no completó la respuesta. Probá reformular el pedido.")
        content = [part for item in data.get("output", []) if item.get("type") == "message"
                   for part in item.get("content", [])]
        if any(part.get("type") == "refusal" for part in content):
            raise ValueError("El proveedor no pudo atender ese pedido. Probá reformularlo.")
        reply = "".join(part.get("text", "") for part in content if part.get("type") == "output_text")
    try:
        proposal = json.loads(reply)
        return without_nulls(proposal) if connection.provider == "openai" else proposal
    except (ValueError, TypeError):
        raise ValueError("El proveedor no devolvió una configuración JSON completa. No se aplicaron cambios.") from None
