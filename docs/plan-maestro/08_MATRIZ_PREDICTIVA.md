# 08 — Matriz predictiva

Fuentes: hoja `Modelos_Predictivos` de la planilla, `SUPERPROMPT_MAESTRO.md` (tratado como referencia científica, no como orden de implementación), `CATALOGO_V9_73.json` y código auditado.

## 1. Estado real

**No existe ningún modelo predictivo ambiental en el repositorio.** Lo que existe:

| Existe | No existe |
|---|---|
| `forecast` con `naive`, `seasonal_naive`, `holt_winters`, `arima`, `sarima` (`M/optional_methods.py:178`); los tres últimos requieren `statsmodels` (opcional) | Baseline climatológico |
| Un holdout cronológico único con comparación contra naive y error por horizonte | Backtesting rolling-origin / walk-forward |
| `ridge`, `multivariable` (bases para modelos con predictores) | Intervalos predictivos (`uncertainty: 'not_estimated'`) |
| | Modelos entrenados, persistidos o registrados |
| | SPI, FWI, balance hídrico, modelos de probabilidad de fuego |
| | **Conector de pronóstico meteorológico o de reforecasts archivados** |
| | Matriz numérica de mínimos históricos y horizontes (`ANEXO_MATEMATICO.md` falta) |

Consecuencia: **todos los horizontes de la planilla son horizontes de prueba propuestos, no validados.** Hasta que exista evidencia de backtesting, el sistema solo puede emitir `exploratory_extrapolation` o baselines rotulados.

## 2. Vocabulario unificado (propuesta para resolver C01 y C02)

| Concepto | Valores | Dónde vive |
|---|---|---|
| **Aptitud del fenómeno** (catálogo, no se altera) | `historical_only`, `direct_forecast`, `derived_from_forecast`, `conditional_scenario` | `phenomena.json: prediction.catalog_mode` |
| **Modo pedido** | `auto`, `forecast`, `scenario`, `extrapolation` | `AnalysisRequest.forecast.mode` |
| **Modo efectivo del resultado** | `validated_forecast`, `conditional_scenario`, `exploratory_extrapolation` | `ForecastBlock.mode` |
| **Estados de no disponibilidad** | `UNSUPPORTED`, `NOT_AUTOMATABLE`, `MODEL_NOT_ELIGIBLE`, `INSUFFICIENT_DATA` | Códigos de error |
| **Familias de modelo** | `M0, M1, M2, M3, M4, M5, M6A, M6B, F1, F5` (los del catálogo); F2, F3, F4 del superprompt son **alias** de M5, M6A, M6B | `models.json: family` |

`UNAVAILABLE` y `EXPERIMENTAL` del superprompt se expresan como `MODEL_NOT_ELIGIBLE` y `exploratory_extrapolation` respectivamente.

---

## 3. Las ocho líneas PRED

Columnas "planilla": texto de la hoja `Modelos_Predictivos`. Columnas "evaluación": análisis de este plan.

### PRED-01 — Precipitación mensual y déficit

| | |
|---|---|
| **Objetivo (planilla)** | Precipitación acumulada del mes t+h (mm) y P[SPI ≤ −1] |
| **Unidad temporal / horizonte de prueba** | Mes / 1–3 meses |
| **Modelo y baseline (planilla)** | SARIMA estacional y climatología como base; opcional ridge con ENSO rezagado |
| **Predictores en t0** | Precipitación hasta la emisión, mes, ENSO disponible; pronóstico externo solo si existe |
| **Métricas** | MAE, CRPS/intervalos; Brier para déficit; skill vs climatología |
| **Validación** | Walk-forward sin partición aleatoria; ajustar SPI **solo** en entrenamiento |
| **Restricción científica** | No pronosticar SPI con lluvia futura observada |
| **Familias / dependencias** | M1 (lluvia) → M0 (SPI) |
| **Datos disponibles hoy** | Precipitación mensual: POWER (1981→, con conversión), Open-Meteo/ERA5 (1940→, agregando diarios), NOAA; ONI. Historia larga: **sí** |
| **Algoritmos existentes / faltantes** | `sarima`, `ridge` / climatología (N09), SPI (N03), backtesting (N07), intervalos (N08), Brier (N13) |
| **Contradicción** | C07: el superprompt propone modelo en dos etapas (logística + Gamma/Tweedie). C08: el superprompt condiciona 1–3 meses a reforecasts con skill |
| **Evaluación** | Viable como experimento. La predictibilidad de la precipitación mensual a 1–3 meses con modelos estadísticos suele ser baja: es **probable que no supere a la climatología**, y en ese caso se muestra la climatología con la bandera correspondiente (T11). Se empieza con la propuesta de la planilla (SARIMA vs climatología) por ser la que ya tiene método implementado |
| **Estado** | Especificado |
| **Prioridad / ola** | MVP / O5 (segunda línea) |

### PRED-02 — NDVI y vigor vegetal

| | |
|---|---|
| **Objetivo** | NDVI mediano del área en t+h con intervalo; p(anomalía < P20) |
| **Unidad / horizonte de prueba** | 16 días o mes / 1 período – 2 meses |
| **Modelo y baseline** | Ridge/ElasticNet autorregresivo + estacionalidad; baseline climatología |
| **Predictores** | NDVI anterior, precipitación acumulada anterior, T2m anterior, humedad del suelo anterior |
| **Métricas** | MAE, RMSE, cobertura del intervalo, Brier |
| **Validación** | Espacio-temporal; enmascarar píxeles agrícolas en cosecha |
| **Restricción** | No incluir lluvia ni humedad futuras reales |
| **Familias / dependencias** | M3 ← M1 + M2 |
| **Datos disponibles hoy** | NDVI: **no** (AppEEARS sin procesador). Predictores meteorológicos: sí |
| **Algoritmos** | `ridge` (API de monomios, no admite matriz de predictores) → usar `multivariable` con diseño de rezagos y armónicos, o ridge multivariable nuevo (decisión D-23) / N07, N08, N09 |
| **Evaluación** | Bloqueada por datos hasta EZE-12. El diseño con predictores **rezagados** evita depender de pronósticos meteorológicos |
| **Estado** | Especificado |
| **Prioridad / ola** | MVP / O5 (tercera línea, tras EZE-12) |

### PRED-03 — Temperatura del aire mensual

| | |
|---|---|
| **Objetivo** | T2m media en t+h (°C) con intervalo |
| **Unidad / horizonte de prueba** | Mes / 1–3 meses |
| **Modelo y baseline** | SARIMA/ETS; regresión dinámica si mejora al baseline |
| **Predictores** | T2m rezagada, estacionalidad, forzantes conocidos |
| **Métricas** | MAE, RMSE, skill climatológico, cobertura del intervalo |
| **Validación** | Rolling-origin y prueba final fija; revisar cambio de régimen |
| **Restricción** | Una tendencia lineal no es pronóstico fiable indefinido |
| **Familias / dependencias** | M1; sin dependencias aguas arriba |
| **Datos disponibles hoy** | **Sí**: POWER T2M mensual desde 1981 |
| **Algoritmos** | `sarima`, `holt_winters`, `seasonal_naive` / N07, N08, N09 |
| **Contradicción** | C07: el superprompt propone ARX regularizado; restricción adicional Tmin ≤ Tmedia ≤ Tmax |
| **Evaluación** | **Primera línea a implementar** (recorrido 3): única con datos, método y ausencia de dependencias ya resueltos |
| **Estado** | Especificado |
| **Prioridad / ola** | MVP / O5 (primera línea) |

### PRED-04 — Temperatura superficial terrestre

| | |
|---|---|
| **Objetivo** | Anomalía de LST futura (°C) |
| **Unidad / horizonte de prueba** | Mes u 8 días / 1–2 períodos |
| **Modelo y baseline** | Autorregresivo estacional |
| **Predictores** | LST observado sin nubes, estacionalidad, NDVI pasado |
| **Métricas** | MAE, % cobertura QA, intervalos |
| **Validación** | Partir por fecha y sensor; reportar huecos |
| **Restricción** | LST no predice temperatura del aire |
| **Familias / dependencias** | M4 ← M1 + M2 + M3 |
| **Datos disponibles hoy** | **No** (AppEEARS) |
| **Evaluación** | Tras EZE-12. Los huecos por nubes rompen la regularidad que exigen SARIMA/ETS: hay que definir la política de huecos antes |
| **Estado / prioridad / ola** | Especificado / P2 / O6 |

### PRED-05 — Peligro meteorológico de fuego

| | |
|---|---|
| **Objetivo** | Probabilidad calibrada de condiciones meteorológicas favorables al fuego, **no** ignición exacta |
| **Unidad / horizonte de prueba** | Día / 1–7 días |
| **Modelo y baseline** | FWI con pronóstico meteorológico; modelo calibrado si hay inventario etiquetado |
| **Predictores** | Pronóstico disponible en la emisión (HR, viento, T, P); combustible |
| **Métricas** | Brier, calibración, PR-AUC, skill vs persistencia |
| **Validación** | Backtest con **pronósticos archivados**; control de sesgo espacial |
| **Restricción** | No prometer detección ni predicción de un foco específico |
| **Familias / dependencias** | M5 ← M1 (diario); M6A ← M5 + M2 + M3 + F1 |
| **Datos disponibles hoy** | T y P diarias: sí. **Humedad relativa y viento diarios: no** (Open-Meteo expone 8 variables fijas; POWER es mensual). **Pronósticos y pronósticos archivados: no hay conector** |
| **Algoritmos** | — / FWI (N12), métricas probabilísticas (N13) |
| **Evaluación** | En dos etapas. **(a) FWI histórico diario** como indicador de peligro meteorológico observado: viable al ampliar variables diarias. **(b) Pronóstico**: requiere un conector de pronóstico (D-19). Sin pronósticos archivados solo es posible un `perfect_forcing_hindcast`, que **no valida uso operacional** |
| **Estado / prioridad / ola** | Especificado / P2 / O6 (etapa a) |

### PRED-06 — Área quemada regional

| | |
|---|---|
| **Objetivo** | Área quemada mensual regional (ha) como **escenario exploratorio** |
| **Unidad / horizonte de prueba** | Mes / 1 mes |
| **Modelo y baseline** | Baseline estacional + modelo de conteo/zero-inflated solo si hay suficiente historia |
| **Predictores** | Área quemada histórica, pronósticos meteorológicos disponibles |
| **Métricas** | MAE, intervalos, precisión espacial contextual |
| **Validación** | Años fuera de muestra, clase cero y fallos del detector |
| **Restricción** | No proyectar un perímetro exacto ni incendios futuros |
| **Familias / dependencias** | M6B ← M6A / F1 + combustible + meteorología |
| **Datos disponibles hoy** | **No** (MCD64A1 vía AppEEARS sin procesador de área) |
| **Contradicción** | C06: P3 y exploratorio aquí; N1.4C es MVP con modo `direct_forecast`. C07: zero-inflated vs hurdle |
| **Evaluación** | La parte MVP de N1.4C es el **mapa y la serie históricos**; la predicción queda en baseline estacional rotulado como escenario exploratorio |
| **Estado / prioridad / ola** | Especificado / P3 / O7 |

### PRED-07 — Nivel de agua

| | |
|---|---|
| **Objetivo** | WSE de la próxima observación o nivel de estación (m) |
| **Unidad / horizonte de prueba** | Diaria o por pasada / días–semanas |
| **Modelo y baseline** | AR + precipitación de cuenca; balance si hay caudal |
| **Métricas** | MAE, cobertura del intervalo, skill vs persistencia |
| **Validación** | Datum fijo, retardos correctos; datos irregulares de SWOT |
| **Restricción** | No extrapolar a 20 años de SWOT |
| **Datos disponibles hoy** | INA (altura hidrométrica, series largas): sí. SWOT: desde 2022, irregular; `dschg_c` sin valores válidos |
| **Contradicción** | **C04**: el catálogo declara N1.9.0, N1.9A y B3.4 `historical_only`, sin familia, y el superprompt no define modelo hidrológico |
| **Evaluación** | **No se implementa hasta resolver C04 (D-12).** Si se aprueba, solo con series de estación INA y baseline de persistencia; nunca sobre SWOT solo |
| **Estado / prioridad / ola** | Especificado, en conflicto / P3 / O7 |

### PRED-08 — SST y clorofila

| | |
|---|---|
| **Objetivo** | SST futura; clorofila futura por separado |
| **Unidad / horizonte de prueba** | Semanal / 1–4 semanas |
| **Modelo y baseline** | SARIMA para SST; ridge con viento y SST pasada para clorofila |
| **Métricas** | MAE por variable; skill climatológico; incertidumbre |
| **Validación** | Backtest por tiempo y bandas costeras; cobertura nubosa |
| **Restricción** | No pronosticar floraciones tóxicas desde clorofila |
| **Datos disponibles hoy** | SST: OISST diaria (sí). Clorofila: **no** |
| **Contradicción** | **C05**: N1.1.1 es `historical_only`; ningún modelo M cubre SST ni clorofila |
| **Evaluación** | Solo la mitad de SST es viable técnicamente (SARIMA semanal sobre OISST). Sujeto a D-12 |
| **Estado / prioridad / ola** | Especificado, en conflicto / P3 / O7 |

### Resumen

| Línea | Datos hoy | Método base existe | Bloqueo principal | Orden |
|---|---|---|---|---|
| PRED-03 T2m | Sí | Sí (`sarima`, `holt_winters`) | N07–N09 | **1** |
| PRED-01 Precipitación | Sí | Sí | N03, N07–N09, N13 | **2** |
| PRED-02 NDVI | No | Parcial | EZE-12 | **3** |
| PRED-04 LST | No | Sí | EZE-12; política de huecos | 4 |
| PRED-05 Fuego | Parcial | No | N12; variables diarias; conector de pronóstico | 5 |
| PRED-08 SST | Sí (SST) | Sí | D-12 | — |
| PRED-07 Nivel | Sí (INA) | Sí | D-12 | — |
| PRED-06 Área quemada | No | No | EZE-13; D-12 | — |

---

## 4. Familias M0–M6 y componentes F1, F5

### Dependencias (del superprompt, texto fiel)

"M0 depende de M1 y climatologías; M2 depende de M1; M3 depende de M1+M2; M4 depende de M1+M2+M3; F2 depende de M1; F3 depende de F2+M2+M3+F1 histórico; F4 depende de F3/F1 histórico+combustible/meteorología; F5 depende de M3+historia de área quemada. M3/M4 no requieren ejecutar F2/F4." No hay realimentación fuego → clima.

| Familia | Contenido | Depende de | Método de referencia (superprompt) | Línea PRED | Estado real | Qué falta |
|---|---|---|---|---|---|---|
| **M1A** Temperatura | T2m mensual (máx, mín, media) | — | ARX/AR regularizado estacional; restricción Tmín ≤ Tmedia ≤ Tmáx | PRED-03 | Sin modelo | N07–N09; decisión de método (D-23) |
| **M1B** Lluvia | Precipitación | — | Dos etapas (ocurrencia + monto); mensual Gamma/Tweedie o climatología | PRED-01 | Sin modelo | Ídem |
| **M0** Indicadores | Anomalías, déficit, exceso, SPI | M1 + climatologías | SPI calibrado por mes y escala solo en entrenamiento; para escala 12, 11 meses observados + 1 pronosticado | PRED-01 | Sin implementar | N01, N03 |
| **M2** Estado hídrico | Humedad de suelo, almacenamiento, balance | M1 | Balance de almacenamiento con capas; sin parámetros de suelo → modelo estadístico, **no** presentarlo como balance físico | — | Sin implementar | Parámetros de suelo inexistentes → vía estadística |
| **M3** Vegetación | NDVI, EVI, fenología, recuperación | M1 + M2 | Autorregresivo con rezagos + meteorología + humedad; forzantes de t para t+1 | PRED-02 | Sin modelo | Datos NDVI |
| **M4** LST | Temperatura superficial | M1 + M2 + M3 | Regresión dinámica; día y noche; QA | PRED-04 | Sin modelo | Datos LST |
| **M5** FWI | FFMC, DMC, DC, ISI, BUI, FWI | M1 diario | Algoritmo oficial diario con adaptación al hemisferio sur; **no** FWI mensual desde meteorología mensual; guardar estado y spin-up | PRED-05 | Sin implementar | N12; variables diarias |
| **M6A** Actividad de fuego | Probabilidad de evento definido | M5 + M2 + M3 + F1 | Logística regularizada; calibración en validación anidada; comparar climatología, FWI solo y FWI+ | PRED-05 | Sin implementar | Todo lo anterior + etiquetado con máscara de observabilidad |
| **M6B** Área quemada | Ocurrencia de área positiva y magnitud | M6A / F1 | Modelo hurdle (ocurrencia + Gamma o lognormal), regional y mensual; sin perímetros | PRED-06 | Sin implementar | Datos de área |
| **F1** Histórico de fuego | Detecciones, FRP y área quemada en capas separadas | — | Capas separadas | — | Parcial (FIRMS como serie) | Separación por sensor; área quemada |
| **F5** Recuperación | Recuperación espectral | M3 + área quemada | Reutiliza M3 con tiempo desde el incendio, fracción quemada y dNBR | — | Sin implementar | N14; datos |

### Orden de construcción recomendado

1. Infraestructura predictiva común: N09 baselines → N07 backtesting → N08 intervalos → `ModelRegistry` y puerta de elegibilidad.
2. M1A (PRED-03).
3. M1B + M0 (PRED-01).
4. M3 reducido (PRED-02), con M2 en su versión estadística.
5. M5 histórico.
6. M4, M6A, M6B, F5: solo tras evidencia de las anteriores.

---

## 5. Registro de elegibilidad

Estructura en `03_ALGORITHM_HANDLER.md` §8 (`ModelDescriptor.horizons[]`). La elegibilidad depende de **modelo × variable × ubicación o región × frecuencia × estación del año × horizonte × versión**. No hay una tolerancia temporal universal.

### Valores iniciales

Los documentos disponibles aportan solo estos puntos de partida; todos quedan marcados `status: "proposed"` en `models.json` hasta contar con backtesting:

| Elemento | Punto de partida documentado | Origen |
|---|---|---|
| Horizontes de prueba | Los de cada línea PRED (p. ej. 1–3 meses para T2m y precipitación) | Planilla |
| Base de SPI | < 20 años → baja robustez o no habilitar | Q05 |
| Climatología | 1991–2020 si se cubre | Q02 |
| Nivel del intervalo | 90% por defecto; 95% solo con cobertura verificada | Superprompt |
| Historia mínima de entrenamiento por modelo | **No documentada** | Falta `ANEXO_MATEMATICO.md` → D-03 |
| Número mínimo de orígenes de backtest | **No documentado** | D-21 |
| Tolerancia de cobertura del intervalo | **No documentada** | D-21 |

### Decisión con pocos datos

| Condición | Acción |
|---|---|
| Historia insuficiente para ajustar el modelo | Solo análisis descriptivo; se informa cuánto falta |
| Alcanza para baseline pero no para el modelo | Baseline rotulado (`exploratory_extrapolation`) |
| Backtest válido solo hasta un horizonte menor | Se reduce el horizonte a lo validado |
| El modelo no supera al baseline | Se muestra el baseline con `not_superior_to_baseline` |
| Faltan predictores futuros legítimos | Escenario condicional si el usuario aporta supuestos; si no, modelo reducido |
| Hay una fuente alternativa con más historia | Se sugiere (`suggestions[]`) |
| Nada de lo anterior | `MODEL_NOT_ELIGIBLE` |

---

## 6. Validación fuera de muestra

Distinta de los benchmarks de rendimiento: mide **capacidad predictiva**, no velocidad.

| Requisito | Implementación |
|---|---|
| Sin partición aleatoria | Rolling-origin con ventana expansiva; orígenes equiespaciados |
| Sin fuga | Climatologías, parámetros de SPI y escalados se ajustan **dentro de cada pliegue**, solo con datos anteriores al origen (Q15) |
| Fechas de disponibilidad | Cada predictor lleva `available_at`; se descarta si es posterior al origen (T10) |
| Bloque final ciego | El último tramo se reserva para la decisión de habilitación |
| Baselines | Climatología mensual y persistencia siempre; año análogo y naive estacional según la línea |
| Métricas continuas | MAE, RMSE, sesgo, skill = 1 − error_modelo / error_baseline, cobertura empírica del intervalo |
| Métricas de eventos | Brier, Brier skill score (solo si la referencia es > 0), fiabilidad |
| Pronósticos externos | Solo los emitidos antes del origen; si no existen, `perfect_forcing_hindcast` en un registro **separado** que no habilita `validated_forecast` |
| Evidencia | `backtest_id` con configuración, pliegues, métricas por horizonte y huella de los datos |

### Criterios para `validated_forecast` (los siete del superprompt)

Sin fugas · muestra suficiente · skill sobre el baseline en el bloque de prueba · calibración · estabilidad entre pliegues · rendimiento medido · semántica correcta en la respuesta. **Si falla uno, no se marca como validado.**

---

## 7. Incertidumbre

| Qué se expresa | Cómo | Regla |
|---|---|---|
| Estimación central | `central[]` con `central_kind` | |
| Intervalo predictivo | Cuantiles derivados de residuales fuera de muestra por horizonte | Se informa nivel nominal **y** cobertura empírica |
| Cuantiles | `quantiles` | Solo si provienen de un método que los respalda |
| Probabilidad de evento | `event.probability` con `definition` explícita | Solo para eventos definidos; `calibrated: true` solo con evidencia. **No se inventan probabilidades para variables continuas** |
| Limitaciones del modelo | `limitations[]` del `ModelDescriptor` | |
| Sensibilidad a supuestos | En escenarios: una trayectoria por conjunto de supuestos | |
| Comparación con referencias | `baseline` y `skill_vs_baseline` siempre presentes | |
| Sin calibración posible | `interval: null` y texto "sin intervalo calibrado" | Nunca un "% de confianza" inventado |

**Intervalo de confianza ≠ intervalo predictivo** (glosario): el primero describe la incertidumbre de un parámetro estimado (p. ej. la pendiente de Sen) y usa `uncertainty.confidence_level`; el segundo describe valores futuros y usa `uncertainty.interval_level`. Son campos, leyendas y colores distintos en toda la aplicación.

---

## 8. Predicción encadenada y propagación

Ejemplo: pronóstico meteorológico → estado hídrico → vegetación → indicadores de fuego.

| Problema | Diseño |
|---|---|
| Romper covarianzas al muestrear cada variable por separado | Los miembros del ensemble se generan **conjuntamente** aguas arriba y se identifican con `member_id`; los modelos aguas abajo consumen el mismo `member_id` |
| Cómo generar miembros conjuntos sin pronóstico numérico | Remuestreo por bloques de residuales conjuntos o años análogos completos (preserva la relación T–P). Queda como diseño; se implementa recién con M3 |
| Trazabilidad | `inputs_from_models[]` en cada `ForecastBlock`; el DAG muestra las aristas entre nodos `predict` |
| Horizonte efectivo | El horizonte validado de una cadena es el **mínimo** de los horizontes validados de sus eslabones |
| Propagación no implementada | `uncertainty_propagation: "not_propagated"` y advertencia explícita |
| Coherencia temporal | Todos los eslabones comparten `issue_time` |

---

## 9. Plan de integración por línea

| Paso | PRED-03 (recorrido 3) | Responsable |
|---|---|---|
| 1 | `ModelDescriptor` `pred03.t2m_monthly.sarima` + baselines en `models.json` | Ema (EMA-18) |
| 2 | Baselines y backtesting | Ema (EMA-19) |
| 3 | Intervalos y cobertura | Ema (EMA-20) |
| 4 | Receta `R-FORECAST` y nodos `eligibility → backtest → fit → predict → intervals` | Ema (EMA-21) |
| 5 | Caché de ajustes y backtests | Eze (EZE-04) |
| 6 | `ForecastBlock` y `VizHint: forecast_fan` | Ema (EMA-21) |
| 7 | Gráfico de abanico con etiqueta de modo y baseline | Juan (JUAN-06) |
| 8 | Controles de horizonte y modo en el configurador | José (JOSE-05) |
| 9 | Explicación con modo, skill y limitaciones | JP (JP-05) |
| 10 | Pruebas T10 y T11 | Ema + Eze |

PRED-01 repite los pasos agregando SPI calibrado dentro de cada pliegue; PRED-02 agrega predictores rezagados y depende de EZE-12.
