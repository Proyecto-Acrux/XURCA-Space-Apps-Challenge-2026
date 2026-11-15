"""Resolve a map selection to provider IDs before requesting observations."""

import json
import ssl
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .environmental_series import INA, PSMSL, area_bounds, inside_area, read_text, selected_geometry
from .public_sources import request_json

NOAA_STATIONS = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
SWOT_CATALOG = "https://arcgis.cuahsi.org/arcgis/rest/services/SWOT/"
SWOT_LAYERS = {"Reach": ("world_SWORD_reaches_mercator_v17b", "reach_id", "20"),
               "PriorLake": ("SWOT_pld_v202", "lake_id_Double", "10")}
ENTITY_ROUTES = {"noaa.ncei.station", "noaa.ncei.daily", "nasa.swot.hydrocron",
                 "argentina.ina.series", "psmsl.rlr.monthly"}
MAX_CANDIDATES = 12


@lru_cache(maxsize=1)
def noaa_stations():
    return tuple((row[:11], row[41:71].strip(), float(row[21:30]), float(row[12:20]))
                 for row in read_text(NOAA_STATIONS, "Catálogo NOAA").splitlines() if len(row) >= 71)


@lru_cache(maxsize=1)
def tide_stations():
    stations = []
    for line in read_text(PSMSL + "filelist.txt", "Catálogo PSMSL").splitlines():
        fields = line.split(";")
        if len(fields) >= 7:
            identifier, latitude, longitude, name = (field.strip() for field in fields[:4])
            stations.append((identifier, name, float(longitude), float(latitude)))
    return tuple(stations)


@lru_cache(maxsize=16)
def ina_series(variable):
    result, _ = request_json(INA.rstrip("/"), "Catálogo INA", format="geojson", var_id=variable)
    return result["features"]


def ina_variables():
    result, _ = request_json("https://alerta.ina.gov.ar/a5/obs/variables", "Catálogo INA")
    return sorted([{"id": f"var-{row['id']}", "label": row["nombre"]}
                   for row in result if row.get("type") == "num" and row.get("nombre")],
                  key=lambda row: row["label"].casefold())


def distance_km(origin, target):
    lon1, lat1, lon2, lat2 = (radians(value) for value in (*origin, *target))
    angle = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 12742 * asin(min(1, sqrt(angle)))


def center(geometry):
    if geometry["type"] == "Point":
        return geometry["coordinates"][:2]
    west, south, east, north = area_bounds(geometry)
    return (west + east) / 2, (south + north) / 2


def rank_points(rows, geometry, radius):
    origin = center(geometry)
    matches = []
    for identifier, name, lon, lat in rows:
        if geometry["type"] != "Point" and not inside_area(lon, lat, geometry):
            continue
        distance = distance_km(origin, (lon, lat))
        if geometry["type"] != "Point" or distance <= radius:
            matches.append((distance, identifier, name))
    return sorted(matches)[:MAX_CANDIDATES]


def arcgis_polygon(geometry):
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    rings = []
    for polygon in polygons:
        for i, ring in enumerate(polygon):
            area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
            rings.append(list(reversed(ring)) if (area > 0) == (i == 0) else ring)
    return {"rings": rings, "spatialReference": {"wkid": 4326}}


def geometry_distance(origin, shape):
    if shape["type"] in {"Polygon", "MultiPolygon"} and inside_area(*origin, shape):
        return 0.0
    kind, coordinates = shape["type"], shape["coordinates"]
    if kind == "LineString":
        paths = [coordinates]
    elif kind in {"MultiLineString", "Polygon"}:
        paths = coordinates
    else:
        paths = [ring for polygon in coordinates for ring in polygon]
    scale = max(1e-6, cos(radians(origin[1])))
    best = float("inf")
    for path in paths:
        for a, b in zip(path, path[1:]):
            x, y = (a[0] - origin[0]) * scale, a[1] - origin[1]
            dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
            length = dx * dx + dy * dy
            offset = max(0, min(1, -(x * dx + y * dy) / length)) if length else 0
            interpolated = a[0] + (b[0] - a[0]) * offset, a[1] + dy * offset
            best = min(best, distance_km(origin, interpolated))
    return best


def swot_candidates(feature, geometry):
    layer, field, radius = SWOT_LAYERS[feature]
    point = geometry["type"] == "Point"
    origin = center(geometry)
    name_field = "names" if feature == "PriorLake" else "river_name"
    params = {"f": "geojson", "where": "1=1", "outFields": f"{field},{name_field}",
              "outSR": 4326, "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
              "geometryType": "esriGeometryPoint" if point else "esriGeometryPolygon",
              "geometry": ",".join(map(str, origin)) if point else json.dumps(arcgis_polygon(geometry))}
    if point:
        params.update(distance=radius, units="esriSRUnit_Kilometer")
    url = SWOT_CATALOG + f"{layer}/FeatureServer/0/query?" + urlencode(params)
    try:
        try:
            import truststore
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            context = ssl.create_default_context()
        with urlopen(url, context=context, timeout=30) as response:
            result = json.load(response)
    except (URLError, TimeoutError, ValueError) as error:
        raise ValueError("No se pudo consultar el catálogo geográfico de SWOT.") from error
    if "features" not in result:
        raise ValueError("El catálogo geográfico de SWOT no pudo resolver esta selección.")
    if result.get("exceededTransferLimit") or (result.get("properties") or {}).get("exceededTransferLimit"):
        raise ValueError("El área contiene demasiadas entidades SWOT. Seleccioná un área más pequeña.")
    candidates = []
    for item in result["features"]:
        properties = item["properties"]
        identifier = properties.get(field)
        if identifier is None or not item.get("geometry"):
            continue
        identifier = str(int(identifier))
        label = properties.get(name_field) or ("Tramo" if feature == "Reach" else "Lago")
        distance = geometry_distance(origin, item["geometry"])
        if not point or distance <= float(radius):
            candidates.append((distance, identifier, label))
    return sorted(candidates)[:MAX_CANDIDATES]


def candidates_for(source, investigation, start, end):
    route = source["access"]
    geometry = selected_geometry(source, investigation, {"Point", "Polygon", "MultiPolygon"})
    upstream = source["upstream"]
    if route.startswith("noaa."):
        return rank_points(noaa_stations(), geometry, 150)
    if route == "psmsl.rlr.monthly":
        return rank_points(tide_stations(), geometry, 150)
    if route == "argentina.ina.series":
        variable = upstream["variableId"]
        # Projects previously stored raw series IDs. Migrate them to the variable.
        if variable.isdecimal():
            metadata, _ = request_json(INA + variable, "Catálogo INA")
            variable = str((metadata.get("var") or {}).get("id", ""))
        else:
            variable = variable.removeprefix("var-")
        rows = []
        for entry in ina_series(variable):
            props = entry["properties"]
            first, last = props.get("timestart"), props.get("timeend")
            if (not props.get("public") or str(props.get("var_id")) != variable or props.get("proc_id") != 1
                    or not first or not last or first[:10] > str(end) or last[:10] < str(start)):
                continue
            if not entry.get("geometry") or entry["geometry"].get("type") != "Point":
                continue
            lon, lat = entry["geometry"]["coordinates"][:2]
            rows.append((str(props["series_id"]), props["nombre"], lon, lat))
        return rank_points(rows, geometry, 150)
    return swot_candidates(upstream["selectors"]["featureType"], geometry)


def fetch_for_selection(source, investigation, start, end, fetch):
    candidates = candidates_for(source, investigation, start, end)
    route = source["access"]
    upstream = source["upstream"]
    for distance, identifier, name in candidates:
        selectors = dict(upstream.get("selectors") or {})
        if route.startswith("noaa."):
            selectors["stationId"] = identifier
        elif route == "nasa.swot.hydrocron":
            selectors["featureId"] = identifier
        chosen = {**upstream, "selectors": selectors}
        if route in {"argentina.ina.series", "psmsl.rlr.monthly"}:
            chosen["variableId"] = identifier
        result = fetch({**source, "upstream": chosen})
        if any(point["value"] is not None for point in result["points"]):
            result["location"] = f"{name} · ID {identifier} · {distance:.1f} km del punto de referencia"
            result["selectedEntity"] = {"id": identifier, "name": name, "distanceKm": round(distance, 2)}
            result["variable"] = upstream["variableId"]
            if route in {"argentina.ina.series", "psmsl.rlr.monthly"}:
                result["label"] = source.get("variable") or result["product"]
            return result
    detail = "No hay registros compatibles en la selección y el período." if candidates else "El catálogo no encontró una entidad en el área o cerca del punto."
    raise ValueError(f"{source.get('product') or route}: {detail}")
