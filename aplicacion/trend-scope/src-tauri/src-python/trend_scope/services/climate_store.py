"""Download ECMWF reanalysis grids with the official CDS client."""

import hashlib
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_STORED, ZipFile

from ..configuration import directory
from .downloads import result_for_download
from .environmental_series import area_bounds, selected_geometry

DATASETS = {"reanalysis-era5-single-levels", "reanalysis-era5-pressure-levels", "reanalysis-era5-land"}
LEVELS = "1000,925,850,700,500,300,250,200"
CDS = "https://cds.climate.copernicus.eu/api"


def monthly_windows(start, end):
    current = start
    while current <= end:
        next_month = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
        last = min(end, next_month - timedelta(days=1))
        yield current, last
        current = next_month


def fetch_cds(source, investigation, start, end):
    upstream = source["upstream"]
    dataset = upstream.get("productId", "")
    variable = upstream["variableId"]
    if dataset not in DATASETS:
        return fetch_cds_product(source, dataset)
    if not re.fullmatch(r"[a-z][a-z0-9_]+", variable):
        raise ValueError("Elegí un producto ERA5 válido e ingresá el código CDS de la variable.")
    geometry = selected_geometry(source, investigation, {"Polygon", "MultiPolygon"})
    west, south, east, north = area_bounds(geometry)
    request = {"variable": [variable], "area": [north, west, south, east], "data_format": "netcdf",
               "download_format": "unarchived", "time": [f"{h:02}:00" for h in range(24)]}
    if dataset != "reanalysis-era5-land":
        request["product_type"] = ["reanalysis"]
    if dataset.endswith("pressure-levels"):
        levels = upstream.get("selectors", {}).get("pressureLevels") or LEVELS
        request["pressure_level"] = [level.strip() for level in levels.split(",")]
        if not all(re.fullmatch(r"\d{1,4}", level) for level in request["pressure_level"]):
            raise ValueError("Ingresá niveles de presión en hPa separados por comas.")
    manifest = {"dataset": dataset, "request": request, "start": str(start), "end": str(end), "geometry": geometry}
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:24]
    folder = directory() / "downloads" / "cds"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{fingerprint}.zip"
    windows = list(monthly_windows(start, end))
    if not target.exists():
        retrieve_months(dataset, request, windows, manifest, target)
    return result_for_download(source, "Copernicus CDS", dataset, target,
                               f"https://cds.climate.copernicus.eu/datasets/{dataset}", len(windows), geometry)


def cds_client():
    import cdsapi

    token = os.environ.get("CDSAPI_KEY", "").strip()
    try:
        return cdsapi.Client(url=CDS, **({"key": token} if token else {}), quiet=True, progress=False)
    except Exception as error:
        raise ValueError("Configurá CDSAPI_KEY o .cdsapirc y aceptá los términos del producto CDS.") from error


def fetch_cds_product(source, dataset):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", dataset):
        raise ValueError("Ingresá el identificador oficial del conjunto de datos CDS.")
    try:
        request = json.loads(source["upstream"].get("selectors", {}).get("requestJson", ""))
    except (TypeError, ValueError) as error:
        raise ValueError("Pegá la solicitud del proveedor como JSON, con sus fechas y filtros.") from error
    if not isinstance(request, dict) or not request:
        raise ValueError("La solicitud CDS debe ser un objeto JSON con los parámetros del producto.")
    manifest = {"dataset": dataset, "request": request}
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:24]
    folder = directory() / "downloads" / "cds"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{fingerprint}.zip"
    if not target.exists():
        retrieve_archive(dataset, [(None, request)], manifest, target)
    result = result_for_download(source, "Copernicus CDS", dataset, target,
                                 f"https://cds.climate.copernicus.eu/datasets/{dataset}", 1, {"type": "request"})
    return {**result, "location": "Selección de la solicitud CDS"}


def retrieve_months(dataset, request, windows, manifest, target):
    queries = [(f"{first:%Y-%m}", {**request, "year": [str(first.year)], "month": [f"{first.month:02}"],
                                    "day": [f"{day:02}" for day in range(first.day, last.day + 1)]})
               for first, last in windows]
    retrieve_archive(dataset, queries, manifest, target)


def retrieve_archive(dataset, queries, manifest, target):
    client = cds_client()
    with NamedTemporaryFile(dir=target.parent, suffix=".part", delete=False) as temporary:
        staged = Path(temporary.name)
    try:
        with ZipFile(staged, "w", ZIP_STORED, allowZip64=True) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for month, params in queries:
                with NamedTemporaryFile(dir=target.parent, suffix=".part", delete=False) as temporary:
                    downloaded = Path(temporary.name)
                try:
                    client.retrieve(dataset, params, str(downloaded))
                    with downloaded.open("rb") as output:
                        signature = output.read(8)
                    formats = {b"CDF": "nc", b"\x89HDF": "nc", b"PK": "zip", b"GRIB": "grib", b"\x1f\x8b": "gz"}
                    extension = next((ext for marker, ext in formats.items() if signature.startswith(marker)), "bin")
                    if month and extension != "nc":
                        raise ValueError("CDS devolvió un archivo que no es NetCDF.")
                    if not signature:
                        raise ValueError("CDS devolvió un archivo vacío.")
                    archive.write(downloaded, f"{month or 'datos'}.{extension}")
                finally:
                    downloaded.unlink(missing_ok=True)
        staged.replace(target)
    except Exception as error:
        raise ValueError("No se completó la descarga de CDS. Revisá la variable, los términos y los límites del producto.") from error
    finally:
        staged.unlink(missing_ok=True)
