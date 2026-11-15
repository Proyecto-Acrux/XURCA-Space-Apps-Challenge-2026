"""AppEEARS catalog and downloadable point or area extraction bundles."""

import base64
import hashlib
import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

from ..configuration import directory
from .environmental_series import selected_geometry, series

API = "https://appeears.earthdatacloud.nasa.gov/api/"


def request(path, headers=None, payload=None, method=None):
    headers = dict(headers or {})
    if payload is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(payload).encode()
    request = Request(API + path, data=payload, method=method)
    # urllib drops unredirected headers when AppEEARS redirects to storage.
    for key, value in headers.items():
        request.add_unredirected_header(key, value)
    try:
        return urlopen(request, timeout=60)
    except HTTPError as error:
        raise ValueError(f"AppEEARS rechazó la solicitud (HTTP {error.code}). Revisá la sesión y el producto.") from error
    except (URLError, TimeoutError) as error:
        raise ValueError("No se pudo conectar con AppEEARS.") from error


def read_json(path, **options):
    with request(path, **options) as response:
        try:
            return json.load(response)
        except (UnicodeError, ValueError) as error:
            raise ValueError("AppEEARS devolvió una respuesta inválida.") from error


def catalog(product=None):
    if product:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", product):
            raise ValueError("Ingresá un identificador de producto AppEEARS válido.")
        return [{"id": name, "label": row.get("Description") or name,
                 "unit": row.get("Units") or ""}
                for name, row in read_json("product/" + quote(product, safe="")).items()
                if row.get("Available")]
    return [{"id": row["ProductAndVersion"], "label": row.get("Description") or row["ProductAndVersion"]}
            for row in read_json("product") if row.get("Available")]


def login():
    token = os.environ.get("APPEEARS_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    username = os.environ.get("EARTHDATA_USERNAME")
    password = os.environ.get("EARTHDATA_PASSWORD")
    if not username or not password:
        raise ValueError("Configurá APPEEARS_TOKEN o las credenciales Earthdata antes de abrir Earth Detective.")
    basic = base64.b64encode(f"{username}:{password}".encode()).decode()
    token = read_json("login", headers={"Authorization": f"Basic {basic}"}, method="POST").get("token")
    if not token:
        raise ValueError("AppEEARS no devolvió un token de sesión.")
    return {"Authorization": f"Bearer {token}"}


def download_bundle(task_id, headers, output):
    files = read_json(f"bundle/{task_id}", headers=headers).get("files", [])
    if not files:
        raise ValueError("AppEEARS no devolvió archivos para el período y la geometría elegidos.")
    with NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as temporary:
        staged = Path(temporary.name)
    try:
        with ZipFile(staged, "w", ZIP_DEFLATED, allowZip64=True) as archive:
            for item in files:
                name = item["file_name"].replace(chr(92), "/").split("/")[-1]
                if not name or name in {".", ".."} or name in archive.namelist():
                    raise ValueError("AppEEARS devolvió un nombre de archivo inválido o repetido.")
                identifier = quote(item["file_id"], safe="")
                checksum = hashlib.sha256()
                with request(f"bundle/{task_id}/{identifier}", headers=headers) as response:
                    with archive.open(name, "w", force_zip64=True) as destination:
                        for chunk in iter(lambda: response.read(1024 * 1024), b""):
                            checksum.update(chunk)
                            destination.write(chunk)
                if item.get("sha256") and checksum.hexdigest() != item["sha256"]:
                    raise ValueError("La descarga de AppEEARS no coincide con su checksum.")
        staged.replace(output)
    except OSError as error:
        raise ValueError("No se pudo guardar la extracción de AppEEARS.") from error
    finally:
        staged.unlink(missing_ok=True)


def fetch_appeears(source, investigation, start, end):
    headers = login()
    upstream = source["upstream"]
    product = upstream.get("productId", "")
    layer = upstream["variableId"]
    geometry = selected_geometry(source, investigation, {"Point", "Polygon", "MultiPolygon"})
    point = geometry["type"] == "Point"
    params = {"dates": [{"startDate": start.strftime("%m-%d-%Y"), "endDate": end.strftime("%m-%d-%Y")}],
              "layers": [{"product": product, "layer": layer}]}
    if point:
        longitude, latitude = geometry["coordinates"][:2]
        params["coordinates"] = [{"longitude": longitude, "latitude": latitude}]
    else:
        params["geo"] = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": geometry, "properties": {}}]}
        params["output"] = {"format": {"type": "netcdf4"}, "projection": "geographic"}
    folder = directory() / "downloads" / "appeears"
    folder.mkdir(parents=True, exist_ok=True)
    request_key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:28]
    task_name = "EarthDetective-" + request_key
    existing = read_json("task?limit=100&task_name=" + task_name, headers=headers)
    task = next((entry for entry in existing if entry.get("task_name") == task_name
                 and entry.get("status") in {"pending", "processing", "done"}), None)
    if task is None:
        task = read_json("task", headers=headers, payload={
            "task_type": "point" if point else "area", "task_name": task_name, "params": params})
    task_id = task.get("task_id", "")
    if not re.fullmatch(r"[a-fA-F0-9-]{36}", task_id):
        raise ValueError("AppEEARS no devolvió un identificador de trabajo válido.")
    path = folder / f"{task_id}.zip"
    if not path.exists():
        task = read_json(f"task/{task_id}", headers=headers)
        if task.get("status") == "error":
            raise ValueError("Falló el trabajo de AppEEARS. Revisá fechas, área y capa.")
        if task.get("status") != "done":
            result = series(source, "NASA AppEEARS", product, "", [], "Punto" if point else "Área", None)
            return {**result, "message": "Extracción en curso. Volvé a pulsar Procesar para descargarla cuando termine.",
                    "taskId": task_id}
        if (task.get("summary") or {}).get("empty"):
            raise ValueError("AppEEARS no encontró datos para esta selección.")
        download_bundle(task_id, headers, path)
    result = series(source, "NASA AppEEARS", product, "", [], "Punto" if point else "Área", None)
    return {**result, "downloadPath": str(path), "taskId": task_id,
            "message": "Extracción descargada con sus archivos y metadatos originales."}
