TAREA: W01 — Climatología y anomalías

ARCHIVOS CREADOS:
- climate/climatology.py
- catalog_registry.py
- tests/test_climatology.py
- W01_REPORT.md

Archivo modificado: AGENTS.md, exclusivamente mover W01 de Pendientes a Candidate.

FIRMAS:
```python
climatology(values, groups, baseline, *, min_count) -> dict
anomalies(values, groups, reference, *, kind) -> dict
catalog_registry(*, include_optional: bool = True)
```

REGISTRO (method_id, mínimo de observaciones, unidades de salida):
- climatology: 1 observación; además min_count por grupo en la base.
  mean/std/median/mad en variable.unit; group_ids/count en 1.
- anomalies: 1 observación; calcula su referencia con groups, baseline y
  min_count explícitos. absolute en variable.unit; percent en %;
  standardized/robust_z en 1. Incluye la referencia y sus unidades.
- groups y baseline son IDs de variables temporales adimensionales.
  El contrato protegido rechaza variables booleanas: baseline se transporta
  explícitamente como 0/1 y se convierte a bool después de validar esos valores.
  La API directa exige una máscara booleana. No se modificó el contrato.

ORÁCULO USADO Y RESULTADO:
Prueba analítica independiente: ciclo de cuatro grupos más tendencia 2*t;
base t<12. Para grupo g, media esperada ciclo[g]+2*(g+4), desvío
sqrt(128/3), MAD 8 y anomalía 2*(t-g-4). Prueba escrita, NO ejecutada.

PRUEBAS EJECUTADAS (comando y resultado real):
Ambos comandos se intentaron desde aplicacion/trend-scope/src-tauri/.
No llegaron a ejecutar pytest. Salida real del primero (exit code 1):

```text
python -m pytest src-python/trend_scope/models/tests/test_climatology.py -q
python : El término 'python' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 1
+ python -m pytest src-python/trend_scope/models/tests/test_climatology ...
+ ~~~~~~
    + CategoryInfo          : ObjectNotFound: (python:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
```

Salida real del segundo (exit code 1):

```text
python -m pytest -q
python : El término 'python' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 1
+ python -m pytest -q
+ ~~~~~~
    + CategoryInfo          : ObjectNotFound: (python:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
```

Comprobación adicional: `py -0p` devolvió `No installed Pythons found!`.
No se instalaron dependencias. Las pruebas cubren los siete tipos de §5,
pero sus resultados quedan pendientes. No se ejecutaron benchmarks.

ARCHIVOS PROTEGIDOS TOCADOS: ninguno

`git diff --stat` y `git diff --check` no produjeron salida: los archivos
nuevos y AGENTS.md ya no estaban bajo seguimiento. La comparación con el
manifiesto encontró 26 hashes diferentes en archivos protegidos existentes;
ninguno fue editado en esta tarea. No se afirma que el checkout coincida con
PRESERVATION.json ni se regeneró ese manifiesto.

SUPUESTOS Y LÍMITES CIENTÍFICOS:
Observaciones finitas, sin máscaras, grupos enteros, pesos iguales.
Desvío poblacional ddof=0; MAD cruda en la referencia; robust_z=(x-mediana)/(1,4826·MAD) (decisión del 2026-11-15).
No elige el período de base ni estima incertidumbre. Percent requiere una
escala de razón físicamente adecuada. No infiere fechas, convierte unidades,
interpola, pronostica ni prueba significancia. Desbordamientos se rechazan.
Registro aditivo, sin cambios en IPC ni UI. Dependencia nueva: ninguna;
implementación numérica: NumPy. Tiempo O(n log n), memoria O(n).

VALORES QUE QUEDARON COMO PARÁMETRO OBLIGATORIO:
min_count y kind; grupos y máscara de base también explícitos.

ESTADO: candidate

Próximo paso: ejecutar ambas suites con Python disponible y realizar auditoría
independiente antes de aprobar W01.
