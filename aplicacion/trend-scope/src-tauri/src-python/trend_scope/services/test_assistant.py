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

    def response(url, body):
        assert url == "https://example.test/interpret"
        assert body == {"question": "Humedad en San Luis", "language": "es", "context": "previous turns"}
        return {"message": "¿Humedad del aire o del suelo?", "changes": {}}

    monkeypatch.setattr(assistant, "post_json", response)
    result = assistant.interpret(assistant.AssistantQuestion(
        question="Humedad en San Luis", endpoint="https://example.test/interpret", context="previous turns"
    ))
    assert result["changes"] == {}
