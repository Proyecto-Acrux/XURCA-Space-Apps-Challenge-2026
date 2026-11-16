# AGENTS.md — `trend_scope/models/` · Funciones científicas pendientes

Instrucciones para **Codex** al trabajar dentro de `models/`. Este archivo define **qué funciones faltan** y **cómo deben construirse**. El protocolo general de trabajo (implementar, auditar, corregir) está en `stats/AGENTS.md` y sigue vigente: este archivo lo complementa, no lo reemplaza.

Origen de la cola: contraste entre la investigación científica del equipo (planilla `Trend_Detective_v9…xlsx`) y el código existente. Detalle en `docs/plan-maestro/22_BARRIDO_CIENCIA_VS_CODIGO.md` (raíz del repositorio).

## 0. Regla de oro

**Una función de la cola por solicitud.** Cuando el usuario diga «Implementá W0x», hacé solo W0x, con sus pruebas y su registro. No adelantes la siguiente.

## 1. Leé esto antes de escribir código

| Archivo | Para qué |
|---|---|
| `numeric.py` | Validadores obligatorios de entradas (`temporal`, `array`, `scalar`, `integer`, `finite`) |
| `stats/trends.py` | Estilo de referencia de una función nueva (`sen_slope`, `mann_kendall`) |
| `extended_registry.py` | Cómo se registra un método de forma aditiva |
| `contracts.py`, `execution.py`, `registry.py` | Contratos y ejecución. **Solo lectura** |
| `tests/test_new_stats.py`, `tests/test_extended_registry.py` | Estilo de pruebas |
| `ENGINE_STATUS.md` | Estado declarado del motor |
| `PRESERVATION.json` | Archivos que no se pueden modificar |

## 2. Qué no se toca

1. **Ningún archivo listado en `PRESERVATION.json`** (`contracts.py`, `execution.py`, `registry.py`, `serialization.py`, `validation.py`, `adapters/`, `stats/linear_kernel.py`, `stats/polynomial.py`, `stats/schemas.py`, `dynamical/rk4*.py`, benchmarks, y las funciones `linear_regression` y `polynomial_regression`).
2. **Ninguna función existente con tests**, aunque su archivo no esté en esa lista: `sen_slope`, `mann_kendall`, `multivariable_ols`, `cusum`, `forecast`, `stl`, `pelt`, etc. Si una tarea parece requerir cambiar una, **detenete y pedí decisión**; la solución por defecto es una función nueva que la envuelva.
3. **Nada fuera de `models/`**: ni conectores (`services/`), ni `desktop.py`, ni frontend.
4. **No ejecutar ni reescribir benchmarks de rendimiento.**
5. **No hacer `git commit`, `git push` ni cambios de dependencias** sin pedido expreso.
6. **No agregar dependencias.** Todo lo de la cola se resuelve con NumPy y SciPy (ya instalados). Las bibliotecas opcionales (`statsmodels`, etc.) solo pueden usarse como **oráculo en pruebas**, con `pytest.importorskip`.

## 3. Convenciones de una función nueva

Seguí el patrón de `stats/trends.py`:

```python
def nombre(times, values, *, parametro, otro=valor) -> dict:
    """Qué calcula, en una línea.

    Supuestos, unidades de la salida, referencia bibliográfica y para qué NO sirve.
    """
    t, y = temporal(times, values, regular=..., minimum=...)   # numeric.py
    ...
    return {"clave": ..., "warnings": [...]}
```

- **Entradas:** arreglos reales finitos. Los tiempos son numéricos (el llamador ya los convirtió), estrictamente crecientes. **Sin NaN, sin máscaras, sin interpolar, sin ordenar**: lo impone `numeric.temporal`.
- **Sin calendario:** las funciones no reciben fechas. Cuando hace falta agrupar por mes, día del año o estación, la función recibe un arreglo `groups` de etiquetas enteras, del mismo largo que `values` (igual que `mann_kendall` recibe `seasons`). Cuando hace falta distinguir un período de referencia, recibe una máscara booleana (`baseline`, `calibration`).
- **Parámetros:** solo por nombre después de `*`. Validalos con `numeric.integer` y `numeric.scalar`.
- **Salida:** `dict` de escalares y arreglos NumPy, siempre con la clave `"warnings"` (lista de cadenas). Sin objetos propios, sin pandas.
- **Errores:** `ValueError` con mensaje accionable para entradas inválidas o datos insuficientes. Nunca devolver un número cuando el cálculo no es válido.
- **Incertidumbre:** si no se estima, decirlo explícitamente (`"uncertainty": "not_estimated"`). Nunca inventar un intervalo.
- **Aleatoriedad:** parámetro `seed` obligatorio y `numpy.random.default_rng(seed)`.
- **Límites de recursos:** parámetro `max_…` con valor por defecto cuando el costo crece más que linealmente (como `max_pairs` en `sen_slope`).
- **Idioma:** mensajes de error en inglés, como el resto de los métodos nuevos del motor.

### Valores científicos: no inventar

La investigación **no fija** estos números (falta el anexo matemático). Deben ser **parámetros obligatorios sin valor por defecto**:

- años mínimos de la base climatológica o de calibración (`min_count`),
- desfases a evaluar (`lags`),
- duración mínima de un evento (`min_duration`),
- tamaño de entrenamiento inicial y paso del backtest.

Sí están documentados y pueden ser valores por defecto: nivel de confianza `0.95` para tendencias, nivel de intervalo predictivo `0.90`, umbrales de SPI `−1` y `+1`, escalas de SPI `1, 3, 6, 12`. El aviso de «menos de 20 años de calibración» para SPI se emite como *warning*, no como error.

## 4. Dónde va cada cosa

```text
models/
├─ climate/        climatology.py · spi.py · events.py · etccdi.py     (carpeta nueva)
├─ stats/          sen_interval.py · lagged.py · multiple_testing.py · bootstrap.py · diagnostics.py · descriptive.py
├─ signal/         convolution2d.py
├─ forecasting/    baselines.py · backtest.py · intervals.py · prob_metrics.py · forecasters.py   (carpeta nueva)
├─ fire/           fwi.py                                              (carpeta nueva)
├─ vegetation/     burn_indices.py                                     (carpeta nueva)
├─ landcover/      transitions.py                                      (carpeta nueva)
├─ atmosphere/     hypsometric.py                                      (carpeta nueva)
├─ catalog_registry.py     registro aditivo de todo lo anterior (archivo nuevo)
└─ tests/          test_<modulo>.py por cada archivo nuevo
```

`models/` no tiene `__init__.py` (solo `adapters/` lo tiene): **no agregues `__init__.py`** en las carpetas nuevas; seguí la forma de importar de las carpetas existentes (`change_detection/`, `signal/`, `similarity/`).

### Registro

No edites `extended_registry.py`. Creá (en la primera tarea) `catalog_registry.py`, que **envuelve** a `scientific_registry()` igual que este envuelve a `default_registry()`:

```python
def catalog_registry(*, include_optional: bool = True):
    registry = scientific_registry(include_optional=include_optional)
    # registry.register(MethodSpec(...), runner) por cada método nuevo
    return registry
```

Cada tarea agrega su método ahí, con un `MethodSpec` que declare **el mínimo real de observaciones**, la regularidad exigida, los parámetros y la complejidad, y un *runner* que arme el `AnalysisResult` con las `metric_units` correctas (derivadas de `variable.unit` y `data.time.unit`). Los métodos que necesitan una segunda serie o etiquetas (`groups`, `baseline`) las reciben como identificadores de otras variables del `ScientificDataset`, como hace `multivariable` con `features`.

## 5. Pruebas obligatorias por función

En `tests/test_<modulo>.py`, con pytest:

1. **Respuesta conocida:** datos sintéticos donde el resultado se sabe de antemano.
2. **Referencia independiente** cuando exista (columna «Oráculo» de la cola). Nunca comparar contra otra función escrita en el mismo cambio.
3. **Propiedades:** las que apliquen (invariancia ante traslación o cambio de escala, simetría, cobertura en simulación con semilla fija).
4. **Bordes:** serie constante, tamaño mínimo, un grupo sin datos, empates.
5. **Fallo controlado:** entradas inválidas producen `ValueError`.
6. **Ruta por registro:** una prueba que ejecute el método vía `analyze()` con `catalog_registry()` y verifique `metric_units`.
7. **Serialización:** el resultado pasa por `serialization.dumps` sin `NaN` ni `Infinity`.

Para todo lo predictivo, además: **prueba de no fuga** (modificar datos posteriores al origen no cambia nada calculado con datos anteriores).

Ejecución, desde `aplicacion/trend-scope/src-tauri/`:

```powershell
python -m pytest src-python/trend_scope/models/tests/test_<modulo>.py -q
python -m pytest -q                      # suite completa antes de entregar
```

**No declarar que las pruebas pasaron sin haberlas ejecutado.** Si el entorno no lo permite, decirlo.

---

## 6. Cola de trabajo

Orden recomendado: el de la numeración. «Destraba» indica fenómenos del catálogo y controles de calidad de la planilla.

**Estado de la cola** (única línea que se edita al entregar una tarea):

- Pendientes: W05, W04
- Candidate: W01 (`robust_z` corregido el 2026-11-15; pendiente de auditoría), W02, W03, W06, W07, W08, W09, W10, W11, W12, W13, W14, W15, W16, W17, W18, W19, W20 (todas implementadas sin ejecutar ni probar; W06-W09, W17, W18 y W20 se usan desde los handlers, el resto son API de Python sin registrar)
- Aprobadas tras auditoría: —

| ID | Función | Depende de | Destraba |
|---|---|---|---|
| W01 | Climatología y anomalías | — | 14 fenómenos; Q02 |
| W02 | Intervalo de confianza de Theil-Sen | — | N1.1.0, N1.1A, N1.2A; Q03 |
| W03 | SPI | W01 | N1.2.0, N1.2A, N1.2C, B3.5; Q05 |
| W04 | Percentiles, eventos y composites | W01 | 9 fenómenos |
| W05 | Correlación con desfases y parcial | — | B2.2, B5.4, B6.1, B6.2, B9.1, B1.4 |
| W06 | FDR de Benjamini-Hochberg | — | Q04 |
| W07 | Baselines de pronóstico | — | Las 8 líneas PRED |
| W08 | Backtesting con origen móvil | W07 | Q15 |
| W09 | Intervalos predictivos | W08 | Q16 |
| W10 | Índices ETCCDI | — | N1.1B, N1.2B |
| W11 | Bootstrap por bloques y diferencia pareada | — | N1.1C, B1.2, B2.6, B3.4, B8.1 |
| W12 | Fire Weather Index | — | B9.2; PRED-05 |
| W13 | Métricas probabilísticas | — | PRED-01, PRED-05 |
| W14 | Índices de quema y recuperación | W11 | N1.4D, B9.3, B2.6 |
| W15 | Matriz de transición de cobertura | — | B1.1, B2.1, N1.3A, B8.3 |
| W16 | Ecuación hipsométrica | — | N1.8.1 |
| W17 | Diagnósticos de serie (autocorrelación lag-1, fuerza estacional) | — | Reglas de selección del Algorithm Handler |
| W18 | Estadística descriptiva | — | Struct `describe` |
| W19 | Convolución 2D / FIR 2D | — | Suavizado espacial (nota del mapa de arquitectura) |
| W20 | Pronosticadores para backtesting | W08 | Struct `forecast` |

W17–W20 se agregaron el 2026-11-15 con el plan `docs/plan-maestro/23_ARQUITECTURA_HANDLERS.md`: son las funciones que los handlers (`trend_scope/handlers/`) necesitan y que no estaban en la cola. El orden de la línea «Pendientes» es el que pide ese plan (primero lo que usa la fase 1 de los handlers).

### W01 — Climatología y anomalías
- **Archivo:** `climate/climatology.py`.
- **Funciones:**
  - `climatology(values, groups, baseline, *, min_count) -> dict` con `group_ids`, `mean`, `std`, `median`, `mad`, `count` (uno por grupo), calculados **solo** con las observaciones donde `baseline` es verdadero.
  - `anomalies(values, groups, reference, *, kind) -> dict`, con `kind ∈ {"absolute", "percent", "standardized", "robust_z"}` y `reference` = salida de `climatology`.
- **Reglas:** un grupo con menos de `min_count` observaciones de base → `ValueError` que lo nombra. `percent` exige media de base distinta de cero; `standardized`, desvío distinto de cero; `robust_z`, MAD distinta de cero.
- **Unidades:** `absolute` en la unidad de la variable; `percent` en `%`; las otras dos adimensionales.
- **Oráculo:** serie = ciclo estacional conocido + tendencia lineal → la anomalía absoluta recupera la tendencia más la constante esperada.
- **Límite a documentar:** no decide qué período de base es válido; lo recibe.
- **Decisión sobre la MAD (plan 23, aprobado el 2026-11-15):** `climatology()['mad']` se devuelve **sin escalar**, en la unidad de la variable (es un estadístico descriptivo). El factor de consistencia con la normal se aplica **dentro de `robust_z`**: `robust_z = (x − mediana) / (1.4826 · MAD)`. Así el resultado es comparable con un z estándar y con los umbrales habituales. La implementación candidate divide por la MAD cruda: corregirla, actualizar el docstring y las pruebas de `tests/test_climatology.py`, y agregar una prueba con datos normales sintéticos (semilla fija) donde `robust_z` y `standardized` tengan dispersión similar. Esta corrección es parte de la auditoría de W01, no una tarea nueva.

### W02 — Intervalo de confianza de Theil-Sen
- **Archivo:** `stats/sen_interval.py`. **No modificar `sen_slope`.**
- **Función:** `sen_interval(times, values, *, confidence=0.95, max_pairs=2_000_000) -> dict` con `slope`, `lower`, `upper`, `confidence`, `n_pairs`, `method`.
- **Método:** intervalo por rangos de las pendientes de pares, basado en la varianza de Kendall con corrección por empates.
- **Oráculo:** `scipy.stats.theilslopes(y, t, alpha=confidence)`.
- **Advertencia obligatoria en `warnings`:** el intervalo asume independencia serial; con autocorrelación es demasiado angosto.

### W03 — SPI
- **Archivo:** `climate/spi.py`.
- **Función:** `spi(totals, groups, calibration, *, scale, min_count, epsilon=1e-6) -> dict` con `spi` (los primeros `scale − 1` valores no existen: devolver `valid` booleano en lugar de NaN), `scale`, `parameters` (por grupo: forma, escala, probabilidad de cero, n).
- **Entrada:** totales **mensuales acumulados**, serie regular. `groups` = mes calendario del final de cada ventana.
- **Método:** suma móvil de `scale` meses; por grupo, distribución gamma con masa en cero ajustada **solo** con los valores donde `calibration` es verdadero; transformación a normal estándar con la probabilidad acotada a `(epsilon, 1 − epsilon)`.
- **Reglas:** calibración con menos de 20 años → *warning* de baja robustez (regla Q05 de la planilla), no error. Menos de `min_count` → `ValueError`.
- **Pruebas:** datos generados con gamma de parámetros conocidos → SPI aproximadamente normal estándar en calibración; **no fuga**: cambiar valores fuera de `calibration` no altera `parameters`.
- **Límites a documentar:** no se suman SPI de distintas escalas; SPI no es humedad de suelo.

### W04 — Percentiles, eventos y composites
- **Archivo:** `climate/events.py`.
- **Funciones:**
  - `percentile_thresholds(values, groups, baseline, *, q, min_count) -> dict` (umbral por grupo, solo con la base).
  - `detect_events(times, values, thresholds, *, direction, min_duration) -> dict` con `start_indices`, `end_indices`, `durations` (en pasos), `peak_values`, `mean_exceedance`. `thresholds` es un arreglo del largo de la serie.
  - `event_composite(times, response, event_indices, *, before, after) -> dict` (media y n de la respuesta en cada desplazamiento relativo al evento).
- **Oráculo:** eventos insertados a mano en una serie sintética se recuperan con sus índices exactos.
- **Límite:** un evento no es una tendencia; son salidas distintas (regla Q12).

### W05 — Correlación con desfases y parcial
- **Archivo:** `stats/lagged.py`.
- **Funciones:**
  - `lagged_correlation(times, first, second, *, lags) -> dict` con, por cada desfase de la lista dada: `r`, `n`, `n_effective`, `p_value`. Serie regular. Desfase positivo = `first` antecede a `second`.
  - `partial_correlation(first, second, controls) -> dict`.
- **Reglas:** `lags` es **obligatorio y explícito**. La función **no** devuelve «el mejor desfase» ni ordena por correlación. `n_effective` corrige por autocorrelación de orden 1 de ambas series; el p-valor usa `n_effective`.
- **Oráculos:** `numpy.corrcoef` en desfase 0; desfase insertado se recupera; simulación con semilla fija: dos series AR(1) independientes no superan la tasa nominal de falsos positivos.
- **Advertencia obligatoria:** correlación no implica causalidad; con varios desfases hace falta control de pruebas múltiples (W06).

### W06 — FDR de Benjamini-Hochberg
- **Archivo:** `stats/multiple_testing.py`.
- **Función:** `fdr_bh(p_values, *, alpha=0.05) -> dict` con `q_values`, `rejected`, `n_tests`.
- **Oráculo:** `scipy.stats.false_discovery_control(p, method="bh")`.

### W07 — Baselines de pronóstico
- **Archivo:** `forecasting/baselines.py`.
- **Funciones:** `climatology_forecast(values, groups, future_groups, *, min_count)` y `persistence_forecast(values, *, horizon)`; ambas devuelven `values` del horizonte.
- **Regla:** usan solo los datos recibidos (el pasado). Son la referencia contra la que se mide todo modelo.

### W08 — Backtesting con origen móvil
- **Archivo:** `forecasting/backtest.py`.
- **Función:** `rolling_origin(times, values, *, forecaster, horizon, initial_train, step, baselines) -> dict` con, por horizonte: `mae`, `rmse`, `bias` del modelo y de cada baseline, `skill` (= 1 − error del modelo / error del baseline), `n_origins`, y `residuals` fuera de muestra.
- **`forecaster`:** un *callable* `(train_times, train_values, horizon) -> predicciones`. **Envuelve** a `optional_methods.forecast` sin modificarlo; no se aceptan nombres de función como texto.
- **Reglas:** ventana expansiva; sin barajar; cualquier transformación que el pronosticador necesite se ajusta dentro de cada pliegue. `skill` no se calcula si el error del baseline es cero.
- **Pruebas:** proceso predecible → habilidad positiva; ruido blanco → habilidad ≈ 0 frente a la climatología; **no fuga**: alterar valores posteriores a un origen no cambia las predicciones de ese origen.

### W09 — Intervalos predictivos
- **Archivo:** `forecasting/intervals.py`.
- **Función:** `residual_intervals(point_forecast, residuals_by_horizon, *, level=0.90, min_residuals) -> dict` con `lower`, `upper`, `level`, y `empirical_coverage(observed, lower, upper)`.
- **Regla:** con menos de `min_residuals` por horizonte, no devolver intervalo: `"uncertainty": "not_calibrated"`.
- **Prueba:** cobertura empírica cercana a la nominal en simulación con semilla fija.
- **Límite:** es un intervalo **predictivo**, no un intervalo de confianza; no mezclar los términos.

### W10 — Índices ETCCDI
- **Archivo:** `climate/etccdi.py`.
- **Funciones** (entrada: serie diaria regular + `groups` = año): `rx1day`, `rx5day`, `sdii`, `cdd`, `r95ptot` (con umbral calculado sobre la máscara `baseline` y día húmedo ≥ 1 mm), y `warm_spell_days(values, thresholds, *, min_duration)`.
- **Oráculo:** definiciones publicadas por ETCCDI; casos pequeños calculados a mano.
- **Límite:** cada índice se informa por separado.

### W11 — Bootstrap por bloques y diferencia pareada
- **Archivo:** `stats/bootstrap.py`.
- **Funciones:** `block_bootstrap_ci(values, statistic, *, block_length, n_resamples, confidence=0.95, seed)` y `paired_difference(first, second, *, block_length, n_resamples, confidence=0.95, seed)`.
- **Reglas:** `block_length` obligatorio; `statistic` es un *callable*, no texto.
- **Prueba:** cobertura en simulación; reproducibilidad con la misma semilla.

### W12 — Fire Weather Index
- **Archivo:** `fire/fwi.py`.
- **Función:** `fire_weather_index(temperature, relative_humidity, wind_speed, precipitation, months, *, latitude, initial_state) -> dict` con `ffmc`, `dmc`, `dc`, `isi`, `bui`, `fwi` diarios y `final_state`.
- **Reglas:** formulación oficial del sistema canadiense (Van Wagner), con los factores de duración del día según la latitud (hemisferio sur incluido). Paso **diario**; rechazar entradas mensuales. `initial_state` obligatorio (sin valores de arranque inventados) y devolver el estado final para encadenar.
- **Unidades de entrada:** °C, %, km/h, mm en 24 h. Validar rangos.
- **Oráculo:** tablas de valores de referencia publicadas con la formulación. Si no podés acceder a ellas, **no las inventes**: dejá la prueba marcada como pendiente y decilo.
- **Límite obligatorio en el docstring:** indica peligro meteorológico relativo; no predice ignición ni su ubicación.

### W13 — Métricas probabilísticas
- **Archivo:** `forecasting/prob_metrics.py`.
- **Funciones:** `brier_score`, `brier_skill_score` (no se calcula si el Brier de referencia es cero), `reliability_table(probabilities, outcomes, *, bins)`, `crps_ensemble`.
- **Oráculo:** casos analíticos (pronóstico perfecto, pronóstico constante).

### W14 — Índices de quema y recuperación
- **Archivo:** `vegetation/burn_indices.py`.
- **Funciones:** `nbr(nir, swir)`, `dnbr(pre, post)`, `rdnbr(pre, post)`, `recovery_time(times, values, event_index, reference_low, reference_high) -> dict`.
- **Límite:** dNBR es un indicador espectral de cambio; no es severidad ecológica validada.

### W15 — Matriz de transición de cobertura
- **Archivo:** `landcover/transitions.py`.
- **Función:** `transition_matrix(before, after, *, classes, cell_area=None) -> dict` con conteos y, si se da `cell_area` (arreglo del mismo tamaño), áreas por transición.
- **Regla:** la suma de áreas se conserva.

### W16 — Ecuación hipsométrica
- **Archivo:** `atmosphere/hypsometric.py`.
- **Función:** `pressure_at_height(reference_pressure, reference_height, height, mean_temperature) -> dict`.
- **Regla:** supuestos explícitos (temperatura media de la capa, aire seco); uso educativo, no una tendencia.

### W17 — Diagnósticos de serie
- **Archivo:** `stats/diagnostics.py`.
- **Funciones:**
  - `lag1_autocorrelation(times, values) -> dict` con `r1`, `n`, `threshold` (= 1.96/√n) y `exceeds_threshold`. Serie regular.
  - `seasonal_strength(times, values, groups) -> dict` con la fracción de varianza explicada por las medias de grupo (`groups` = etiquetas enteras, como en W01) y `n_groups`.
- **Uso:** el Algorithm Handler las consulta para elegir entre Mann-Kendall, su variante estacional y la modificada. Son **diagnósticos descriptivos**, no pruebas de hipótesis: decirlo en el docstring y en `warnings`.

### W18 — Estadística descriptiva
- **Archivo:** `stats/descriptive.py`.
- **Función:** `describe(times, values, *, quantiles=(0.05, 0.25, 0.5, 0.75, 0.95)) -> dict` con `n`, `mean`, `std` (ddof=1; no se calcula con n = 1), `minimum`, `maximum`, `quantiles`, `time_start`, `time_end`.
- **Unidades:** todas en la unidad de la variable, salvo `n`.
- **Límite a documentar:** describe las observaciones recibidas; no es un promedio de área ni un total anual.

### W19 — Convolución 2D / FIR 2D
- **Archivo:** `signal/convolution2d.py`.
- **Función:** `convolve2d(grid, kernel, *, boundary) -> dict` con `values` (misma forma que `grid`) y `valid` (máscara de las celdas no afectadas por el borde). `boundary ∈ {"reflect", "constant_zero", "valid_only"}`, **obligatorio**.
- **Reglas:** `grid` y `kernel` reales y finitos, 2D (`numeric.array(..., ndim=2)`); `kernel` de lados impares; límite `max_cells` sobre `grid.size * kernel.size`. No normaliza el núcleo por su cuenta: si no suma 1, lo advierte.
- **Implementación:** `scipy.signal`/`scipy.ndimage`; no reescribir la convolución.
- **Registro:** dimensión `("y", "x")`.
- **Límite a documentar:** suaviza valores de celdas; no pondera por área ni corrige la proyección.

### W20 — Pronosticadores para backtesting
- **Archivo:** `forecasting/forecasters.py`.
- **Funciones:** fábricas que devuelven un *callable* `(train_times, train_values, horizon) -> predicciones`, como exige W08: `seasonal_naive_forecaster(period)`, `holt_winters_forecaster(period)`, `sarima_forecaster(order, seasonal_order)`.
- **Reglas:** **envuelven** a `optional_methods.forecast` sin modificarlo. Órdenes y períodos son argumentos explícitos: no hay búsqueda automática de órdenes. Si falta `statsmodels`, la fábrica lanza `ImportError` con el mensaje de `optional_methods.dependency`.

---

## 7. Fuera de la cola

No implementar aunque aparezcan en la planilla: BFAST completo, detección de cambios SAR, interferometría, índices de bloqueo atmosférico, seguimiento de ciclones, balance hídrico con parámetros de suelo, modelos de susceptibilidad a deslizamientos, modelos de conteo inflados en cero, redes neuronales y modelos fundacionales. Tampoco: conversión de unidades, agregación temporal, estadística zonal ni lectura de archivos satelitales (son preparación de datos, fuera de `models/`).

Si una tarea de la cola parece necesitar algo de esta lista, detenete y pedí decisión.

## 8. Entrega de cada tarea

```text
TAREA: W0x — <nombre>
ARCHIVOS CREADOS:
FIRMAS:
REGISTRO (method_id, mínimo de observaciones, unidades de salida):
ORÁCULO USADO Y RESULTADO:
PRUEBAS EJECUTADAS (comando y resultado real):
ARCHIVOS PROTEGIDOS TOCADOS: ninguno
SUPUESTOS Y LÍMITES CIENTÍFICOS:
VALORES QUE QUEDARON COMO PARÁMETRO OBLIGATORIO:
ESTADO: candidate
```

El estado al entregar es siempre **`candidate`**. Solo pasa a aprobado tras la auditoría independiente descrita en `stats/AGENTS.md` §15. Al terminar, mové el identificador de «Pendientes» a «Candidate» en el bloque «Estado de la cola» de §6, y no cambies nada más de este archivo.
