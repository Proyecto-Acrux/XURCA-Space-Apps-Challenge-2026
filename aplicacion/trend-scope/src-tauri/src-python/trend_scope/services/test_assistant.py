import json
from datetime import date

import pytest

from trend_scope.services import assistant
from trend_scope.services.coverage import CoverageRequest, coverage


@pytest.mark.parametrize(("scope", "expected"), [
    ("land", ("compatible", "catalog")),
    ("area", ("incompatible", "area")),
    ("sea", ("incompatible", "land_only")),
])
def test_argentine_soil_moisture(scope, expected):
    request = CoverageRequest(variable="soil-moisture", start="2000-01-01", end="2025-12-31", scope=scope)
    matches = coverage(request, today=date(2026, 11, 14))
    assert len(matches) == 2
    assert {(row["status"], row["reason"]) for row in matches} == {expected}


def test_partial_period_and_unverified_station():
    request = CoverageRequest(variable="solar-radiation", start="1980-01-01", end="2025-12-31", scope="land")
    assert coverage(request, date(2026, 11, 14))[0]["status"] == "partial"
    request = CoverageRequest(variable="precipitation", start="2000-01-01", end="2025-12-31", scope="station")
    station = next(row for row in coverage(request) if row["selection"] == "Station")
    assert station["status"] == "unverified"


def test_proxy_interpretation_validates_response_without_local_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def response(url, body, headers):
        assert url == assistant.WORKER_URL
        assert set(body) == {"prompt"}
        request = json.loads(body["prompt"].split("\nRequest data: ", 1)[1])
        assert request["question"] == "Humedad en San Luis"
        assert request["context"] == "previous turns"
        return {"answer": json.dumps({"message": "¿Humedad del aire o del suelo?", "changes": {}})}

    monkeypatch.setattr(assistant, "post_json", response)
    result = assistant.interpret(assistant.AssistantQuestion(
        question="Humedad en San Luis", context="previous turns"
    ))
    assert result["changes"] == {}


def test_multiple_places_contract():
    proposal = {"message": "Buscaré las localidades.", "changes": {"places": [
        {"name": "San Luis, San Luis, Argentina", "kind": "localidades"},
        {"name": "El Volcán, San Luis, Argentina", "kind": "localidades"},
    ]}}
    assert assistant.validate_proposal(proposal) == proposal
    with pytest.raises(ValueError):
        assistant.validate_proposal({"message": "x", "changes": {"places": []}})
    with pytest.raises(ValueError):
        assistant.validate_proposal({"message": "x", "changes": {
            **proposal["changes"], "point": {"longitude": -66, "latitude": -33}}})


def test_geocoder_prefers_town_over_duplicate_boundaries(monkeypatch):
    from trend_scope.services import public_sources
    def feature(key, osm_id, state="San Luis"):
        return {"properties": {"name": "San Luis", "state": state, "country": "Argentina",
                "osm_key": key, "osm_type": "R", "osm_id": osm_id},
                "geometry": {"type": "Point", "coordinates": [-66.33, -33.3]}}
    monkeypatch.setattr(public_sources, "request_json", lambda *args, **kwargs: ({"features": [
        feature("place", 1), feature("boundary", 2), feature("boundary", 3),
        feature("place", 4, "Salta")
    ]}, "test"))
    found = public_sources.find_world_cities("San Luis, San Luis, Argentina", "es")
    assert [item["id"] for item in found] == ["R1", "R4"]


def test_proxy_receives_feedback_when_correcting_a_proposal(monkeypatch):
    def response(url, body, headers):
        request = json.loads(body["prompt"].split("\nRequest data: ", 1)[1])
        assert request["question"] == "Radiación solar"
        assert request["previous_attempt_feedback"] == "Correct the invalid proposal."
        return {"answer": "```json\n" + json.dumps({"message": "¿Qué período querés consultar?", "changes": {}}) + "\n```"}

    monkeypatch.setattr(assistant, "post_json", response)
    result = assistant.interpret(assistant.AssistantQuestion(
        question="Radiación solar", feedback="Correct the invalid proposal.",

    ))
    assert result["changes"] == {}
