"""Download scientific products and keep their original files and provenance."""

import hashlib
import json
import os
import re
from datetime import timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
from zipfile import ZIP_STORED, ZipFile

from ..configuration import directory
from .environmental_series import area_bounds, selected_geometry, series
from .public_sources import request_json

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
CDSE_CATALOG = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
CDSE_DOWNLOAD = "https://download.dataspace.copernicus.eu/odata/v1/Products"
PLANETARY = "https://planetarycomputer.microsoft.com"
STAC_SEARCH = PLANETARY + "/api/stac/v1/search"
FORMATS = {".nc", ".nc4", ".cdf", ".hdf", ".hdf5", ".h5", ".tif", ".tiff", ".grib", ".grb", ".zip", ".gz", ".he5"}


def safe_name(name):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name).strip(".")[:190]


def open_remote(url, provider, token=None):
    request = Request(url, headers={"User-Agent": "EarthDetective/0.1"})
    if token:
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        return urlopen(request, timeout=90)
    except HTTPError as error:
        raise ValueError(f"{provider}: la descarga falló con HTTP {error.code}. Revisá acceso, vigencia del token y producto.") from error
    except (URLError, TimeoutError) as error:
        raise ValueError(f"No se pudo conectar con {provider}.") from error


def create_archive(namespace, key, assets, manifest, provider, token=None, authorize=None):
    folder = directory() / "downloads" / namespace
    folder.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:24]
    target = folder / f"{fingerprint}.zip"
    if target.exists():
        return target
    with NamedTemporaryFile(dir=folder, suffix=".part", delete=False) as temporary:
        staged = Path(temporary.name)
    try:
        with ZipFile(staged, "w", ZIP_STORED, allowZip64=True) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            for index, (name, url) in enumerate(assets, 1):
                bearer = token if namespace == "copernicus" or (urlsplit(url).hostname or "").endswith(".nasa.gov") else None
                with open_remote(authorize(url) if authorize else url, provider, bearer) as response:
                    content_type = response.headers.get_content_type()
                    if content_type in {"text/html", "application/json"}:
                        raise ValueError(f"{provider} devolvió una página de acceso en lugar de datos.")
                    with archive.open(f"{index:06d}-{safe_name(name)}", "w", force_zip64=True) as item:
                        for block in iter(lambda: response.read(1024 * 1024), b""):
                            item.write(block)
        staged.replace(target)
    except OSError as error:
        raise ValueError(f"No se pudieron guardar todos los archivos de {provider}.") from error
    finally:
        staged.unlink(missing_ok=True)
    return target


def result_for_download(source, provider, product, path, url, count, geometry):
    result = series(source, provider, product, "", [], "Punto" if geometry["type"] == "Point" else "Área", url)
    return {**result, "downloadPath": str(path), "message": f"Descarga completada. Archivos originales: {count}."}


def fetch_earthdata(source, investigation, start, end):
    provider = "NASA Earthdata"
    upstream = source["upstream"]
    if upstream["variableId"] != "all":
        raise ValueError("Usá all para descargar el gránulo Earthdata con todas sus variables.")
    product = upstream.get("productId", "").strip()
    if not re.fullmatch(r"C\d+-[A-Z0-9_]+", product):
        raise ValueError("Ingresá el ID de colección CMR completo, por ejemplo C2723754864-GES_DISC.")
    geometry = selected_geometry(source, investigation, {"Point", "Polygon", "MultiPolygon"})
    spatial = ({"point": ",".join(map(str, geometry["coordinates"][:2]))} if geometry["type"] == "Point"
               else {"bounding_box": ",".join(map(str, area_bounds(geometry)))})
    params = {"collection_concept_id": product,
              "temporal": f"{start}T00:00:00Z,{end}T23:59:59.999Z",
              "page_size": 100, "sort_key": "start_date", **spatial}
    assets, records = [], []
    page_number = 1
    while True:
        payload, _ = request_json(CMR, provider, **params, page_num=page_number)
        page = payload["feed"]["entry"]
        for granule in page:
            files = []
            for link in granule.get("links", []):
                url = link.get("href", "")
                parsed = urlsplit(url)
                host = parsed.hostname or ""
                filename = unquote(parsed.path.rsplit("/", 1)[-1])
                if (parsed.scheme == "https" and host.endswith((".nasa.gov", ".usgs.gov", ".nsidc.org"))
                        and (link.get("rel") or "").endswith("/data#") and not link.get("inherited")
                        and Path(filename).suffix.lower() in FORMATS):
                    if (filename, url) not in assets:
                        assets.append((filename, url))
                    files.append(filename)
            if not files:
                raise ValueError(f"El gránulo {granule['id']} no tiene un archivo HTTPS directo compatible.")
            records.append({"id": granule["id"], "time_start": granule.get("time_start"), "files": files})
        if len(page) < params["page_size"]:
            break
        page_number += 1
    if not assets:
        raise ValueError("Earthdata no encontró gránulos para esas fechas y geometría.")
    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    manifest = {"provider": provider, "query": params, "geometry": geometry, "granules": records}
    path = create_archive("earthdata", manifest, assets, manifest, provider, token)
    return result_for_download(source, provider, product, path, CMR + "?" + urlencode(params), len(assets), geometry)


def fetch_copernicus(source, investigation, start, end):
    provider = "Copernicus Data Space"
    upstream = source["upstream"]
    collection = upstream.get("productId", "").strip().upper()
    product_type = upstream["variableId"].strip().upper()
    if not all(re.fullmatch(r"[A-Z0-9_-]+", field) for field in (collection, product_type)):
        raise ValueError("Ingresá la colección y el tipo oficial de producto de Copernicus.")
    geometry = selected_geometry(source, investigation, {"Point", "Polygon", "MultiPolygon"})
    if geometry["type"] == "Point":
        lon, lat = geometry["coordinates"][:2]
        spatial = f"POINT({lon} {lat})"
    else:
        west, south, east, north = area_bounds(geometry)
        spatial = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
    filters = [f"Collection/Name eq '{collection}'",
               f"OData.CSC.Intersects(area=geography'SRID=4326;{spatial}')",
               f"ContentDate/Start ge {start}T00:00:00.000Z",
               f"ContentDate/Start lt {end + timedelta(days=1)}T00:00:00.000Z",
               "Online eq true"]
    if product_type != "ALL":
        attribute = "OData.CSC.StringAttribute"
        filters.append(f"Attributes/{attribute}/any(a:a/Name eq 'productType' and a/{attribute}/Value eq '{product_type}')")
    params = {"$filter": " and ".join(filters), "$orderby": "ContentDate/Start asc", "$top": 100,
              "$select": "Id,Name,ContentDate"}
    records = []
    url = CDSE_CATALOG + "?" + urlencode(params)
    while url:
        if not url.startswith(CDSE_CATALOG + "?"):
            raise ValueError("Copernicus devolvió una página de resultados inválida.")
        with open_remote(url, provider) as response:
            page = json.load(response)
        records.extend(page["value"])
        url = page.get("@odata.nextLink")
    if not records:
        raise ValueError("Copernicus no encontró escenas en línea para la selección.")
    token = os.environ.get("CDSE_ACCESS_TOKEN", "").strip()
    if not token:
        raise ValueError(f"Copernicus encontró {len(records)} escenas. Configurá CDSE_ACCESS_TOKEN para descargarlas.")
    assets = []
    for record in records:
        identifier = record["Id"]
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", identifier):
            raise ValueError("Copernicus devolvió un identificador de escena inválido.")
        suffix = "" if record["Name"].lower().endswith((".nc", ".zip")) else ".zip"
        assets.append((record["Name"] + suffix, f"{CDSE_DOWNLOAD}({identifier})/$value"))
    manifest = {"provider": provider, "query": params, "geometry": geometry, "products": records}
    path = create_archive("copernicus", manifest, assets, manifest, provider, token)
    return result_for_download(source, provider, collection, path, CDSE_CATALOG + "?" + urlencode(params), len(assets), geometry)


def sign_planetary_asset(url):
    result, _ = request_json(PLANETARY + "/api/sas/v1/sign", "Planetary Computer", href=url)
    signed = result["href"]
    if urlsplit(signed).scheme != "https" or urlsplit(signed).netloc != urlsplit(url).netloc:
        raise ValueError("Planetary Computer devolvió un enlace de descarga inesperado.")
    return signed


def fetch_planetary(source, investigation, start, end):
    provider = "Microsoft Planetary Computer"
    upstream = source["upstream"]
    collection = upstream.get("productId", "").strip()
    key = upstream["variableId"].strip()
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", collection):
        raise ValueError("Ingresá el identificador oficial de colección STAC.")
    geometry = selected_geometry(source, investigation, {"Point", "Polygon", "MultiPolygon"})
    query = {"collections": collection, "intersects": json.dumps(geometry, separators=(",", ":")),
             "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 100}
    url = original = STAC_SEARCH + "?" + urlencode(query)
    assets, items = [], []
    while url:
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.netloc, parsed.path) != ("https", "planetarycomputer.microsoft.com", "/api/stac/v1/search"):
            raise ValueError("El catálogo STAC devolvió una página inválida.")
        with open_remote(url, provider) as response:
            payload = json.load(response)
        for item in payload["features"]:
            names = []
            for name, asset in item["assets"].items():
                if name != key and not (key == "all" and "data" in asset.get("roles", [])):
                    continue
                href = asset["href"]
                parsed = urlsplit(href)
                if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".blob.core.windows.net"):
                    raise ValueError("El activo STAC no tiene un enlace directo compatible.")
                assets.append((unquote(parsed.path.rsplit("/", 1)[-1]), href))
                names.append(name)
            if names:
                items.append({"id": item["id"], "datetime": item["properties"].get("datetime"), "assets": names})
        url = next((link["href"] for link in payload.get("links", []) if link.get("rel") == "next"), None)
    if not assets:
        raise ValueError("El catálogo STAC no encontró archivos para la capa, geometría y fechas elegidas.")
    manifest = {"provider": provider, "query": query, "assetKey": key, "items": items}
    path = create_archive("planetary", manifest, assets, manifest, provider, authorize=sign_planetary_asset)
    return result_for_download(source, provider, collection, path, original, len(assets), geometry)
