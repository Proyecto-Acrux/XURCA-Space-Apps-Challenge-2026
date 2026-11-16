"""NASA FIRMS detections filtered against the selected polygon."""

import csv
import hashlib
import io
import json
import os
import re
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from statistics import mean
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from ..configuration import directory
from .environmental_series import area_bounds, inside_area, days, read_text, selected_geometry, series
from .public_sources import number
from .regional_layers import temporal_layer

ENDPOINT = "https://firms.modaps.eosdis.nasa.gov/api/area/"
UNITS = {"frp": "MW", "brightness": "K", "bright_t31": "K", "bright_ti4": "K", "bright_ti5": "K",
         "scan": "km", "track": "km"}


def fetch_firms(source, investigation, start, end):
    token = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not token:
        raise ValueError("Configurá FIRMS_MAP_KEY antes de abrir Earth Detective.")
    upstream = source["upstream"]
    sensor = upstream.get("productId", "")
    if not re.fullmatch(r"[A-Z0-9_]+", sensor):
        raise ValueError("Ingresá el código oficial del sensor FIRMS.")
    field = upstream["variableId"].lower()
    geometry = selected_geometry(source, investigation, {"Polygon", "MultiPolygon"})
    bounds = ",".join(map(str, area_bounds(geometry)))
    signature = hashlib.sha256(json.dumps([sensor, str(start), str(end), geometry], sort_keys=True).encode()).hexdigest()[:24]
    folder = directory() / "downloads" / "firms"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sensor}-{signature}.csv"
    staged = None
    try:
        with NamedTemporaryFile(dir=folder, mode="w", encoding="utf-8", newline="", delete=False) as raw:
            staged = Path(raw.name)
            counts, values, events = extract(raw, token, sensor, field, geometry, bounds, start, end)
        staged.replace(path)
    except OSError as error:
        raise ValueError("No se pudieron guardar las detecciones FIRMS.") from error
    finally:
        if staged:
            staged.unlink(missing_ok=True)
    is_count = field == "count"
    raw_only = field == "all" or (not is_count and counts and not values)
    points = [] if raw_only else [
        {"month": day, "value": counts[day] if is_count else mean(values[day]) if values[day] else None}
        for day in days(start, end)
    ]
    label = "Detecciones diarias" if is_count else f"{field} (media diaria de detecciones)"
    if raw_only:
        label = "Detecciones FIRMS · CSV"
    unit = "detecciones" if is_count else UNITS.get(field, "Unidad sin verificar")
    result = series(source, "NASA FIRMS", sensor, "" if raw_only else unit, points, "Polígono", ENDPOINT)
    categorical = sorted({event[field] for event in events if isinstance(event.get(field), str)})
    layer = temporal_layer("events", geometry, start, end, "count" if field == "all" else field,
                           events=events, eventType="fire", categories={value: value for value in categorical},
                           label=field if field not in {"count", "all"} else None)
    return {**result, "label": label, "downloadPath": str(path), "map": layer,
            "message": f"CSV original filtrado al área. Detecciones recuperadas: {sum(counts.values())}."}


def extract(raw, token, sensor, field, geometry, bounds, start, end):
    counts = defaultdict(int)
    values = defaultdict(list)
    events = []
    writer = None
    first = start
    while first <= end:
        length = min(5, (end - first).days + 1)
        url = f"{ENDPOINT}csv/{quote(token, safe='')}/{sensor}/{bounds}/{length}/{first}"
        reader = csv.DictReader(io.StringIO(read_text(url, "NASA FIRMS")))
        if not {"longitude", "latitude", "acq_date"}.issubset(reader.fieldnames or ()):
            raise ValueError("FIRMS no devolvió un CSV válido. Revisá la clave y la cobertura del sensor.")
        if field not in {"all", "count"} and field not in reader.fieldnames:
            raise ValueError(f"El sensor {sensor} no publica el campo {field}.")
        if writer is None:
            writer = csv.DictWriter(raw, fieldnames=reader.fieldnames)
            writer.writeheader()
        elif reader.fieldnames != writer.fieldnames:
            raise ValueError("FIRMS cambió las columnas de la respuesta entre ventanas.")
        for row in reader:
            lon, lat = number(row["longitude"]), number(row["latitude"])
            if lon is None or lat is None or not inside_area(lon, lat, geometry):
                continue
            day = row["acq_date"]
            counts[day] += 1
            writer.writerow(row)
            value = number(row.get(field))
            utc = (row.get("acq_time") or "").strip().zfill(4)
            stamp = day + "T" + utc[:2] + ":" + utc[2:] + ":00Z" if row.get("acq_time") else day
            event = {"id": str(len(events)), "coordinates": [lon, lat], "date": stamp,
                     "quality": row.get("confidence"), "location": row.get("satellite")}
            if field not in {"count", "all"}:
                raw_value = row.get(field)
                event[field] = value
                if value is None and raw_value:
                    try:
                        float(raw_value)
                    except ValueError:
                        event[field] = raw_value
            events.append(event)
            if value is not None:
                values[day].append(value)
        first += timedelta(days=length)
    return counts, values, events
