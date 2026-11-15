"""Isolated scientific harness: bypass desktop __init__, never claim to test IPC.

Usage: python models/run_checks.py [pytest arguments]
Creates a namespace for the real package path; no numeric or dependency stubs.
"""
from pathlib import Path
import sys
import types
import shutil
import tempfile


def isolate_scientific_package() -> Path:
    models = Path(__file__).resolve().parent
    if "trend_scope" not in sys.modules:
        package = types.ModuleType("trend_scope")
        package.__path__ = [str(models.parent)]
        package.__package__ = "trend_scope"
        sys.modules["trend_scope"] = package
    return models


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    models = isolate_scientific_package()
    import pytest
    # Pytest otherwise imports ancestor __init__.py during package collection,
    # even though the scientific namespace is already installed. Copy TESTS ONLY
    # to a temporary collection root; imports still resolve to real source files.
    with tempfile.TemporaryDirectory(prefix="xurca-tests-") as collection:
        root = Path(collection)
        for source in (models / "tests").glob("test_*.py"):
            shutil.copy2(source, root / source.name)
        shutil.copy2(models / "stats" / "test_regression.py", root / "test_regression.py")
        raise SystemExit(pytest.main([
            "--import-mode=importlib", "-p", "no:cacheprovider",
            "--rootdir", str(root), "--confcutdir", str(root), str(root), *sys.argv[1:],
        ]))
