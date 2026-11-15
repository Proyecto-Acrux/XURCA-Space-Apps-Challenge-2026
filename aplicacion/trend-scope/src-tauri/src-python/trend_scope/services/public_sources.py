"""Public station, surface-water, and Argentine place lookups."""

import csv
import io
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def request_json(endpoint, provider, **parameters):
    url = endpoint + "?" + urlencode(parameters)
    try:
        with urlopen(url, timeout=25) as response:
            return json.load(response), url
    except HTTPError as error:
        raise ValueError(f"{provider} rechazó la solicitud (HTTP {error.code}). Revisá el identificador y las fechas.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError(f"No se pudo obtener una respuesta válida de {provider}.") from error


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result not in (-999, -9999, -999999999999) else None


def fetch_public_series(source, period):
    route = source["access"]
    upstream = source.get("upstream") or {}
    variable = upstream.get("variableId")
    selectors = upstream.get("selectors") or {}
    start, end = (date.fromisoformat(period[key]) for key in ("start", "end"))
    if start > end:
        raise ValueError("La fecha inicial debe ser anterior o igual a la final.")

    if route in {"noaa.ncei.station", "noaa.ncei.daily"}:
        provider = "NOAA NCEI"
        station = selectors.get("stationId", "").strip().upper()
        daily = route == "noaa.ncei.daily"
        units = {"PRCP": "mm", "TAVG": "°C", "TMAX": "°C", "TMIN": "°C", "SNOW": "mm", "SNWD": "mm"}
        if not re.fullmatch(r"[A-Z0-9]{11}", station) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", variable or ""):
            raise ValueError("Ingresá un ID de estación NOAA de 11 caracteres y una variable admitida.")
        rows, url = request_json(
            "https://www.ncei.noaa.gov/access/services/data/v1", provider,
            dataset="daily-summaries" if daily else "global-summary-of-the-month", stations=station,
            startDate=(start if daily else start.replace(day=1)).isoformat(),
            endDate=end.isoformat(), dataTypes=variable, units="metric", format="json",
        )
        by_date = {row["DATE"]: number(row.get(variable)) for row in rows}
        if daily:
            dates = ((start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1))
        else:
            dates = (f"{year:04d}-{month:02d}" for year in range(start.year, end.year + 1)
                     for month in range(1, 13)
                     if (start.year, start.month) <= (year, month) <= (end.year, end.month))
        points = [{"month": key, "value": by_date.get(key)} for key in dates]
        location = f"Estación {station}"
    else:
        provider = "NASA SWOT / Hydrocron"
        feature = selectors.get("featureType")
        identifier = selectors.get("featureId", "").strip()
        if feature not in ("Reach", "PriorLake") or not re.fullmatch(r"[0-9]{10,11}", identifier):
            raise ValueError("Ingresá el ID oficial de un tramo de río o lago SWOT.")
        units = {"wse": "m", "area_total": "km²"}
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", variable or ""):
            raise ValueError("La variable elegida no corresponde al tipo de río o lago.")
        field = "reach_id" if feature == "Reach" else "lake_id"
        payload, url = request_json(
            "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries", provider,
            feature=feature, feature_id=identifier, fields=f"{field},time_str,{variable}",
            output="csv", start_time=f"{start}T00:00:00Z", end_time=f"{end}T23:59:59Z",
            collection_name="SWOT_L2_HR_RiverSP_D" if feature == "Reach" else "SWOT_L2_HR_LakeSP_D",
        )
        rows = list(csv.DictReader(io.StringIO(payload.get("results", {}).get("csv") or "")))
        unit = next((row[f"{variable}_units"] for row in rows if row.get(f"{variable}_units")), None)
        if unit:
            units[variable] = unit.replace("km^2", "km²")
        points = sorted(
            ({"month": row["time_str"], "value": number(row.get(variable))}
             for row in rows if row.get("time_str") and row["time_str"] != "no_data"),
            key=lambda point: point["month"],
        )
        location = f"{'Tramo de río' if feature == 'Reach' else 'Lago'} {identifier}"

    return {
        "id": source["id"], "provider": provider, "variable": variable, "points": points,
        "unit": units.get(variable, "Unidad sin verificar"), "location": location, "url": url,
        "retrievedAt": datetime.now(timezone.utc).isoformat(),
        "cadence": {"nasa.swot.hydrocron": "overpass", "noaa.ncei.daily": "daily"}.get(route, "monthly"),
    }


def find_places(query, kind, language="es"):
    if kind not in ("localidades", "provincias") or not 2 <= len(query.strip()) <= 100:
        raise ValueError("Ingresá entre 2 y 100 caracteres para buscar un lugar.")
    if kind == "localidades":
        return find_world_cities(query, language)
    payload, _ = request_json(
        "https://apis.datos.gob.ar/georef/api/v2.0/" + kind,
        "Georef Argentina", nombre=query.strip(), max=8,
    )
    return [
        {"id": item["id"], "name": item["nombre"], "province": (item.get("provincia") or {}).get("nombre"),
         "coordinates": [item["centroide"]["lon"], item["centroide"]["lat"]]}
        for item in payload[kind]
        if (item.get("centroide") or {}).get("lon") is not None and item["centroide"].get("lat") is not None
    ]

def find_world_cities(query, language):
    payload, _ = request_json(
        "https://photon.komoot.io/api/", "Photon",
        q=query.strip(), layer="city", limit=8, lang="en" if language == "en" else "default",
    )
    places = []
    for feature in payload.get("features", []):
        props = feature["properties"]
        if not props.get("name") or feature["geometry"]["type"] != "Point":
            continue
        places.append({
            "id": f'{props["osm_type"]}{props["osm_id"]}',
            "name": props["name"], "province": props.get("state"),
            "country": props.get("country"), "coordinates": feature["geometry"]["coordinates"],
        })
    return places
