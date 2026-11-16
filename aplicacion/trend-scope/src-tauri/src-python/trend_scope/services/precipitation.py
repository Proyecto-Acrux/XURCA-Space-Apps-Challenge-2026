"""Read monthly precipitation from the publishers' georeferenced rasters."""

import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache
from urllib.error import URLError
from urllib.request import urlopen

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.windows import Window, from_bounds

from .environmental_series import area_bounds, days, read_text, selected_geometry, series
from .grid_layers import display_stride
from .regional_layers import temporal_layer

CHIRPS_ROUTE = "ucsb.chirps.monthly"
CHIRPS_DAILY_ROUTE = "ucsb.chirps.daily"
PMRA_ROUTE = "argentina.pmra.monthly"
CHIRPS = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/"
CHIRPS_DAILY = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/rnl/"
PMRA_FOLDER = "1c4OUapwH5QwLwZ-oxQV1-Q6wrQkhV7Gy"
PMRA = f"https://drive.google.com/drive/folders/{PMRA_FOLDER}"
PMRA_LIST = f"https://drive.google.com/embeddedfolderview?id={PMRA_FOLDER}"
PMRA_MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


@lru_cache(maxsize=2)
def monthly_assets(route):
    if route == CHIRPS_ROUTE:
        index = read_text(CHIRPS, "UCSB CHIRPS")
        return {f"{year}-{month}": CHIRPS + f"chirps-v3.0.{year}.{month}.cog"
                for year, month in re.findall(r"chirps-v3\.0\.(\d{4})\.(\d{2})\.cog", index)}
    index = read_text(PMRA_LIST, "Catálogo PMRAv1")
    entries = re.findall(r"/file/d/([\w-]+)/view[^>]*>(?:(?!</a>).)*?PMRA_([a-z]{3})_(\d{4})\.tif", index, re.DOTALL)
    return {f"{year}-{PMRA_MONTHS.index(month) + 1:02d}":
            f"https://drive.google.com/uc?export=download&id={identifier}"
            for identifier, month, year in entries if month in PMRA_MONTHS}


def read_period(route, url, shape, show_map):
    if route != PMRA_ROUTE:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_CONNECTTIMEOUT="8", GDAL_HTTP_TIMEOUT="25"):
            with rasterio.open(url) as dataset:
                return read_precipitation(dataset, shape, show_map)
    with urlopen(url, timeout=25) as response, MemoryFile(response.read()) as image, image.open() as dataset:
        return read_precipitation(dataset, shape, show_map)


def read_precipitation(dataset, shape, show_map, band=1):
    transform = dataset.transform
    if dataset.crs != rasterio.crs.CRS.from_epsg(4326) or transform.b or transform.d:
        raise ValueError("El archivo de precipitación no tiene la grilla geográfica esperada.")
    if shape["type"] == "Point":
        lon, lat = shape["coordinates"][:2]
        if not (dataset.bounds.left <= lon < dataset.bounds.right and dataset.bounds.bottom < lat <= dataset.bounds.top):
            return None, []
        raw = next(dataset.sample([(lon, lat)], indexes=band, masked=True))[0]
        value = float(raw) * dataset.scales[band - 1] + dataset.offsets[band - 1] if not np.ma.is_masked(raw) else math.nan
        return (value if math.isfinite(value) and value >= 0 else None), []

    west, south, east, north = area_bounds(shape)
    west, south = max(west, dataset.bounds.left), max(south, dataset.bounds.bottom)
    east, north = min(east, dataset.bounds.right), min(north, dataset.bounds.top)
    if west >= east or south >= north:
        return None, []
    window = from_bounds(west, south, east, north, transform)
    row, col = max(0, math.floor(window.row_off)), max(0, math.floor(window.col_off))
    height = min(dataset.height, math.ceil(window.row_off + window.height)) - row
    width = min(dataset.width, math.ceil(window.col_off + window.width)) - col
    window = Window(col, row, width, height)
    grid = dataset.window_transform(window)
    data = dataset.read(band, window=window, masked=True).astype(float).filled(np.nan)
    values = data * dataset.scales[band - 1] + dataset.offsets[band - 1]
    valid = np.isfinite(values) & (values >= 0)
    touched = geometry_mask([shape], values.shape, grid, invert=True, all_touched=True)
    scale = 4 if height * width <= 250_000 else 1
    mask = geometry_mask([shape], (height * scale, width * scale), grid @ grid.scale(1 / scale),
                         invert=True)
    fraction = mask.reshape(height, scale, width, scale).mean(axis=(1, 3))
    if not np.any(fraction):
        fraction = touched
    latitude = grid.f + (np.arange(height) + 0.5) * grid.e
    cos_latitude = np.cos(np.radians(latitude))[:, None]
    weights = fraction * valid * cos_latitude
    clean = np.where(valid, values, 0)
    total = weights.sum()
    average = float((clean * weights).sum() / total) if total else None
    if not show_map:
        return average, []

    stride = display_stride(height, width)
    map_weights = touched * valid * cos_latitude
    rows, cols = np.arange(0, height, stride), np.arange(0, width, stride)
    totals = np.add.reduceat(np.add.reduceat(map_weights, rows, axis=0), cols, axis=1)
    sums = np.add.reduceat(np.add.reduceat(clean * map_weights, rows, axis=0), cols, axis=1)
    cells = []
    for y, x in np.argwhere(totals > 0):
        left, top = grid @ (cols[x], rows[y])
        right, bottom = grid @ (min(width, cols[x] + stride), min(height, rows[y] + stride))
        left, right = max(-180, left), min(180, right)
        ring = [[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]]
        cells.append({"value": float(sums[y, x] / totals[y, x]),
                      "geometry": {"type": "Polygon", "coordinates": [ring]}})
    return average, cells


def fetch_precipitation(source, investigation, start, end):
    route = source["access"]
    daily = route == CHIRPS_DAILY_ROUTE
    if daily and (end - start).days >= 366:
        raise ValueError("Elegí hasta 366 días para CHIRPS diario. Cada día requiere leer un ráster del proveedor.")
    if source["upstream"]["variableId"] != "precipitation":
        raise ValueError("Este producto ofrece precipitación acumulada.")
    geometry = selected_geometry(source, investigation, {"Point", "Polygon", "MultiPolygon"})
    regional = geometry["type"] != "Point"
    provider, product, catalog, resolution = (
        ("UCSB Climate Hazards Center", "CHIRPS v3 final", CHIRPS, "0,05°")
        if route != PMRA_ROUTE else ("Gaitán y Biancari", "PMRAv1", PMRA, "5 km")
    )
    if daily:
        product, catalog = "CHIRPS v3 diario · ERA5", CHIRPS_DAILY
        periods = list(days(start, end))
        assets = {key: f"{CHIRPS_DAILY}{key[:4]}/chirps-v3.0.rnl.{key.replace('-', '.')}.tif"
                  for key in periods if key >= "1981-01-01"}
        if not assets:
            raise ValueError("CHIRPS diario está disponible desde enero de 1981.")
    else:
        assets = monthly_assets(route)
        periods = [f"{year:04d}-{month:02d}" for year in range(start.year, end.year + 1) for month in range(1, 13)
                   if str(start)[:7] <= f"{year:04d}-{month:02d}" <= str(end)[:7]]
    if not assets:
        raise ValueError(f"El catálogo de {product} no devolvió archivos.")
    available = [period for period in periods if period in assets]
    if not available:
        raise ValueError(f"{product} no tiene archivos en las fechas elegidas. Catálogo: {min(assets)} a {max(assets)}.")
    yearly = not daily and len(periods) > 120
    cadence = "yearly" if yearly else "daily" if daily and len(periods) <= 93 else "monthly"
    precision = {"yearly": 4, "monthly": 7, "daily": 10}[cadence]
    snapshots = {period[:precision]: period for period in available}
    shown = set(snapshots.values()) if regional else set()

    def load(period):
        try:
            return read_period(route, assets[period], geometry, period in shown), None
        except (OSError, URLError, rasterio.errors.RasterioError, ValueError) as error:
            return (None, []), str(error)

    values, events, failures = {}, [], []
    def collect(reads):
        for period, ((value, cells), error) in reads:
            values[period] = value
            if error:
                failures.append(error)
            events.extend({"id": f"{period}:{index}", "date": period if daily else period + "-01", **cell}
                          for index, cell in enumerate(cells))
    with ThreadPoolExecutor(max_workers=3) as pool:
        collect(zip(available, pool.map(load, available)))
    if len(failures) == len(available):
        raise ValueError(f"No se pudieron leer los archivos de {product}. {failures[0]}")
    if all(value is None for value in values.values()):
        raise ValueError(f"{product} no devolvió celdas válidas para esa selección. Archivos con error: {len(failures)}.")

    points = [{"month": period, "value": values.get(period)} for period in periods]
    result = series(source, provider, product, "mm", points,
                    "Promedio espacial del área" if regional else "Celda del punto seleccionado",
                    catalog, "daily" if daily else "monthly")
    if regional:
        interval = "día" if daily else "mes"
        note = (f"Resolución nativa: {resolution}. Para áreas grandes se agrupan celdas del mapa. "
                f"El gráfico muestra el promedio espacial de cada {interval} completo.")
        result["map"] = temporal_layer("grid", geometry, start if daily else start.replace(day=1), end, "value",
                                       events=events, unit="mm", cadence=cadence, note=note, nativeCadence=result["cadence"])
    if failures:
        result["mapMessage"] = f"No se pudieron leer {len(failures)} de {len(available)} archivos de {product}."
    return result
