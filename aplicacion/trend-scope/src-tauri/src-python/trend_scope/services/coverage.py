"""Evaluate a requested variable against the packaged coverage catalog."""

import json
from datetime import date, timedelta
from importlib.resources import files
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

VARIABLES = {
    "soil-moisture": {
        "GWETROOT", "soil_moisture_0_to_7cm_mean", "soil_moisture_7_to_28cm_mean",
        "soil_moisture_28_to_100cm_mean", "soil_moisture_100_to_255cm_mean",
    },
    "precipitation": {"PRECTOTCORR", "PRCP", "precipitation_sum", "precipitation"},
    "oni": {"anomaly"},
    "nino34-temperature": {"total"},
    "roni": {"roni"},
    "earthquake-count": {"count"},
    "earthquake-magnitude": {"magnitude"},
    "earthquake-depth": {"depth"},
    "relative-humidity": {"RH2M"},
    "temperature": {"T2M", "TAVG"},
    "temperature-max": {"temperature_2m_max"},
    "temperature-min": {"temperature_2m_min"},
    "wind-speed": {"WS2M"},
    "solar-radiation": {"ALLSKY_SFC_SW_DWN"},
    "reference-et": {"et0_fao_evapotranspiration"},
    "water-elevation": {"wse"},
    "water-area": {"area_total"},
}
PRODUCTS = json.loads(files(__package__).joinpath("source-coverage.json").read_text("utf-8"))["products"]


class CoverageRequest(BaseModel):
    variable: str = Field(min_length=1, max_length=64)
    start: date
    end: date
    scope: Literal["land", "sea", "area", "station", "river", "lake"]

    @model_validator(mode="after")
    def ordered_period(self):
        if self.start > self.end:
            raise ValueError("La fecha inicial debe ser anterior o igual a la final.")
        return self


def coverage(request: CoverageRequest, today: Optional[date] = None) -> list[dict]:
    today = today or date.today()
    codes = VARIABLES.get(request.variable, set())
    matches = []
    for product in PRODUCTS:
        variables = [code for code in product["variables"] if code in codes]
        if not variables:
            continue
        start = date.fromisoformat(product.get("from") or product["collectionFrom"])
        end = today - timedelta(days=product.get("publicationLagDays", 0))
        if product.get("through"):
            end = date.fromisoformat(product["through"])
        if product.get("endRule") == "previous-calendar-year":
            end = date(today.year - 1, 12, 31)
        status, reason = assess(product, request, start, end)
        matches.append({
            "access": product["access"], "product": product["product"], "variables": variables,
            "selection": product["selection"], "cadence": product["cadence"],
            "status": status, "reason": reason, "from": start.isoformat(), "through": end.isoformat(),
            "reference": product["reference"],
        })
    return matches


def assess(product, request, start, end):
    selection = product["selection"]
    if request.scope == "area" and selection not in {"Point/Area", "Area", "Index"}:
        return "incompatible", "area"
    if selection == "Area" and request.scope != "area":
        return "incompatible", "area"
    if product.get("maxDays") and (request.end - request.start).days + 1 > product["maxDays"]:
        return "incompatible", "period_limit"
    if selection == "Point/Area":
        if request.scope not in {"land", "area"}:
            return "incompatible", "land_only"
    elif selection in {"Station", "Reach", "PriorLake"}:
        expected = {"Station": "station", "Reach": "river", "PriorLake": "lake"}[selection]
        if request.scope != expected:
            return "incompatible", "identifier"
    elif selection == "Point" and request.scope not in ("land", "sea"):
        return "incompatible", "point"
    if request.scope == "sea":
        if product["geography"] == "land-grid" or request.variable == "soil-moisture":
            return "incompatible", "land_only"
    if request.end < start or request.start > end:
        return "incompatible", "outside_period"
    if request.start < start or request.end > end:
        return "partial", "partial_period"
    if request.scope == "sea" and product["access"] == "openmeteo.archive.daily":
        return "unverified", "marine_cell"
    if product.get("requiresEntityCoverage"):
        return "unverified", "entity"
    if product.get("publisherCatalog") or product["geography"] == "argentina-land-grid":
        return "unverified", "catalog"
    return "compatible", "catalog"
