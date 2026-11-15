"""Baseline benchmark, not an accelerated implementation. Run in a fresh process.

Measures full public fit versus NumPy least squares coefficient calculation.
Timings are intentionally separate workloads: do NOT interpret their ratio as speedup.
"""
from pathlib import Path
import sys
import importlib.util
import json
import platform
import os
import io
from contextlib import redirect_stdout
from statistics import median
from time import perf_counter

import numpy as np


def peak_rss_bytes():
    """Native process lifetime high-water mark; includes imports, JIT and input arrays."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")]
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = wintypes.HANDLE
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not get_memory(get_process(), ctypes.byref(counters), counters.cb):
            raise OSError("GetProcessMemoryInfo failed")
        return counters.PeakWorkingSetSize
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def measure(call, repeats):
    start = perf_counter()
    result = call()
    first = perf_counter() - start
    times = []
    for _ in range(repeats):
        start = perf_counter()
        call()
        times.append(perf_counter() - start)
    return result, {"first_call_s": first, "warm_median_s": median(times),
                    "warm_min_s": min(times), "warm_max_s": max(times), "repeats": repeats}


def main(n=10_000):
    models = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("scientific_checks", models / "run_checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.isolate_scientific_package()
    from trend_scope.models.stats.regression import linear_regression
    import numba
    x = np.linspace(0., 100., n)
    y = 2. * x + 7. + np.random.default_rng(2026).normal(0., .1, n)
    design = np.column_stack((x, np.ones(n)))
    reference, reference_times = measure(lambda: np.linalg.lstsq(design, y, rcond=None)[0], 7)
    fitted, full_fit_times = measure(lambda: linear_regression(x, y), 7)
    actual = np.array([fitted["parameters"]["slope"], fitted["parameters"]["intercept"]])
    np.testing.assert_allclose(actual, reference, rtol=1e-10, atol=1e-10)
    configuration = io.StringIO()
    with redirect_stdout(configuration):
        np.show_config()
    print(json.dumps({
        "n": n, "dtype": "float64", "seed": 2026, "python": platform.python_version(),
        "numpy": np.__version__, "numba": numba.__version__, "platform": platform.platform(),
        "processor": platform.processor(), "numba_threads": numba.get_num_threads(),
        "thread_environment": {name: os.environ.get(name) for name in (
            "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS")},
        "numpy_configuration": configuration.getvalue(),
        "numpy_coefficient_reference": reference_times, "full_legacy_linear_fit": full_fit_times,
        "jit_compilation_s": None, "jit_note": "Current public linear path uses NumPy, not a JIT kernel",
        "max_coefficient_difference": float(np.max(np.abs(actual-reference))),
        "input_bytes": x.nbytes+y.nbytes, "reference_design_bytes": design.nbytes,
        "process_peak_rss_bytes": peak_rss_bytes(),
        "memory_note": "Process lifetime peak; includes reference, imports and public output lists",
        "comparison_note": "Different workloads; no acceleration claim",
    }, allow_nan=False))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10_000)
