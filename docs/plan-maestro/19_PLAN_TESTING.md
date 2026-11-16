# 19 — Plan de testing

Este documento especifica **cómo deberán implementarse** las pruebas. No se ejecutó ninguna.

## 1. Qué es y qué no es

| Es | No es |
|---|---|
| Verificación de corrección científica, de contratos, de datos, de integración y de comportamiento | Benchmarks de rendimiento |
| Validación predictiva fuera de muestra (necesaria para habilitar pronósticos) | Repetición de benchmarks de velocidad sobre algoritmos ya medidos (`STAGE1A`, `POLYNOMIAL_REGRESSION`, `RK4`): **no se replanifican** |

## 2. Punto de partida

- pytest con 131 funciones de test en 18 archivos; `pythonpath` y `testpaths` en `src-tauri/pyproject.toml`; alternativa aislada `models/run_checks.py`.
- `node:test` con 1 archivo en el frontend; sin script `test` en `package.json`.
- Ningún test toca la red ni los conectores reales.
- No hay CI de pruebas.
- `test_libraries.py` y `test_optional_trends.py` fallan con `ImportError` si faltan dependencias opcionales (no usan `importorskip`).

## 3. Niveles

| Nivel | Qué prueba | Herramienta | Dónde | Corre en CI |
|---|---|---|---|---|
| **Unitarias** | Una función con datos sintéticos y casos extremos | pytest | Junto al módulo (`M/tests/`, `handler/tests/`, `dataprep/tests/`) | Sí |
| **De contrato** | Que los ejemplos fijos validan contra los JSON Schema; que cada comando respeta entrada y salida; que cada `statement_key` y cada código de error tiene texto | pytest + `node:test` | `handler/tests/contract/`, `TS/src/lib/services/*.test.js` | Sí |
| **Matemáticas** | Un algoritmo contra referencia independiente, solución analítica o propiedad conocida | pytest | `M/tests/` | Sí |
| **De calidad de datos** | Controles Q de datos con series sintéticas defectuosas | pytest | `dataprep/tests/` | Sí |
| **De integración** | Planificador + ejecutor + motor con **conectores simulados** | pytest | `handler/tests/integration/` | Sí |
| **De fallos de fuentes** | Tiempos agotados, códigos HTTP, respuestas truncadas, credenciales ausentes | pytest con servidor simulado | `handler/tests/faults/` | Sí |
| **De seguridad** | Solicitudes maliciosas, límites, fuga de credenciales | pytest | `handler/tests/security/` | Sí |
| **De comportamiento del asistente** | Estructura de la salida ante consultas tipo, con proveedor simulado | pytest | `services/test_assistant_behavior.py` | Sí |
| **De paridad** | Misma huella y mismo plan por los dos modos | pytest + `node:test` | `handler/tests/parity/` | Sí |
| **End-to-end con simulaciones** | Los 10 casos sobre el backend real con conectores simulados | pytest | `handler/tests/e2e/` | Sí |
| **End-to-end con red** | Los casos con fuentes reales | pytest con marca `network` | ídem | **No** (manual, antes de cada cierre de recorrido) |
| **Funcionales de interfaz** | Guiones por caso de uso | Manual, con guion y capturas | `docs/` de pruebas | No |
| **Validación predictiva** | Backtesting sin fuga, habilidad, cobertura | pytest (lógica) + ejecución con datos reales (evidencia) | `M/tests/`, registro de `backtest_id` | Lógica: sí |

Marcas de pytest a definir: `network`, `optional_deps`, `slow`. Las pruebas con dependencias opcionales pasan a usar `importorskip`.

## 4. Conectores simulados

Pieza central de la estrategia: un conjunto de **respuestas grabadas** por conector (una respuesta buena, una vacía, una con huecos, una con error) y **series sintéticas** con propiedades conocidas (tendencia exacta, estacionalidad, desfase insertado, eventos insertados). El ejecutor recibe el conector por inyección, de modo que las pruebas de integración y end-to-end no dependen de la red ni de credenciales.

Propietario: Eze (respuestas grabadas), Ema (series sintéticas).

---

## 5. Controles Q01–Q18 → pruebas

| Control | Requisito verificable | Dónde se implementa | Prueba | Resp. |
|---|---|---|---|---|
| **Q01** Cobertura y faltantes | Cobertura < umbral bloquea la tendencia; no se interpola | `dataprep/qa.py` | Serie con 70% de datos → `block` y hallazgo `data_gap`; umbral configurable por producto | Eze |
| **Q02** Climatología | Base fija documentada; misma estación o mes; mínimo de años | `M/climate/climatology.py` + validador | Base inexistente → base propia **rotulada**; base con pocos años → `warn`/`block` | Ema |
| **Q03** Tendencia y significación | Sen + MK estacional; control de autocorrelación; IC y magnitud además de p | `validators.py` | Serie sin tendencia → `inconclusive`; serie autocorrelada → se usa el método modificado o se advierte | Ema |
| **Q04** Pruebas múltiples | FDR por familia; selección a posteriori ⇒ exploratorio | `validators.py`, `M/stats/multiple_testing.py` | 24 desfases, uno con p bajo → no confirmatorio | Ema |
| **Q05** Precipitación | Tasa vs acumulado; ventana; base de SPI < 20 años | `dataprep/qa.py`, `M/climate/spi.py` | Tasas mal agregadas detectadas; base de 11 años → `warn` de baja robustez | Eze + Ema |
| **Q06** Satélite óptico | Máscaras de nube, sombra, agua y nieve antes del indicador | `dataprep/satellite_qa.py` | Píxeles marcados quedan inválidos, no interpolados | Eze |
| **Q07** Sensor térmico | Por sensor, confianza, órbita; detección ≠ fuego | `services/firms.py`, `dataprep/` | VIIRS y MODIS no se suman; unidad "detecciones" | Eze |
| **Q08** Área quemada | Área real en proyección adecuada; focos ≠ hectáreas | `dataprep/zonal.py` | Ráster sintético de área conocida se conserva; no existe conversión focos → ha | Eze |
| **Q09** Compatibilidad espacial | Resolución común = la más gruesa; agregación ponderada | `dataprep/align.py` | Fuente gruesa + fina → salida a la gruesa, rotulada | Eze |
| **Q10** Compatibilidad temporal | Calendario, zona horaria, desfases físicos; observación ≠ publicación | `dataprep/align.py`, `series.py` | Series con ventanas diarias distintas se alinean o se bloquean | Eze |
| **Q11** Unidades y datum | Rechazar mezclas sin transformación explícita | `dataprep/units.py`, `qa.py` | mm/día vs mm; kPa vs hPa; dos datums → `block` | Eze |
| **Q12** Anomalía, tendencia, evento | Salidas distintas | `findings.py` | Evento actual con tendencia inconclusa → ambos hallazgos presentes | Ema |
| **Q13** Causalidad | Sin salida causal sin diseño específico | `findings.py`, guardia del asistente | Ningún hallazgo con `causal`; texto causal del asistente bloqueado | Ema + JP |
| **Q14** Riesgo operacional | No presentar como alerta oficial | `findings.py`, vistas | Hallazgos de fuego e hidrología llevan aviso y enlace | Ema + Juan |
| **Q15** Sin fuga | Backtest temporal; transformaciones solo en entrenamiento; predictores conocidos en la emisión | `model_registry.py`, `M/forecasting/backtest.py` | Predictor posterior a la emisión bloqueado; cambiar datos futuros no cambia la predicción | Ema |
| **Q16** Incertidumbre predictiva | Intervalos con cobertura empírica; sin % inventados; bandera si no supera al baseline | `M/forecasting/intervals.py`, `findings.py` | Modelo peor que la referencia → bandera; sin calibración → sin intervalo | Ema |
| **Q17** Línea base y uso del suelo | Comparar por clase y estación; separar cosecha y quema | `validators.py` | NDVI que baja en cosecha → alternativa, no degradación | Ema |
| **Q18** Validación espacial | Polígonos estables; porcentaje de región observada | `dataprep/zonal.py` | `valid_area_fraction` presente; área válida baja → `warn` | Eze |

Regla de implementación: cada control tiene una entrada en `qa_rules.json` con el **texto original** de la planilla, el umbral, su parametrización y la "salida ante falla". Una prueba verifica que los 18 existen y que el texto no fue alterado.

---

## 6. Pruebas de aceptación T01–T21

Cada fila se convierte en al menos una prueba automática. "Nivel": U unitaria · I integración · E end-to-end con simulaciones · UI frontend · A asistente.

| Test | Condición (planilla) | Resultado exigido | Implementación | Nivel | Resp. |
|---|---|---|---|---|---|
| **T01** | Tendencia de precipitación con p ≥ 0.05 | "No hay evidencia suficiente"; jamás "variabilidad natural probada" | Serie sintética sin pendiente → `conclusiveness: inconclusive`; la plantilla y la guardia rechazan "sin cambios" | U + I + UI + A | Ema, Juan, JP |
| **T02** | Déficit y exceso con base consistente | Evolución temporal y mapa con unidades correctas | Serie con ventanas secas y húmedas → SPI y anomalías con misma base; vista `spi_states` | I + UI | Ema, Juan |
| **T03** | Tres detecciones de un mismo fuego | La interfaz no presenta "3 incendios" ni hectáreas | Conteo = 3 con unidad "detecciones"; texto de interfaz y de asistente verificados | I + UI + A | Eze, Juan, JP |
| **T04** | FIRMS y MCD64A1 simultáneos | Dos capas y leyendas separadas, procedencia visible | Dos `VizHint` independientes; ninguna operación los combina | I + UI | Ema, Juan |
| **T05** | LST 40 °C, T2m 27 °C | No reportar ola de calor del aire por LST | Variables no intercambiables; el selector no ofrece T2m para LST; leyendas distintas | U + I + UI | Ema, Eze, José |
| **T06** | Píxel con 70% de nubes en el mes | Sin tendencia; aviso de cobertura insuficiente | Cobertura < 0.8 → `block` | U + I | Eze |
| **T07** | Humedad en P10 el último mes; Sen no significativo | Reportar sequía superficial; no negarla por p | Hallazgo `event` presente junto a `trend` inconcluso | I | Ema |
| **T08** | Ola de calor marina + clorofila anómala | No afirmar floración tóxica | Advertencia fija; la guardia bloquea "tóxico" y "marea roja" | I + A | Ema, JP |
| **T09** | 24 desfases, uno con p bajo | Exploratorio o validado en prueba externa | `exploratory: true` si la selección fue a posteriori; FDR aplicado | U + I + UI | Ema, Juan |
| **T10** | Objetivo en 2025, predictor de 2026 | Bloquear el predictor y registrar el error | `LEAKAGE_BLOCKED` | U + I | Ema |
| **T11** | RMSE del modelo > RMSE del baseline | Mostrar experimental; no prometer mejora | `not_superior_to_baseline`; la vista destaca la referencia | U + I + UI | Ema, Juan |
| **T12** | 2000–2025 solo con SWOT | Bloquear y ofrecer otra fuente histórica | `TEMPORAL_INCOMPATIBLE` en el planificador, sin red, con alternativa | U + I + UI | Eze, José |
| **T13** | SMAP grueso y Sentinel-2 de 10 m | Agregar al soporte efectivo; nunca SMAP a 10 m | Alineación a la más gruesa; leyenda con resolución efectiva | U + I + UI | Eze, Juan |
| **T14** | GPM en mm/h con muestras de 30 min | Suma mensual conservadora y verificable | Conversión de tasa a acumulado; total conocido | U | Eze |
| **T15** | WSE con datums distintos | Sin tendencia hasta convertir | `UNIT_INCOMPATIBLE` / `block` de Q11 | U + I | Eze |
| **T16** | NDVI desciende durante la cosecha | Cosecha probable; no degradación confirmada | Q17 → alternativa en el hallazgo | I | Ema |
| **T17** | Mismos ROI, período, variable y opciones | Mismo plan y resultado reproducible | Misma `request_hash` y `plan_id` por formulario y por asistente; segunda ejecución usa caché y da los mismos números | I + E | JP, José, Ema |
| **T18** | Consulta fuera de catálogo | Exploración genérica o `UNSUPPORTED` | La intención no asigna fenómeno; el asistente tampoco | U + A | Ema, JP |
| **T19** | AppEEARS, GPM o FIRMS sin credencial o con cuota | Error explícito + datos de muestra etiquetados | `CREDENTIALS_MISSING`; muestra con `demo: true` solo si se permite; insignia en la interfaz | I + UI | Eze, Juan |
| **T20** | FIRMS contra MCD64A1 | Gráficos y mapas separados; unidades independientes | Igual que T04, sobre la comparación | I + UI | Ema, Juan |
| **T21** | Se elige Giovanni como fuente | Proponer producto o `NOT_AUTOMATABLE` | El selector rechaza el portal y sugiere el producto subyacente | U + I | Eze |

**Matriz de aceptación del sistema:** las 21 filas, cada una con el identificador de sus pruebas automáticas y su estado, se mantienen en un archivo de seguimiento que CI actualiza. Un recorrido no se cierra con una prueba de su alcance en rojo.

---

## 7. Pruebas matemáticas de los algoritmos nuevos

Mismo patrón que ya usa el repositorio (referencia independiente + propiedades):

| Algoritmo | Referencia o propiedad |
|---|---|
| Climatología y anomalías | Serie = estacionalidad conocida + tendencia → la anomalía recupera la tendencia |
| IC de Theil-Sen | `scipy.stats.theilslopes`; cobertura en simulación |
| SPI | Datos de distribución conocida → valores esperados; no fuga entre calibración y aplicación |
| Eventos | Eventos insertados se recuperan con sus fechas |
| Correlación con desfases | Desfase insertado se detecta; series independientes autocorreladas no superan la tasa nominal de falsos positivos |
| FDR | Coincidencia con una implementación de referencia |
| Backtesting | Proceso predecible → habilidad positiva; ruido blanco → habilidad ≈ 0; invariancia ante cambios en el futuro |
| Intervalos | Cobertura empírica ≈ nominal en simulación |
| FWI | Valores de referencia publicados de la formulación oficial |

## 8. Pruebas de seguridad

| Caso | Resultado esperado |
|---|---|
| Campo desconocido en la solicitud | Rechazo (`extra="forbid"`) |
| `recipe_id`, `algorithm_id`, `source_id` o `model_id` inexistente | `INVALID_REQUEST`; nada se ejecuta |
| Cadenas con código, rutas de archivo o URL en campos de texto | Tratadas como texto; sin efecto |
| Período de un siglo, 10 000 variables, polígono con un millón de vértices | Rechazo por límites |
| Salida del asistente con instrucciones inyectadas por el usuario | Descartada por el validador de esquema |
| Búsqueda de credenciales en resultados, planes, huellas y registros | Ninguna aparición |
| Texto devuelto por una fuente con apariencia de instrucción | No llega al prompt como instrucción |

## 9. Pruebas de fallos de fuentes

Por cada conector envuelto: tiempo agotado → reintento → `SOURCE_UNAVAILABLE`; HTTP 429 con `Retry-After` respetado; HTTP 404 sin reintento; respuesta vacía → `INSUFFICIENT_DATA`; respuesta truncada → reintento; credencial ausente → `CREDENTIALS_MISSING` sin intento de descarga; fallo de una fuente con otras sanas → resultado `partial`; cancelación durante la descarga → `CANCELLED` sin archivos a medias.

## 10. Puertas de calidad

| Momento | Debe pasar |
|---|---|
| Cada PR | Unitarias, de contrato, de integración, de seguridad y de comportamiento (CI) |
| PR que toca un conector | Además: prueba manual con datos reales, anotada con fecha |
| PR que toca `M/` | Además: verificación de que ningún archivo de `PRESERVATION.json` cambió |
| Cierre de un recorrido | Pruebas T de su alcance; end-to-end con red; guion funcional; demostración |
| Fase 8 | Matriz T01–T21 completa; revisión científica de resultados reales |

## 11. Qué prueba que todo está integrado

1. Los 10 casos de uso corren end-to-end con conectores simulados en CI.
2. Los mismos casos corren con fuentes reales en la aplicación empaquetada.
3. T17 demuestra que formulario y asistente convergen.
4. Las 21 pruebas de aceptación están en verde o con excepción documentada.
5. `get_capabilities` informa, para los 73 fenómenos, un estado que coincide con lo que de verdad se puede ejecutar (prueba que intenta planificar cada fenómeno marcado como disponible).
