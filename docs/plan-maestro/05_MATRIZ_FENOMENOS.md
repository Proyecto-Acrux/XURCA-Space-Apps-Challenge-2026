# 05 — Matriz de integración científica de los 73 fenómenos

Fuentes: planilla `Trend_Detective_v9…xlsx` (hojas `Nivel_1_Corregido`, `Nivel_2_Corregido`), `CATALOGO_V9_73.json`, código auditado. Los identificadores son los originales. Los textos de **método**, **afirmación permitida** y **afirmación prohibida** se abrevian de las columnas I, J y K; el texto literal completo debe copiarse a `knowledge/phenomena.json` (tarea EMA-03).

La matriz pedida tiene 18 columnas; se divide en dos tablas por nivel para que sea legible:

- **Tabla científica:** ID · objetivo · variables objetivo · variables explicativas · preprocesamiento · método de la planilla · qué puede afirmarse · qué no puede afirmarse.
- **Tabla de integración:** ID · productos requeridos · vía de datos real · receta y transformaciones · algoritmos (existentes / faltantes) · dependencias · restricciones espaciales y temporales · mínimos de datos · controles de validación · modelos predictivos · estado · ola.

## Leyenda

**Vía de datos:** `SR` serie disponible hoy · `SR*` serie con selección de estación frágil · `RAW` solo archivo crudo (requiere procesador) · `—` sin conector.

**Preparación (estado de integración).** Los 73 fenómenos están **especificados y ninguno implementado** en código. La columna indica qué falta:

| Código | Significado |
|---|---|
| **L1** | Datos como serie y métodos existentes; faltan solo adaptadores y algoritmos menores |
| **L2** | Datos como serie; faltan algoritmos nuevos |
| **L3** | Falta un procesador de datos (AppEEARS, ráster, variable no expuesta) |
| **L4** | Requiere procesamiento especializado fuera del alcance de la v1 → `UNSUPPORTED` / `NOT_AUTOMATABLE` con justificación |

**Ola de desarrollo** (ver `12_ROADMAP.md`): O1 recorrido 1 · O2 series disponibles · O3 AppEEARS por punto · O4 fuego y rejilla · O5 predictivo · O6 segunda prioridad · O7 tercera prioridad · X fuera de alcance v1.

**Algoritmos faltantes** (ver `06_MATRIZ_ALGORITMOS.md`): N01 climatología/anomalías · N02 IC de Sen · N03 SPI · N04 percentiles/eventos · N05 correlación con desfases · N06 FDR · N10 ETCCDI · N11 bootstrap · N12 FWI · N14 dNBR/recuperación · N15 matriz de transición · N16 hipsométrica.

**Mínimos de datos.** Los documentos disponibles fijan pocos valores; el resto depende de `ANEXO_MATEMATICO.md`, que no existe (decisión D-03).

| Código | Regla documentada | Pendiente |
|---|---|---|
| MIN-T (tendencia) | Cobertura ≥ 0.8 (Q01); misma estación/mes (Q02) | Años mínimos para informar tendencia |
| MIN-A (anomalía/evento) | Climatología de base fija con "cobertura mínima de años" (Q02) | Cuántos años de base |
| MIN-S (SPI) | Base < 20 años → "baja robustez o no habilitar" (Q05) | Política: rotular o bloquear |
| MIN-E (extremos) | Umbrales calendarizados de referencia fija | Años de referencia |
| MIN-L (desfases) | Desfases predefinidos; FDR por familia (Q04) | n efectivo mínimo |
| MIN-C (conteos) | Por sensor (Q07) | Temporadas mínimas |
| MIN-R (ráster/área) | Fracción de área válida informada (Q18); cobertura ≥ 0.8 (Q01) | Umbral por producto |

**Modo predictivo:** el del catálogo, sin alterar (`historical` · `direct` · `derived` · `scenario`). Que el catálogo diga `direct` **no** significa que exista un modelo: hoy no hay ninguno (ver `08_MATRIZ_PREDICTIVA.md`).

---

## Nivel 1 — Detección (36)

Evidencia: "Observación / detección". En N1 la planilla indica "Explicativas solo para N2": ningún fenómeno N1 usa variables explicativas.

### Tabla científica N1

| ID | Objetivo | Variables objetivo | Preprocesamiento | Método (planilla) | Puede afirmarse | No puede afirmarse |
|---|---|---|---|---|---|---|
| N1.1.0 | Tendencia de temperatura del aire y LST, por separado | T2m; LST | QA/nubes LST; °C; media por área; anomalías por mes y sensor; día/noche separados | Sen + MK estacional/autocorrelación; IC95; serie y climatología | Pendiente °C/década, IC, p ajustada y período; no significación = evidencia insuficiente | Confundir LST con temperatura del aire |
| N1.1.1 | Temperatura superficial de cuerpos de agua | SST / LSWT | Máscara de agua estable; QA; anomalía mensual | Sen; MK; estacionalidad; cobertura | Cambios observados sobre agua, distinguiendo océano y lago | Inferir mezcla vertical o temperatura profunda |
| N1.1A | Calentamiento regional sostenido | T2m | Series homogéneas; anomalías; control de cambios de estación | Sen + IC; contraste en subperíodos | Tendencia positiva consistente con calentamiento regional | Atribuir causas antropogénicas con un indicador local |
| N1.1B | Frecuencia y duración de olas de calor | Tmax/Tmin diaria | Umbrales calendarizados de referencia fija; días consecutivos | Índices ETCCDI o definición local explícita; conteo anual | Episodios con duración mínima definida y tendencia de frecuencia | Exigir presión alta o suelo seco como requisito |
| N1.1C | Diferencial térmico urbano-rural superficial | LST urbana y rural | Emparejar hora/estación, elevación y coberturas rurales | ΔLST pareado; IC bootstrap | Diferencia térmica **superficial** urbano-rural | Confundir con isla de calor del aire |
| N1.2.0 | Precipitación: déficit, exceso y evolución | Precipitación acumulada | Acumular mm/día→mes; series completas; climatología por mes | Anomalía absoluta/%, SPI 1/3/6/12, Sen+MK en totales | Déficit/exceso por región y período, duración y persistencia | Etiquetar causalidad o sequía hidrológica solo con lluvia |
| N1.2A | Sequía meteorológica y aridificación (separadas) | Precipitación; SPI; índice de aridez | Ajuste SPI válido; PET explícita | SPI por escala; tendencia P/PET con IC y ventanas largas | SPI negativo = déficit relativo; aridificación requiere indicador de largo plazo | Que SPI confirme aridificación o impactos en agua superficial |
| N1.2B | Lluvias intensas y períodos secos | Precipitación diaria | QA diaria; umbrales según días húmedos | RX1day, RX5day, R95pTOT, SDII, CDD; tendencia por índice | Cada indicador por separado | Que R95pTOT↑ y CDD↑ prueben tormentas más violentas |
| N1.3.0 | Vigor de vegetación y fenología | NDVI; EVI | QA nube/aerosol; máscara de cobertura; compuestos; anomalías estacionales | Sen por estación; percentiles; amplitud y comienzo de estación | Vigor respecto de su propio ciclo y clase de vegetación | Que NDVI equivalga a biomasa o salud ecológica |
| N1.3A | Pérdida persistente de cobertura vegetal | NDVI/EVI; cobertura arbórea | Máscara de bosque; segmentación temporal; nubes/sombra | BFAST/ruptura + pre/post + cobertura | Pérdida de verdor; deforestación solo con transición bosque→no bosque | Llamar deforestación a cosecha, incendio o sequía |
| N1.3B | Anomalías negativas del vigor | NDVI/EVI | Desestacionalizar por cultivo/bioma; QA | Percentiles, duración de anomalías, Sen | Disminución de vigor; estrés hídrico como hipótesis | Que NDVI bajo identifique causa única |
| N1.3C | Reverdecimiento | NDVI/EVI | Control de fenología, uso del suelo y calidad | Sen; rupturas; comparación entre estaciones iguales | Incremento de verdor sin clasificar origen | Que reverdecimiento + ET alta confirme riego |
| N1.4.0 | Focos de calor activos | Detecciones FIRMS | Filtrar confianza, sensor, QA y duplicados; cuadrícula | Conteo por sensor normalizado; densidad; series | Detecciones, ubicaciones y cambios de actividad observada | Que cada foco sea un incendio o una hectárea quemada |
| N1.4A | Estacionalidad y recurrencia térmica | Detecciones FIRMS | Separar plataformas, nubosidad y cambios de sensor | Recuentos por temporada; intervalo | Cambios de cantidad por temporada y persistencia | Inferir incidencia real sin corregir detectabilidad |
| N1.4B | Potencia radiativa | FRP | Calidad, sensor, saturación, geometría | Percentiles FRP por sensor | Potencia alta entre detecciones válidas | Que FRP alta implique megaincendio o severidad |
| N1.4C | Superficie quemada | Área quemada mensual/anual | Producto burned-area; área geodésica; máscara QA | Unión espacial por fecha; km²/ha y % del área válida; tendencia | Área estimada por producto y comparativa anual | Derivar hectáreas del número de focos |
| N1.4D | Cicatrices y recuperación inicial | NBR; dNBR; NDVI | Pre/post de misma estación y sensor; máscaras | dNBR/RdNBR; diferencia NDVI | Cambio espectral tras incendio | Que dNBR sea severidad de suelo validada |
| N1.5.0 | Humedad superficial y radicular (separadas) | Humedad del suelo | m³/m³; observación vs modelo; profundidad | Anomalía por estación y percentiles | Agua relativa para producto y profundidad precisos | Comparar % de saturación con humedad volumétrica |
| N1.5A | Déficit de humedad del suelo | Humedad del suelo | Climatología y QA; máscaras | Percentiles; intensidad y duración del déficit | Anomalía seca con duración y extensión | Exigir tendencia para una sequía actual |
| N1.5B | Exceso de humedad antecedente | Humedad del suelo | Percentiles locales; profundidad; agregación antecedente | P90/P95 del producto | Humedad excepcionalmente alta | Que P90 equivalga a saturación o umbral de inundación |
| N1.6.0 | Evapotranspiración real y demanda potencial | ET real; PET/ET0 | mm/intervalo; no mezclar ET0 con ET real | Estacionalidad, anomalías y razones | ET real y PET por separado | Llamar déficit hídrico sin modelo |
| N1.6A | Cambios de ET bajo disponibilidad de agua | ET real | QA, uso del suelo, balance energético | Tendencia ET | Cambio de ET observado | Que ET↑ pruebe aceleración del ciclo hidrológico |
| N1.6B | Descenso anómalo de ET | ET real | Ajuste estacional; QA | Anomalía y persistencia | ET bajo climatología | Que ET↓ implique solo desecación |
| N1.7.0 | Carga óptica de aerosoles | AOD | QA nubes; longitud de onda consistente | Mediana y anomalías; Sen+MK | Tendencia de profundidad óptica de columna | Que AOD mida PM2.5 superficial |
| N1.7A | Cambios de NO2 y AOD | NO2; AOD | Normalizar geometría, nubes, escala | Anomalías y cambio relativo | Tendencia de gases y aerosoles | Identificar fuente industrial o exposición |
| N1.7B | Episodios de aerosoles extremos | AOD | P95 estacional | Anomalías episódicas y mapas | Pulso de carga óptica | Que ausencia de FIRMS descarte humo transportado |
| N1.8.0 | Evolución de presión atmosférica | SLP o presión de estación | No mezclar presión de superficie con reducida al mar | Estacionalidad, extremos y anomalías | Presión y extremos según referencia | Que baja presión demuestre tormenta severa |
| N1.8.1 | Perfil altitudinal de presión (educativo) | Presión; elevación | Perfil vertical, temperatura, corrección de altura | Ecuación hipsométrica | Presión esperada según altura | Tratar gradiente estático como tendencia climática |
| N1.8A | Episodios de presión alta | SLP; geopotencial | Campos espaciales, persistencia | Índices de bloqueo validados en N2 | Persistencia de altas presiones como precursor | Que SLP media↑ confirme bloqueos |
| N1.8B | Ciclones y bajas presiones | SLP | Datos diarios/subdiarios | Extremos y trayectorias | Eventos de presión baja, no daños | Que un mínimo bajo sea tormenta intensa |
| N1.9.0 | Nivel de agua en ríos, lagos y embalses | WSE; altura de estación | Datum consistente; series discontinuas | Anomalías de nivel, cambios entre fechas | Nivel dentro del mismo datum y lugar | Que SWOT cubra décadas |
| N1.9A | Descenso sostenido del nivel | WSE | Operaciones y curvas altura-volumen | Sen/ruptura; anomalía | Bajante observada; causa como hipótesis | Atribuir a riego por NDVI agrícola |
| N1.9B | Crecida y expansión de aguas | WSE; extensión | Fechas comparables; SAR; datum | P95 nivel; cambio de extensión | Alza o expansión observada con incertidumbre | Atribuir a deshielo sin balances |
| N1.1D | Anomalías de LST y mapas | LST | Emisividad, QA nube, máscara; climatología por píxel y mes | Z-score robusto/percentil; hotspots persistentes | Píxeles excepcionalmente calientes respecto de sí mismos | Que un píxel cálido sea temperatura del aire o foco |
| N1.2C | Persistencia y transición déficit/exceso | Precipitación; SPI | Ventanas 1/3/6/12; climatología fija | SPI secuencial, duración, frecuencia, intensidad | Transición déficit→normal→exceso | Sumar SPI de escalas o usarlo sin serie suficiente |
| N1.3D | Posibles indicios de degradación | NDVI/EVI; cobertura | Control de cultivos, incendios, tendencia | Declive persistente + cambios de cobertura + rupturas | Señal de alerta que requiere validación en terreno | Etiquetar degradación definitiva con NDVI solo |

### Tabla de integración N1

| ID | Prod. requeridos | Vía de datos real | Receta / transformaciones | Algoritmos (existentes / faltantes) | Dep. | Restricciones espaciales y temporales | Mín. | QA | Predictivo (familia · línea · modo) | Estado | Ola | Prior. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N1.1.0 | X02, X07 | T2m: POWER, NOAA (SR). LST: AppEEARS (RAW) | R-TREND: climatología → anomalía mensual → tendencia | `sen`, `seasonal_mann_kendall`, `modified_mann_kendall` / N01, N02 | — | Punto o estación; LST día y noche separados; mensual | MIN-T | Q01 Q02 Q03 Q06 Q11 Q12 | M1, M4 · PRED-03/04 · derived | L1 (T2m) · L3 (LST) | O1 · O3 | MVP |
| N1.1.1 | X18 | SST: OISST (SR, sustituye a GHRSST). LSWT: — | R-TREND | ídem N1.1.0 | — | Celda oceánica 0.25°; lagos sin vía | MIN-T | Q01 Q02 Q03 Q11 | — · PRED-08 (C05) · historical | L1 océano · L4 lago | O2 | P2 |
| N1.1A | X02 | POWER, NOAA (SR) | R-TREND + subperíodos | ídem | N1.1.0 | Homogeneidad de estación | MIN-T | Q01 Q02 Q03 | M1 · PRED-03 · derived | L1 | O1 | P2 |
| N1.1B | X02 | Open-Meteo Tmax/Tmin diaria; NOAA diario (SR) | R-EXTREMES | `sen`, `mann_kendall` / N10, N04 | — | Diaria; umbral calendarizado | MIN-E | Q01 Q02 Q12 | M1 · derived | L2 | O6 | P2 |
| N1.1C | X07 | AppEEARS (RAW) + máscara X08 | R-PAIRED | — / N11 | Cobertura | Pares comparables en hora, estación y elevación | MIN-R | Q06 Q09 Q17 Q18 | M4 · scenario | L3 | O6 | P2 |
| N1.2.0 | X01 | Open-Meteo/ERA5, POWER (con conversión), NOAA, INA (SR). IMERG: RAW | R-ANOM + R-SPI + R-TREND: acumulado mensual → anomalía → SPI → tendencia | `sen`, `mann_kendall` / N01, N03, N02 | — | Acumulado mensual; base por mes | MIN-S | Q01 Q02 Q03 Q05 Q11 | M1, M0 · PRED-01 · derived | L2 | O2 | MVP |
| N1.2A | X01 | ídem + ET₀ Open-Meteo | R-SPI + R-TREND (P/PET) | `sen` / N03 | N1.2.0 | Ventanas largas | MIN-S | Q02 Q05 Q12 | M1, M0 · derived | L2 | O6 | P2 |
| N1.2B | X01 | Precipitación diaria (SR) | R-EXTREMES | `sen`, `mann_kendall` / N10 | — | Diaria | MIN-E | Q01 Q05 | M1 · scenario | L2 | O6 | P2 |
| N1.3.0 | X06 | AppEEARS (RAW) | R-TREND + R-ANOM + fenología | `sen`, `harmonic` / N01, N04 | — | 16 días, ~250 m; por clase de vegetación | MIN-T | Q01 Q02 Q06 Q17 | M3 · PRED-02 · direct | L3 | O3 | MVP |
| N1.3A | X06 (+X08) | RAW | R-BREAK + R-TRANSITION | `stl`, `pelt` / N15 | Cobertura | Máscara de bosque | MIN-R | Q06 Q17 | M3 · historical | L3 | O7 | P2 |
| N1.3B | X06 | RAW | R-ANOM + R-TREND | `sen` / N01, N04 | N1.3.0 | Desestacionalizar por bioma | MIN-A | Q01 Q02 Q06 Q12 Q17 | M2, M3 · derived | L3 | O3 | MVP |
| N1.3C | X06 | RAW | R-TREND + R-BREAK | `sen`, `stl`, `pelt` | N1.3.0 | Estaciones iguales | MIN-T | Q06 Q17 | M3 · derived | L3 | O6 | P2 |
| N1.4.0 | X04 | FIRMS (SR, clave sin verificar) | R-COUNT por sensor, área y tiempo | — / separación por sensor (dataprep) | — | Polígono; diario; por sensor | MIN-C | Q07 Q14 Q18 | F1 · historical | L2 | O4 | MVP |
| N1.4A | X04 | FIRMS | R-COUNT por temporada | `sen`, `mann_kendall` | N1.4.0 | Cambios de sensor | MIN-C | Q07 Q14 | F1, M6A · direct | L2 | O6 | P2 |
| N1.4B | X04 | FIRMS (`frp`) | R-ANOM (percentiles por sensor) | — / N04 | N1.4.0 | Por sensor | MIN-C | Q07 | F1 · historical | L2 | O6 | P2 |
| N1.4C | X05 | AppEEARS (RAW, área) | R-AREA + R-TREND | `sen` / área geodésica y zonal (dataprep) | — | ~500 m; mensual | MIN-R | Q08 Q14 Q18 | F1, M6B · PRED-06 (C06) · direct | L3 | O4 | MVP |
| N1.4D | X11 | Planetary (RAW, bandas) | R-PREPOST | — / N14 | N1.4C | 30 m; pre/post misma estación | MIN-R | Q06 Q08 | M3, F5 · derived | L4 | O7 | P2 |
| N1.5.0 | X09 | ERA5-Land por capa (SR, modelo; sustituye a SMAP). SMAP: RAW | R-ANOM | — / N01, N04 | — | Profundidad explícita; observación vs modelo | MIN-A | Q01 Q02 Q11 | M2 · direct | L2 | O2 | P2 |
| N1.5A | X09 | ídem | R-ANOM (déficit, duración) | — / N01, N04 | N1.5.0 | ídem | MIN-A | Q01 Q02 Q12 | M2 · derived | L2 | O2 | P2 |
| N1.5B | X09 | ídem | R-ANOM (P90/P95) | — / N01, N04 | N1.5.0 | ídem | MIN-A | Q01 Q02 Q14 | M2 · derived | L2 | O2 | P2 |
| N1.6.0 | X20 | ET₀: Open-Meteo (SR). ET real: AppEEARS (RAW) | R-ANOM | — / N01 | — | ET real y ET₀ nunca combinadas | MIN-A | Q11 | M2 · scenario | L2 (ET₀) · L3 (ET real) | O6 | P2 |
| N1.6A | X20 | RAW | R-TREND | `sen` | N1.6.0 | 8 días, ~500 m | MIN-T | Q06 Q17 | M2, M3 · scenario | L3 | O7 | P3 |
| N1.6B | X20 | RAW | R-ANOM | — / N01, N04 | N1.6.0 | ídem | MIN-A | Q06 | M2, M3 · scenario | L3 | O6 | P2 |
| N1.7.0 | X28 | Earthdata (RAW) | R-TREND | `sen`, `mann_kendall` | — | Columna atmosférica | MIN-T | Q06 | — · historical | L4 | X | P2 |
| N1.7A | X19, X28 | CDSE, Earthdata (RAW) | R-ANOM | — | — | Productos separados | MIN-A | Q06 | — · historical | L4 | X | P3 |
| N1.7B | X28 | RAW | R-ANOM | — / N04 | N1.7.0 | — | MIN-A | Q06 | — · historical | L4 | X | P2 |
| N1.8.0 | X02 | POWER `PS` (presión de superficie, kPa; SR). SLP: CDS (RAW) | R-ANOM | — / N01 | — | No mezclar presión de superficie y reducida | MIN-A | Q11 | M1 · historical (C03) | L2 (PS) · L3 (SLP) | O7 | P3 |
| N1.8.1 | X02 | `PS` + elevación (X17, RAW) | R-PHYS | — / N16 | — | Educativo | — | Q11 | — · historical | L3 | O7 | P3 |
| N1.8A | X02 | CDS (RAW) | Índices de bloqueo | Fuera de alcance | — | Campos espaciales | — | — | — · scenario | L4 | X | P3 |
| N1.8B | X02 | CDS (RAW) | Seguimiento de trayectorias | Fuera de alcance | — | Subdiario | — | — | — · scenario | L4 | X | P3 |
| N1.9.0 | X14 | SWOT (SR\*, desde 2022); INA altura (SR\*) | R-ANOM | — / N01 | — | Mismo datum y lugar; serie irregular | MIN-A | Q01 Q11 Q14 | — · PRED-07 (C04) · historical | L2 | O2 | P2 |
| N1.9A | X14 | INA (series largas); SWOT | R-TREND + R-BREAK | `sen`, `pelt`/`cusum` | N1.9.0 | Datum | MIN-T | Q03 Q11 | — · historical | L2 | O6 | P2 |
| N1.9B | X14 | Nivel (SR\*). Extensión: SAR, — | R-ANOM (P95 de nivel) | — / N04 | N1.9.0 | Rama de extensión bloqueada | MIN-A | Q11 Q14 | — · scenario | L2 (nivel) · L4 (extensión) | O6 | P2 |
| N1.1D | X07 | AppEEARS (RAW, área) | R-ANOM por celda | `analyze_grid` / N01, N04 | — | Rejilla con tope de celdas; día/noche | MIN-R | Q06 Q09 Q18 | M4 · PRED-04 · derived | L3 | O4 | MVP |
| N1.2C | X01 | Precipitación (SR) | R-SPI: estados, duración, transición | — / N03, N04 | N1.2.0 | Ventanas 1/3/6/12; climatología fija | MIN-S | Q02 Q05 Q12 | M1, M0 · PRED-01 · derived | L2 | O2 | MVP |
| N1.3D | X06 (+X08) | RAW | R-TREND + R-BREAK + R-TRANSITION | `sen`, `stl`, `pelt` / N15 | N1.3A | Comparación contextual | MIN-R | Q17 | M2, M3, M4 · scenario | L3 | O7 | P2 |

---

## Nivel 2 — Diagnóstico multivariable (37)

Evidencia: "Evidencia asociativa; validar hipótesis". **La planilla no separa variables objetivo de explicativas en N2**: la asignación de roles de la tabla es una **propuesta** de este plan, a validar por la ingeniera química (decisión D-03). El detalle de hipótesis, desfases y variables de confusión por fenómeno está en la sección "Reglas de cruce" más abajo.

### Tabla científica N2

| ID | Objetivo | Objetivo (propuesto) | Explicativas (propuesto) | Preprocesamiento | Método (planilla) | Puede afirmarse | No puede afirmarse |
|---|---|---|---|---|---|---|---|
| B1.1 | Expansión urbana y conversión de cobertura | Cobertura urbana | Cobertura, NDVI | Clasificación multifecha, matriz de transición, QA | Cambios vegetación→urbano y tendencia NDVI | Expansión cartografiada + menor verdor en áreas convertidas | Que NDVI pruebe impermeabilización |
| B1.2 | Isla de calor superficial y pérdida de vegetación | LST (ΔLST) | NDVI, ET, cobertura | Emparejar fechas, día/noche, altitud, superficie, área rural | ΔLST urbano-rural y análisis condicionado | Asociación consistente, no atribución única | Isla de calor atmosférica a partir de LST |
| B1.3 | Aerosoles urbanos y ventilación | AOD, NO2 | Viento, PBLH | QA nubes/sensor; coincidencia temporal | Multivariable NO2/AOD–viento–PBLH | Condiciones favorables a acumulación en columna | Concentración superficial o exposición |
| B1.4 | Patrones de HCHO y NO2 | HCHO | NO2, T2m, vegetación | Normalizar columnas; estacionalidad | Correlaciones parciales / modelo explicativo | Compatibilidad con posibles fuentes | Clasificar fuente de COV |
| B2.1 | Pérdida de bosque por cambio de uso | Cobertura forestal | NDVI, LST | Máscara de bosque original; clasificación temporal | Transición bosque→no bosque corroborada | Pérdida confirmada por transición de clase | Expansión agropecuaria sin clase destino |
| B2.2 | Estrés vegetal asociado a déficit de agua | NDVI/EVI | P, humedad del suelo, T2m | Anomalías estacionales; desfases plausibles; tipo de cobertura | Regresión dinámica con lags; sensibilidad; controles | Menor vigor coincide o es precedido por déficit; hipótesis explícita | Causalidad por correlación simple |
| B2.3 | Cambios de productividad primaria | GPP/NPP | LAI, T2m, P | Separar GPP de NPP; unidades de carbono | Tendencia + regresión explicativa | Variación de productividad | Que NPP positiva sea sumidero neto |
| B2.4 | Cambios estructurales con SAR | Retrodispersión SAR | Cobertura, NDVI | Órbitas, speckle, polarización | Detección de cambios SAR + verificación óptica | Cambio estructural probable con incertidumbre | Que baja retrodispersión confirme tala |
| B3.1 | Sequía hidrológica y bajantes | WSE, caudal | P, humedad del suelo, ET | Precipitación de cuenca y lags; datum; operaciones | Anomalías conjuntas + balance hídrico | Bajante coincide con déficit de aporte; causas alternativas abiertas | Atribuir toda bajante al clima o al riego |
| B3.2 | Anegamiento e inundación observada | Extensión SAR, WSE | P, humedad del suelo | Ventanas antecedentes; máscara SAR | Mapa de agua pre/post; lluvia antecedente | Extensión observada y factores compatibles | Que P95 de lluvia y suelo húmedo prueben inundación |
| B3.3 | Limitación energética vs hídrica de ET | ET | PET, humedad del suelo, radiación, NDVI | ET y PET compatibles; anomalías | Sensibilidades y regresión | Clasificación indicativa de régimen | Disponibilidad hídrica solo de ET₀–ET |
| B3.4 | Altura, ancho, pendiente y descarga fluvial | WSE, ancho, pendiente | Caudal modelado | Datum y geometría; error de medición | Comparaciones longitudinales con IC | Cambios estimados con limitaciones | Caudal "centimétrico" o morfología de dos niveles |
| B4.1 | Retroceso glaciar y pérdida de masa | Área glaciar | Elevación, nieve | Máscara de hielo; DEM co-registrados | Cambio de área; diferencia de DEM | Área; masa solo con altimetría | Que menor área cuantifique adelgazamiento |
| B4.2 | Duración de cobertura nival | NDSI, nieve | T2m, SWE | QA nubes; nieve por altitud | Inicio-fin, duración, asociación con T2m | Temporada más corta o larga | Que cobertura equivalga a SWE |
| B4.3 | Avance glaciar potencial | Área glaciar | Nieve, T2m | Clasificación estacional | Cambios del frente; validación geodésica | Avance geométrico observado | Que un invierno nivoso pruebe ganancia de masa |
| B4.4 | Degradación de permafrost | InSAR | Temperatura del suelo | Líneas de base InSAR | Tendencias térmicas y subsidencia | Compatibilidad con deformación por deshielo | Que subsidencia pruebe degradación |
| B5.1 | Elevación absoluta del mar y cambios costeros | SSH absoluta | SST, línea de costa | Datum altimétrico, mareas | Tendencia SSH + cartografía litoral | Alza geocéntrica | Que SST cuantifique expansión térmica local |
| B5.2 | Nivel relativo del mar y movimiento vertical | Mareógrafo | GNSS, SSH | Datum mareográfico | Diferencia de tendencias | Posible movimiento vertical | Atribuir a rebote isostático |
| B5.3 | Olas de calor marinas y clorofila | SST | Clorofila, viento | Climatología SST diaria y percentiles | MHW ≥P90 y duración; clorofila independiente | Ola de calor + anomalía de clorofila | Que clorofila alta sea marea roja tóxica |
| B5.4 | Surgencia y productividad marina | SST, clorofila | Viento paralelo a la costa, nutrientes | Orientación litoral, Ekman, desfase | Composites / estudio de eventos; regresión con lags físicos | Patrón compatible con surgencia | Medir nutrientes por SST/clorofila |
| B6.1 | Teleconexiones ENSO | P, T2m | Niño 3.4 | Anomalías, lags declarados, estratificar estaciones | Correlaciones parciales + validación fuera de muestra; lags limitados | Asociación regional según lugar y época | Efecto causal invariable |
| B6.2 | Contrastes espaciales asociados a ENSO | P/T regional | Niño 3.4 | Climatologías por región | Patrones de correlación + incertidumbre múltiple | Respuesta diferencial entre regiones | Sumar regiones o extrapolar la teleconexión |
| B6.3 | Tendencias en radiación y aerosoles | Radiación | AOD, nube | Homogeneidad radiométrica | Sen/MK + modelo multivariante | Oscurecimiento o abrillantamiento detectado | Que AOD y nubes expliquen todo el cambio |
| B7.1 | Plumas volcánicas | SO2, aerosol | T2m | Altitud de pluma, dispersión | Detección de SO2 y estudio de eventos | Perturbación radiativa plausible | Exigir enfriamiento tras toda erupción |
| B7.2 | Deformación cortical y sismos | InSAR | Sismos | Corrección atmosférica, coherencia | Interferometría diferencial + ubicación | Desplazamiento en línea de visión | Vector 3D con una geometría |
| B7.3 | Condiciones predisponentes a deslizamiento | Susceptibilidad | P, pendiente, humedad, cobertura | Resolución compatible; inventario | Modelo de susceptibilidad calibrado localmente | Condiciones favorables | Regla universal pendiente>20° y lluvia>P99 |
| B8.1 | Gradientes orográficos de precipitación | P | Viento, DEM | Bandas de elevación; sotavento/barlovento | Contrastes apareados | Diferencias compatibles con sombra de lluvia | Inferir foehn |
| B8.2 | Calentamiento dependiente de elevación | T2m | DEM, nieve | Bandas altitudinales | Tendencias por banda + interacción | Diferencia de tendencias por altura | Mecanismo hielo-albedo por correlación |
| B8.3 | Cambio altitudinal de vegetación | Cobertura arbórea | NDVI, DEM | Clasificación multifecha | Cambio altitudinal de límites de clase | Desplazamiento observado si hay cambio de clase | Que NDVI en altura demuestre ascenso del límite |
| B9.1 | Recurrencia de fuego y superficie quemada | FIRMS; área quemada | P, T2m | Distinguir detecciones, eventos y área | Frecuencia, temporada, km² y lags meteorológicos | Evolución por métrica independiente y asociaciones | Número de incendios desde detecciones |
| B9.2 | Condiciones meteorológicas de peligro | Índice de peligro (FWI) | T, HR, viento, P, combustible | Datos diarios/horarios; calibración local | FWI u otro índice validado | Peligro meteorológico relativo | Predicción del incendio exacto; regla 30-30-30 universal |
| B9.3 | Severidad espectral y recuperación | NBR/dNBR, NDVI | Lluvia | Pre/post misma estación; máscara de área quemada | dNBR + trayectorias de recuperación | Cambio espectral y recuperación comparativa | Que dNBR sea daño ecológico absoluto |
| B9.4 | Atlas histórico de incendios | Área quemada, FIRMS | NBR | Productos comparables, mosaico anual | Series de ha, mapas anuales; recurrencia por píxel | Capas separadas de focos, área y cambio espectral | Sustituir área quemada por densidad de focos |
| B2.5 | Degradación ambiental multiseñal | NDVI/EVI, cobertura | LST, P, humedad | Anomalías comparables, estratos | Regresión con controles, rupturas | Alerta multievidencia | Desertificación irreversible sin evidencia de suelo |
| B2.6 | Recuperación tras sequía | NDVI/EVI | P, humedad, LST | Definir evento y referencia | Tiempo de recuperación + IC | Recuperación espectral observada | Restauración ecosistémica total |
| B3.5 | Déficit/exceso de lluvia y respuesta del territorio | Humedad del suelo, NDVI, WSE | P, SPI | Precipitación por cuenca; ventanas; lags | Cambio de estados SPI y respuesta diferida | Evolución del episodio y posibles impactos | Impacto directo sin sensibilidad local |
| B1.5 | Calentamiento anormal y pérdida de cubierta | LST | T2m, NDVI, cobertura | Alinear por estación/hora, clase, sensor | Hotspots persistentes + control regional | Zonas cálidas anómalas coincidentes con pérdida vegetal | Atribuir a urbanización sin transiciones observadas |

### Tabla de integración N2

| ID | Prod. requeridos | Vía de datos real | Receta | Algoritmos (existentes / faltantes) | Dep. | Restricciones | Mín. | QA | Predictivo | Estado | Ola | Prior. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1.1 | X08, X06 | AppEEARS (RAW) | R-TRANSITION + R-TREND | `sen` / N15 | — | 500 m anual: no confirma escala de parcela | MIN-R | Q09 Q17 Q18 | — · historical | L3 | O7 | P2 |
| B1.2 | X07, X06, X08 | RAW | R-PAIRED + R-LAGREG | `multivariable` / N11 | N1.1C | Escala común = la más gruesa | MIN-R | Q09 Q10 Q13 | M3, M4 · scenario | L3 | O7 | P2 |
| B1.3 | X28, X19, X02 | RAW | R-LAGREG | Fuera de alcance v1 | — | — | — | Q13 | — · historical | L4 | X | P3 |
| B1.4 | X19, X02 | RAW | R-PARTIAL | Fuera de alcance v1 | — | — | — | Q13 | — · historical | L4 | X | P3 |
| B2.1 | X08, X06 | RAW | R-TRANSITION | — / N15 | — | Máscara de bosque original | MIN-R | Q17 | — · historical | L3 | O7 | P2 |
| B2.2 | X06, X01, X09, X02 | NDVI: RAW. P, humedad, T2m: SR | R-LAGREG: anomalías → alineación → correlación con desfases → FDR → regresión | `multivariable` / N01, N05, N06 | N1.3B, N1.2.0, N1.5.0 | Mensual; escala de la fuente más gruesa; desfases predefinidos | MIN-L | Q01 Q02 Q04 Q06 Q09 Q10 Q13 Q17 | M2, M3 · PRED-02 · derived | L3 (por NDVI) | O3 | MVP |
| B2.3 | X21, X02, X01 | GPP/NPP: RAW | R-TREND + regresión | `sen`, `multivariable` | — | Anual / 8 días | MIN-T | Q13 | — · historical | L3 | O7 | P3 |
| B2.4 | X13, X06 | SAR: RAW | Detección de cambios SAR | Fuera de alcance v1 | — | — | — | — | — · historical | L4 | X | P3 |
| B3.1 | X01, X14, X09 | P, humedad (SR); nivel y caudal INA (SR\*); ET real: RAW | R-LAGREG (anomalías conjuntas) | `multivariable` / N01, N05, N06 | N1.2.0, N1.5.0, N1.9.0 | Cuenca (hoy solo punto/estación); datum | MIN-L | Q04 Q09 Q10 Q11 Q13 Q14 | — · scenario (C03) | L2 | O6 | P2 |
| B3.2 | X01, X13, X14 | P, humedad, nivel (SR). Extensión: — | R-PREPOST | Fuera de alcance v1 (extensión) | — | — | — | Q14 | — · historical | L4 | X | P2 |
| B3.3 | X20, X09, X02 | ET real: RAW. ET₀, humedad, radiación: SR | R-LAGREG | `multivariable` / N05 | N1.6.0 | — | MIN-L | Q13 | M1, M2 · scenario | L3 | O7 | P3 |
| B3.4 | X14 | SWOT `wse`, `width`, `slope` (SR\*); caudal sin valores válidos | R-PAIRED (longitudinal + IC) | — / N11 | N1.9.0 | Serie corta e irregular | MIN-A | Q11 | — · historical | L2 | O7 | P3 |
| B4.1 | X24, X02, X29 | RAW / — | — | Fuera de alcance v1 | — | — | — | — | — · historical | L4 | X | P3 |
| B4.2 | X24, X02 | NDSI: RAW. T2m: SR | R-COUNT (duración) + asociación | — / N05 | — | Por banda de altitud | MIN-R | Q06 Q13 | — · scenario (C03) | L3 | O7 | P3 |
| B4.3 | X24, X02 | RAW | — | Fuera de alcance v1 | — | — | — | — | — · historical | L4 | X | P3 |
| B4.4 | X02, X13 | InSAR: — | — | Fuera de alcance v1 | — | — | — | — | — · historical | L4 | X | P3 |
| B5.1 | X14, X18 | SSH: —. SST: OISST (SR) | R-TREND | Rama SSH sin vía | — | Datum altimétrico | — | Q11 | — · historical | L4 | X | P3 |
| B5.2 | X22, X14 | Mareógrafo: PSMSL (SR\*). GNSS, SSH: — | R-TREND (solo mareógrafo) | `sen`, `mann_kendall` / N02 | — | Referencia local RLR | MIN-T | Q03 Q11 | — · historical | L2 parcial | O7 | P3 |
| B5.3 | X18, X15 | SST: OISST (SR). Clorofila: RAW | R-ANOM (≥P90 y duración) + asociación | — / N01, N04 | N1.1.1 | Climatología diaria | MIN-A | Q02 Q12 Q13 | — · PRED-08 · scenario (C03) | L2 (calor marino) · L3 (clorofila) | O6 | P2 |
| B5.4 | X18, X15, X02 | SST (SR). Viento direccional y clorofila: sin serie | R-COMPOSITE + R-LAGREG | — / N04, N05 | B5.3 | Orientación de costa | MIN-L | Q13 | — · historical | L3 | O7 | P2 |
| B6.1 | X16, X01, X02 | ONI, P, T2m (SR) | R-PARTIAL / R-LAGREG con validación fuera de muestra | `multivariable` / N05, N06 | N1.2.0, N1.1.0 | Estratificar por estación del año; desfases limitados | MIN-L | Q04 Q10 Q13 | M1 · scenario | L2 | O6 | P3 |
| B6.2 | X16, X01, X02 | ídem, varios puntos | R-LAGREG por región + FDR | ídem | B6.1 | Regiones = conjunto de puntos | MIN-L | Q04 Q13 | M1 · scenario | L2 | O7 | P3 |
| B6.3 | X16, X01, X02 **(C12: no incluye AOD ni radiación)** | Radiación: POWER (SR). AOD, nube: sin serie | R-TREND + R-LAGREG | `sen`, `mann_kendall` | — | — | MIN-T | Q13 | — · historical | L3; ruteo a corregir (D-14) | O7 | P3 |
| B7.1 | X19, X28 | RAW | Estudio de eventos | Fuera de alcance v1 | — | — | — | — | — · historical | L4 | X | P3 |
| B7.2 | X13, X23 | Sismos: USGS (SR). InSAR: — | Solo contexto de eventos | Fuera de alcance v1 (InSAR) | — | — | — | — | — · historical | L4 | X | P3 |
| B7.3 | X01, X09, X17 | Requiere inventario de deslizamientos | Modelo de susceptibilidad | Fuera de alcance v1 | — | — | — | Q14 | — · scenario (C03) | L4 | X | P3 |
| B8.1 | X01, X02, X17 | P: SR multipunto. DEM: RAW | R-PAIRED | — / N11 | — | Bandas de elevación | MIN-A | Q09 | M1 · historical (C03) | L3 | O7 | P3 |
| B8.2 | X02, X17 | T2m: SR multipunto. DEM: RAW | R-TREND por banda | `sen` / N02 | N1.1.0 | Bandas altitudinales | MIN-T | Q03 Q09 | M1, M4 · scenario | L3 | O7 | P3 |
| B8.3 | X06, X08, X17 | RAW | R-TRANSITION | — / N15 | — | — | MIN-R | Q17 | M3 · historical (C03) | L3 | O7 | P3 |
| B9.1 | X04, X05, X01, X02 | FIRMS (SR, clave); área quemada: RAW; P, T2m: SR | R-COUNT + R-AREA + R-LAGREG | `sen` / N05, N06 | N1.4.0, N1.4C | Tres métricas separadas; nunca combinadas | MIN-C, MIN-L | Q04 Q07 Q08 Q13 Q14 | F1, M6A, M6B · derived | L2 (focos y meteorología) · L3 (área) | O4 | MVP |
| B9.2 | X01, X02, X09 | T y P diarias: SR. Humedad relativa y viento diarios: sin serie | R-PHYS (FWI) | — / N12 | — | Diario; estado y spin-up; hemisferio sur | — | Q14 Q15 | M5, M6A · PRED-05 · direct | L3 | O6 | P2 |
| B9.3 | X06, X05 | RAW | R-PREPOST + recuperación | — / N14 | N1.4C | Pre/post misma estación | MIN-R | Q06 Q08 | M3, F5 · derived | L3 | O4 (último del MVP) | MVP |
| B9.4 | X05, X04 | Área quemada: RAW. FIRMS: SR | R-AREA + R-COUNT (capas separadas) | — / área geodésica | N1.4C, N1.4.0 | Mosaico anual | MIN-R | Q07 Q08 Q14 | F1 · historical | L3 | O4 | MVP |
| B2.5 | X08, X06 | RAW | R-LAGREG + R-BREAK | `multivariable`, `pelt` | B2.2, N1.3D | Estratos ecológicos | MIN-L | Q13 Q17 | M2, M3, M4 · scenario | L3 | O7 | P2 |
| B2.6 | X06 | NDVI: RAW. P, humedad: SR | Tiempo de recuperación + IC | — / N11, N14 | B2.2 | Evento y referencia definidos | MIN-A | Q17 | M2, M3 · derived | L3 | O6 | P2 |
| B3.5 | X01, X14 | P, humedad, nivel (SR). NDVI: RAW | R-SPI + R-LAGREG | `multivariable` / N03, N04, N05, N06 | N1.2C, N1.5.0, N1.9.0 | Cuenca aproximada por punto; ventanas 1/3/6/12 | MIN-S, MIN-L | Q02 Q04 Q05 Q10 Q13 | M1, M0, M2, M3 · PRED-01 · derived | L2 | O2 | MVP |
| B1.5 | X06 | LST, NDVI, cobertura: RAW. T2m: SR | R-ANOM por celda + control regional | `analyze_grid` / N01, N04 | N1.1D | Alinear por estación, hora, clase y sensor | MIN-R | Q09 Q13 Q17 | M3, M4 · derived | L3 | O7 | P2 |

---

## Reglas de cruce de variables (N2)

El Handler **no cruza variables porque estén disponibles**: cada cruce nace de una hipótesis declarada en `knowledge/phenomena.json`. Para los cinco fenómenos N2 del MVP, este es el contenido propuesto. Los desfases marcados `proposed` requieren confirmación de la ingeniera química (D-03); **ningún documento disponible fija valores numéricos de desfase**.

| | B2.2 | B3.5 | B9.1 | B9.3 | B9.4 |
|---|---|---|---|---|---|
| **Qué se relaciona** | Vigor (NDVI) con disponibilidad de agua | Estados de lluvia (SPI) con respuesta del territorio | Actividad de fuego con meteorología | Cambio espectral con recuperación | Focos, área quemada y cicatrices |
| **Papel de cada variable** | Objetivo: NDVI. Explicativas: P, humedad del suelo. Confusión: T2m, cobertura | Conductor: P/SPI. Respuestas: humedad, NDVI, nivel | Objetivos independientes: detecciones, área. Explicativas: P, T2m | Objetivo: dNBR, NDVI. Explicativa: lluvia | Sin relación estadística: capas comparadas |
| **Hipótesis** | El vigor cae durante o tras un déficit hídrico | Un déficit o exceso se propaga con retardo a suelo, vegetación y nivel | La actividad aumenta tras períodos secos y cálidos | La recuperación del verdor sigue al retorno de la lluvia | — (descriptivo) |
| **Transformaciones** | Anomalías estacionales de todas las series | SPI 1/3/6/12; anomalías de las respuestas | Conteos por temporada y sensor; km²; anomalías meteorológicas | dNBR pre/post; trayectoria de NDVI | Mosaico anual; recurrencia por píxel |
| **Escalas** | Mensual; la escala espacial de la fuente más gruesa | Mensual; cuenca aproximada | Mensual o por temporada; región | Evento; píxel dentro del área quemada | Anual; píxel |
| **Desfases con sentido físico** | Respuesta retardada de la vegetación (`proposed`: 0–3 meses) | Suelo antes que vegetación antes que nivel (`proposed`) | Meteorología antecedente (`proposed`) | Tiempo desde el incendio | — |
| **Método** | Correlación con desfases predefinidos + FDR → regresión con esos desfases (`multivariable`) | Estados SPI + respuesta diferida | Frecuencia y km² + correlación con desfases | dNBR + tiempo de recuperación | Series y mapas |
| **Variables de confusión a informar** | Cosecha, cambio de uso, incendio, temperatura | Riego, operación de embalses, uso del suelo | Cambios de sensor, nubosidad, actividad humana | Tipo de ecosistema, uso posterior | Diferencias entre productos |
| **Significación y robustez** | FDR por familia de desfases; sensibilidad a la base y al período | Ídem | Ídem; por sensor | IC por bootstrap | — |
| **Conclusión permitida** | "Coincide o es precedida por déficit; hipótesis explícita" | "Evolución del episodio y posibles impactos" | "Evolución por métrica independiente y asociaciones" | "Cambio espectral y recuperación comparativa" | "Capas separadas" |
| **Limitación a comunicar** | Asociación, no causalidad (Q13) | Sin sensibilidad local no hay impacto directo | Detecciones ≠ incendios; no operativo (Q14) | dNBR ≠ daño ecológico | Área quemada ≠ densidad de focos |

Para los 32 fenómenos N2 restantes, la misma ficha se completa cuando el fenómeno entra en una ola de desarrollo; hasta entonces su entrada en `phenomena.json` contiene el texto de la planilla y `recipe_params.status: "proposed"`.

---

## Resumen por preparación

| Preparación | Cantidad | Fenómenos |
|---|---|---|
| L1 | 3 | N1.1.0 (rama T2m), N1.1A, N1.1.1 (rama oceánica) |
| L2 | 24 | N1.1B, N1.2.0, N1.2A, N1.2B, N1.2C, N1.4.0, N1.4A, N1.4B, N1.5.0, N1.5A, N1.5B, N1.6.0 (rama ET₀), N1.8.0 (rama presión de superficie), N1.9.0, N1.9A, N1.9B (rama nivel), B3.1, B3.4, B3.5, B5.2 (rama mareógrafo), B5.3 (rama calor marino), B6.1, B6.2, B9.1 (rama focos y meteorología) |
| L3 | 29 | N1.1C, N1.3.0, N1.3A, N1.3B, N1.3C, N1.4C, N1.6A, N1.6B, N1.8.1, N1.1D, N1.3D, B1.1, B1.2, B2.1, B2.2, B2.3, B3.3, B4.2, B5.4, B6.3, B8.1, B8.2, B8.3, B9.2, B9.3, B9.4, B2.5, B2.6, B1.5 |
| L4 | 17 | N1.4D, N1.7.0, N1.7A, N1.7B, N1.8A, N1.8B, B1.3, B1.4, B2.4, B3.2, B4.1, B4.3, B4.4, B5.1, B7.1, B7.2, B7.3 |

*Total 73. Los fenómenos con ramas en dos niveles se cuentan por su rama más avanzada.*

**Conclusión operativa:** de los 13 fenómenos MVP, **7 dependen por completo de convertir AppEEARS en series o en estadística de área** (N1.3.0, N1.3B, N1.4C, N1.1D, B2.2, B9.3, B9.4) y otros 2 lo necesitan para una de sus ramas (LST en N1.1.0, área quemada en B9.1). Ese procesador (tareas EZE-12 y EZE-13) es el camino crítico del MVP. Solo N1.2.0, N1.2C, N1.4.0 y B3.5 pueden completarse con las series que ya existen.
