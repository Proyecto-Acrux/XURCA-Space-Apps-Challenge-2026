# Etapa 1B — regresión polinómica 1.0.0-candidate

Estado: pruebas y revisión preliminar realizadas; pendiente de auditoría
independiente. Rama ema_workspace. No se modificaron RK4/RK45, otras regresiones,
frontend, conectores, handlers, configuración ni dependencias del proyecto.

## Diagnóstico y alcance

La implementación previa construía una Vandermonde en x sin escalar y llamaba
`np.linalg.lstsq` dentro de Numba. Descartaba rango y valores singulares; aceptaba
ajustes no identificables, y las métricas compartidas tenían grados de libertad
incorrectos y podían devolver infinito. La única prueba polinómica era x².

Se conserva mínimos cuadrados y la función pública:
`polynomial_regression(x: list[float], y: list[float], degree: int = 2)`.
Ahora delega en `polynomial.fit_polynomial`, con álgebra lineal nativa NumPy.
Las claves existentes `algorithm`, `x`, `y_pred`, `residuals`, `parameters` y
`metrics` se conservan. `parameters` sigue conteniendo c_d…c_0 en coordenadas
originales. PolynomialFitOutput extiende FitOutput con advertencias, versión,
grado, rango, valores singulares, condición, rcond, grados de libertad y
`stable_basis`. Métricas matemáticamente indefinidas son None/JSON null.

Los kernels privados antiguos permanecen disponibles como referencia del
benchmark; no se llaman desde la nueva función pública polinómica. Los helpers
compartidos de otras regresiones mantienen su comportamiento previo.

## Matemática y decisiones numéricas

Se minimiza sum((y_i - sum(c_k*x_i**k))**2), con pesos iguales.
Se transforma x a z=(x-x_offset)/x_scale, con centro del rango y escala máxima
absoluta, de modo que z queda aproximadamente en [-1,1]. También se desplaza
y escala y. La Vandermonde usa columnas 1,z,…,z**degree. `np.linalg.lstsq`
resuelve el problema y entrega los valores singulares para verificar el rango.

Se exige rango completo p=degree+1 con corte `rcond=max(n,p)*eps(float64)`.
No se baja el grado silenciosamente. `condition_number` es la razón entre los
valores singulares extremos de la matriz ESCALADA, no de la matriz original.
El rango completo no implica que los coeficientes sean físicamente importantes
ni que el ajuste tenga utilidad predictiva. La condición se reporta sin inventar
un umbral universal de validez científica.

La evaluación de los ajustados usa la base escalada. La conversión de los pocos
coeficientes a coordenadas originales se realiza por composición de Horner con
Decimal a 80 dígitos, de la biblioteca estándar, y verificación final de float64.
Esta conversión O(p²) evita que coeficientes no representables se transformen
silenciosamente en cero o infinito. No convierte el ajuste en alta precisión:
los coeficientes originales de entrada al conversor fueron estimados en float64.
La acumulación alrededor de un origen lejano puede seguir siendo muy sensible.
Se debe evaluar usando stable_basis, no reconstruir automáticamente los ajustados
con los c_k originales. Si estos c_k no pueden representarse, se rechaza el
resultado con instrucciones para reescalar: no se altera el contrato devolviendo
coeficientes corruptos ni se eliminan términos pequeños arbitrariamente.

Representación estable (coeficientes en orden ascendente):

```
z = (x - basis['x_offset']) / basis['x_scale']
y_fit = basis['y_offset'] + basis['y_scale'] * polyval(z, basis['coefficients'])
```

Residuos=y-y_fit; RMSE=sqrt(SSE/n); MAE=sum(abs(residuos))/n.
R²=1-SSE/SST; R² ajustado=1-(1-R²)*(n-1)/(n-p), cuando n>p y SST>0.
AIC=n*(log(2*pi)+1+log(SSE/n))+2*(p+1), contando coeficientes y varianza.
R² es null para y constante; R² ajustado es null si y es constante o n=p.
AIC es null si SSE=0 o n=p. El ajuste saturado es interpolación, sin grados de
libertad residuales; el redondeo no se interpreta como varianza residual válida.
No se calculan intervalos de confianza ni significancia.

Unidades: c_k tiene unidad(y)/unidad(x)^k; residuos/RMSE/MAE tienen unidad(y).
Un polinomio de grado mayor a uno no tiene una pendiente constante.
La pendiente local requeriría evaluar su derivada; esta etapa no crea ese análisis.

Referencias:
- [NumPy: escalado del dominio polinómico y conversión de coeficientes](https://numpy.org/doc/stable/reference/generated/numpy.polynomial.polynomial.Polynomial.fit.html).
- [NumPy: mínimos cuadrados, rango y corte relativo](https://numpy.org/doc/1.26/reference/generated/numpy.linalg.lstsq.html).

## Validación y recursos

Se admiten vectores 1D reales finitos, al menos p observaciones y grado entero
>=1. Se rechazan booleanos, texto, fechas sin normalizar, nulos, NaN/Infinity,
dimensiones incorrectas y enteros fuera de +/-2**53 antes de convertir a float64.
MaskedArray se rechaza explícitamente: np.asarray no debe descartar su máscara.
No se imputan, interpolan ni eliminan observaciones. La función numérica conserva
pares desordenados y réplicas si hay rango completo, emitiendo advertencias.

El adaptador `adapters/polynomial.py` acepta una variable con dimensión (time,)
y exige tiempos estrictamente crecientes sin datos marcados inválidos. Preserva
origen temporal, calendario, unidades, calidad, procedencia y transformaciones.
El registro usa ID `polynomial`, parámetro `degree` con valor predeterminado 2,
y comunica que el mínimo depende del grado. El executor verifica ese mínimo
real; el mínimo global de 2 solo corresponde al grado mínimo 1.

Complejidad aproximada: O(n*p²) del solver, O(n*p) de la matriz, O(p²) de conversión
y O(n log n) de comprobación de duplicados. Hay listas de salida O(n).
Guardas explícitas de implementación: matriz <=64 MiB y n*p²<=100 millones de
unidades de trabajo aproximadas. Son límites computacionales del MVP, no pruebas
de suficiencia estadística ni límites exactos de RSS. El solver puede reservar
copias y espacio adicional. Los cálculos siguen siendo síncronos para ejecutar
en un worker; no se añadió cancelación dentro de LAPACK ni integración nativa.

## Pruebas ejecutadas

`python ../run_checks.py -q`: **119 passed in 2.09s** en el entorno portátil
Python 3.11.9, NumPy 2.4.6, Numba 0.68.1, pytest 9.2.0, SciPy 1.17.1.
El harness prueba los módulos científicos reales, aislando el __init__ de
escritorio; no demuestra que funcione el dispatcher/PyTauri.

Incluye polinomios conocidos, respuesta constante, ruido analítico ortogonal a
1/x/x², ruido con semilla contra Polynomial.fit, x con origen 1e12, cambios de
escala y origen, grado 1 contra regresión lineal, saturación, rango insuficiente,
duplicados/desorden, entradas inválidas, recursos, máscaras, fallos de LAPACK,
readonly/float32, unidades/procedencia/registro y JSON estricto.
Tolerancias típicas 1e-12 para ejemplos analíticos bien condicionados; comparación
de señales ruidosas contra la biblioteca usa 1e-11 absoluto/relativo.

La revisión adversarial encontró que la conversión inicial mediante Polynomial
podía subdesbordar c_2 a cero sin error. Se sustituyó solamente la conversión de
salida por Decimal y comprobaciones explícitas. Los casos x~1e-200 y x~1e200
ahora fallan controladamente cuando c_2 no cabe en float64. Todos los tests
anteriores de etapas 0 y 1A siguen pasando. No es una auditoría independiente.

## Benchmark real

`python benchmark_polynomial.py --output stage1b_results.json`.
Datos sintéticos, semilla 2026, grado 2, x en [-1,1], float64, Windows AMD64,
un hilo configurado, 7 repeticiones calientes por proceso. La versión anterior
se mide con compilación y carga de caché explícitas de sus tres kernels,
verificando misses/hits. La nueva ruta no tiene compilación JIT.

| n | Anterior caliente (ms) | Nueva caliente (ms) | RSS anterior con caché (MiB) | RSS nueva (MiB) |
|---:|---:|---:|---:|---:|
| 100 | 0.0385 | 0.3416 | 100.86 | 59.02 |
| 10,000 | 1.2666 | 2.1903 | 103.61 | 62.58 |
| 1,000,000 | 164.9309 | 259.3404 | 369.42 | 387.26 |

Compilación anterior: 8.84–9.53 s; carga de caché anterior: 0.74–0.94 s.
La API nueva hace más trabajo y es más lenta en estas mediciones calientes;
no se afirma una aceleración. Evita la compilación y añade controles científicos.
La memoria tampoco mejora universalmente. RSS es el pico del proceso completo
antes de verificar contra la referencia, con importaciones y outputs repetidos.
No es una medición aislada de asignaciones del solver.

Los ajustados coinciden con Polynomial.fit dentro de 6.50e-12 absoluto en los
tamaños medidos. Las métricas antiguas no se usan como referencia matemática.
El JSON conserva dispersión temporal, compilación/caché, versiones, configuración
NumPy/BLAS, hilos, memoria y errores. No extrapolar estos tiempos a grados altos.

## Límites y siguiente paso

Polinomios altos pueden sobreajustar y extrapolar de manera extrema. No se
evalúan autocorrelación, estacionalidad, heterocedasticidad ni errores de medida
en x. Una curva histórica no constituye un pronóstico ni prueba causalidad.
No se agregaron bibliotecas ni se tocaron las reglas del frontend/IPC.

Auditoría pendiente: ecuaciones, rango numérico, conversión de bases, tolerancias,
política nullable, presupuesto y compatibilidad nativa. Luego corresponde la
etapa 1C: revisar y validar RK4 en un cambio separado.
