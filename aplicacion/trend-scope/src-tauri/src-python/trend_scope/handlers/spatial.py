"""Area sampling: a lattice of points inside a polygon (v1 has no raster reader).

The result is ALWAYS a sample of points, never a zonal mean: every output that
uses it says so. Sample sources are clones of a point-route source template.
"""
from __future__ import annotations

import copy
import math

from ..services.environmental_series import area_bounds, inside_area
from .contracts import INVALID_REQUEST, UNSUPPORTED_SPATIAL, HandlerError

POINT_ROUTES = {"nasa.power.monthly", "openmeteo.archive.daily"}
POLYGONS = {"Polygon", "MultiPolygon"}
MAX_SIDE = 40


def sample_points(geometry: dict, n_points: int) -> list:
    """`n_points` lon/lat pairs on a regular lattice inside the polygon (cell centers)."""
    try:
        west, south, east, north = area_bounds(geometry)
    except ValueError as error:
        raise HandlerError(UNSUPPORTED_SPATIAL, str(error)) from None
    for side in range(max(2, math.ceil(math.sqrt(n_points))), MAX_SIDE + 1):
        found = []
        for row in range(side):
            for column in range(side):
                x = west + (column + 0.5) * (east - west) / side
                y = south + (row + 0.5) * (north - south) / side
                if inside_area(x, y, geometry):
                    found.append([round(x, 6), round(y, 6)])
        if len(found) >= n_points:
            if n_points == 1:
                return [found[len(found) // 2]]
            picks = [round(i * (len(found) - 1) / (n_points - 1)) for i in range(n_points)]
            return [found[i] for i in picks]
    raise HandlerError(UNSUPPORTED_SPATIAL, "No se pudo muestrear el polígono: es demasiado angosto o pequeño.")


def expand(spec, params: dict, sources: dict, investigation: dict) -> tuple:
    """Add sample points and cloned sources to `investigation`. Returns (new_sources, ids)."""
    scope = {"analysis_id": spec.id}
    template = sources[spec.targets[0]]
    if template.get("access") not in POINT_ROUTES:
        raise HandlerError(UNSUPPORTED_SPATIAL, "El patrón espacial necesita una variable de punto (NASA POWER u "
                           "Open-Meteo) como plantilla.", scope)
    selection = investigation.setdefault("geography", {}).setdefault("selection", {"type": "FeatureCollection", "features": []})
    features = selection.setdefault("features", [])
    wanted = params.get("area_feature_id")
    areas = [f for f in features if isinstance(f, dict) and (f.get("geometry") or {}).get("type") in POLYGONS
             and (wanted is None or f.get("id") == wanted)]
    if len(areas) != 1:
        raise HandlerError(INVALID_REQUEST, "Indicá area_feature_id: se necesita exactamente un polígono seleccionado.", scope)
    points = sample_points(areas[0]["geometry"], int(params["n_points"]))
    new_sources, ids = {}, []
    for index, (x, y) in enumerate(points, 1):
        feature_id = f"{spec.id}-p{index}"
        features.append({"type": "Feature", "id": feature_id, "properties": {"name": f"Muestra {index}"},
                         "geometry": {"type": "Point", "coordinates": [x, y]}})
        clone = copy.deepcopy(template)
        clone["id"] = f"{template['id']}@{spec.id}:{index}"
        clone["upstream"]["geometryId"] = feature_id
        new_sources[clone["id"]] = clone
        ids.append(clone["id"])
    return new_sources, ids
