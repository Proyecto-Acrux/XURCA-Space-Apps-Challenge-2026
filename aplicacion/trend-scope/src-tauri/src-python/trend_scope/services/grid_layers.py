"""Build regional map snapshots from compatible downloaded raster assets."""

import math
import re
import shutil
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np

from .environmental_series import area_bounds, inside_area, selected_geometry
from .regional_layers import temporal_layer

NETCDF = {".nc", ".nc4", ".cdf", ".h5", ".hdf5"}
RASTERS = {".tif", ".tiff", ".jp2"}
MAX_DISPLAY_CELLS = 1200


def find_axis(dataset, names, axis):
    return next((v for name, v in dataset.variables.items() if v.ndim == 1
                 and (name.lower() in names or getattr(v, "axis", "").upper() == axis)), None)


def choose_variable(candidates, requested):
    def normalized(value):
        return re.sub(r"[^a-z0-9]+", "", str(value).lower())
    if requested and requested != "all":
        name = normalized(requested)
        if not name:
            return None
        matches = [variable for variable in candidates
                   if normalized(variable.name).endswith(name) or name in
                   {normalized(getattr(variable, key, "")) for key in
                    ("standard_name", "long_name", "GRIB_cfVarName", "GRIB_cfName")}]
        if len(matches) == 1:
            return matches[0]
        return None
    return candidates[0] if len(candidates) == 1 else None


def snapshot_index(variable, time, start, end, precision):
    from netCDF4 import num2date

    if time is None or time.dimensions[0] not in variable.dimensions:
        return []
    if not getattr(time, "units", None):
        return []
    latest = {}
    stamps = num2date(time[:], time.units, calendar=getattr(time, "calendar", "standard"))
    for index, stamp in enumerate(stamps):
        if np.ma.is_masked(stamp):
            continue
        text = stamp.isoformat()
        if str(start) <= text[:10] <= str(end):
            key = text[:precision]
            if key not in latest or latest[key][0] < text:
                latest[key] = (text, index)
    return list(latest.values())


def netcdf_frames(path, area, start, end, precision, requested, level):
    from netCDF4 import Dataset

    with Dataset(path) as root:
        for group in [root, *root.groups.values()]:
            yield from netcdf_group_frames(group, area, start, end, precision, requested, level)


def netcdf_group_frames(dataset, area, start, end, precision, requested, level):
    latitude = find_axis(dataset, {"latitude", "lat"}, "Y")
    longitude = find_axis(dataset, {"longitude", "lon"}, "X")
    if latitude is None or getattr(latitude, "units", "") in {"m", "metres", "meters"}:
        latitude = next((v for v in dataset.variables.values() if v.ndim == 1
                         and getattr(v, "units", "") == "degrees_north"), None)
    if longitude is None or getattr(longitude, "units", "") in {"m", "metres", "meters"}:
        longitude = next((v for v in dataset.variables.values() if v.ndim == 1
                          and getattr(v, "units", "") == "degrees_east"), None)
    if latitude is None or longitude is None or len(latitude) < 2 or len(longitude) < 2:
        return
    if getattr(latitude, "units", "") not in {"degrees_north", "degree_north", "degrees_N", "degree_N"} or getattr(longitude, "units", "") not in {"degrees_east", "degree_east", "degrees_E", "degree_E"}:
        return
    candidates = list(v for v in dataset.variables.values()
                      if latitude.dimensions[0] in v.dimensions and longitude.dimensions[0] in v.dimensions
                      and v.dtype.kind in "biuf")
    variable = choose_variable(candidates, requested)
    if variable is None:
        return
    native = variable.name
    attrs = {"unit": getattr(variable, "units", "") or "Unidad sin verificar",
             "label": getattr(variable, "long_name", "") or native,
             "categories": category_labels(variable)}
    x = np.asarray(longitude[:], dtype=float)
    y = np.asarray(latitude[:], dtype=float)
    dx, dy = float(np.median(np.abs(np.diff(x)))), float(np.median(np.abs(np.diff(y))))
    if not np.allclose(np.abs(np.diff(x)), dx) or not np.allclose(np.abs(np.diff(y)), dy) or not dx or not dy:
        return
    x = (x + 180) % 360 - 180
    west, south, east, north = area_bounds(area)
    cols = np.where((x + dx / 2 >= west) & (x - dx / 2 <= east))[0]
    rows = np.where((y + dy / 2 >= south) & (y - dy / 2 <= north))[0]
    stride = display_stride(len(rows), len(cols))
    rows, cols = rows[::stride], cols[::stride]
    if not len(rows) or not len(cols):
        return
    attrs["resolution"] = f"{dx:g}° × {dy:g}°"
    attrs["sampled"] = stride > 1
    time = find_axis(dataset, {"time", "valid_time"}, "T")
    time_dim = time.dimensions[0] if time is not None else None
    spatial = [latitude.dimensions[0], longitude.dimensions[0]]
    indices = {}
    suffix = ""
    for dim in variable.dimensions:
        if dim == time_dim or dim in spatial:
            continue
        if len(dataset.dimensions[dim]) == 1:
            indices[dim] = 0
        elif dim in {"level", "pressure_level", "plev"} and level and dim in dataset.variables:
            levels = dataset[dim][:]
            expected = level * 100 if getattr(dataset[dim], "units", "") == "Pa" else level
            match = np.where(np.isclose(levels, expected))[0]
            if not len(match):
                return
            indices[dim] = int(match[0])
            suffix = f" · {level:g} hPa"
        else:
            return
    attrs["label"] += suffix
    order = [dim for dim in variable.dimensions if dim in spatial]
    for stamp, index in snapshot_index(variable, time, start, end, precision):
        if index is not None:
            indices[time_dim] = index
        col_dim = longitude.dimensions[0]
        row_dim = latitude.dimensions[0]
        key = tuple(rows if dim == row_dim else cols if dim == col_dim else indices[dim]
                    for dim in variable.dimensions)
        values = np.ma.asarray(variable[key], dtype=float)
        if order != spatial:
            values = values.T
        cells = []
        for i, j, value in valid_pixels(values):
            lon, lat = x[cols[j]], y[rows[i]]
            if lon + dx / 2 > 180 or lon - dx / 2 < -180:
                continue
            corners = [(lon-dx/2, lat-dy/2), (lon+dx/2, lat-dy/2),
                       (lon+dx/2, lat+dy/2), (lon-dx/2, lat+dy/2)]
            append_cell(cells, corners, value, area)
        yield stamp, attrs, cells


def category_labels(variable):
    values = np.atleast_1d(getattr(variable, "flag_values", [])).tolist()
    names = str(getattr(variable, "flag_meanings", "")).split()
    return {f"{value:g}": name.replace("_", " ") for value, name in zip(values, names)} if names else {}


def display_stride(rows, cols):
    return max(1, math.ceil(math.sqrt(rows * cols / MAX_DISPLAY_CELLS)))


def valid_pixels(values):
    valid = (~np.ma.getmaskarray(values)) & np.isfinite(values.filled(np.nan))
    for i, j in np.argwhere(valid):
        yield int(i), int(j), float(values[i, j])


def append_cell(cells, corners, value, area):
    lon, lat = (sum(pair[axis] for pair in corners) / 4 for axis in (0, 1))
    if not (-180 <= lon <= 180 and -90 <= lat <= 90) or not inside_area(lon, lat, area):
        return
    a, b, c = corners[:3]
    if (b[0]-a[0]) * (c[1]-b[1]) < (b[1]-a[1]) * (c[0]-b[0]):
        corners = corners[::-1]
    cells.append({"value": value, "center": [lon, lat],
                  "geometry": {"type": "Polygon", "coordinates": [[*corners, corners[0]]]}})


def dated_image(name, start, end):
    for groups in re.findall(r"(?<!\d)((?:19|20)\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)", name):
        try:
            day = date(*map(int, groups))
        except ValueError:
            continue
        if start <= day <= end:
            return day.isoformat()
    return None


def raster_frame(path, name, area, start, end):
    import rasterio
    from rasterio.transform import xy
    from rasterio.warp import transform, transform_bounds
    from rasterio.windows import Window, from_bounds

    stamp = dated_image(name, start, end)
    if not stamp:
        return
    with rasterio.open(path) as dataset:
        if dataset.count != 1 or not dataset.crs or dataset.transform.b or dataset.transform.d:
            return
        bounds = transform_bounds("EPSG:4326", dataset.crs, *area_bounds(area), densify_pts=21)
        west, south = max(bounds[0], dataset.bounds.left), max(bounds[1], dataset.bounds.bottom)
        east, north = min(bounds[2], dataset.bounds.right), min(bounds[3], dataset.bounds.top)
        if east <= west or north <= south:
            return
        window = from_bounds(west, south, east, north, dataset.transform)
        left, top = max(0, math.floor(window.col_off)), max(0, math.floor(window.row_off))
        right = min(dataset.width, math.ceil(window.col_off + window.width))
        bottom = min(dataset.height, math.ceil(window.row_off + window.height))
        window = Window(left, top, right-left, bottom-top)
        stride = display_stride(window.height, window.width)
        rows, cols = math.ceil(window.height/stride), math.ceil(window.width/stride)
        raw = dataset.read(1, window=window, out_shape=(rows, cols), masked=True).astype(float)
        values = raw * dataset.scales[0] + dataset.offsets[0]
        transform_grid = dataset.window_transform(window) * dataset.transform.scale(window.width/cols, window.height/rows)
        cells = []
        indices = list(valid_pixels(values))
        if indices:
            cols_grid, rows_grid = zip(*[(j + dx, i + dy) for i, j, _ in indices
                                         for dx, dy in [(0, 0), (0, 1), (1, 1), (1, 0)]])
            xs, ys = xy(transform_grid, rows_grid, cols_grid, offset="ul")
            lon, lat = transform(dataset.crs, "EPSG:4326", xs, ys)
            for index, (_, _, value) in enumerate(indices):
                offset = index * 4
                append_cell(cells, list(zip(lon[offset:offset+4], lat[offset:offset+4])), value, area)
        resolution_unit = "°" if dataset.crs.is_geographic else dataset.crs.linear_units
        attrs = {"unit": dataset.units[0] or "Unidad del archivo sin verificar",
                 "label": dataset.descriptions[0] or "Banda de la fuente", "sampled": stride > 1,
                 "resolution": f"{dataset.res[0]:g} × {dataset.res[1]:g} {resolution_unit}"}
        yield stamp, attrs, cells


def archive_frames(archive, folder, source, area, start, end, precision, nested=False):
    upstream = source["upstream"]
    selectors = upstream.get("selectors", {})
    band = selectors.get("mapVariable", "").strip()
    requested = band or upstream["variableId"]
    level_text = selectors.get("pressureLevels", "")
    level = float(level_text.split(",")[0]) if level_text.strip() else 1000
    files = [entry for entry in archive.infolist() if not entry.is_dir()]
    for index, entry in enumerate(files):
        name = entry.filename
        suffix = Path(name).suffix.lower()
        if suffix not in NETCDF | RASTERS | ({".zip"} if not nested else set()):
            continue
        if suffix in RASTERS and band and band.casefold() not in Path(name).stem.casefold():
            continue
        if suffix in RASTERS and not band and (source["access"] in {"nasa.earthdata", "copernicus.dataspace"}
                                             or upstream["variableId"] == "all"):
            continue
        path = folder / f"{int(nested)}-{index}{suffix}"
        with archive.open(entry) as input_file, path.open("wb") as output:
            shutil.copyfileobj(input_file, output)
        try:
            if suffix in NETCDF:
                yield from netcdf_frames(path, area, start, end, precision, requested, level)
            elif suffix in RASTERS:
                yield from raster_frame(path, name, area, start, end)
            else:
                with ZipFile(path) as inner:
                    yield from archive_frames(inner, folder, source, area, start, end, precision, nested=True)
        finally:
            path.unlink(missing_ok=True)


def with_grid_map(result, source, investigation, start, end):
    path = result.get("downloadPath")
    if not path:
        return result
    area = selected_geometry(source, investigation, {"Point", "Polygon", "MultiPolygon"})
    if area["type"] == "Point":
        return result
    layer = temporal_layer("grid", area, start, end, "value")
    precision = {"daily": 10, "monthly": 7, "yearly": 4}[layer["cadence"]]
    frames = {}
    attrs = None
    had_sampled = False
    with TemporaryDirectory() as temp, ZipFile(path) as archive:
        for stamp, info, cells in archive_frames(archive, Path(temp), source, area, start, end, precision):
            if attrs is None:
                attrs = info
            if any(info.get(key) != attrs.get(key) for key in ("label", "unit", "categories")):
                continue
            had_sampled = had_sampled or info["sampled"]
            key = stamp[:precision]
            previous = frames.get(key)
            if previous is None or previous[0] < stamp:
                frames[key] = (stamp, cells)
            elif previous[0] == stamp:
                previous[1].extend(cells)
    if attrs is None:
        return {**result, "mapMessage": "La descarga está disponible. Para el mapa se requiere una banda georreferenciada o una variable NetCDF con grilla regular y fecha identificable."}
    events = []
    for stamp, cells in frames.values():
        step = max(1, math.ceil(len(cells) / MAX_DISPLAY_CELLS))
        had_sampled = had_sampled or step > 1
        events.extend({"id": f"{stamp}:{index}", "date": stamp, **cell}
                      for index, cell in enumerate(cells[::step]))
    sampling = " La visualización submuestrea celdas sin interpolar." if had_sampled else ""
    return {**result, "map": {**layer, "events": events, "unit": attrs["unit"], "label": attrs["label"],
                              "categories": attrs.get("categories", {}),
                              "note": f"Última imagen o medición disponible por ventana. Resolución nativa: {attrs['resolution']}." + sampling}}
