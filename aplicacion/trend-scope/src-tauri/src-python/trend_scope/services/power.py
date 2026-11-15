"""Retrieve monthly gridded climate series from NASA POWER."""

import json
import math
import re
from datetime import date, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .catalog import acquisition_gaps

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/monthly/point"
ROUTE = "nasa.power.monthly"



def fetch_series(investigation: dict) -> list[dict]:
    sources = investigation.get("sources") or []
    if not sources or any(source.get("access") != ROUTE for source in sources):
        raise ValueError("Seleccioná variables de NASA POWER para realizar la consulta.")
    period = investigation["time"]
    if period.get("resolution") != "Mensual":
        raise ValueError("Esta consulta admite resolución mensual.")
    start, end = (date.fromisoformat(period[key]) for key in ("start", "end"))
    today = date.today()
    if start > end or start.year < 1981 or end.year >= today.year:
        raise ValueError(f"Elegí fechas entre 1981 y {today.year - 1}, en orden.")
    features = investigation["geography"]["selection"]["features"]
    queries = {}
    for source in sources:
        gaps = acquisition_gaps(source, investigation)
        if gaps:
            raise ValueError("Completá los datos de la fuente: " + ", ".join(gaps))
        upstream = source["upstream"]
        variable = upstream["variableId"]
        community = upstream["selectors"]["community"]
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", variable) or community not in {"AG", "RE", "SB"}:
            raise ValueError("La variable o comunidad de NASA POWER no está habilitada.")
        feature = next(item for item in features if item["id"] == upstream["geometryId"])
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise ValueError("Las coordenadas están fuera del rango WGS 84.")
        queries.setdefault((longitude, latitude, community), []).append(source)

    results = []
    batches = []
    for (longitude, latitude, community), group in queries.items():
        for offset in range(0, len(group), 20):
            batches.append((longitude, latitude, community, group[offset:offset + 20]))
    for longitude, latitude, community, group in batches:
        variables = list(dict.fromkeys(source["upstream"]["variableId"] for source in group))
        url = ENDPOINT + "?" + urlencode({
            "parameters": ",".join(variables), "community": community,
            "longitude": longitude, "latitude": latitude, "start": start.year,
            "end": end.year, "format": "JSON",
        })
        try:
            with urlopen(url, timeout=25) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise ValueError(f"NASA POWER rechazó la consulta (HTTP {error.code}).") from error
        except (URLError, TimeoutError) as error:
            raise ValueError("No se pudo conectar con NASA POWER. Probá de nuevo.") from error

        retrieved_at = datetime.now(timezone.utc).isoformat()
        fill = payload.get("header", {}).get("fill_value", -999)
        returned_series = payload.get("properties", {}).get("parameter", {})
        for source in group:
            variable = source["upstream"]["variableId"]
            raw = returned_series.get(variable)
            unit = payload.get("parameters", {}).get(variable, {}).get("units")
            if not isinstance(raw, dict) or not unit:
                raise ValueError(f"NASA POWER no devolvió una serie con unidades para {variable}.")
            points = []
            for year in range(start.year, end.year + 1):
                for month in range(1, 13):
                    if (year, month) < (start.year, start.month) or (year, month) > (end.year, end.month):
                        continue
                    value = raw.get(f"{year:04d}{month:02d}")
                    if not isinstance(value, (int, float)) or not math.isfinite(value) or value == fill:
                        value = None
                    points.append({"month": f"{year:04d}-{month:02d}", "value": value})
            results.append({
                "id": source["id"], "variable": variable, "unit": unit, "points": points,
                "provider": "NASA POWER", "coordinates": [longitude, latitude],
                "url": url, "retrievedAt": retrieved_at,
            })
    return results
