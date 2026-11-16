"""Resolve a map selection to provider IDs before requesting observations."""

import json
import ssl
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .environmental_series import INA, PSMSL, area_bounds, inside_area, read_text, selected_geometry, series
from .public_sources import request_json
from .regional_layers import temporal_layer

NOAA_STATIONS = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
SWOT_CATALOG = "https://arcgis.cuahsi.org/arcgis/rest/services/SWOT/"
SWOT_LAYERS = {"Reach": ("world_SWORD_reaches_mercator_v17b", "reach_id", "20"),
               "PriorLake": ("SWOT_pld_v202", "lake_id_Double", "10")}
ENTITY_ROUTES = {"noaa.ncei.station", "noaa.ncei.daily", "nasa.swot.hydrocron",
                 "argentina.ina.series", "psmsl.rlr.monthly"}
MAX_CANDIDATES = 12
NOAA_AREA_RADIUS_KM = 150
NOAA_AREA_CANDIDATES = 24
NOAA_DAILY_SURFACE_VARIABLES = {"TMAX", "TMIN", "TAVG", "PRCP"}


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
            matches.append((distance, identifier, name, {"type": "Point", "coordinates": [lon, lat]}))
    return sorted(matches, key=lambda row: row[:3])


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


def noaa_area_stations(geometry):
    west, south, east, north = area_bounds(geometry)
    latitude_margin = NOAA_AREA_RADIUS_KM / 110
    extreme_latitude = min(90, max(abs(south), abs(north)) + latitude_margin)
    longitude_margin = latitude_margin / max(1e-6, cos(radians(extreme_latitude)))
    origin = center(geometry)
    matches = []
    for identifier, name, lon, lat in noaa_stations():
        if not south - latitude_margin <= lat <= north + latitude_margin:
            continue
        if not any(west - longitude_margin <= candidate <= east + longitude_margin
                   for candidate in (lon, lon - 360, lon + 360)):
            continue
        separation = geometry_distance((lon, lat), geometry)
        if separation <= NOAA_AREA_RADIUS_KM:
            distance = distance_km(origin, (lon, lat))
            matches.append((separation, distance, identifier, name,
                            {"type": "Point", "coordinates": [lon, lat]}))
    matches.sort(key=lambda row: row[:4])
    return [row[1:] for row in matches]


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
    url = SWOT_CATALOG + f"{layer}/FeatureServer/0/query"
    request = Request(url + "?" + urlencode(params)) if point else Request(url, data=urlencode(params).encode())
    try:
        try:
            import truststore
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            context = ssl.create_default_context()
        with urlopen(request, context=context, timeout=30) as response:
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
            candidates.append((distance, identifier, label, item["geometry"]))
    return sorted(candidates, key=lambda row: row[:3])


def candidates_for(source, geometry, start, end):
    route = source["access"]
    upstream = source["upstream"]
    if route.startswith("noaa."):
        if geometry["type"] != "Point":
            return noaa_area_stations(geometry)
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
    area = selected_geometry(source, investigation, {"Point", "Polygon", "MultiPolygon"})
    candidates = candidates_for(source, area, start, end)
    route = source["access"]
    upstream = source["upstream"]

    def fetch_candidate(candidate):
        distance, identifier, name, shape = candidate
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
        return None

    if area["type"] != "Point":
        return regional_entities(source, area, start, end, candidates, fetch_candidate)
    for candidate in candidates[:MAX_CANDIDATES]:
        result = fetch_candidate(candidate)
        if result:
            return result
    detail = "No hay registros compatibles en la selección y el período." if candidates else "El catálogo no encontró una entidad en el área o cerca del punto."
    raise ValueError(f"{source.get('product') or route}: {detail}")


def regional_entities(source, area, start, end, candidates, fetch_candidate):
    route = source.get("access", "")
    noaa = route in {"noaa.ncei.station", "noaa.ncei.daily"}
    attempted = candidates[:NOAA_AREA_CANDIDATES if noaa else MAX_CANDIDATES]
    failures = []

    def read(candidate):
        try:
            return fetch_candidate(candidate), None
        except ValueError as error:
            return None, str(error)

    result = None
    events = []
    entities = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for candidate, (response, error) in zip(attempted, pool.map(read, attempted)):
            if error:
                failures.append(error)
                continue
            if not response:
                continue
            if result is None:
                result = response
            if response["unit"] != result["unit"]:
                failures.append("Hay entidades con unidades incompatibles.")
                continue
            _, identifier, name, shape = candidate
            entities += 1
            for index, row in enumerate(response["points"]):
                if row["value"] is not None:
                    events.append({"id": f"{identifier}:{index}", "entityId": identifier, "geometry": shape,
                                   "date": row["month"], "value": row["value"], "location": name,
                                   "quality": row.get("qualityFlag")})
    if attempted and not result and len(failures) == len(attempted):
        raise ValueError(failures[0])
    if noaa and not result:
        variable = source.get("variable") or source["upstream"]["variableId"]
        detail = f"Se consultaron {len(attempted)} estaciones." if attempted else "El catálogo no encontró estaciones."
        if failures:
            detail += f" NOAA no respondió correctamente para {len(failures)} de ellas."
        raise ValueError(f"NOAA NCEI no devolvió datos de {variable} para las fechas elegidas en el área "
                         f"ni hasta {NOAA_AREA_RADIUS_KM} km de su límite. {detail}")
    result = result or series(source, source.get("provider", ""), source.get("product", ""), "", [], "Área", None)
    map_layer = temporal_layer("entities", area, start, end, "value", events=events,
                               matched=len(candidates), attempted=len(attempted), entities=entities,
                               failures=len(failures))
    if result.get("cadence") == "monthly" and map_layer["cadence"] == "daily":
        map_layer["cadence"] = "monthly"
    if route == "noaa.ncei.daily" and source["upstream"]["variableId"] in NOAA_DAILY_SURFACE_VARIABLES:
        map_layer["stationSurface"] = True
    if noaa:
        result = {**result, "product": source.get("product") or "NOAA NCEI"}
    return {**result, "map": map_layer,
            "message": f"Entidades con observaciones: {entities}. Entidades consultadas: {len(attempted)} de {len(candidates)}."}
