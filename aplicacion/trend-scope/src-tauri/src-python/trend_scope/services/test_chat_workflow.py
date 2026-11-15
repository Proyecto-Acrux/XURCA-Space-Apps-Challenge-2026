import json
from datetime import date

import pytest
from jsonschema import Draft202012Validator

from . import assistant, assistant_providers as providers
from .acquisition import validate_investigation
from .evidence import summarize_series
from .gemini import CONTRACT


@pytest.fixture(autouse=True)
def clean_connection(monkeypatch):
    monkeypatch.setattr(providers, "_connection", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.mark.parametrize("changes", [
    {"execute": "anything"}, {"time": {"start": "2024-02-30"}},
    {"time": {"start": "2024-01-01", "end": "2020-01-01"}},
    {"point": {"longitude": 500, "latitude": 0}},
    {"point": {"longitude": float("nan"), "latitude": 0}},
    {"point": {"longitude": 1, "latitude": 2}, "place": {"name": "X", "kind": "localidades"}},
    {"sources": [{"id": "x", "secret": "bad"}]},
])
def test_invalid_proposals_never_reach_workspace(changes):
    with pytest.raises(ValueError, match="No se aplicaron cambios"):
        assistant.validate_proposal({"message": "Propuesta", "changes": changes})


def test_openai_adapter_normalizes_only_optional_null_fields(monkeypatch):
    def response(url, payload, headers, provider):
        assert url == "https://api.openai.com/v1/responses"
        assert headers == {"Authorization": "Bearer test-key"}
        assert payload["store"] is False
        schema = payload["text"]["format"]["schema"]
        changes = {key: None for key in CONTRACT["schema"]["properties"]["changes"]["properties"]}
        changes["time"] = {"start": "2020-01-01", "end": None}
        proposal = {"message": "Cambio de inicio", "changes": changes}
        Draft202012Validator(schema).validate(proposal)
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(proposal)}]}]}
    monkeypatch.setattr(providers, "post_json", response)
    result = providers.generate(providers.Connection(provider="openai", model="gpt-4.1-mini", apiKey="test-key"), "hello", "instructions")
    assert assistant.validate_proposal(result)["changes"] == {"time": {"start": "2020-01-01"}}


def test_gemini_refuses_truncated_response(monkeypatch):
    monkeypatch.setattr(providers, "post_json", lambda *a, **kw: {"candidates": [{"finishReason": "MAX_TOKENS"}]})
    with pytest.raises(ValueError, match="no completó"):
        providers.generate(providers.Connection(provider="gemini", model="test", apiKey="test"), "x", "x")


def test_failed_connection_keeps_previous_key_and_status_never_returns_it(monkeypatch):
    previous = providers.Connection(provider="gemini", model="test", apiKey="old-secret")
    monkeypatch.setattr(providers, "_connection", previous)
    def failure(*args):
        raise ValueError("No connection")
    monkeypatch.setattr(providers, "generate", failure)
    with pytest.raises(ValueError):
        providers.configure_connection(providers.Connection(provider="openai", model="test", apiKey="new-secret"))
    assert providers.current_connection() == previous
    assert "secret" not in json.dumps(providers.connection_status())


def test_conversation_and_evidence_reach_selected_provider(monkeypatch):
    monkeypatch.setattr(providers, "_connection", providers.Connection(provider="openai", model="test", apiKey="secret"))
    context = {"history": [{"role": "user", "text": "Temperatura en el punto seleccionado"}],
               "results": [{"mean": 20, "unit": "C", "validCount": 12}]}
    def generate(connection, prompt, instruction):
        assert connection.provider == "openai"
        assert json.loads(json.loads(prompt)["context"]) == context
        assert "coverage" in instruction
        return {"message": "El promedio disponible es 20 C.", "changes": {}}
    monkeypatch.setattr(assistant, "generate", generate)
    assert assistant.interpret(assistant.AssistantQuestion(question="Explicame", context=json.dumps(context)))["changes"] == {}


def test_full_series_summary_uses_elapsed_time_and_excludes_missing():
    start = date(2000, 1, 1)
    stamps = ["2000-01-01", "2002-01-01", "2010-01-01"]
    points = [{"month": stamp, "value": 10 + 2 * (date.fromisoformat(stamp) - start).days / 365.2425} for stamp in stamps]
    points += [{"month": "2001-01-01", "value": None}, {"month": "2003-01-01", "value": float("nan")}]
    summary = summarize_series({"id": "test", "unit": "C", "points": points, "url": "https://source.test"})
    assert summary["validCount"] == 3
    assert summary["missingOrInvalidCount"] == 2
    assert summary["trend"]["perYear"] == pytest.approx(2)
    assert summary["trend"]["rSquared"] == pytest.approx(1)
    assert summary["trend"]["confidenceInterval"] is None
    assert summary["url"] == "https://source.test"


def test_empty_and_constant_series():
    assert "mean" not in summarize_series({"points": []})
    summary = summarize_series({"points": [{"month": f"2020-0{n}", "value": 5} for n in range(1, 4)]})
    assert summary["trend"]["perYear"] == 0
    assert summary["trend"]["rSquared"] is None


def test_incomplete_configuration_is_rejected_before_fetch():
    with pytest.raises(ValueError, match="Revisá la investigación"):
        validate_investigation({"schemaVersion": 1, "time": {"start": "2000-01-01", "end": "2020-01-01"},
                                "sources": [{"id": "temperature", "access": "nasa.power.monthly", "upstream": {"variableId": "T2M"}}],
                                "geography": {"selection": {"features": []}}})


@pytest.mark.parametrize("route", ["noaa.ncei.station", "nasa.swot.hydrocron", "usgs.earthquakes", "noaa.cpc.oni"])
def test_merged_sources_allow_geographic_resolution_and_new_routes(route):
    validate_investigation({"schemaVersion": 1, "time": {"start": "2000-01-01", "end": "2020-01-01"},
        "sources": [{"id": "test", "access": route, "upstream": {"geometryId": "point", "variableId": "test", "selectors": {}}}],
        "geography": {"selection": {"features": [{"id": "point", "geometry": {"type": "Point", "coordinates": [-66, -33]}}]}}})
