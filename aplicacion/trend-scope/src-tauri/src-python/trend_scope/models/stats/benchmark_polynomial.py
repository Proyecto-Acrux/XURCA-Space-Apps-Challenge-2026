"""Polynomial stage 1B benchmark. Old raw NumPy/Numba solver vs scaled native solver.

Run each workload in a fresh process, same data and full fit payload; new fit
additionally reports rank/conditioning/normalized representation. No speedup
is presumed. Old metric semantics are not treated as a correctness oracle.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from time import perf_counter

import importlib.util


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(mode: str, n: int, degree: int) -> dict:
    models=Path(__file__).resolve().parents[1]
    load("checks",models/"run_checks.py").isolate_scientific_package()
    measurement=load("measurement",models/"benchmarks"/"linear_baseline.py")
    import numpy as np
    import numba
    from trend_scope.models.stats import regression
    rng=np.random.default_rng(2026)
    x=np.linspace(-1.,1.,n)
    y=2*x*x-3*x+7+rng.normal(0.,.1,n)
    compile_s=None
    cache_hits=cache_misses=None
    if mode != "native":
        signatures=[(regression._jit_poly_fit,(numba.types.float64[::1],numba.types.float64[::1],numba.types.int64)),
                    (regression._jit_eval_poly,(numba.types.float64[::1],numba.types.float64[::1])),
                    (regression._jit_compute_metrics,(numba.types.float64[::1],numba.types.float64[::1],numba.types.int64))]
        start=perf_counter()
        for function,signature in signatures:
            function.compile(signature)
        compile_s=perf_counter()-start
        cache_hits=sum(sum(function.stats.cache_hits.values()) for function,_ in signatures)
        cache_misses=sum(sum(function.stats.cache_misses.values()) for function,_ in signatures)
        if mode == "old-cold" and cache_misses != 3:
            raise AssertionError("Expected three cold compilations")
        if mode == "old-cached" and cache_hits != 3:
            raise AssertionError("Expected three cache hits")
    def old_fit():
        xa,ya=regression._validate_inputs(x,y)
        coeffs=regression._jit_poly_fit(xa,ya,degree)
        predicted=regression._jit_eval_poly(xa,coeffs)
        return regression._build_output("polynomial_regression",xa,ya,predicted,
            {f"c_{degree-i}":float(c) for i,c in enumerate(coeffs)})
    call=(lambda: regression.polynomial_regression(x,y,degree)) if mode == "native" else old_fit
    result,timing=measurement.measure(call,7)
    rss=measurement.peak_rss_bytes()
    expected=np.polynomial.Polynomial.fit(x,y,degree)
    fitted_error=float(np.max(np.abs(np.asarray(result["y_pred"])-expected(x))))
    np.testing.assert_allclose(result["y_pred"],expected(x),rtol=1e-11,atol=1e-11)
    import io
    from contextlib import redirect_stdout
    configuration=io.StringIO()
    with redirect_stdout(configuration):
        np.show_config()
    return {"n":n,"degree":degree,"mode":mode,"full_api":timing,
        "compile_or_cache_load_s":compile_s,"cache_hits":cache_hits,"cache_misses":cache_misses,
        "peak_rss_before_verification_bytes":rss,"input_bytes":x.nbytes+y.nbytes,
        "design_bytes":n*(degree+1)*8,"max_fitted_difference":fitted_error,
        "dtype":"float64","seed":2026,"python":platform.python_version(),"numpy":np.__version__,
        "numba":numba.__version__,"platform":platform.platform(),"processor":platform.processor(),
        "numpy_configuration":configuration.getvalue(),
        "threads":{k:os.environ.get(k) for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMBA_NUM_THREADS")},
        "note":"New solver adds rank, conditioning, scaled basis, validation; old metrics are not an oracle. Native path has no JIT."}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker",choices=["old-cold","old-cached","native"])
    parser.add_argument("--n",type=int,default=10000)
    parser.add_argument("--degree",type=int,default=2)
    parser.add_argument("--output",default="stage1b_results.json")
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker,args.n,args.degree),allow_nan=False))
        return
    records=[]
    for n in (100,10000,1000000):
        with tempfile.TemporaryDirectory(prefix="xurca-poly-bench-") as cache:
            environment=os.environ.copy()
            environment.update(NUMBA_CACHE_DIR=cache,PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="1",
                               OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",NUMBA_NUM_THREADS="1")
            for mode in ("old-cold","old-cached","native"):
                process=subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"--worker",mode,
                    "--n",str(n),"--degree",str(args.degree)],env=environment,capture_output=True,text=True,check=True)
                record=json.loads(process.stdout)
                records.append(record)
                print(f'{n} {mode}: {record["full_api"]["warm_median_s"]:.6f}s',flush=True)
    Path(args.output).write_text(json.dumps(records,indent=2,allow_nan=False),encoding="utf-8")


if __name__ == "__main__":
    main()
