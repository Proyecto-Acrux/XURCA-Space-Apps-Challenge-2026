"""Stable access routes and their investigation configuration requirements."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AccessRoute:
    name: str
    documentation: str
    authentication: str
    selectors: tuple[str, ...] = ()
    geometry: tuple[str, ...] = ()
    product_required: bool = True
    variable_required: bool = True


ROUTES = {
    "openmeteo.archive.daily": AccessRoute(
        "Open-Meteo Historical Weather / ERA5",
        "https://open-meteo.com/en/docs/historical-weather-api",
        "Public for noncommercial use", geometry=("Point",), product_required=False,
    ),
    "nasa.appeears": AccessRoute(
        "AppEEARS",
        "https://appeears.earthdatacloud.nasa.gov/api/",
        "Earthdata Login for jobs",
        geometry=("Point", "MultiPoint", "Polygon", "MultiPolygon"),
    ),
    "noaa.ncei.station": AccessRoute(
        "NOAA NCEI Data Access Service",
        "https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation",
        "Public for the tested collection", selectors=("stationId",),
    ),
    "noaa.ncei.daily": AccessRoute(
        "NOAA NCEI Daily Summaries",
        "https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation",
        "Public", selectors=("stationId",), product_required=False,
    ),
    "noaa.oisst.daily": AccessRoute(
        "NOAA PSL OISST Daily",
        "https://psl.noaa.gov/data/gridded/data.noaa.oisst.v2.highres.html",
        "Public", geometry=("Point",), product_required=False,
    ),
    "noaa.cpc.oni": AccessRoute(
        "NOAA CPC ONI",
        "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
        "Public", product_required=False,
    ),
    "usgs.earthquakes": AccessRoute(
        "USGS ComCat",
        "https://earthquake.usgs.gov/fdsnws/event/1/",
        "Public", geometry=("Polygon", "MultiPolygon"), product_required=False,
    ),
    "nasa.firms.area": AccessRoute(
        "NASA FIRMS Area",
        "https://firms.modaps.eosdis.nasa.gov/api/area/",
        "FIRMS MAP_KEY", geometry=("Polygon", "MultiPolygon"),
    ),
    "argentina.ina.series": AccessRoute(
        "INA Alerta5",
        "https://alerta.ina.gov.ar/a5/swagger/index.html",
        "Public for the tested series", product_required=False,
    ),
    "psmsl.rlr.monthly": AccessRoute(
        "PSMSL RLR Monthly",
        "https://psmsl.org/data/obtaining/notes.php",
        "Public", product_required=False,
    ),
    "noaa.cdo.station": AccessRoute(
        "NOAA Climate Data Online v2",
        "https://www.ncei.noaa.gov/cdo-web/webservices/v2",
        "NOAA CDO token", selectors=("stationIds",),
    ),
    "nasa.earthdata": AccessRoute(
        "NASA Earthdata / CMR",
        "https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html",
        "Earthdata Login for protected downloads",
        geometry=("Point", "Polygon", "MultiPolygon"),
    ),
    "copernicus.dataspace": AccessRoute(
        "Copernicus Data Space OData",
        "https://documentation.dataspace.copernicus.eu/APIs/OData.html",
        "Access token for downloads", geometry=("Point", "Polygon", "MultiPolygon"),
    ),
    "copernicus.cds": AccessRoute(
        "Copernicus Climate Data Store",
        "https://cds.climate.copernicus.eu/how-to-api",
        "CDS API key and dataset terms",
    ),
    "microsoft.planetary.stac": AccessRoute(
        "Microsoft Planetary Computer STAC",
        "https://planetarycomputer.microsoft.com/docs/concepts/sas/",
        "Public catalog and temporary SAS", geometry=("Point", "Polygon", "MultiPolygon"),
    ),
    "nasa.swot.hydrocron": AccessRoute(
        "SWOT / Hydrocron",
        "https://podaac.github.io/hydrocron/timeseries/",
        "Public for the tested series", selectors=("featureType", "featureId"),
    ),
    "canada.geo.stac": AccessRoute(
        "GEO.ca Data Cube",
        "https://datacube.services.geo.ca/stac/api/",
        "Depends on collection and asset", selectors=("assetKey",),
        variable_required=False,
    ),
    "nasa.power.monthly": AccessRoute(
        "NASA POWER monthly point",
        "https://power.larc.nasa.gov/docs/services/api/temporal/monthly/",
        "Public", selectors=("community",), geometry=("Point",),
        product_required=False,
    ),
    "meteomatics.weather": AccessRoute(
        "Meteomatics Weather API",
        "https://www.meteomatics.com/en/api/request/",
        "Meteomatics account", geometry=("Point",),
        product_required=False,
    ),
}


def acquisition_gaps(source: dict, investigation: dict) -> list[str]:
    """Return missing input paths for a configured route or an unsupported route."""

    route = ROUTES.get(source.get("access"))
    if route is None:
        return ["access"]

    upstream = source.get("upstream") or {}
    missing = []
    if route.product_required and not upstream.get("productId"):
        missing.append("upstream.productId")
    if route.variable_required and not upstream.get("variableId"):
        missing.append("upstream.variableId")
    selectors = upstream.get("selectors") or {}
    missing.extend(f"upstream.selectors.{key}" for key in route.selectors if not selectors.get(key))

    period = investigation.get("time") or {}
    for field in ("start", "end"):
        if not period.get(field):
            missing.append(f"time.{field}")

    if route.geometry:
        features = ((investigation.get("geography") or {}).get("selection") or {}).get("features", [])
        reference = upstream.get("geometryId")
        geometry_type: Optional[str] = None
        for feature in features:
            if reference is not None and feature.get("id") == reference:
                geometry_type = (feature.get("geometry") or {}).get("type")
                break
        if geometry_type not in route.geometry:
            missing.append("upstream.geometryId")
    return missing
