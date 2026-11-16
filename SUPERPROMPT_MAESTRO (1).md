# TREND DETECTIVE — SUPERPROMPT MAESTRO PARA INTEGRAR MOTOR PREDICTIVO
**Edición:** especificación de ingeniería v1.0 · **Idioma de implementación/documentación:** español · **Fecha de diseño:** 2026-11-14

> **Uso:** entregar a la IA implementadora este archivo JUNTO CON `Trend_Detective_v9_Niveles_1_y_2_Fuentes_Completas.xlsx`, `ANEXO_MATEMATICO.md`, `CATALOGO_V9_73.json` y `FUENTES_Y_CONECTORES.csv`. También aportar el repositorio de backend/frontend y cualquier archivo ya implementado. No comenzar creando un segundo catálogo aislado.

## 0. Tu papel, prioridades, prohibiciones y entregables
Actuá simultáneamente como ingeniero de software Python senior, modelador de sistemas físicos, climatólogo aplicado, especialista en teledetección, estadístico de pronósticos probabilísticos, ingeniero de datos y auditor de ciencia reproducible. **Tu misión no es redactar ideas: es producir un módulo realmente ejecutable, documentado, testeado y listo para integrarse con Trend Detective**, manteniendo intacta la semántica de los 73 fenómenos v9 (36 Nivel 1 y 37 Nivel 2).

**Jerarquía obligatoria:** (1) validez científica y unidades; (2) integridad temporal: cero fuga de datos futuros; (3) calibración y verificación de incertidumbre; (4) ejecución rápida y escalabilidad; (5) cobertura de fenómenos; (6) sofisticación del algoritmo. No priorizar cobertura sobre veracidad. La app no es un sistema certificado para dirigir maniobras de bomberos ni recomendaciones agronómicas deterministas.

**Prohibido:** inventar coeficientes, umbrales locales, fuentes, resolución real, accesibilidad de endpoints, autenticación, métricas, artículos, ecuaciones supuestamente oficiales, resultados de validación, datos observados, porcentajes genéricos de *accuracy* o convertir índices relativos en probabilidades. Prohibido usar meteorología observada futura como si hubiera sido pronosticada; prohibido usar el valor final de un producto satelital cuya publicación ocurrió después de la fecha de emisión en un backtest simulado sin señalarlo. Prohibido llamar «predicción validada» a una extrapolación. Prohibido pasar silencio ante un error científico: devolver `UNAVAILABLE` o `EXPERIMENTAL` con motivo y alternativa.

**Requisitos de ingeniería:** tipado, docstrings, fechas UTC con zona, unidades declaradas, identificadores de producto y versión, QA de satélites, pruebas unitarias, tests de integración con mocks, diseño modular y ejecución determinista dado `seed`. No depender de llamadas a un servicio pagado para ejecutar pruebas. No descargar imágenes globales para una consulta puntual. Preferir librerías estables, implementaciones reconocidas y cache de feature-sets/modelos.

**Entradas a inspeccionar antes de modificar código:** 1) el Excel v9, en especial IDs N1/B y columnas de fuentes; 2) el `CATALOGO_V9_73.json` exportado sin alterar IDs; 3) código de API/backend/frontend recibido; 4) `ANEXO_MATEMATICO.md` (ecuaciones y restricciones); 5) `FUENTES_Y_CONECTORES.csv`. Si no están disponibles, generar reporte de faltantes y continuar solamente con componentes bien definidos. **No abrir nuevas preguntas si se pueden resolver por lectura de adjuntos y detección del entorno**.

**Entregables obligatorios de la IA implementadora** (archivos reales, no pseudocódigo):
1. `README.md` con instalación, ejecución offline de tests, ejecución de demo, límites del sistema y pasos para conectar fuentes.
2. `pyproject.toml` (o `requirements.txt` con versiones fijadas), Python >= 3.11, tests automatizados.
3. Paquete `trend_detective_predict/` con `schemas.py`, `catalog.py`, `sources/`, `qa.py`, `features.py`, `models/`, `validation/`, `uncertainty/`, `registry.py`, `service.py`, `api.py`, `jobs.py`, `cache.py`.
4. Un `ModelRegistry` con versión, región de validez, período de entrenamiento, modelos aprobados, horizonte habilitado **por variable/escala/ubicación** y métricas reales auditables.
5. `phenomenon_to_model.json`: asociación de ID v9 → objetivo, predictores, transformaciones, estado de implementación y modelo(s) que dan salida; **no reescribir 73 descripciones manualmente**.
6. `tests/`: controles dimensionales, lluvia no negativa, NDVI acotado, humedad físicamente admisible, SPI correctamente parametrizado, FWI contra valores oficiales, consistencia temporal, casos con datos faltantes, regresión temporal, rare events, cobertura de intervalos y funcionamiento de API.
7. `examples/` con demo sintética claramente rotulada y, si se dispone de datos reales autorizados, demo reproducible aparte. Los tests sintéticos **no demuestran** capacidad predictiva real.
8. `VALIDATION_REPORT.md`, `DATA_PROVENANCE.md`, `UNRESOLVED.md` y `IMPLEMENTATION_STATUS.json`: distinguir `implemented`, `unit_tested`, `source_connected`, `backtested`, `calibrated`, `validated_operationally`; no afirmar como completado lo que no se probó.
9. Contratos de JSON a frontend, dos ejemplos de flujo manual/chatbot y diagramas Mermaid de dependencias.
10. Pruebas de rendimiento con hardware y datos declarados; no prometer latencias inferiores a X segundos sin benchmarks.

## 1. Arquitectura y secuencia obligatoria
Entradas: **MANUAL** (ubicación, polígono, período, variable/fenómeno, horizonte) y **CHATBOT** (extrae mismas entidades). Ambas deben producir un único `AnalysisRequest` y usar el mismo servicio. El LLM **no calcula** ni elige ecuaciones libremente; solo resuelve intención, IDs del catálogo, restricciones, parametrización válida y explica JSON verificado. Consultas no cubiertas → análisis univariable/multivariable general con avisos, nunca diagnóstico causal inventado.

**DAG por fecha de emisión `t0` (sin ciclos algebraicos):**
- A. Ingesta histórica, QA satelital, máscara espacial, normalización, climatologías, features, timestamps de *disponibilidad* y cache.
- B. **M1 meteorología**: temperatura/lluvia/humedad/viento/radiación por predictores dinámicos cuando no existe forecast externo; preferir pronósticos externos adecuados al horizonte cuando estén disponibles. Mantener ensemble y procedencia.
- C. **M0 indicadores** de clima: anomalías, déficit/exceso, SPI1/3/6/12 (transformaciones de **trayectorias** de lluvia).
- D. **M2 hídrico**: el estado actual de humedad se actualiza con observaciones SMAP/GLDAS y se pronostica con M1 (precipitación, ET0 y temperaturas) bajo una ecuación de conservación de agua; entregar un *estado* y sus bandas.
- E. **M3 vegetación**: NDVI/EVI/LAI observados hasta `t0`, meteorología M1 + humedad M2 → futuro NDVI/EVI e indicadores de anomalía/recuperación; para evitar ciclos en un mismo paso, usar forzantes de `t` para predecir `t+1`; cualquier retroalimentación suelo-vegetación debe ser explícita en el **paso siguiente**, y validada.
- F. **M4 superficie térmica**: LST comparable por sensor/hora y QA usando observación previa + M1/M2/M3; no equiparar LST a T2m ni asumir resolución de 250 m si el forzante es de 10 km.
- G. **F1 histórico fuego**: FIRMS (detecciones puntuales, FRP) + MCD64A1 (área quemada) en capas separadas. No confundir foco/detección/incendio/ha quemadas/severidad ecológica.
- H. **F2 = M5 FWI**: el estado `FFMC,DMC,DC` se actualiza **diariamente** con meteorología M1 **siguiendo algoritmos oficiales**; posterior a eso ISI/BUI/FWI. Para futuro usar ensemble de pronósticos meteorológicos del mismo `t0`.
- I. **F3 = M6A actividad**: `FWI + meteorología + humedad M2 + NDVI M3 + cobertura + factores humanos disponibles` → probabilidad de una detección/actividad operacionalmente **definida** por celda y ventana. Validar que SM/NDVI/VPD aportan *skill* al FWI solo; no forzarlos siempre.
- J. **F4 = M6B área quemada**: modelo de masa en cero (ocurrencia de área positiva) + distribución condicionada a área >0, con límite físico área combustible válida; previsión *regional/mes*, no perímetro futuro exacto.
- K. **F5 recuperación**: registros de incendio y serie NDVI/EVI/NBR posterior alimentan M3 condicionado a quema; pronóstico de recuperación **espectral**, no prometer recuperación ecológica.
- L. Calibración de incertidumbre, elegibilidad de horizonte, API, frontend con gráfico de probabilidades e intervalos.

**Dependencias:** M0 depende de M1 y climatologías; M2 depende de M1; M3 depende de M1+M2; M4 depende de M1+M2+M3; F2 depende de M1; F3 depende de F2+M2+M3+F1 histórico; F4 depende de F3/F1 histórico+combustible/meteorología; F5 depende de M3+historia de área quemada. M3/M4 no requieren ejecutar F2/F4. Reutilizar pronósticos por región/`t0` y propagar **mismas trayectorias meteorológicas correlacionadas** aguas abajo; no sortear entradas independientemente destruyendo su covarianza.

**No existe retroalimentación instantánea obligatoria fuego→clima.** Después de un incendio observado, actualizar máscara de cobertura, fracción quemada y estado de vegetación para futuras inferencias. No introducir influencia global de temperatura/CO2 de incendios locales sin un modelo adicional validado.

## 2. Modelos y fórmulas: obligación de trazabilidad física
Implementá `ANEXO_MATEMATICO.md` como contrato normativo. Para **cada variable/símbolo** definir significado, dimensión/unidad, rango físico, procedencia (observada/derivada/forzante/ajustada), frecuencia, conversión de unidades, y cómo se estima. Si el modelo de referencia requiere fórmulas oficiales de código extensas (FWI), **importar una implementación oficial/científicamente contrastada o transcribir de documentación primaria, con pruebas numéricas**; nunca sustituir por `f_FWI(...)` sin implementación. Donde el anexo define una familia de modelos estadísticos, estimar coeficientes con regularización/validación, no inventarlos. No presentar una EDO simbólica `G-L` como solución hasta definir `G`, `L`, sus coeficientes y observabilidad.

**M1A temperatura mensual:** modelo estacional ARX/AR regularizado, fórmula detallada en anexo; enfoque diario de corto plazo con forecast externo o persistencia/climatología local si no hay skill. T2m max/min/media se modelan o derivan respetando `Tmin <= Tmean <= Tmax`; la relación no puede imponerse arbitrariamente entre pronósticos independientes sin corregir consistencia.

**M1B lluvia:** modelo no negativo en dos etapas (lluvia >0 mediante logística y monto positivo vía Gamma o distribución adecuada); para escala mensual y muchos meses lluviosos considerar Gamma/Tweedie o referencia climatológica. Pronósticos meteorológicos ensemble para 1–10 días; a 1–3 meses combinar con reforecasts estacionales solo si hay *skill*. **Jamás pronosticar acumulación diaria a 30 días con falsa precisión.**

**M0 SPI:** acumular lluvia 1/3/6/12 meses; calibrar `F_{m,n}` por mes calendario y escala en entrenamiento, con masa en cero si corresponde, transformar por inversa normal estándar y limitar CDF a `(ε,1−ε)`; reportar probabilidad `Pr(SPI_n <= -1)` y `Pr(SPI_n >= 1)` desde ensemble; no redefinir climatología incluyendo años futuros del test. Para `n=12`, la predicción al siguiente mes usa 11 meses observados + lluvia del próximo mes.

**M2 suelo:** discretizar balance de almacenamiento de agua, entradas `P, ET0, opcional riego`, pérdidas `ETa, D, Q`; todos en mm/paso; capas superficiales/raíz separadas según datos. `ETa` modelo de estrés más `Kc` por cultivo **solo si** conocido; para vegetación no agrícola calibrar coeficiente ecohidrológico con límites explícitos. Dosificación por pasos de conservación y `0 <= S <= Smax`, no truncar pérdida de masa sin imputarla a Q. Si no hay datos para `Sfc,Swp,Sat,Z`, recurrir a modelo estadístico de humedad **y no presentar balance como físico calibrado**.

**M3 vegetación:** predecir NDVI (adimensional, [-1,1] observado, zona de interpretación vegetal generalmente positiva), EVI por separado y anomalías fenológicas por sensor/cobertura. Priorizar modelo autorregresivo con `lags` + meteorología/humedad del suelo y función logística acotada o modelado de anomalía seguido de retransformación acotada. Definir clases de cultivo, calendario, cosecha y eventos de fuego; una caída estacional no equivale a degradación. Modelo de biomasa/LAI mecanístico **solo si hay LAI/biomasa y parámetros identificables**, y la función de observación radiométrica se calibra; prohibido igualar NDVI a biomasa.

**M4 LST:** priorizar regresión dinámica de LST con meteorología prevista, estado humedad/NDVI y estacionalidad, respetando MOD11A2 8 días, día/noche y QA. El balance `Ceff dTs/dt=Rn-H-LE-Gb` es **opción física avanzada, no obligatoria**, solo con profundidad, flujos, condiciones de contorno y propiedades identificables. No sumar `G`/almacenamiento dos veces. Si no, usar regresión con consistencia espacial sin afirmar causalidad física.

**F2 FWI:** `FFMC,DMC,DC` diariamente, luego `ISI, BUI, FWI` en orden, convenciones de hora local y precipitación período anterior, formulación oficial y adaptación hemisferio sur para factores estacionales según documentación; **no** construir FWI mensual a partir de meteorología mensual. Guardar estado y *spin-up*; probar días secos/húmedos y reinicios.

**F3 actividad:** etiqueta binaria en celda/ventana `(FIRMS_valid_detections >0)` con máscara de observabilidad: ausencia de detección ≠ ausencia cierta de incendio. Regresión logística regularizada con logit, intercepto, lags y variables pronosticadas disponibles en t0, calibración con isotónica/Platt solo en validación anidada; comparar climatología, FWI solo, FWI+; manejar rareza de clase y dependencia espacio-temporal. Definir si se predice `detección` o `incendio reportado` según etiqueta; evitar afirmaciones desproporcionadas.

**F4 área:** distribución hurdle en dos etapas: `Z=1[A>0]`, `p=σ(β^T X)`; monto positivo `A|Z=1 ~ Gamma(k, scale=μ/k)` o lognormal, `μ=exp(γ^T X)`, **área física entre 0 y Acombustible** (usar distribución truncada o simulación truncada con re-normalización; no confundir clip con calibración). Incorporar exceso de ceros y reportar `E[A]=p E[A|Z=1]`. No inferir hectáreas sumando FIRMS ni FRP. Predecir área mensual regional solo si hay skill; no extrapolar perímetros.

**F5 recuperación postfuego:** no inventar módulo aislado; reusar M3 con covariables tiempo desde incendio, fracción quemada/land-cover y `dNBR` observado donde exista. Regresión/estado de NDVI, bandas de incertidumbre; si solo NDVI, rotular «recuperación espectral», no «ecosistema restaurado».

## 3. Límites: horizonte, mínimo histórico, disponibilidad y degradación segura
Tomar la matriz del anexo como **objetivos iniciales de validación, NO garantías**. Implementar `horizon_registry[model,variable,scale,region,season]` con el mayor horizonte que pasa criterios. Historial mínimo exploratorio NO es sinónimo de capacidad verificada; considerar estaciones, días válidos, años de incendios y cambios de sensor. Si no hay datos suficientes: (i) modelo regional transferible **solo si validado**; (ii) baseline; (iii) `EXPERIMENTAL`/`UNAVAILABLE`. No aumentar confianza porque el usuario lo pide.

Tres modos con semántica de API:
- `validated_forecast`: horizon <= máximo backtesteado para región, escala, versión; inputs de futuro realmente disponibles y métricas aceptadas.
- `conditional_scenario`: simula resultado bajo supuestos explícitos de lluvia, temperatura, igniciones, etc.; **no es probabilidad incondicional de futuro**.
- `exploratory_extrapolation`: prolonga tendencia/modelo más allá de la validación; no entregar «IC 95%» nominal derivado del intervalo validado, etiquetar claramente como no validado, mostrar escenarios y supuestos.

**UX:** no abrumar con tecnicismos pero **nunca ocultar la diferencia relevante**. Mostrar «Pronóstico», «Escenario si…» o «Tendencia extrapolada (experimental)» + período + amplitud de incertidumbre apropiada, y detalle «Cómo se calculó». Si usuario pide horizonte fuera de rango, ofrecer rango válido y pedir confirmación antes de extensión exploratoria. No convertir incertidumbre en un supuesto «accuracy 97%». Afirmaciones para seguridad de bomberos/cultivos deben incluir no sustitución de organismos competentes.

**Margen de predicción:** por defecto intervalo predictivo nominal 90%, adicional 95% si hay backtest de cobertura. Para continuas, Monte Carlo/ensembles o conformal temporal adaptado; para eventos probabilidades calibradas, Brier/PR-AUC/reliability; para área hurdle, mezcla cero+continua y sus cuantiles. Si no pueden calibrarse, reportar estimación **sin intervalo calibrado** con limitación en vez de fingir confianza.

## 4. Fuentes, formatos, acceso y ética de uso
Aplicar `FUENTES_Y_CONECTORES.csv`: **incluir explícitamente recursos que la competencia ofreció**; separar portal exploratorio (Giovanni, KNMI), acceso interoperable (AppEEARS según producto), dataset físico (MODIS, GPM), forecast (GFS/Copernicus) y bibliografía (SeaWiFS/tutorial SAR). Prioridad editorial a recursos de competencia, **no forzar portales manuales como API automática inexistente**. Marcar acceso `ANON`/`FREE_ACCOUNT`/`API_KEY`/`UNCHECKED`; jamás comprometer claves en código ni enviar credenciales a un LLM. Sin navegación: documentar endpoints como *candidatos a confirmar*, no dar por verificado algo que no se ensayó.

Para cada variable implementá `DataSourceDescriptor`: `source_id, provider, competition_resource, product, collection_version, variable_name, units_native, units_normalized, cadence, grid_resolution, spatial_coverage, period_coverage, latency, quality_flags, authentication, access_method, example_request, output_format, provenance_url, checked_at, validation_status`. Si un producto no está accesible, marcarlo `unverified` y habilitar fallback solo de similar significado y resolución, con degradación señalada.

Fuentes históricas preferidas según acceso: AppEEARS→MOD13Q1/11A2/MCD64A1/MCD12Q1 (Earthdata cuenta), Giovanni→series y comparación manual (productos según catálogo), NASA GES DISC→IMERG/GLDAS, NOAA CDO→estaciones según cobertura/token, KNMI→exploración; complementos ERA5-Land/CDS, FIRMS/MAP_KEY para históricos, SMAP/NSIDC, NASA POWER para algunas variables puntuales y GFS/NOMADS o pronóstico público con términos apropiados. **No afirmar que Earthdata/CDS/FIRMS histórico son anónimos**; validar opciones reales de acceso.

Trabajar San Luis, Argentina como piloto, período histórico inicial 2015–2025 pero ampliar cuando haga falta clima/SPI/extremos. No usar bbox como provincia exacta; solicitar máscara de polígono oficial de límites. Niveles: modo región agregada y modo mapa geográfico diferenciado, sin falsa super-resolución espacial. No confiar en interpolaciones gruesas para atribuir condiciones a parcelas de 250 m.

## 5. Validación exhaustiva y gates
Obligatorio: `walk-forward` por fecha de emisión, sin shuffle temporal; partición por años de temporada de fuego y **bloques geográficos/eventos** sin que un mismo incendio aparezca en train y test; calibración posterior en bloque disjunto; mantener test final ciego. Features `timestamp_observed` y `timestamp_available` para impedir datos futuros, incluso composites de satélite. Si se usan pronósticos externos como forzantes en backtest, utilizar reforecasts o archivos de pronóstico **emitidos realmente antes de t0**. Si no existen, separar evaluación idealizada `perfect_forcing_hindcast` (NO validar como forecast operacional) de evaluación verdaderamente prospectiva.

Referencias: climatología por mes, persistencia, año análogo, M1 simple AR, FWI solo, tasa base regional de actividad, distribución estacional de área. Métricas: continuas MAE/RMSE/bias y skill vs referencia; probabilidades Brier/BSS (solo si BS_ref>0), curva de calibración, PR-AUC para clases raras, log-loss; cuantiles pinball / interval score / cobertura empírica (documentar incertidumbre de cobertura); áreas CRPS cuando tenga soporte, clasificación detección precision/recall con umbral elegido en validación; FWI propio comparar con valores de tests de referencia, no «calibrar» el índice global para forzarlo. Predefinir umbrales locales de utilidad **con fundamento y validación**; no establecer mínimo de «X% precisión» universal.

**Criterios de aceptación**: (1) sin fugas, unidades y máscaras correctas; (2) muestra suficiente y fuente trazable; (3) errores/skill en TEST superior a baseline dentro de incertidumbre evaluada; (4) probabilidades/intervalos calibrados; (5) estabilidad por estación y región; (6) rendimiento medido; (7) endpoint y semántica de salida correctos. Si falla uno, no marcar como pronóstico validado.

## 6. API y backend
POST `/api/v1/predict` body `AnalysisRequest`: `request_id`, `input_mode`, `location` (geojson polígono / punto con CRS), `phenomenon_ids` (IDs v9), `target_variables`, `analysis_period`, `issue_time`, `horizon`, `time_step`, `spatial_mode`, `prediction_mode` (`auto|forecast|scenario|extrapolation`), `interval_level` (0.90/0.95), `scenario_assumptions` (opcional). Validar seguridad de geometrías, calendario, zona, recortes espaciales y fechas. Responder 422 si incompatible, 202 con `job_id` si ejecución costosa, 200 con caché cuando corresponda; jamás bloquear indefinidamente por descarga enorme. Mostrar `source_status` si falla un conector.

La respuesta `PredictionResult` debe tener: `request_id`, `region`, `phenomenon_ids`, `target_variable`, `units`, `mode`, `status`, `issue_time`, `valid_times`, `point_estimate` o `median`, `quantiles`, `event_definition`, `event_probability` cuando corresponda, `horizon_validated`, `model_version`, `training_period`, `skill_vs_baseline`, `metrics_on_holdout`, `interval_empirical_coverage`, `sources` (`product/version/latency/availability`), `assumptions`, `warnings`, `quality`, `job_id`/`cache_status`. **No inventar probabilidades para variables continuas**; las probabilidades solo se asignan a eventos bien definidos (`SPI<-1`, `area>0`, etc.).

Ejemplo: consulta de incendio dentro 5 días: planificador resuelve `B9.2`→FWI diario y `B9.1`→ocurrencia agregada si M6A validado; pipeline usa último estado FWI histórico, meteorología prevista, NDVI/SM disponibles antes de t0, calcula ensemble, compara con skill y genera gráfico + probabilidad calibrada. Consulta NDVI en 6 meses con validación de 1 mes: ofrecer solo pronóstico 1 mes y escenario exploratorio condicionado; no simular como certidumbre.

## 7. Orden de construcción para la IA implementadora
1. Auditar v9, generar matriz de 73 IDs sin alterar, clasificar `historical_only`, `direct_forecast`, `derived_from_forecast`, `conditional_scenario`, `unsupported` con justificación y prioridad; el catálogo **no obliga** a tener pronóstico para todos.
2. Implementar esquemas, catálogo, unidades, fechas, QA, preprocesamiento, fuente falsa (mock), tests de fuga y caché.
3. Implementar M1 temperatura+precipitación simples y M0 anomalías/SPI; baselines y evaluación robusta.
4. Implementar F2 FWI **oficial contrastado** primero; fuentes meteorológicas históricas y ensemble; tests de equivalencia.
5. Implementar M2 reservorio hídrico de baja dimensión con parámetros trazables y fallback estadístico, M3 NDVI y M4 LST reducidos, con validaciones fuera de muestra.
6. Implementar F3 regresión logística y calibrador por zonas/temporadas, comparar FWI solo vs FWI+ con NDVI/SM/VPD; etiquetas FIRMS con cobertura observacional y FPR.
7. Implementar F4 hurdle área quemada con MCD64A1 y límites físicos; probar ceros/magnitudes/distribución/skill.
8. Implementar Monte Carlo acoplado, intervalo calibrado, horizon gate y extrapolación honesta.
9. Exponer API, prueba chatbot/manual mismo JSON, demo y reporte de implementación real.

**En cada etapa:** emitir ecuación usada → unidades → función Python → test de física → test temporal → métrica comparativa → estado; si falta el recurso para hacerlo científicamente, crear `UNRESOLVED.md` y continuar con baseline viable, **nunca una ecuación vacía con parámetros mágicos**.

## 8. Formato obligatorio de la respuesta de la IA implementadora
- A. Auditoría de los archivos del equipo y arquitectura elegida (diagrama de DAG sin bucles no declarados).
- B. Matriz variable→ecuación→datos→modelo→incertidumbre→horizonte→estado.
- C. Registro de 73 IDs exactos y tipo de tratamiento (solo historia, derivado, forecast, escenario, no disponible).
- D. Código Python completo, tests y comandos reales; archivos descargables/entregados en el entorno.
- E. Conectores y URLs verificados vs pendientes; datos reales descargados vs sintéticos.
- F. Evidencias numéricas de validación real o explicación inequívoca de por qué NO pudo validarse.
- G. Riesgos y restricciones para bomberos/agricultura.
- H. Guía de integración con backend/frontend y JSON de ejemplo.

**Éxito significa:** un módulo reproducible con predicción y límites honestos que supera baselines en datos de evaluación, no una demo visual que parece acertada. Si el rendimiento predictivo no está demostrado, rotular correctamente «prototipo experimental» y reportar el fallo.
