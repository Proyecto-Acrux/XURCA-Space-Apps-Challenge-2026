"""Stage 1C benchmark: cold JIT, cache loading, warm performance, native RSS.

Synthetic decay only; classical explicit RK4 is not validated for all ODEs by
this benchmark. Run: python rk4_benchmark.py --output rk4_results.json
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


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(mode,n):
    models=Path(__file__).resolve().parents[1]
    load("checks",models/"run_checks.py").isolate_scientific_package()
    measure=load("measure",models/"benchmarks"/"linear_baseline.py")
    import numpy as np
    import numba
    from trend_scope.models.dynamical.rk4 import rk4
    from trend_scope.models.benchmarks.rk4_reference import rk4 as previous
    from trend_scope.models.tests.rk4_fixtures import decay
    times=np.linspace(0.,1.,n)
    state=np.arange(1.,9.)
    elapsed=None
    hits=misses=None
    if mode=="python":
        call=lambda:previous.py_func(decay.py_func,state,times)
    else:
        function=previous if mode.startswith("old") else rk4
        signature=(numba.typeof(decay),numba.types.float64[::1],numba.types.float64[::1])
        if mode.startswith("new"):
            signature += (numba.types.Omitted(()),numba.types.Omitted(256*1024*1024),numba.types.Omitted(1_000_000))
        start=perf_counter()
        function.compile(signature)
        elapsed=perf_counter()-start
        hits=sum(function.stats.cache_hits.values())
        misses=sum(function.stats.cache_misses.values())
        if mode.endswith("cold") and misses != 1:
            raise AssertionError("Cold compile unexpectedly used cache")
        # A dispatcher-valued argument can miss cache across processes. Record
        # the observed result instead of labelling an attempted reload a hit.
        call=lambda:function(decay,state,times)
    output,timing=measure.measure(call,7)
    rss=measure.peak_rss_bytes()
    exact=np.exp(-times[:,None])*state
    error=float(np.max(np.abs(output-exact)))
    np.testing.assert_allclose(output,exact,rtol=2e-9,atol=1e-12)
    import io
    from contextlib import redirect_stdout
    configuration=io.StringIO()
    with redirect_stdout(configuration):
        np.show_config()
    return {"mode":mode,"n_times":n,"state_size":len(state),"dtype":"float64","rhs":"synthetic y'=-y",
        "full_call":timing,"compile_or_cache_load_s":elapsed,"cache_hits":hits,"cache_misses":misses,
        "cache_reused": bool(hits) if hits is not None else None,
        "peak_rss_before_verification_bytes":rss,"input_bytes":times.nbytes+state.nbytes,
        "output_bytes":output.nbytes,"max_absolute_analytic_error":error,
        "python":platform.python_version(),"numpy":np.__version__,"numba":numba.__version__,
        "platform":platform.platform(),"processor":platform.processor(),"numpy_configuration":configuration.getvalue(),
        "threads":{k:os.environ.get(k) for k in ("NUMBA_NUM_THREADS","OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")},
        "note":"New solver includes guards/callback isolation/scaled increments; RSS includes imports/JIT and retained outputs."}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker",choices=("old-cold","old-cached","new-cold","new-cached","python"))
    parser.add_argument("--n",type=int,default=10001)
    parser.add_argument("--output",default="rk4_results.json")
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker,args.n),allow_nan=False))
        return
    records=[]
    for n in (101,10001,100001):
        with tempfile.TemporaryDirectory(prefix="xurca-rk4-bench-") as cache:
            environment=os.environ.copy()
            environment.update(NUMBA_CACHE_DIR=cache,PYTHONDONTWRITEBYTECODE="1",
                NUMBA_NUM_THREADS="1",OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1")
            modes=["old-cold","old-cached","new-cold","new-cached"]
            if n<=10001:
                modes.append("python")
            for mode in modes:
                # Keep old/new caches independent so even the shared RHS starts cold.
                environment["NUMBA_CACHE_DIR"]=str(Path(cache)/("new" if mode.startswith("new") else "old"))
                result=subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"--worker",mode,"--n",str(n)],
                    env=environment,capture_output=True,text=True)
                if result.returncode:
                    raise RuntimeError(f"Benchmark worker failed: {result.stderr}")
                record=json.loads(result.stdout)
                records.append(record)
                print(f'{n} {mode}: {record["full_call"]["warm_median_s"]:.6f}s',flush=True)
    Path(args.output).write_text(json.dumps(records,indent=2,allow_nan=False),encoding="utf-8")


if __name__=="__main__":
    main()
