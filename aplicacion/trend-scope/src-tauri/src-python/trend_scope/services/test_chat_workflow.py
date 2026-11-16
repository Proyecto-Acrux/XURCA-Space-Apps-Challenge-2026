import json
from datetime import date

import pytest
from jsonschema import Draft202012Validator

from . import assistant
from .acquisition import validate_investigation
from .evidence import summarize_series
from .gemini import CONTRACT


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
