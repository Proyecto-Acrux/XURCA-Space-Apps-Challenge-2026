# Etapa 1C: Runge–Kutta clásico de orden 4

Estado: **candidate**, pendiente de auditoría independiente. Versión del método:
`1.0.0-candidate`. Se conserva el integrador existente y se refuerzan sus
validaciones y aritmética; RK45 no forma parte de esta entrega.

## Método y límites científicos

Para `y'=f(t,y,p)` y cada intervalo explícito `h=t[i+1]-t[i]`:

```
k1 = f(t,       y,          p)
k2 = f(t+h/2,   y+h*k1/2,   p)
k3 = f(t+h/2,   y+h*k2/2,   p)
k4 = f(t+h,     y+h*k3,     p)
y_next = y + h*(k1+2*k2+2*k3+k4)/6
```

Con suficiente suavidad y estabilidad, el error local es O(h^5) y el global
O(h^4). No se estima ese error durante la integración. La grilla puede ser
irregular: **cada intervalo es un paso**, sin interpolación ni pasos internos
adaptativos. El usuario debe comprobar convergencia al refinarla. Para
`y'=lambda*y`, la estabilidad depende de
`|1+z+z^2/2+z^3/6+z^4/24| <= 1`, con `z=h*lambda`; valores finitos no certifican
estabilidad ni exactitud. Sistemas rígidos pueden requerir otro integrador.

Referencias: [NIST DLMF §3.7](https://dlmf.nist.gov/3.7),
[SciPy solve_ivp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).
RK4 es una simulación condicionada por ecuaciones, parámetros y condiciones
iniciales. No detecta tendencias ni produce por sí solo pronósticos validados,
intervalos de confianza o estimaciones de incertidumbre física.

## Contratos y compatibilidad

`rk4(rhs, y0, t, args=(), max_output_bytes=268435456, max_steps=1000000)`
conserva las llamadas existentes de tres argumentos y desde funciones Numba.
Acepta estados vectoriales o matriciales numéricos y devuelve `float64` con
forma `(len(t), *y0.shape)`. El callback compilable recibe
`rhs(t, state, *args)` y debe devolver un array de igual forma, finito y real.
Debe ser determinista, sin efectos externos. Los errores de tipado de un
callback incompatible se propagan; no se ocultan con excepciones genéricas.
`rk4_multi` delega en este mismo núcleo para no duplicar las ecuaciones.
`rk4_multi_independent` permanece sin cambios y no queda auditado aquí.

La API de aplicación es:

```python
simulate_rk4(problem: ODEProblem, models: ODEModelRegistry,
             analysis_id: str, provenance: Provenance,
             context: ExecutionContext = ExecutionContext(), *,
             block_steps: int = 1024,
             max_output_bytes: int = 268435456) -> AnalysisResult
```

Esta API admite un vector de estado, parámetros físicos escalares y una grilla
explícita que incluye ambos extremos de `time_span`. `ODEModel` registra ID,
versión, callback `@njit`, nombres y unidades de parámetros, unidades de estado
y unidad de tiempo. No hay modelos físicos predeterminados, evaluación de
texto, importaciones desde configuración ni acoplamiento NASA/UI.

Los nombres de parámetros deben coincidir exactamente con el registro y sus
valores se pasan como un array de solo lectura en cada ejecución. Las unidades
de estado y tiempo deben coincidir exactamente; convertirlas es una operación
previa explícita. Las unidades son etiquetas declaradas: no se deduce ni
verifica dimensionalmente el código del modelo. Las coordenadas temporales son
números relativos en la unidad declarada, no timestamps convertidos en silencio.

`RK4_SPEC` usa los metadatos comunes `MethodSpec`, pero el registro de modelos
EDO es separado. El ejecutor de series observadas `analyze` no acepta un
`ODEProblem` y no se modifica para simular observaciones ficticias.
El resultado usa `AnalysisResult`, `output_kind='simulation'`, procedencia
explícita `kind='simulation'`, marca `demo`, versión, parámetros, unidades,
trayectoria, número de pasos y cuatro evaluaciones RHS por paso. La incertidumbre
es `not_estimated`. El serializador existente permite JSON estricto para
resultados de tamaño admitido; no se envían trayectorias ilimitadas por IPC.

## Ejemplo reproducible

Ejecutar en el entorno Python científico de XURCA (no requiere una fuente NASA):

```python
import numpy as np
from numba import njit
from trend_scope.models.contracts import ODEProblem, Provenance
from trend_scope.models.dynamical.rk4_service import (
    ODEModel, ODEModelRegistry, simulate_rk4,
)
from trend_scope.models.serialization import dumps

@njit  # En un módulo .py puede usarse cache=True.
def decay(t, state, parameters):
    return -parameters[0] * state

models = ODEModelRegistry()
models.register(ODEModel('decay', '1', decay, ('rate',), ('K',), 's', ('1/s',)))
problem = ODEProblem('decay', np.array([2.]), ('K',), {'rate': 0.5},
                     (0., 2.), 's', np.linspace(0., 2., 201))
result = simulate_rk4(problem, models, 'demo-decay',
                     Provenance('synthetic-decay', 'simulation', True))
np.testing.assert_allclose(result.payload['states'][:, 0],
                           2*np.exp(-0.5*problem.output_times), rtol=1e-11)
serialized = dumps(result)
```

## Decisiones numéricas y recursos

- Cálculo en float64, `@njit(cache=True, nogil=True)`, sin fastmath ni
  paralelización artificial de pasos dependientes.
- Se rechazan nulos, infinitos, booleanos, grillas duplicadas/desordenadas,
  estados vacíos, derivadas de forma incorrecta y enteros fuera de ±2^53.
  La API de servicio rechaza máscaras, objetos y números complejos.
- Los puntos medios deben ser estrictamente interiores y representables;
  en caso contrario se requiere cambiar el origen o escala temporal.
- Las etapas trabajan sobre copias para proteger estados guardados frente a
  callbacks que muten su entrada o reutilicen buffers.
- La combinación de derivadas se escala por su magnitud máxima y los productos
  usan mantisa/exponente para evitar overflow intermedio evitable. Incrementos
  no nulos que no puedan representarse se rechazan, en vez de silenciarlos.
  Esto no elimina el redondeo ni la cancelación propios de float64.
- Costo O(pasos*(dimensión+ costo RHS)); salida O(tiempos*dimensión), trabajo
  adicional O(dimensión) en el núcleo y O(bloque*dimensión) en el servicio.
- El servicio verifica presupuesto de entradas, cantidad de tiempos y una
  estimación conservadora de buffers de salida/trabajo antes de asignarlos.
  No es un límite duro de RSS: excluye JIT, allocator y memoria interna del RHS.
- Cancelación y progreso entre bloques; un callback prolongado no se interrumpe.
  La API es síncrona y debe ejecutarse fuera del hilo de UI. No agrega un scheduler
  ni modifica IPC. La integración nativa Tauri no se probó en esta entrega.

## Pruebas y auditoría

Comando desde `models/stats`: `python -B ../run_checks.py -q`.
El harness existente aísla el paquete científico del arranque PyTauri y ejecuta
los módulos reales. Última ejecución: **152 passed**, 58.36 s, Python 3.11.9,
NumPy 2.4.6, Numba 0.68.1, SciPy 1.17.1, pytest 9.2.0.

Casos RK4: crecimiento/decaimiento exponencial, constante, forzamiento cúbico
en tiempos irregulares, sistema acoplado, oscilador y energía, convergencia de
cuarto orden, referencia independiente SciPy DOP853, matrices float32 y arrays
no contiguos, equivalencia exacta entre bloques, llamadas desde Numba,
parámetros variables, aislamiento de entradas, unidades, JSON estricto,
cancelación, presupuestos, derivadas inválidas, overflow, subnormales,
enteros inexactos y puntos medios irrepresentables. Las tolerancias analíticas
corresponden al tamaño del paso de cada caso; no prometen precisión universal.

La segunda pasada del implementador agregó casos adversariales de parámetros
enteros, límites temporales y aliasing. No sustituye una auditoría independiente.
El auditor debe revisar especialmente productos escalados y subnormales,
cancelación numérica, presupuesto real de buffers, validación de callbacks,
compatibilidad de caché/empaquetado Numba y comportamiento con modelos físicos
reales. Rigidez, precisión de un modelo particular y estabilidad de cualquier
grilla siguen siendo responsabilidad de validación específica.

## Benchmark

`python -B ../benchmarks/rk4_benchmark.py --output rk4_results.json` mide el
núcleo con ocho estados y `y'=-y`, 101/10001/100001 tiempos, siete repeticiones
en caliente, procesos separados y un hilo configurado. Conserva como referencia
el núcleo previo sin cambios (`rk4_reference.py`) y lo ejecuta también en Python
para los dos tamaños menores. Cada salida se contrasta con la solución analítica.

Se mide explícitamente compilación inicial, intento de recarga de caché y
ejecución posterior. `*-cached` describe un **intento**, no garantiza un hit;
los campos `cache_hits`, `cache_misses` y `cache_reused` registran lo ocurrido.
En este entorno el argumento que contiene el dispatcher RHS impide asumir
reutilización entre procesos. `cache=True` no implica arranque gratuito.

RSS es el máximo residente del proceso antes de verificar la solución e incluye
imports/JIT y salidas retenidas, no solo memoria del algoritmo. Los bytes de
entrada/salida se informan por separado. El benchmark mide el núcleo, no IPC,
serialización ni servicio por bloques. Las comprobaciones adicionales tienen
costo: no se afirma una mejora respecto del núcleo previo sin medirla.
Resultados completos y versiones: `../benchmarks/rk4_results.json`.

Medianas medidas (corridas `*-cold`, después de compilar):

| Tiempos × estados | Anterior Numba | RK4 protegido Numba | Anterior Python | JIT protegido | RSS protegido |
|---|---:|---:|---:|---:|---:|
| 101 × 8 | 0.068 ms | 0.518 ms | 1.399 ms | 7.770 s | 160.5 MiB |
| 10001 × 8 | 5.012 ms | 28.087 ms | 164.761 ms | 6.946 s | 161.7 MiB |
| 100001 × 8 | 60.961 ms | 311.748 ms | no ejecutado | 7.541 s | 173.6 MiB |

Las seis corridas que intentaron recargar caché (anterior y nueva) registraron
0 hits y 1 miss cada una. El error absoluto máximo del nuevo núcleo frente a
la exponencial fue respectivamente 2.473e-10, 2.309e-14 y 6.484e-14.
La salida del caso mayor ocupa 6,400,064 bytes. El nuevo núcleo es más lento
que el anterior: esta entrega prioriza controles explícitos y aislamiento de
callbacks; no cumple una hipotética meta de superar su velocidad. No se añadió
Rust porque no hay evidencia comparativa que justifique esa integración.

Próximo paso: auditoría independiente de esta candidata; RK45 requiere una
etapa separada con control adaptativo y estimación de error propios.
