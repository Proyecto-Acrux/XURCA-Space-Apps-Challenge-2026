from datetime import date
from zipfile import ZipFile

from netCDF4 import Dataset
import pytest
import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from .grid_layers import with_grid_map
from . import firms
from . import station_catalogs
from .precipitation import read_precipitation
from .station_catalogs import regional_entities


AREA = {"type": "Polygon", "coordinates": [[[-0.4, -0.4], [1.4, -0.4], [1.4, 1.4], [-0.4, 1.4], [-0.4, -0.4]]]}
START, END = date(2025, 1, 1), date(2025, 1, 2)


def test_precipitation_keeps_zero_and_clips_to_valid_cells():
    with MemoryFile() as image:
        with image.open(driver="GTiff", width=2, height=2, count=1, dtype="float32",
                        crs="EPSG:4326", transform=from_origin(0, 2, 1, 1)) as raster:
            raster.write(np.array([[0, 12], [24, -9999]], dtype="float32"), 1)
            point = {"type": "Point", "coordinates": [0.1, 1.9]}
            assert read_precipitation(raster, point, False) == (0, [])
            point["coordinates"] = [1.1, 0.1]
            assert read_precipitation(raster, point, False) == (None, [])
            tiny = {"type": "Polygon", "coordinates": [
                [[1.1, 1.1], [1.2, 1.1], [1.2, 1.2], [1.1, 1.2], [1.1, 1.1]]
            ]}
            average, cells = read_precipitation(raster, tiny, True)
            assert average == pytest.approx(12)
            assert [cell["value"] for cell in cells] == pytest.approx([12])


def test_download_to_map_preserves_native_values_and_missing_cells(tmp_path):
    path = tmp_path / "fields.nc"
    with Dataset(path, "w") as data:
        for axis, values, units in [
            ("lat", [0, 1], "degrees_north"),
            ("lon", [0, 1], "degrees_east"),
            ("time", [0, 12, 24], "hours since 2025-01-01 00:00:00"),
        ]:
            data.createDimension(axis, len(values))
            coord = data.createVariable(axis, "f4", (axis,))
            coord.units = units
            coord[:] = values
        rainfall = data.createVariable("precipitation", "f4", ("time", "lat", "lon"), fill_value=-9999)
        rainfall.units = "mm"
        rainfall[:] = [[[800, 800], [800, 800]], [[2, -9999], [3, 4]], [[5, 6], [7, 8]]]
        unrelated = data.createVariable("temperature", "f4", ("time", "lat", "lon"))
        unrelated.units = "K"
    archive_path = tmp_path / "grid.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.write(path, path.name)
    source = {"id": "rain", "access": "nasa.earthdata",
              "upstream": {"geometryId": "p", "variableId": "all", "selectors": {"mapVariable": "precipitation"}}}
    investigation = {"geography": {"selection": {"features": [{"id": "p", "geometry": AREA}]}}}
    result = with_grid_map({"downloadPath": str(archive_path)}, source, investigation, START, END)
    layer = result["map"]
    assert layer["kind"] == "grid"
    assert layer["unit"] == "mm"
    assert [row["value"] for row in layer["events"]] == [2, 3, 4, 5, 6, 7, 8]
    assert layer["events"][0]["date"] == "2025-01-01T12:00:00"
    source["upstream"]["selectors"]["mapVariable"] = "unknown"
    missing = with_grid_map({"downloadPath": str(archive_path)}, source, investigation, START, END)
    assert "map" not in missing
    assert "mapMessage" in missing


def test_station_area_keeps_each_feature_and_can_skip_a_failed_candidate():
    candidates = [(0, key, key, {"type": "Point", "coordinates": [x, x]})
                  for key, x in [("first", 0), ("failed", 0.4), ("third", 1)]]

    def fetch(candidate):
        if candidate[1] == "failed":
            raise ValueError("Provider unavailable")
        return {"unit": "m", "cadence": "monthly", "points": [{"month": "2025-01", "value": candidate[3]["coordinates"][0]}]}

    result = regional_entities({"id": "water", "upstream": {"variableId": "level"}}, AREA, START, END, candidates, fetch)
    layer = result["map"]
    assert layer["cadence"] == "monthly"
    assert layer["failures"] == 1
    assert [row["entityId"] for row in layer["events"]] == ["first", "third"]
    assert [row["value"] for row in layer["events"]] == [0, 1]


def test_noaa_area_checks_nearby_stations_and_preserves_zero_rainfall(monkeypatch):
    monkeypatch.setattr(station_catalogs, "noaa_stations", lambda: (
        ("outside", "Too far", 4, 0),
        ("nearby", "Nearby", 2.2, 0),
        ("inside", "Inside", 1, 0),
    ))
    source = {"id": "rain", "access": "noaa.ncei.daily", "product": "NOAA daily",
              "upstream": {"variableId": "PRCP", "geometryId": "p"}}
    investigation = {"geography": {"selection": {"features": [{"id": "p", "geometry": AREA}]}}}
    calls = []

    def fetch(candidate):
        station = candidate["upstream"]["selectors"]["stationId"]
        calls.append(station)
        return {"unit": "mm", "cadence": "daily", "points": [
            {"month": "2025-01-01", "value": 0 if station == "nearby" else None}
        ]}

    result = station_catalogs.fetch_for_selection(source, investigation, START, END, fetch)
    assert sorted(calls) == ["inside", "nearby"]
    assert result["map"]["stationSurface"]
    assert result["map"]["events"][0]["entityId"] == "nearby"
    assert result["map"]["events"][0]["value"] == 0
    with pytest.raises(ValueError, match="no devolvió datos de PRCP"):
        station_catalogs.fetch_for_selection(source, investigation, START, END,
                                             lambda _: {"points": []})


def test_firms_emits_detections_and_keeps_original_csv(monkeypatch, tmp_path):
    monkeypatch.setenv("FIRMS_MAP_KEY", "fixture")
    monkeypatch.setattr(firms, "directory", lambda: tmp_path)
    monkeypatch.setattr(firms, "read_text", lambda *_:
                        "latitude,longitude,acq_date,acq_time,frp,confidence\n"
                        "0,0,2025-01-01,0830,15,nominal\n"
                        "4,4,2025-01-01,0930,80,high\n")
    source = {"id": "frp", "upstream": {"variableId": "frp", "productId": "VIIRS_SNPP_SP", "geometryId": "p"}}
    investigation = {"geography": {"selection": {"features": [{"id": "p", "geometry": AREA}]}}}
    result = firms.fetch_firms(source, investigation, START, END)
    assert result["map"]["eventType"] == "fire"
    [detection] = result["map"]["events"]
    assert detection["date"] == "2025-01-01T08:30:00Z"
    assert detection["frp"] == 15
    assert "fixture" not in str(result)
