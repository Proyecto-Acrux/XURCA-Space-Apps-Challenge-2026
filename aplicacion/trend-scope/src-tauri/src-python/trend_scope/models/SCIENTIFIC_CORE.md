# Scientific infrastructure v1 — candidate

Stage 0 adds contracts, structural validation, an explicit registry, synchronous
execution, bounded strict JSON and an adapter to the EXISTING linear regression.
It does not implement a new regression, other algorithms, a selector, storage or IPC.

## Contracts

`ScientificDataset` owns metadata but borrows arrays. Dataclasses are frozen;
arrays and nested mappings are NOT deeply immutable. Callers must not mutate
them during validation/execution. No implicit copies or in-place operations.
Float64 conversion occurs at the existing regression boundary.

Shapes: (time,), (y,x), (time,y,x), (time,feature), (time,y,x,feature).
Shared dimension lengths must agree. Prefer separate named variables with their
own units; feature arrays require names and one unit per feature. Coordinates
can be rectilinear 1D or curvilinear 2D with an explicit CRS. CRS and unit strings
are recorded, not geodetically interpreted or automatically converted.
Optional spatial_resolution records positive x/y nominal resolutions in CRS
axis units. It is not inferred for irregular or curvilinear grids.

Time uses elapsed numeric coordinates with a required origin, unit and calendar.
Optional bounds capture observation duration; optional frequency is a declared
label, not a claim of regularity. No date parsing/calendar conversion is performed.
Masked nonfinite data are structurally allowed only with an exact boolean mask
(True = invalid). Algorithms decide whether missingness is supported.

The temporal linear adapter accepts a selected (time,) variable only, at least
two strictly increasing times and no invalid samples. It preserves irregular
spacing, values, units, metadata and transformations. It rejects duplicates and
disorder rather than sorting or aggregating them. Legacy `linear_regression(x,y)`
retains its original public behavior, including its different duplicate policy.
Time coordinates must already represent elapsed duration, not ordinal month labels.

`ODEProblem` is a separately validated request with initial state, physical
parameters, units, output times and model ID. No ODE executor is registered yet;
no user-provided code is executed. RK4/RK45 remain unchanged.

## Registry, results and execution

`default_registry()` exposes only method `linear`, status candidate, via an
explicit function reference. Existing output `algorithm=linear_regression` and
FitOutput keys are preserved inside AnalysisResult.payload. No configuration or
schema migrations are necessary. Unknown methods/parameters are errors.

`analyze(dataset, request, registry, context)` returns AnalysisResult. It reports
completed results only. ValueError denotes invalid/incompatible/insufficient
input or exhausted input budget; AnalysisCancelled denotes cancellation. No
generic exception catch hides scientific/runtime failures. Result status fields
reserve future richer lifecycle reports; they are not implemented states today.

Stages emitted: validating, analysing, completed. Cancellation is cooperative
BEFORE/AFTER the current monolithic fit, not interruptible mid-kernel. This is
a synchronous worker API: callers must schedule it off the UI thread. This stage
does not claim UI responsiveness or wire callbacks into PyTauri.

Input byte and observation budgets are preflight guards, not total RSS guarantees.
The existing fit creates temporary arrays and Python output lists. Only small
outputs should be serialized; JSON item/depth/byte limits reject oversized
transport. Byte validation occurs after encoding; it is not a streaming memory
limit. NaN/Infinity are rejected, never silently replaced. Mathematical undefined
metrics remain explicit None in the existing linear payload.

Validation O(total elements), plus metadata checks. Current linear adapter has
O(n log n) time (legacy duplicate detection) and O(n) memory. No accelerated
implementation was added; stage 1 must benchmark a representative Numba kernel.
No fastmath, Rust, GPU, heavy framework or new project dependency.

## Reproducible verification

From any folder, with NumPy, Numba, pytest and SciPy available:

```
python path/to/models/run_checks.py -q
python path/to/models/benchmarks/linear_baseline.py 10000
```

The harness installs a namespace for the REAL trend_scope package path without
executing its desktop __init__. It collects temporary copies of the tests to
prevent pytest from importing the desktop ancestor during collection. Source
modules are imported from the actual checkout. It does not stub scientific functions. This is
explicit scientific isolation, NOT a successful normal-package/IPC integration
test. The existing desktop import and broken handler dispatcher are untouched.
SciPy is used by Numba's existing polynomial linalg path in the legacy test;
no pyproject change was authorized or made.

Tests cover all contract shapes, coordinate alignment, feature units, masks,
nonfinite metadata, chronological requirements, legacy payload preservation,
units/provenance, unknown methods, budgets, cancellation, JSON and ODE validation.
The original regression tests run in the same isolated harness.

Benchmark: synthetic seed 2026, float64, NumPy lstsq coefficient reference,
first call and 7 warm repetitions, native process peak RSS plus array sizes.
Reference coefficients and full public fit are DIFFERENT WORKLOADS; their timing
ratio is not a speedup claim. Compilation is null because this path is NumPy.
Run each sample size in a fresh process for meaningful memory/first-call records.
Future JIT benchmarks must additionally distinguish empty-cache compilation,
cache loading and warm execution, capture BLAS/thread settings and test equivalence
against independent equations/reference code before interpreting performance.

## Pending acceptance

Independent scientific audit, normal import/PyTauri verification, dispatcher
repair with separate authorization, kernel benchmark with actual compilation,
and hard memory/mid-kernel cancellation require later work. No confidence
intervals, forecasts, spatial aggregation or per-pixel execution are inferred.

## Executed evidence — 2026-11-14

Branch ema_workspace. Portable Python 3.11.9 installed in a temporary directory
with NumPy 2.4.6, Numba 0.68.1, pytest 9.2.0 and SciPy 1.17.1. These are the
tested versions, not changes to the project's dependency declarations.

Initial pytest collection failed because the desktop ancestor required AnyIO.
The isolated collection harness above resolved this without changing desktop code.
First suite: 52 passed in 11.97 s. After adversarial metadata/shape tests and
validation corrections: **56 passed in 1.88 s**, including legacy regression.
No native integration tests were run. No claim of independent audit approval.

Baseline processes on Windows, float64, seed 2026, seven warm repetitions:

| Samples | First full fit (ms) | Warm full fit median (ms) | Process peak RSS (bytes) | Max coefficient difference vs NumPy |
|---:|---:|---:|---:|---:|
| 100 | 32.344 | 0.211 | 63,434,752 | 8.88e-16 |
| 10,000 | 45.363 | 5.010 | 65,105,920 | 1.42e-14 |
| 1,000,000 | 706.672 | 616.837 | 415,051,776 | 8.79e-14 |

Raw records are in benchmarks/results, including NumPy build configuration,
thread environment, timing spread, platform, array sizes and reference timings.
The public fit includes lists and all metrics; the NumPy reference only estimates
coefficients. Timings are not directly comparable as acceleration evidence.
The first call is NOT a compilation measurement. JIT compilation is null.
RSS includes imports and both workloads and is not incremental allocation.
The million-sample memory peak demonstrates why the next stage must avoid
unnecessary output lists and temporaries before processing large grids.

Next delivery: validate and benchmark one representative Numba linear kernel
against the existing candidate, retaining the public API; no other algorithm
should be added in that change.
