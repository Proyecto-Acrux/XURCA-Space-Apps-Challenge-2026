"""Daily ocean grids, ENSO indicators and event series from public APIs."""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .public_sources import number, request_json


OISST = "https://psl.noaa.gov/thredds/ncss/grid/Datasets/noaa.oisst.v2.highres/"
ONI = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"
OISST_FIELDS = {"sst": ("sst.day.mean", "degC"), "err": ("sst.day.err", "degC"),
                "icec": ("icec.day.mean", "%"), "anom": ("sst.day.anom", "degC")}
INA = "https://alerta.ina.gov.ar/a5/obs/puntual/series/"
PSMSL = "https://psmsl.org/data/obtaining/rlr.monthly.data/"


def read_text(url, provider):
    try:
        with urlopen(Request(url, headers={"User-Agent": "EarthDetective/0.1"}), timeout=45) as response:
            return response.read().decode("utf-8-sig")
    except HTTPError as error:
        raise ValueError(f"{provider}: HTTP {error.code}. Revisá el producto y las fechas.") from error
    except (URLError, TimeoutError, UnicodeError) as error:
        raise ValueError(f"No se pudo leer la respuesta de {provider}.") from error


def selected_geometry(source, investigation, allowed):
    features = investigation["geography"]["selection"]["features"]
    candidates = [item for item in features if item["geometry"]["type"] in allowed]
    reference = source["upstream"].get("geometryId")
    if reference:
        candidates = [item for item in candidates if item["id"] == reference]
    if len(candidates) != 1:
        raise ValueError("Seleccioná una geometría válida para la fuente.")
    return candidates[0]["geometry"]


def area_bounds(geometry):
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    vertices = [point for polygon in polygons for point in polygon[0]]
    west = min(point[0] for point in vertices)
    east = max(point[0] for point in vertices)
    south = min(point[1] for point in vertices)
    north = max(point[1] for point in vertices)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("El área necesita un perímetro válido en WGS 84.")
    return west, south, east, north


def inside_ring(x, y, ring):
    inside = False
    for first, second in zip(ring, ring[1:] + ring[:1]):
        a, b = first[:2]
        c, d = second[:2]
        if (b > y) != (d > y) and x < (c - a) * (y - b) / (d - b) + a:
            inside = not inside
    return inside


def inside_area(x, y, geometry):
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    return any(inside_ring(x, y, polygon[0]) and not any(inside_ring(x, y, hole) for hole in polygon[1:])
               for polygon in polygons)


def days(start, end):
    for offset in range((end - start).days + 1):
        yield (start + timedelta(days=offset)).isoformat()


def series(source, provider, product, unit, points, location, url, cadence="daily"):
    return {"id": source["id"], "variable": source["upstream"]["variableId"], "provider": provider,
            "product": product, "unit": unit, "points": points, "location": location,
            "url": url, "cadence": cadence, "retrievedAt": datetime.now(timezone.utc).isoformat()}


def fetch_oisst(source, investigation, start, end):
    provider = "NOAA PSL"
    field = source["upstream"]["variableId"]
    if field not in OISST_FIELDS:
        raise ValueError("OISST admite sst, anom, err e icec en el producto diario.")
    filename, unit = OISST_FIELDS[field]
    lon, lat = selected_geometry(source, investigation, {"Point"})["coordinates"][:2]
    values = {}
    for year in range(start.year, end.year + 1):
        first = max(start, date(year, 1, 1))
        last = min(end, date(year, 12, 31))
        params = urlencode({"var": field, "longitude": lon % 360, "latitude": lat,
                            "time_start": f"{first}T00:00:00Z", "time_end": f"{last}T23:59:59Z",
                            "accept": "csv"})
        csv_text = read_text(f"{OISST}{filename}.{year}.nc?{params}", provider)
        reader = csv.DictReader(io.StringIO(csv_text))
        key = next((key for key in reader.fieldnames or [] if key.split("[")[0].strip() == field), None)
        if key is None:
            raise ValueError("NOAA PSL no devolvió la columna OISST solicitada.")
        for row in reader:
            value = number(row[key])
            if row.get("time"):
                values[row["time"][:10]] = value if value is not None and value > -1e20 else None
    return series(source, provider, "OISST v2.1", unit,
                  [{"month": day, "value": values.get(day)} for day in days(start, end)],
                  f"Punto {lon:.4f}, {lat:.4f} (lon, lat)",
                  "https://psl.noaa.gov/thredds/catalog/Datasets/noaa.oisst.v2.highres/catalog.html")


def fetch_oni(source, investigation, start, end):
    values = []
    for row in read_text(ONI, "NOAA CPC").splitlines()[1:]:
        if not row.strip():
            continue
        season, year, total, anomaly = row.split()
        month = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ").index(season) + 1
        center = date(int(year), month, 1)
        if start.replace(day=1) <= center <= end:
            value = anomaly if source["upstream"]["variableId"] == "anomaly" else total
            values.append({"month": center.isoformat()[:7], "value": number(value)})
    return series(source, "NOAA CPC", "ONI · media móvil de tres meses", "°C", values,
                  "Niño 3.4", ONI, "monthly")


def fetch_ina(source, investigation, start, end):
    identifier = source["upstream"]["variableId"]
    if not identifier.isascii() or not identifier.isdecimal():
        raise ValueError("Ingresá el ID numérico de la serie puntual del INA.")
    endpoint = INA + identifier
    description, _ = request_json(endpoint, "INA")
    rows, url = request_json(endpoint + "/observaciones", "INA",
                             timestart=f"{start}T00:00:00Z", timeend=f"{end}T23:59:59Z")
    unit = (description.get("unidades") or {}).get("abrev") or "Unidad sin verificar"
    station = (description.get("estacion") or {}).get("nombre") or identifier
    points = sorted([{"month": row["timestart"], "value": number(row.get("valor"))}
                     for row in rows if row.get("timestart")], key=lambda point: point["month"])
    return series(source, "INA", f"Serie puntual {identifier}", unit, points, f"Estación {station}", url, "observation")


def fetch_tide_gauge(source, investigation, start, end):
    identifier = source["upstream"]["variableId"]
    if not identifier.isascii() or not identifier.isdecimal():
        raise ValueError("Ingresá el ID numérico de un mareógrafo PSMSL.")
    url = PSMSL + identifier + ".rlrdata"
    points = []
    for row in csv.reader(io.StringIO(read_text(url, "PSMSL")), delimiter=";"):
        if not row:
            continue
        stamp, height, missing, flag = (field.strip() for field in row[:4])
        decimal_year = float(stamp)
        year = int(decimal_year)
        month = min(12, int((decimal_year - year) * 12) + 1)
        if start.replace(day=1) <= date(year, month, 1) <= end:
            points.append({"month": f"{year:04d}-{month:02d}", "value": None if height == "-99999" else number(height),
                           "missingDays": number(missing), "qualityFlag": flag})
    return series(source, "PSMSL", "Nivel relativo del mar · RLR mensual", "mm",
                  points, f"Estación {identifier}", url, "monthly")


def fetch_earthquakes(source, investigation, start, end):
    geometry = selected_geometry(source, investigation, {"Polygon", "MultiPolygon"})
    west, south, east, north = area_bounds(geometry)
    params = {"minlongitude": west, "minlatitude": south, "maxlongitude": east, "maxlatitude": north,
              "starttime": f"{start}T00:00:00Z", "endtime": f"{end}T23:59:59.999Z", "format": "geojson",
              "eventtype": "earthquake", "orderby": "time-asc", "limit": 10000}
    min_magnitude = source["upstream"]["selectors"].get("minMagnitude")
    if min_magnitude:
        params["minmagnitude"] = float(min_magnitude)
    totals = {}
    records = []
    offset = 1
    while True:
        payload, _ = request_json(USGS, "USGS", **params, offset=offset)
        page = payload["features"]
        for item in page:
            lon, lat, depth = item["geometry"]["coordinates"]
            if not inside_area(lon, lat, geometry):
                continue
            stamp = datetime.fromtimestamp(item["properties"]["time"] / 1000, tz=timezone.utc).isoformat()
            day = stamp[:10]
            totals[day] = totals.get(day, 0) + 1
            records.append((stamp, item["properties"]["mag"], depth))
        if len(page) < params["limit"]:
            break
        offset += len(page)
    field = source["upstream"]["variableId"]
    if field == "count":
        values = [{"month": day, "value": totals.get(day, 0)} for day in days(start, end)]
        unit, cadence = "sismos", "daily"
    else:
        values = [{"month": stamp, "value": magnitude if field == "magnitude" else depth}
                  for stamp, magnitude, depth in records]
        unit, cadence = ("magnitud" if field == "magnitude" else "km"), "event"
    return series(source, "USGS", "ComCat", unit, values, "Polígono", USGS, cadence)
