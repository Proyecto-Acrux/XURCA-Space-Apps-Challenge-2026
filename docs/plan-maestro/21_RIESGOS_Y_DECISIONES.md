# 21 — Riesgos y decisiones pendientes

## Parte A — Decisiones pendientes

Cada decisión indica la **recomendación** de este plan y con qué supuesto se siguió diseñando. Ninguna fue resuelta en silencio. "Bloquea" indica qué no puede avanzar hasta decidir.

Quién decide: **E** equipo completo · **B** backend (Ema y Eze) · **F** IA/frontend · **Q** ingeniera química (decisiones científicas).

### Bloqueantes de la Fase 1

| ID | Decisión | Opciones | Recomendación | Bloquea | Decide |
|---|---|---|---|---|---|
| **D-01** | Vocabulario único de modos y estados (contradicción C01) | Mantener los cuatro vocabularios / unificar | Unificar según `08` §2: aptitud del catálogo intacta; modo pedido; modo efectivo; estados como códigos de error | Contratos (EMA-01) | E + Q |
| **D-04** | Versionar los documentos científicos de la raíz | Sí / no | **Sí**: `knowledge/` deriva de ellos y hoy solo existen en un disco. Unificar además el nombre del `.xlsx` (sin "(1)") y borrar la copia duplicada del superprompt | EMA-03 | E |
| **D-06** | Dependencias opcionales en la aplicación empaquetada | No incluirlas / incluir `statsmodels`, `pymannkendall`, `ruptures` / incluir todas | Incluir esas tres: sin ellas no hay STL, PELT, SARIMA ni Mann-Kendall modificado, que el catálogo y Q03 requieren. Verificar tamaño y compilación por plataforma | Recorridos 2 y 3; EZE-20 | B |
| **D-15** | Propiedad de `services/assistant*.py` (Python del asistente) | Backend / JP con revisión de Ema | JP con Ema como revisora obligatoria: es lógica de IA, no del motor; los comandos PyTauri siguen siendo de backend | JP-01, JP-06 | E |
| **D-16** | Versión mínima de Python | ≥3.9 (actual) / ≥3.11 | ≥3.11: es donde se probaron las dependencias opcionales y lo que pide el superprompt | EZE-18, EZE-20 | B |

### Científicas

| ID | Decisión | Contexto | Recomendación | Bloquea | Decide |
|---|---|---|---|---|---|
| **D-03** | Umbrales y parámetros que no figuran en los documentos disponibles | Falta `ANEXO_MATEMATICO.md`: no hay historia mínima por método, años mínimos de base climatológica, desfases por fenómeno, n efectivo mínimo ni mínimos de entrenamiento por modelo | (a) Ubicar el anexo si existe; (b) si no, la ingeniera química define los valores por ola; (c) mientras tanto, todo valor va marcado `proposed` en `knowledge/` y visible como tal en los resultados | Estados "validado"; valores por defecto de N2 | Q |
| **D-02** | Nomenclatura de familias de modelo (C02) | El superprompt usa F2, F3, F4; el catálogo M5, M6A, M6B | Usar los nombres del catálogo y tratar los del superprompt como alias | Solo documentación | Q + B |
| **D-08** | Qué significa "validado" para el motor existente | El pedido habla de algoritmos validados; `ENGINE_STATUS.md` los declara *candidate, no aprobado*, sin auditoría independiente (C21) | Adoptar la escala de estados de `12` §4 y definir quién firma "validado matemáticamente" (propuesta: revisor distinto del autor, con referencia independiente). No declarar "aprobado" lo que hoy es candidato | Estados en `get_capabilities` | E |
| **D-09** | BFAST | La planilla lo nombra; no está implementado | Usar `stl` + `pelt` (o `cusum`) **rotulado como aproximación**; no implementar BFAST en la v1 | N1.3A, N1.3C, N1.9A, N1.3D, B2.5 | Q |
| **D-12** | PRED-06, PRED-07 y PRED-08 frente al catálogo (C04, C05, C06) | La planilla propone pronósticos que el catálogo y el superprompt no respaldan | No implementar PRED-07 ni PRED-08 hasta resolver; PRED-06 solo como baseline estacional rotulado exploratorio | Líneas predictivas P3 | Q |
| **D-13** | Períodos por defecto (C09) | Piloto 2015–2025 frente a SPI con menos de 20 años y base 1991–2020 | Descargar siempre desde la base climatológica cuando la fuente lo permita (POWER y ERA5 lo permiten), aunque el análisis se muestre sobre el período pedido | Valores por defecto | Q |
| **D-14** | Ruteo de B6.3 (C12) | Variables radiación, AOD y nube con productos ENSO, IMERG y ERA5 | Corregir en la planilla; hasta entonces B6.3 queda con la rama de radiación (POWER) y el resto bloqueado | B6.3 | Q |
| **D-17** | Sustitución de productos requeridos por alternativas de la misma magnitud | IMERG → ERA5/POWER; SMAP → ERA5-Land (modelo); GHRSST → OISST; ERA5 por CDS → POWER u Open-Meteo | Aceptar con rótulo explícito en cada resultado; **rechazar** `GWETROOT` de POWER como humedad volumétrica | O1 y O2 completas | Q |
| **D-21** | Tolerancias de validación predictiva | Cuántos orígenes de backtest, tolerancia de cobertura del intervalo, umbral de habilidad | Habilidad > 0 en el bloque final es el piso (T11); el resto, a definir con los primeros backtests reales, no antes | `validated_forecast` | Q + B |
| **D-23** | Método cuando planilla y superprompt difieren (C07) | SARIMA/ETS vs ARX regularizado; SARIMA + ridge vs dos etapas; zero-inflated vs hurdle | Empezar por el de la planilla cuando ya exista el método (SARIMA, Holt-Winters) y registrar el del superprompt como candidato a comparar en el mismo backtest. Para predictores múltiples con regularización hace falta un ridge multivariable nuevo (el actual es de monomios) | PRED-01, 02, 03 | Q + B |
| **D-26** | Traducción de las afirmaciones normativas | Los textos de la planilla están en español | Mostrarlas en español hasta que la ingeniera química valide una traducción | Interfaz en inglés | Q + F |

### Técnicas

| ID | Decisión | Opciones | Recomendación | Bloquea | Decide |
|---|---|---|---|---|---|
| **D-05** | Destino del código duplicado | Borrar / conservar como heredado | Conservar hasta la Fase 9. `evidence.summarize_series` queda como resumen descriptivo y deja de rotular "trend" cuando hay resultado del Handler; `execute_regression` y `handlers/analysis.py` quedan heredados y sin nuevos usos | EMA-31 | B |
| **D-07** | Discrepancia de `dynamical/multi_ode.py` con `PRESERVATION.json` (C20) | Restaurar el archivo / actualizar la huella | Revisar el historial para saber qué cambió y por qué; luego actualizar la huella o restaurar. Hacerlo antes de activar la verificación en CI | Verificación de archivos protegidos | B |
| **D-10** | Biblioteca para leer los archivos de área de AppEEARS | Pedir CSV de estadísticas de área a AppEEARS / `netCDF4` / `xarray` / `rasterio` | Evaluar primero si la salida tabular de AppEEARS alcanza para estadística zonal (evita dependencia nueva); si no, la dependencia más liviana que funcione empaquetada | EZE-13 | B |
| **D-11** | Pesos del ordenamiento de fuentes | Fijos en código / parámetros en `sources.json` | Parámetros en datos; el orden de criterios es fijo | EZE-10 | B |
| **D-18** | Marco de pruebas de componentes del frontend | Solo `node:test` para servicios y stores / agregar un marco de componentes | Empezar con `node:test` + guiones funcionales; evaluar un marco de componentes solo si los guiones resultan insuficientes | JUAN-12 | F |
| **D-19** | Conector de pronóstico meteorológico | No tener / agregar uno con fechas de emisión | Necesario para M1 de corto plazo y para PRED-05; sin pronósticos **archivados** no hay validación operacional. Posponer hasta después del MVP | PRED-05 etapa b | B + Q |
| **D-20** | Análisis sobre un área (provincia, cuenca) | Punto representativo / muestreo en varios puntos / ráster | Hoy solo punto, **informándolo siempre**. Muestreo multipunto como mejora intermedia para variables de reanálisis; ráster cuando exista EZE-13 | Casos con polígonos | B + Q |
| **D-22** | IC de Theil-Sen | Extender `sen_slope` (archivo protegido) / función nueva | Función nueva | EMA-13 | B |
| **D-24** | Tipado del frontend | Migrar a TypeScript / JSDoc generado | JSDoc generado desde los JSON Schema; sin migración | JUAN-01 | F |
| **D-25** | Canal de progreso | Sondeo / eventos | Sondeo; reconsiderar solo si resulta insuficiente | — | B + F |

---

## Parte B — Riesgos

Impacto y prioridad: **A** alto · **M** medio · **B** bajo.

### Dependencias críticas

| ID | Riesgo | Impacto | Prior. | Mitigación | Responsable |
|---|---|---|---|---|---|
| R-01 | **El procesador de AppEEARS es el camino crítico**: 7 de los 13 fenómenos MVP dependen por completo de él y 2 más en una rama | A | A | Línea paralela desde la Fase 1; verificar credenciales primero (EZE-19); empezar por extracción por punto; el MVP muestra antes los 4 fenómenos que no dependen de AppEEARS | Eze |
| R-02 | Las descargas autenticadas nunca se verificaron en campo (FIRMS, AppEEARS, Earthdata, CDS, Copernicus Data Space) | A | A | EZE-19 como una de las primeras tareas; registrar `last_verified`; datos de muestra rotulados como respaldo para demostraciones | Eze |
| R-03 | Los contratos se retrasan o cambian mucho después de congelados | A | A | EMA-01 es la primera tarea; revisión conjunta antes de congelar; cambios posteriores solo compatibles o con versión nueva | Ema |
| R-04 | Las dependencias opcionales no empaquetan en alguna plataforma | M | A | Decidir D-06 temprano; probar el empaquetado en la Fase 1; descriptor `available: false` con alternativa | Eze |
| R-05 | Disponibilidad de la ingeniera química para revisar `phenomena.json` y resultados | A | M | Revisiones por ola, con material acotado (los fenómenos de esa ola); todo lo no revisado queda `proposed` | Ema |

### Problemas científicos

| ID | Riesgo | Impacto | Prior. | Mitigación | Responsable |
|---|---|---|---|---|---|
| R-06 | Faltan umbrales (historia mínima, desfases, tolerancias) por ausencia del anexo | A | A | D-03; valores `proposed` visibles; ningún estado "validado" sin ellos | Ema + Q |
| R-07 | Sustituir productos requeridos (IMERG, SMAP) por reanálisis cambia lo que se puede afirmar | M | A | `source_substitution` obligatorio en el resultado; insignias; D-17 | Eze + Q |
| R-08 | Un punto no representa un área | A | M | Aviso permanente; D-20; no llamar "provincial" a un análisis puntual | Ema |
| R-09 | Asociaciones espurias por estacionalidad compartida o autocorrelación | A | A | Anomalías, tamaño efectivo de muestra, desfases predefinidos, FDR (EMA-16, EMA-22) | Ema |
| R-10 | Los modelos estadísticos no superan a la climatología (probable en precipitación mensual) | M | A | Es un resultado válido: se muestra la referencia con su bandera (T11). No presionar para "que dé" | Ema |
| R-11 | Un resultado se interpreta como alerta operacional | A | M | Aviso de Q14 en hallazgos y vistas; enlaces a organismos oficiales; la IA lo repite | Ema, Juan, JP |
| R-12 | El motor está en estado candidato, sin auditoría independiente | M | M | D-08; pruebas de contrato sobre la ruta del registro; no declarar "validado" | Ema |
| R-13 | Aproximar BFAST con STL + PELT da rupturas distintas | M | B | Rotular como aproximación; D-09 | Ema + Q |

### Datos y conectores

| ID | Riesgo | Impacto | Prior. | Mitigación | Responsable |
|---|---|---|---|---|---|
| R-14 | La selección de estaciones sigue eligiendo series pobres | A | A | EZE-06 con el caso reportado como prueba de regresión; candidatos visibles; corrección manual | Eze |
| R-15 | Los pedidos históricos largos fallan (Open-Meteo, CDS) | M | A | Troceo temporal (EZE-11); caché | Eze |
| R-16 | Cuotas y límites de los proveedores | M | M | Caché; un proveedor a la vez; respeto de `Retry-After` | Eze |
| R-17 | Los proveedores cambian formatos o rutas | M | M | Respuestas grabadas para detectar el cambio; `last_verified`; errores tipados | Eze |
| R-18 | No hay conector de pronóstico ni pronósticos archivados | M | M | D-19; los pronósticos por ahora son puramente estadísticos y así se rotulan | Eze |
| R-19 | Variables requeridas no expuestas como serie (SLP, viento y humedad relativa diarios, clorofila, AOD) | M | M | Fenómenos marcados L3 o L4 con motivo; EZE-21, EZE-22 | Eze |
| R-20 | `dschg_c` de SWOT sin valores válidos | B | B | B3.4 sin la rama de caudal | Eze |
| R-21 | Descargas crudas sin límite de tamaño | M | M | Límite por nodo (EZE-03) | Eze |

### Modelos no validados

| ID | Riesgo | Impacto | Prior. | Mitigación | Responsable |
|---|---|---|---|---|---|
| R-22 | Presentar extrapolaciones como pronósticos | A | A | Puerta de elegibilidad; `validated_forecast` exige `backtest_id`; vista con tramo exploratorio diferenciado | Ema, Juan |
| R-23 | Fuga de información futura en el backtesting | A | A | Transformaciones dentro de cada pliegue; `available_at`; pruebas de invariancia (T10) | Ema |
| R-24 | Intervalos mal calibrados presentados como nominales | A | M | Cobertura empírica obligatoria; sin calibración → sin intervalo | Ema |
| R-25 | Confundir horizonte de prueba de la planilla con horizonte validado | A | M | `horizons[]` con `status`; `proposed` hasta tener evidencia | Ema |

### Integración

| ID | Riesgo | Impacto | Prior. | Mitigación | Responsable |
|---|---|---|---|---|---|
| R-26 | Los ejemplos fijos divergen de las respuestas reales | M | A | Prueba de contrato en CI; retiro de cada simulación en el mismo PR que prueba el comando real | Ema, Juan |
| R-27 | Fallo de paridad entre formulario y asistente | A | M | Una sola función de armado; valores por defecto solo en el backend; T17 | JP, José, Ema |
| R-28 | La IA propone capacidades inexistentes o ids inventados | A | M | Capacidades dinámicas; validación de ids; suite de comportamiento | JP |
| R-29 | La IA redacta afirmaciones no respaldadas | A | A | Guardia determinista; plantillas; el modelo solo ve hallazgos | JP |
| R-30 | El contexto de la IA no alcanza para 73 fenómenos | M | M | Índice compacto + detalle bajo demanda (JP-02) | JP, Ema |
| R-31 | Jobs largos bloquean o confunden a la interfaz | M | M | JobManager, sondeo, estados claros, cancelación | Eze, Juan |
| R-32 | Migración de `cfg_data` rompe espacios de trabajo guardados | M | M | Migración con pruebas sobre archivos v1 reales (JOSE-08) | José |
| R-33 | Un cambio accidental en un algoritmo protegido | A | B | Verificación de huellas en CI; `CODEOWNERS` | Ema, Eze |

### Arquitectura

| ID | Riesgo | Impacto | Prior. | Mitigación | Responsable |
|---|---|---|---|---|---|
| R-34 | Sobredimensionar el Handler | M | M | Sin infraestructura distribuida ni base de datos; cada pieza se justifica por un caso de uso | Ema |
| R-35 | La capa de conocimiento en JSON se vuelve difícil de mantener | M | M | Generación desde el catálogo; verificación de integridad; un archivo por tema; revisión por PR | Ema |
| R-36 | Estado en memoria: se pierde al cerrar la aplicación | B | B | Resultados y caché en disco; los jobs en curso se pierden, y eso es aceptable en escritorio | Eze |
| R-37 | Un solo proceso: límite de simultaneidad | B | B | Máximo de jobs; suficiente para un usuario | Eze |

### Coordinación del equipo

| ID | Riesgo | Impacto | Prior. | Mitigación | Responsable |
|---|---|---|---|---|---|
| R-38 | Ema concentra demasiadas tareas críticas (contratos, planificador, ejecutor, algoritmos, predictivo) | A | A | Orden estricto por recorrido; Eze revisa y toma `ops/` de datos; los algoritmos P2 pueden repartirse; no empezar R3 antes de cerrar R1 | Ema, Eze |
| R-39 | Propiedad ambigua de archivos compartidos | M | M | Reglas de `18` §3 y §4; `CODEOWNERS` | E |
| R-40 | Cada integrante construye su módulo y se integra recién al final | A | A | Recorridos end-to-end con demostración; simulaciones retiradas progresivamente | E |
| R-41 | Documentos científicos solo en un disco local | A | A | D-04 | E |
| R-42 | El plan queda desactualizado | M | M | Los estados viven en datos (`knowledge/`, capacidades), no en prosa; este documento registra las decisiones con fecha | Ema |

---

## Parte C — Registro de decisiones tomadas

*Vacío. Cada decisión que el equipo cierre se anota aquí con: ID, fecha, qué se decidió, quiénes, y qué documentos del plan hay que actualizar.*

| ID | Fecha | Decisión | Participantes | Documentos a actualizar |
|---|---|---|---|---|
| | | | | |
