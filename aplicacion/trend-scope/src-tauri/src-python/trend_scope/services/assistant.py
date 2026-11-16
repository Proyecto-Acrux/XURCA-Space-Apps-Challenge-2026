"""Interpret a question and validate the assistant's structured response."""

import json
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field
from jsonschema import Draft202012Validator, ValidationError as SchemaError

from .gemini import CONTRACT, post_json

WORKER_URL = "https://gemini-tauri-api.bilbaojuani.workers.dev"


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    language: Literal["es", "en"] = "es"
    feedback: str = Field(default="", max_length=700)
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
        if sum(key in changes for key in ("point", "place", "places", "polygon")) > 1:
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
    request = {
        "question": question, "language": body.language,
        "context": body.context, "previous_attempt_feedback": body.feedback,
    }
    prompt = (
        CONTRACT["instruction"]
        + "\nRespond with a single JSON object matching this schema. Use no Markdown."
        + "\nSchema: " + json.dumps(CONTRACT["schema"], separators=(",", ":"))
        + "\nRequest data: " + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    answer = post_json(WORKER_URL, {"prompt": prompt}, {"User-Agent": "EarthDetective/1.0"}).get("answer")
    try:
        if not isinstance(answer, str):
            raise ValueError()
        answer = answer.strip()
        if answer.startswith(("```json\n", "```\n")) and answer.endswith("```"):
            answer = answer.split("\n", 1)[1][:-3].strip()
        proposal = json.loads(answer)
    except (ValueError, TypeError):
        raise ValueError("La IA devolvió una propuesta inválida.") from None
    return validate_proposal(proposal)
