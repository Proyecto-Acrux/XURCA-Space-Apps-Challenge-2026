"""Interpret a question and validate the assistant's structured response."""

import json
from datetime import date
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from jsonschema import Draft202012Validator, ValidationError as SchemaError

from .gemini import CONTRACT, post_json
from .assistant_providers import current_connection, generate
from .coverage import PRODUCTS


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    language: Literal["es", "en"] = "es"
    endpoint: Optional[str] = Field(default=None, max_length=512)
    context: str = Field(default="", max_length=18000)


def validate_proposal(proposal):
    try:
        Draft202012Validator(CONTRACT["schema"]).validate(proposal)
        changes = proposal["changes"]
        period = changes.get("time", {})
        for value in period.values():
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError()
        if period.get("start", "") > period.get("end", "9999-12-31"):
            raise ValueError()
        if sum(key in changes for key in ("point", "place", "polygon")) > 1:
            raise ValueError()
        point = changes.get("point")
        if point and not (-180 <= point["longitude"] <= 180 and -90 <= point["latitude"] <= 90):
            raise ValueError()
        polygon = changes.get("polygon")
        if polygon is not None and (not 3 <= len(polygon) <= 100 or any(
            len(p) != 2 or not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90) for p in polygon
        )):
            raise ValueError()
        json.dumps(proposal, allow_nan=False)
    except (SchemaError, ValueError, TypeError, KeyError):
        raise ValueError("La IA devolvió una propuesta inválida. No se aplicaron cambios; reformulá el pedido.") from None
    return proposal


def interpret(body: AssistantQuestion) -> dict:
    question = body.question.strip()
    if not question:
        raise ValueError("Escribí una pregunta para el asistente.")
    prompt = {"question": question, "language": body.language, "context": body.context}
    connection = current_connection()
    if connection:
        instruction = CONTRACT["instruction"] + "\nAvailable coverage metadata: " + json.dumps(PRODUCTS)
        proposal = generate(connection, json.dumps(prompt, ensure_ascii=False), instruction)
    elif body.endpoint:
        uri = urlparse(body.endpoint)
        if uri.scheme != "https" or not uri.hostname or uri.username or uri.password:
            raise ValueError("El servicio del asistente requiere una URL HTTPS.")
        proposal = post_json(body.endpoint, prompt)
    else:
        raise ValueError("Abrí Conectar IA y elegí un proveedor para empezar a conversar.")
    return validate_proposal(proposal)
