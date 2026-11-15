# Stage 1A — linear regression 1.1.0-candidate

Scope: accelerate only the existing linear regression. Public arguments and
FitOutput/LinearFitOutput keys remain unchanged. No new dependencies, other
algorithms, IPC, source connectors, frontend, storage or Tauri changes.
Registry metadata now matches the method version and acceleration technology.

## Numerical method

For paired observations, minimize sum((y_i-a-b*x_i)^2). Compute shifted values
relative to the first observation, divide by maximum absolute shift, and center
the resulting bounded coordinates. Compensated (Kahan) sums accumulate means,
cross products, sums of squares and residual magnitudes in a fixed serial order.
The slope is the normalized cross product divided by the normalized x sum of
squares, restored to physical units; intercept is y_mean-b*x_mean. Predictions
use the centered form to avoid cancellation from a large absolute x origin.

`frexp`/`ldexp` restore the slope scale without a premature overflow/underflow
in multiplying and then dividing scale factors. Unrepresentable spans, slopes,
intercepts, predictions or error metrics produce ValueError. Float64 cannot
recover information lost before the call. Integer inputs beyond +/-2**53 are
conservatively rejected: normalize timestamps to elapsed time before conversion.
This rejects even individually representable larger integers to keep the accepted
integer range exact and predictable. Floating input retains its supplied precision.

Residual = observed-fitted; RMSE=sqrt(SSE/n), MAE=sum(abs(residual))/n.
R²=1-SSE/SST, adjusted R²=1-(1-R²)*(n-1)/(n-2). Constant y gives null R²;
n=2 gives null adjusted R². AIC uses the Gaussian likelihood with three estimated
parameters (slope, intercept, variance); it is null for zero residuals or n=2.
The saturated two-point case must not turn roundoff into a fitted error variance.
No arbitrary near-zero threshold is used for larger samples.

## Technology and memory

`linear_kernel.py:linear_kernel(x, y)` is private and accepts validated finite
float64 vectors. It is compiled using `njit(cache=True, nogil=True)`, nopython,
without fastmath or parallel reductions. Reproducibility applies within the
tested environment; cross-platform bitwise identity is not promised.

Kernel: O(n) time, two float64 output arrays (16*n bytes) and O(1) auxiliary
storage. Public API: O(n) for ordered x; O(n log n) if unordered duplicate
detection is required. Unsorted pairs are never reordered. Typed NumPy arrays
avoid the previous Python per-element boolean scan; Python sequences retain it.
Contiguous float64 arrays are reused; noncontiguous/different dtype inputs may
need one explicit conversion. Inputs are never modified.

Keeping lists for x, fitted values and residuals preserves the existing API but
still costs O(n) Python-object memory. This stage does not introduce bulk-output
storage or claim a hard RSS limit. Parallelization is deferred: a single series
has ordered reductions; independent pixels are a separate explicitly requested
adapter and benchmark task. No evidence justifies a Rust rewrite here.

## Reference and verification

`linear_reference.py` freezes the preceding NumPy implementation exclusively
for equivalence tests and fair before/after API benchmarks. It is never registered
or called by the product. Independent checks also use analytical lines, orthogonal
noise, NumPy least squares and Decimal with 70-digit arithmetic for a large-origin
case. Equivalence to the old implementation alone would not establish correctness.

Tests cover growing/decreasing/constant series; noise; offsets and scales;
insufficient data; nonfinite/invalid data; duplicate and unsorted coordinates;
float32 promotion; readonly/strided arrays; under/overflow boundaries; integer
precision loss; permutation and physical-unit conversion invariants; strict JSON;
nopython signatures; repeatability; and registry/version integration. Tolerances
are scale-aware (typically 1e-12 or stricter on well-conditioned fixtures); near
zero residuals and AIC are not expected to match bitwise across reduction methods.

The final isolated scientific suite passed **82 tests in 14.62 s** using Python
3.11.9, NumPy 2.4.6, Numba 0.68.1, pytest 9.2.0 and SciPy 1.17.1. An earlier run
failed two tests because the integer-precision validation error was hidden by
a generic ValueError wrapper; that masking was removed and the tests passed.
This is self-review and executed evidence, not independent audit approval.

```
python ../run_checks.py -q
python benchmark_linear.py --output stage1a_results.json
```

The inherited test harness isolates the REAL scientific modules from the desktop
package __init__. It does not verify ordinary package import, PyTauri or the
known broken dispatcher. No native integration success is claimed.

## Benchmark protocol

Raw evidence: `stage1a_results.json`. Every size/mode runs in a separate process;
float64 synthetic data, seed 2026, seven warm repetitions, thread environment
fixed to one. Compare the SAME public API workload, including validation,
warnings, metrics and output lists. The private kernel is additionally timed.
Both implementations are checked against NumPy lstsq coefficients.

Cold mode explicitly compiles the kernel signature with a fresh temporary cache;
cached mode explicitly loads the same signature in another process. Dispatcher
cache counters assert a cold miss and a subsequent hit, respectively. Times
include compiler/runtime initialization or cache-load overhead; they are separate
from first numerical execution and warm execution. Imports/data generation are
outside these timings. No installed cache is deleted or modified by the harness.

Native process peak RSS is captured before independent verification. It includes
imports, compilation/cache loading and repeated public outputs, not only kernel
arrays. The script retains one output while measuring repeated calls identically
for both implementations. Peak RSS comparisons are process-level observations,
not precise incremental allocator measurements. Initial JIT overhead can make
small one-off calls slower despite faster warm execution.

Final run (2026-11-14, Windows AMD64, one configured thread):

| n | Previous full API, warm ms | New full API, warm ms | Kernel, warm ms | Full API ratio | Cold compile s | Cache load s |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.3432 | 0.02990 | 0.00430 | 11.48x | 1.861 | 0.625 |
| 10,000 | 4.9498 | 0.70230 | 0.21710 | 7.05x | 1.884 | 0.578 |
| 1,000,000 | 578.0579 | 120.88350 | 27.44590 | 4.78x | 1.934 | 0.597 |

Each cached worker recorded one cache hit; each cold worker recorded one miss.
Maximum coefficient error against NumPy for the new implementation was 7.38e-14
or less. Warm API gains include validation/duplicate-check improvements as well
as the numeric kernel; they cannot be attributed solely to JIT compilation.
Process peak RSS (old API / cached new API): 58.20/98.57 MiB for n=100,
61.46/101.26 MiB for n=10,000 and 380.16/359.55 MiB for n=1,000,000.
Thus the JIT runtime increases process memory for small samples; memory saving
is demonstrated only for the large tested workload, not universally.
Seven-repetition min/max timings and full environment are preserved in raw JSON.

## Limits and next audit

Slope has unit(y)/unit(x); elapsed time conventions, origin and physical units
remain the caller's responsibility. Autocorrelation, seasonality, heteroscedasticity,
outliers and errors in x are not corrected by acceleration. No confidence interval,
p-value, causal interpretation or independently validated forecast is introduced.
The native deployment must verify writable Numba cache behavior and package imports.
`nogil` permits worker execution but does not schedule work or provide mid-kernel
cancellation; the stage-0 executor still checks cancellation between phases only.

Independent audit should especially review scaled arithmetic, compensated sums,
extreme dynamic ranges, the n=2 likelihood convention, output compatibility,
memory measurements and cache behavior in packaged Tauri. Status: candidate,
pending that audit. Next algorithm remains a separate delivery.
