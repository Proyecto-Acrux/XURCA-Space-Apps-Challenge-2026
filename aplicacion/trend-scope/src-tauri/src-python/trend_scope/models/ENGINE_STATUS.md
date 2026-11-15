# Scientific engine: implementation inventory and handoff

Status: **candidate implementations, not an independently approved engine**.
Performance experiments were suspended at the user's request on 2026-11-15.
All prior benchmark scripts/results are retained unchanged. No new performance
claim or benchmark is part of this expansion.

## Preservation classification

**Protected:** linear and polynomial regression, their kernels/contracts/tests,
RK4 and its service/vector wrapper, stage-0 contracts/validators/default registry,
prior documentation and benchmark artifacts. Existing reports label these
`candidate`; functional evidence must not be confused with independent approval.
The new work does not upgrade that status. `PRESERVATION.json` records hashes
and protected function-source hashes for the shared regression file.

**Previously partial, completed within the specified numerical domain:** RK45
finite-input/derivative/step/buffer guards and terminal-step handling; legacy
ridge, exponential, logarithmic, power and harmonic regression validation and
stable computation. In the shared regression file only unprotected helpers and
legacy methods changed; public linear/polynomial functions are byte-for-byte
identical at the source-segment level and their kernels are unchanged.

The old transformed-linear helper formed differences of large raw moments,
losing slope information with large predictor offsets. It now reuses the
preserved linear kernel. Ridge solves the equivalent augmented least-squares
system instead of normal equations, keeping its original unpenalized intercept
and raw-power penalty. Harmonic regression rejects numerical rank deficiency.
Undefined/model-dependent adjusted R2 and AIC are now null on these legacy
paths; FitOutput already allows nullable metrics. Exponential and power fits
still minimize squared log-response errors, not original-scale OLS. Their
amplitudes must be representable. No protected algorithm was rewritten.

## Implemented inventory

| Family | Implementations | Entry points |
|---|---|---|
| Trends | Sen; conventional/seasonal MK; multivariable OLS | `stats/trends.py` |
| Dependence corrections | Hamed–Rao and Yue–Wang MK, explicit lag | `optional_methods.modified_mann_kendall` |
| Changes | two-sided reset CUSUM; exact l2 PELT via ruptures; ADWIN via river | `change_detection/cusum.py`, `optional_methods.py` |
| Signals | trailing mean; FIR taps/design; SOS IIR causal/forward-backward; FFT; one shared SSA | `signal/processing.py` |
| Decomposition | STL, discrete multilevel wavelet with reconstruction | `optional_methods.py` |
| Forecasts | naive/seasonal naive, additive Holt–Winters, ARIMA, SARIMA; chronological holdout against naive | `optional_methods.forecast` |
| Similarity | exact banded DTW; exact bounded self-join Matrix Profile; DTW K-Means/DBA | `similarity/`, `optional_methods.dtw_kmeans` |
| Reduction | fractional-bin PAA, LTTB visualization selection | `data_reduction/reduction.py` |
| Events | Count-Min Sketch, Misra–Gries, Space-Saving; Kleinberg exponential-gap automaton | `text_events/` |
| Anomalies | seeded Isolation Forest | `optional_methods.isolation_forest` |
| Dynamics | preserved RK4, guarded Dormand–Prince RK45, vector systems; explicit 1D diffusion | `dynamical/` |
| Spatial adapter | independent temporal analysis per `(time,y,x)` cell, explicit bounds | `adapters/grid.py` |

No duplication of CUSUM, SSA or Matrix Profile across conceptual families.
Matrix Profile uses exact direct distances for bounded small inputs; it is not
labelled STOMP/SCRIMP++ or a high-volume implementation. Constant windows are
rejected because the chosen z-normalization is undefined.

## Contracts and integration

Use `extended_registry.scientific_registry()` with the existing
`execution.analyze(dataset, request, registry, context)`. It extends, without
modifying, `default_registry()`. IDs and parameter names are available through
`registry.describe()`. Optional methods are advertised only when their package
is installed; no dynamic import or executable expression comes from config.
Existing frontend/IPC dispatch is preserved; new methods are Python engine
capabilities, not new UI controls or arbitrary LLM-executable functions.

Inputs are finite real arrays with explicit units and time coordinates. Missing
data require an upstream, recorded policy. No silent sorting, imputation,
flattening, normalization, unit conversion or aggregation occurs. Regular-grid
methods reject irregular sampling; temporal diagnostics allow ordered irregular
data where valid. Boolean arrays, masks and inexact large integer conversion are
rejected by new boundaries. Float overflow yields a controlled failure rather
than nonfinite JSON. Use the existing bounded strict serializer for transport.

Multivariable OLS selects a separate `(time,feature)` variable by ID and reports
one slope unit per feature. DTW comparison requires matching units. ADWIN's
adapter requires explicit dimensionless normalization to [0,1]. A per-cell map
keeps coordinates and separate results; it is not a regional average or a
multiple-testing correction. The adapter has a small explicit result-count cap.

ODE/PDE simulations and event/collection algorithms have different contracts:
RK4 uses ODEProblem and trusted ODEModelRegistry; RK45 keeps its original
compiled `(rhs,y0,t_span,...) -> (times,states)` interface with adaptive output.
Diffusion accepts initial values, physical positions and times, constant positive
diffusivity and fixed Dirichlet boundaries equal to initial endpoints. It rejects
`alpha*dt/dx^2 > 1/2`; it is not a universal PDE solver. Event sketches accept
strings; Kleinberg accepts strictly ordered event arrivals; DTW clustering
accepts `(series,time,feature)` collections. These are explicit Python APIs,
not coercions of a single observed environmental series.

Core uses NumPy/Numba/SciPy. Optional packages are lazy and separately documented
in `requirements-scientific-optional.txt`, a tested Python 3.11 environment.
No optional package became an unconditional desktop dependency. No Rust, GPU
framework, trained weights, remote data acquisition or new persistence layer.
No new speed or memory benchmarks were run. Native libraries are used rather
than recreating statistical optimizers. Custom compatible loops use serial
Numba without fastmath. This API remains synchronous: schedule off the UI thread.
Cancellation exists at execution boundaries/cells, not inside every optimizer.

## Mathematical decisions and limitations

- Sen is median pairwise slope, with a centered median intercept and no IID CI.
  MK uses tie-corrected score variance and continuity-corrected asymptotic normal
  tails. Seasonal variance assumes independent strata; autocorrelation variants
  are explicit named methods, not automatically guaranteed corrections.
- OLS uses centered/scaled SVD least squares, rejects rank deficiency and returns
  descriptive fit metrics. Correlation, trend significance and physical
  importance remain distinct. No confidence interval is invented.
- CUSUM baseline, allowance and threshold must be supplied and calibrated;
  resets identify detection time, not exact onset. PELT penalty is in squared
  response units. Neither method certifies operational emergencies.
- FIR uses zero initial history; forward-backward IIR, STL and SSA use future
  samples within their input. Split data before preprocessing for prediction.
  FFT amplitude uses a rectangular window and mean removal by default, with
  leakage/aliasing warnings. Wavelet boundary extension is symmetric.
- Forecasts fit only the prefix for evaluation, compare the held-out suffix
  against naive, report MAE/RMSE and errors by horizon, then refit for the requested
  future horizon. This is one chronological holdout, not rolling-origin evidence
  or calibrated uncertainty. ARIMA order limits bound resources; failures to
  converge are errors. Additive Holt–Winters is the supported variant.
- Kleinberg minimizes exponential-gap emission costs plus upward state penalties
  with exact dynamic programming. It returns hierarchical intervals. Sketch
  frequency bounds apply only to insertion-only event streams. Hashing is
  deterministic; probabilistic Count-Min guarantees assume suitable hashing.
- DTW/DBA clustering is a local optimization with explicit iteration limits;
  no claim of globally optimal clustering. Isolation Forest reports exploratory
  in-sample anomalies with a recorded seed.
- Resource guards bound explicit array/pair/iteration work, not total process
  memory. Truncation/roundoff and domain-specific scientific assumptions still
  require independent review and validation on real environmental products.

## Explicitly pending — not registered or represented as completed

1. **LSTM, GRU, TFT, Chronos, TimesFM, Moirai:** approved architectures/checkpoints,
   versions/licenses, data and training/evaluation protocol, resource/dependency
   decisions. No heavyweight framework or pretrained model is downloaded. An
   operator question about approved weights/data remains unanswered.
2. **BERTopic and Top2Vec:** approved corpus, language/embedding model and model
   download policy are required. Numerical environmental arrays are not text.
3. **Prophet:** optional inclusion was conditional in the specification; its
   extra dependency and benefit have not been established. No placeholder.
4. **Additional PDEs, general grid statistics and multivariable grid forecasting:**
   equation, domain, boundary conditions, units/aggregation and scientific
   question must be specified; the delivered diffusion problem is explicit.
5. **Rolling-origin calibration, production IPC/UI exposure, learned-model
   packaging and independent scientific audit:** not established by unit tests.

The engine is therefore **not claimed complete for the entire aspirational
inventory**. Publish only these implemented candidate capabilities with this
inventory, not a claim of completed neural/text methods. No pending entry is
represented by a dummy function, simulated metric or false registry capability.

## Correctness checks and references

Tests use analytic exponential/oscillatory/diffusion solutions, MK score/tie
formulas, SciPy Sen reference, independent exhaustive PELT/Kleinberg objectives,
signal impulses and known spectral amplitudes, full SSA/wavelet reconstruction,
frequency-summary bounds, constant/step cases, chronological leakage checks,
JSON/provenance/units and registry compatibility. No stress or performance tests.
Run targeted files with pytest in a normal importable checkout, or select new
modules with `models/run_checks.py -q -k ...` using a writable NUMBA_CACHE_DIR.
The isolated harness does not prove native PyTauri behavior.

Final integration verification (2026-11-15): origin/main commits through
`c44914a` were incorporated by fast-forward without conflicts. The new-method
tests plus existing contract/infrastructure tests ran with **normal package
imports**, not the isolation harness: **94 passed**. One tslearn warning reports
that optional HDF5 support is unavailable; no HDF5 operation is used. The
36-file working-tree preservation check and both protected regression source
segments matched. Hashes record Windows working-tree bytes; a checkout that
changes line endings changes raw hashes. No performance tests were executed.
The existing Python regression handler additionally passed **7 compatibility
tests** covering all its exposed regression IDs and strict JSON payloads.
This is Python handler verification, not a native-window or end-to-end NASA test.
`git diff --cached --check` reports one pre-existing extra EOF blank line in
`stats/linear_reference.py:102`. That protected reference was intentionally
preserved byte-for-byte; no new numerical or integration failure is hidden by
this formatting exception.

Subsequent collaborator commit `6303f22` was integrated without conflicts in
merge `ba7d096`. It changes sources/coverage, not models. After this integration,
the normal-import handler and extended-registry checks passed **20 tests**.
Protected implementation files remained unchanged. Native desktop execution and
the pending methods above remain outside the verified scope of this delivery.

Sources: [SciPy Sen](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html),
[SciPy signal](https://docs.scipy.org/doc/scipy/reference/signal.html),
[statsmodels SARIMAX](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html),
[statsmodels STL](https://www.statsmodels.org/stable/generated/statsmodels.tsa.seasonal.STL.html),
[PyWavelets](https://pywavelets.readthedocs.io/en/latest/ref/dwt-discrete-wavelet-transform.html),
[pyMannKendall source](https://github.com/mmhs013/pyMannKendall),
[tslearn clustering](https://tslearn.readthedocs.io/en/stable/gen_modules/tslearn.clustering.html),
[Kleinberg 2002](https://www.cs.cornell.edu/info/people/kleinber/bhs.pdf).
