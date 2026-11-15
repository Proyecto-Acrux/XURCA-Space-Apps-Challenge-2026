# Regresión lineal — 1.1.0-candidate

Estado: candidato con pruebas ejecutadas mediante aislamiento científico;
pendiente de auditoría independiente e integración nativa.

## Contrato y alcance

`linear_regression(x: list[float], y: list[float]) -> LinearFitOutput`
conserva los argumentos y las claves existentes de `FitOutput`. La extensión
añade `warnings`, `uncertainty`, `method_version` y `n_observations`.
`metrics` admite ahora `None` (JSON `null`): R² para y constante, R² ajustado
para y constante o n=2 y AIC para error residual exactamente cero o n=2. Los consumidores
deben tratar `null` como no definido, no como cero. Es un cambio semántico
explícito respecto a los antiguos ceros/infinitos; las pruebas lo comprueban.
No se modifican las métricas ni los núcleos compartidos de otros métodos.

Entradas: vectores numéricos reales unidimensionales, finitos, igual longitud,
al menos dos pares y dos x distintos. Se rechazan texto, fechas, booleanos,
complejos, nulos, NaN e infinitos. No se imputan ni eliminan observaciones.
El orden se conserva. Réplicas e intervalos irregulares se admiten con avisos;
cada observación tiene el mismo peso. La depuración de fechas duplicadas
corresponde a la normalización previa: no se interpreta automáticamente una
réplica como dato independiente. Datos fuera del rango representable producen
`ValueError`, incluso si una solución con precisión arbitraria podría existir.

La función no conoce fuentes, NASA, UI ni PyTauri. El llamador conserva IDs,
referencias, unidades, origen temporal y marca demo; no se inventan aquí.
Para tiempo, usar tiempo transcurrido real (por ejemplo días desde una fecha
documentada), no índices de muestra si hay irregularidad. Un año requiere una
convención explícita; no convertir meses variables a días constantes.

## Matemática y estabilidad

Se minimiza SSE = sum((y_i - a - b*x_i)^2), con intercepto:

- b = sum((x_i-x̄)(y_i-ȳ)) / sum((x_i-x̄)^2).
- a = ȳ - b*x̄; ajustados evaluados en coordenadas centradas.
- Residuos = y - ajustados; RMSE = sqrt(SSE/n), MAE = sum(abs(residuos))/n.
- R² = 1 - SSE/SST; SST = sum((y_i-ȳ)^2).
- R² ajustado = 1 - (1-R²)*(n-1)/(n-2), solo con n>2 y SST>0.
- AIC = n*(log(2*pi)+1+log(SSE/n))+2*3: verosimilitud gaussiana con
  pendiente, intercepto y varianza estimados. No comparar con el antiguo AIC
  reducido de otros métodos ni con ajustes a distintas observaciones/unidades.

Se resta primero el primer dato, luego se escala y centra cada vector antes
de productos internos con sumas compensadas. RMSE usa residuos escalados y AIC usa log(RMSE),
evitando formar cuadrados dimensionales enormes o diminutos. Float64 no puede
recuperar diferencias ya perdidas en la entrada. El intercepto lejos del dominio
observado puede tener gran error absoluto; priorizar los ajustados centrados.
Kernel O(n), con dos arrays de salida y memoria auxiliar O(1). La API es O(n)
para x ordenado y O(n log n) para x desordenado por la comprobación de duplicados.
Las listas de salida existentes conservan un costo de memoria O(n).

Etapa 1A: ver `STAGE1A.md`, `benchmark_linear.py` y `stage1a_results.json`.
La referencia congelada `linear_reference.py` se utiliza solo en pruebas y
benchmarks: no está registrada ni participa de la ejecución del producto.

Pendiente: unidad(y)/unidad(x); intercepto, residuos, RMSE y MAE: unidad(y).
R² es adimensional y no mide causalidad ni utilidad física ni precisión futura.
OLS es sensible a outliers y errores de medida en x. Autocorrelación,
estacionalidad y heterocedasticidad no se corrigen ni diagnostican aquí.
El AIC supone errores gaussianos independientes y homocedásticos; se informa
ese supuesto sin afirmar que se cumple. No hay p-valores, intervalos ni
pronóstico. `uncertainty="not_estimated"` es explícito.

Referencias:
- [NIST: criterio de mínimos cuadrados](https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd431.htm).
- [R: summary.lm, R² y grados de libertad](https://www.stat.ethz.ch/R-manual/R-devel/library/stats/html/summary.lm.html).

## Ejemplo reproducible y pruebas

```python
import json
from trend_scope.models.stats.regression import linear_regression

# Datos SINTÉTICOS, días desde un origen y temperatura en °C.
result = linear_regression([0., 1., 2.], [10., 12., 14.])
assert abs(result["parameters"]["slope"] - 2.) < 1e-12  # °C/día
json.dumps(result, allow_nan=False)
```

Desde `src-tauri`, con las dependencias declaradas y Python disponible:
`python -m pytest src-python/trend_scope/models/stats/test_regression.py -q`.
La suite cubre rectas crecientes/decrecientes/constantes, ruido analítico
ortogonal a x y al intercepto, ruido con semilla contra `numpy.linalg.lstsq`,
grandes orígenes, cambios de escala, dos puntos, réplicas, desorden,
irregularidad, errores de entrada y serialización estricta.
Tolerancias 1e-12 para casos bien condicionados; intercepto alrededor de 3e12
usa 1e-3 absoluto (unos pocos ULP), sin tolerancia relativa en ese chequeo.

## Diagnóstico de integración y auditoría pendiente

La implementación original usaba sumas crudas con cancelación catastrófica,
devolvía pendiente cero para x constante, usaba n-3 en el R² ajustado y
producía AIC=-Infinity en ajustes exactos. Solo se corrige el camino lineal.
Había dos pruebas, una lineal básica y otra polinómica; no cubrían esos bordes.
Dependencias existentes: NumPy, Numba, pytest (extra dev); ninguna añadida.

Fuera del alcance: `handlers/analysis.py` define otro `run_regression_analysis`
dentro del dispatcher y nunca lo llama ni devuelve su resultado. El servicio
recibe None; la integración no puede declararse operativa. Además importar
`trend_scope` ejecuta su `__init__.py` que carga PyTauri: el núcleo no depende
de UI, pero el paquete impide una importación aislada normal sin ese entorno.
No se modificaron handlers, configuración ni frontend. `docs/fuentes-de-datos.md`
no existe en este checkout. README, SOUL y cfg_data sí fueron consultados.

La auditoría independiente debe ejecutar la suite, revisar los bordes de
float64 y la semántica nullable, verificar el AIC y confirmar conservación
de pares/unidades. Integración nativa y procedencia completa quedan pendientes
de arreglar el dispatcher con autorización y disponer del entorno PyTauri.

## Comprobaciones realizadas en esta sesión

- Rama `ema_workspace`; `git fetch origin` completado. `HEAD...origin/main`
  devuelve 0/0: sin commits pendientes de incorporar. Sin merge ni commit.
- `git diff --check`: pasó. Solo cambios dentro de `models/stats/`; los
  archivos preexistentes sin seguimiento AGENTS.md y ../CLAUDE.md se conservaron.
- `py -0p`: `No installed Pythons found!`.
- `py -m pytest test_regression.py -q -p no:cacheprovider`:
  `No installed Python found!`. No se ejecutó ningún test Python ni NumPy/Numba.
- Revisión estática preliminar realizada; no sustituye las pruebas ni una
  auditoría independiente. No se verificó IPC nativo.

Actualización de etapa 0 (2026-11-14): se preparó Python portátil 3.11.9 en un
directorio temporal. `models/run_checks.py -q` ejecutó las pruebas anteriores
junto con la infraestructura nueva: **56 passed in 1.88s**. El harness importa
el código científico real evitando el __init__ de escritorio; no es una prueba
del dispatcher ni de PyTauri. Ver `../SCIENTIFIC_CORE.md` para versiones,
benchmarks reales y límites. El bloqueo de ejecución de la sesión anterior
quedó resuelto para este entorno temporal.
