"""Stage 1A: isolated processes, explicit compilation/cache load, equivalent full APIs.

python benchmark_linear.py --output stage1a_results.json
Fresh temporary Numba cache per sample size; no existing caches are deleted.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from time import perf_counter


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(mode, n):
    models = Path(__file__).resolve().parents[1]
    load("checks", models/"run_checks.py").isolate_scientific_package()
    baseline = load("baseline", models/"benchmarks"/"linear_baseline.py")
    import numpy as np
    import numba
    from trend_scope.models.stats.regression import linear_regression
    from trend_scope.models.stats.linear_reference import linear_regression as reference
    from trend_scope.models.stats.linear_kernel import linear_kernel
    rng = np.random.default_rng(2026)
    x = np.linspace(0.,100.,n)
    y = 2*x+7+rng.normal(0., .1,n)
    compiled_s = None
    cache_hits = cache_misses = None
    if mode != "reference":
        start = perf_counter()
        linear_kernel.compile((numba.types.float64[::1],numba.types.float64[::1]))
        compiled_s = perf_counter()-start
        if not linear_kernel.nopython_signatures:
            raise AssertionError("Kernel did not compile in nopython")
        cache_hits = sum(linear_kernel.stats.cache_hits.values())
        cache_misses = sum(linear_kernel.stats.cache_misses.values())
        if mode == "cold" and cache_misses != 1:
            raise AssertionError("Cold benchmark unexpectedly reused a cache")
        if mode == "cached" and cache_hits != 1:
            raise AssertionError("Cached benchmark did not load the compiled kernel")
    function = reference if mode == "reference" else linear_regression
    result, timing = baseline.measure(lambda: function(x,y),7)
    peak_before_verification = baseline.peak_rss_bytes()
    kernel_timing = None
    if mode != "reference":
        _, kernel_timing = baseline.measure(lambda: linear_kernel(x,y),7)
    # Both full workloads get checked against an independent native least-squares solution.
    coeffs = np.linalg.lstsq(np.column_stack((x,np.ones(n))),y,rcond=None)[0]
    actual = [result["parameters"]["slope"],result["parameters"]["intercept"]]
    np.testing.assert_allclose(actual,coeffs,rtol=1e-10,atol=1e-10)
    import io
    from contextlib import redirect_stdout
    configuration=io.StringIO()
    with redirect_stdout(configuration):
        np.show_config()
    return {"mode":mode,"n":n,"dtype":"float64","seed":2026,
            "cache_hits":cache_hits,"cache_misses":cache_misses,
            "compile_or_cache_load_s":compiled_s,"full_api":timing,"kernel":kernel_timing,
            "peak_rss_before_verification_bytes":peak_before_verification,
            "memory_note":"Lifetime process peak incl imports and compile/cache load; verification excluded",
            "input_bytes":x.nbytes+y.nbytes,"kernel_output_bytes":2*n*8,
            "max_coefficient_error":float(np.max(np.abs(np.array(actual)-coeffs))),
            "python":platform.python_version(),"numpy":np.__version__,"numba":numba.__version__,
            "platform":platform.platform(),"processor":platform.processor(),
            "numpy_configuration":configuration.getvalue(),
            "threads":{key:os.environ.get(key) for key in (
                "OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMBA_NUM_THREADS")}}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker",choices=["reference","cold","cached"])
    parser.add_argument("--n",type=int,default=10000)
    parser.add_argument("--output",default="stage1a_results.json")
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker,args.n),allow_nan=False))
        return
    records=[]
    for n in (100,10000,1000000):
        with tempfile.TemporaryDirectory(prefix="xurca-numba-bench-") as cache:
            environment=os.environ.copy()
            environment.update(NUMBA_CACHE_DIR=cache,PYTHONDONTWRITEBYTECODE="1",
                               OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",
                               MKL_NUM_THREADS="1",NUMBA_NUM_THREADS="1")
            for mode in ("reference","cold","cached"):
                process=subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),
                                        "--worker",mode,"--n",str(n)],env=environment,
                                       capture_output=True,text=True,check=True)
                record=json.loads(process.stdout)
                records.append(record)
                print(f'{n} {mode}: {record["full_api"]["warm_median_s"]:.6f}s',flush=True)
    Path(args.output).write_text(json.dumps(records,indent=2,allow_nan=False),encoding="utf-8")


if __name__ == "__main__":
    main()
