# 22 — Barrido: investigación científica vs código existente

Contrasta lo que pide la investigación de la ingeniera química (planilla `Trend_Detective_v9…xlsx`: hojas de Nivel 1, Nivel 2, `Modelos_Predictivos`, `QA_y_Reglas_Globales`) con lo que hoy está programado en `aplicacion/trend-scope/src-tauri/src-python/trend_scope/`.

Base: auditoría de lectura del commit `c8f6555` (ver `02_AUDITORIA.md`). **No se ejecutó código.** "Existe" significa que hay implementación con tests en el repositorio; no significa validación independiente.

Columna **Cola**: identificador de la tarea en `trend_scope/models/AGENTS.md` (cola de trabajo para Codex). Lo que no es una función del motor matemático se marca **Equipo** y remite al backlog humano.

Equivalencia con la numeración de `06_MATRIZ_ALGORITMOS.md`: W01–W06 = N01–N06 (con N04 y N05 en el mismo orden); W07 = N09, W08 = N07, W09 = N08; W10–W16 = N10–N16. La cola W ordena por dependencia de construcción.

## 1. Resultado en números

| | Cantidad |
|---|---|
| Métodos distintos que nombra la planilla en la columna "Método / análisis" | 39 |
| Cubiertos por código existente | 6 |
| Cubiertos solo en parte | 6 |
| Sin implementar | 21 (19 se resuelven con funciones del motor; 2 son tareas de orquestación o de datos) |
| Fuera de alcance de la v1 (procesamiento especializado) | 6 |
| **Funciones nuevas del motor matemático que hacen falta** | **16 (W01–W16), contando las que piden las hojas de QA y de modelos** |
| Controles Q01–Q18 implementados como tales | 0 de 18 |
| Líneas predictivas PRED-01–08 con modelo | 0 de 8 |

## 2. Métodos de la planilla, uno por uno

Ordenados por cantidad de fenómenos que los requieren.

| Método que pide la planilla | Fenómenos | En el código | Qué falta | Cola |
|---|---|---|---|---|
| Anomalías (absoluta, %, estacional, conjuntas) | 14 | **No existe.** Solo se leen anomalías ya publicadas por OISST y ONI | Climatología de base fija y anomalías | **W01** |
| Pendiente de Sen | 10 | Existe: `stats/trends.py: sen_slope` | Nada para la pendiente | — |
| "Tendencia" sin método nombrado | 10 | Existe (`sen` + `mann_kendall`) | Se aplica la misma receta que Sen + MK | — |
| Percentiles y umbrales (P10, P90, P95, ≥P90 con duración) | 9 | **No existe** | Umbrales por percentil y detección de eventos por rachas | **W04** |
| Intervalo de confianza (IC95) | 6 | **No existe.** `sen_slope` devuelve la incertidumbre como no estimada | IC de la pendiente de Sen | **W02** |
| Mann-Kendall (incluye estacional y con autocorrelación) | 5 | Existe: `mann_kendall`, `seasonal_mann_kendall`; `modified_mann_kendall` requiere `pymannkendall` (opcional) | Empaquetar la dependencia | Equipo (D-06) |
| BFAST / rupturas | 5 | Parcial: `stl` + `pelt` (opcionales) y `cusum`. **BFAST no existe** | Decidir si STL + PELT se acepta como aproximación rotulada | Equipo (D-09) |
| Regresión (dinámica con lags, explicativa, con controles) | 5 | Parcial: `multivariable_ols` existe; no hay construcción de la matriz de rezagos | Matriz de diseño con rezagos (es preparación, no un método nuevo) | Equipo (EMA-17) |
| Conteos, frecuencia y recuentos por temporada | 5 | Parcial: `firms.py` cuenta por día o mes, sin separar sensores | Conteo por temporada y sensor | Equipo (EZE-14, EMA-23) |
| Estacionalidad, amplitud, comienzo de estación | 4 | Parcial: `harmonic_regression`, `stl`, `fft` | Indicadores de fenología (comienzo de estación) sin definir | Equipo (decisión científica) |
| SPI (escalas 1/3/6/12, secuencial, estados) | 4 | **No existe** | SPI con calibración separada de la aplicación | **W03** |
| Lags y desfases meteorológicos | 4 | **No existe** | Correlación para desfases predefinidos con tamaño efectivo de muestra | **W05** |
| Correlación parcial y patrones de correlación | 3 | **No existe** | Correlación parcial | **W05** |
| Modelo multivariable | 3 | Existe: `multivariable_ols` | — | — |
| Sensibilidad | 3 | **No existe** como función; es repetir el análisis variando base y período | Lo resuelve el orquestador | Equipo (EMA-17) |
| Comparación pre/post | 2 | **No existe** | Diferencia entre ventanas | **W14** |
| Índices ETCCDI (RX1day, RX5day, R95pTOT, SDII, CDD) | 2 | **No existe** | Índices de extremos | **W10** |
| dNBR / RdNBR y trayectorias de recuperación | 2 | **No existe** | Índices de quema y tiempo de recuperación | **W14** |
| ΔLST pareado urbano-rural | 2 | **No existe** | Diferencia pareada (con W11 para el intervalo) | **W11** |
| Matriz de transición de cobertura | 2 | **No existe** | Matriz y áreas por transición | **W15** |
| Control de autocorrelación | 1 | Parcial: `modified_mann_kendall` (opcional) | Ver Mann-Kendall | Equipo (D-06) |
| Bootstrap espacio-temporal | 1 | **No existe** | Bootstrap por bloques | **W11** |
| Z-score robusto y hotspots persistentes | 1 (+1) | **No existe** | Z robusto (en W01) y persistencia (en W04) | **W01, W04** |
| Mediana | 1 | Trivial con NumPy | — | — |
| Tiempo de recuperación a banda de referencia | 1 | **No existe** | Con W14 | **W14** |
| Validación fuera de muestra | 1 | Parcial: un único holdout dentro de `forecast` | Backtesting con origen móvil | **W08** |
| Ecuación hipsométrica | 1 | **No existe** | Fórmula física | **W16** |
| FWI | 1 | **No existe** | FFMC, DMC, DC, ISI, BUI, FWI diarios | **W12** |
| Composites / estudio de eventos | 1 | **No existe** | Promedio de la respuesta alrededor de eventos (usa W04) | **W04** |
| Contrastes apareados | 1 | **No existe** | Con W11 | **W11** |
| Comparaciones longitudinales con IC | 1 | **No existe** | Con W11 | **W11** |
| Interacción elevación-tiempo | 1 | Existe vía `multivariable_ols` | Construcción del término de interacción | Equipo |
| Unión espacial y área geodésica | 1 | **No existe** | Área por píxel y estadística zonal | Equipo (EZE-13) |
| Balance hídrico | 1 | **No existe** | Requiere parámetros de suelo que no hay | Fuera de alcance v1 |
| Índices de bloqueo atmosférico | 1 | **No existe** | — | Fuera de alcance v1 |
| Extremos y trayectorias de ciclones | 1 | **No existe** | — | Fuera de alcance v1 |
| Detección de cambios SAR | 1 | **No existe** | — | Fuera de alcance v1 |
| Interferometría diferencial | 1 | **No existe** | — | Fuera de alcance v1 |
| Modelo de susceptibilidad a deslizamientos | 1 | **No existe** | Requiere inventario local | Fuera de alcance v1 |

Métodos que aparecen en otras hojas sin estar asignados a un fenómeno:

| Método | Hoja | En el código | Cola |
|---|---|---|---|
| FDR de Benjamini-Hochberg | QA (Q04) | **No existe** | **W06** |
| Walk-forward / rolling-origin | Modelos (PRED-01, 03), QA (Q15) | **No existe** | **W08** |
| Baseline de climatología y persistencia | Modelos (las 8 líneas) | **No existe** (hay naive y naive estacional) | **W07** |
| Intervalos predictivos con cobertura | QA (Q16) | **No existe** | **W09** |
| Brier, CRPS, calibración | Modelos (PRED-01, 05) | **No existe** | **W13** |
| SARIMA, ETS | Modelos | Existe (`sarima`, `holt_winters`; opcionales) | — |
| Ridge / ElasticNet autorregresivo con predictores | Modelos (PRED-02) | Parcial: `ridge` es polinómico de una variable | Decisión D-23 |
| Zero-inflated / hurdle | Modelos (PRED-06) | **No existe** | Fuera de alcance v1 |

## 3. Reglas de calidad (Q01–Q18)

Ninguna existe como control explícito. Hay piezas sueltas: `evidence.py` cuenta valores válidos, los conectores convierten centinelas a nulos, FIRMS aclara que un foco no es área quemada.

| Control | Dónde iría | Depende de | Responsable |
|---|---|---|---|
| Q01 cobertura · Q05 precipitación · Q06 QA óptico · Q07 sensor térmico · Q08 área quemada · Q09 espacial · Q10 temporal · Q11 unidades y datum · Q18 validación espacial | Preparación de datos | Conectores y agregación | Equipo (Eze) |
| Q02 climatología | Motor + validador | **W01** | Codex + Ema |
| Q03 tendencia y significación | Validador | **W02** | Codex + Ema |
| Q04 pruebas múltiples | Validador | **W05, W06** | Codex + Ema |
| Q15 sin fuga | Backtesting | **W03, W08** | Codex + Ema |
| Q16 incertidumbre predictiva | Intervalos | **W08, W09** | Codex + Ema |
| Q12, Q13, Q14, Q17 | Construcción de hallazgos | Orquestador | Equipo (Ema) |

## 4. Líneas predictivas

| Línea | Método de la planilla | Funciones que faltan | Datos |
|---|---|---|---|
| PRED-01 Precipitación y déficit | SARIMA + climatología; ridge con ENSO | W03, W07, W08, W09, W13 | Disponibles |
| PRED-02 NDVI | Ridge autorregresivo + estacionalidad | W07, W08, W09 + D-23 | **Faltan** (AppEEARS) |
| PRED-03 T2m mensual | SARIMA / ETS | W07, W08, W09 | Disponibles |
| PRED-04 LST | Autorregresivo estacional | W07, W08, W09 | **Faltan** |
| PRED-05 Peligro de fuego | FWI + pronóstico meteorológico | W12, W13 | Faltan variables diarias y pronóstico |
| PRED-06 Área quemada | Baseline estacional + conteo | W07 | **Faltan** |
| PRED-07 Nivel de agua | AR + precipitación | — | En conflicto con el catálogo (D-12) |
| PRED-08 SST y clorofila | SARIMA; ridge | — | En conflicto con el catálogo (D-12) |

## 5. Lo que falta fuera del motor matemático

No lo resuelve Codex dentro de `models/`; son tareas del backlog del equipo.

| Brecha | Efecto | Tarea |
|---|---|---|
| El motor no está conectado a la aplicación | Nada de lo anterior llega al usuario | EMA-05 a EMA-11 |
| El catálogo de 73 fenómenos no está en el código | No hay relación fenómeno → método | EMA-03 |
| AppEEARS no devuelve series | NDVI, LST, ET real, área quemada y cobertura inaccesibles: 7 de los 13 fenómenos MVP | EZE-12, EZE-13 |
| Conversión de unidades (`PRECTOTCORR` en mm/día, presión en kPa) | SPI y totales incorrectos si se usa NASA POWER sin convertir | EZE-07 |
| Agregación temporal con control de faltantes | Sin acumulados mensuales confiables | EZE-08 |
| Selección de estaciones por cobertura | Series pobres elegidas por cercanía | EZE-06 |
| Humedad relativa y viento diarios; pronóstico meteorológico | FWI y PRED-05 bloqueados | EZE-21 |

## 6. Orden de construcción

Por cantidad de fenómenos que destraba y por dependencias entre funciones:

1. **W01** climatología y anomalías — base de 14 fenómenos y de W03, W04.
2. **W02** IC de Sen — cierra la tendencia de N1.1.0 (recorrido 1).
3. **W06** FDR — pequeña e independiente.
4. **W05** correlación con desfases y parcial.
5. **W04** percentiles y eventos.
6. **W03** SPI.
7. **W07** baselines → **W08** backtesting → **W09** intervalos.
8. **W10** ETCCDI · **W11** bootstrap · **W13** métricas probabilísticas.
9. **W12** FWI.
10. **W14** dNBR y recuperación · **W15** matriz de transición · **W16** hipsométrica.

Con 1–6 quedan cubiertos los métodos de 8 de los 13 fenómenos MVP (N1.1.0, N1.2.0, N1.2C, N1.3.0, N1.3B, N1.1D, B2.2, B3.5). Los otros 5 (N1.4.0, N1.4C, B9.1, B9.3, B9.4) dependen además de conteos por sensor, de área quemada o de W14. Que el método exista no alcanza: 7 de los 13 necesitan también los datos de AppEEARS (§5).

## 7. Valores que la investigación no fija

Ningún documento disponible da estos números (falta `ANEXO_MATEMATICO.md`). Las funciones **no deben traerlos como valor por defecto**: se reciben como parámetro obligatorio.

- Años mínimos de la base climatológica.
- Años mínimos para informar una tendencia.
- Desfases por fenómeno.
- Duración mínima de un evento (salvo donde el fenómeno la define).
- Historia mínima de entrenamiento, número de orígenes de backtest y tolerancia de cobertura.

Lo que **sí** está documentado y puede usarse: cobertura mínima 0.8 (Q01), base 1991–2020 si se cubre (Q02), aviso con menos de 20 años para SPI (Q05), IC del 95% para tendencias, intervalo predictivo del 90%, SPI ≤ −1 y ≥ 1 como umbrales de déficit y exceso, escalas de SPI 1/3/6/12.
