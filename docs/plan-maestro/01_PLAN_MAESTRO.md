# 01 — Plan maestro de arquitectura de XURCA

Fecha: 2026-11-15 · Estado: **propuesta para revisión del equipo** · Alcance: diseño y planificación; no se escribió código.

## 1. En una página

**Qué se encontró.** XURCA tiene tres activos valiosos que hoy no se tocan entre sí: un motor matemático amplio y probado (`models/`), dieciséis conectores a fuentes ambientales (diez dan series utilizables), y un catálogo científico de 73 fenómenos con reglas de qué puede y qué no puede afirmarse. La aplicación que ve el usuario usa solo los conectores y una regresión simple; el motor no está conectado y el catálogo no aparece en el código.

**Qué se propone.** Un **Algorithm Handler**: un orquestador que recibe una solicitud JSON única (venga del formulario o del asistente), la traduce a un plan científico —qué variables, de qué fuente, con qué preparación, con qué métodos ya registrados, en qué orden y con qué controles—, lo ejecuta y devuelve un resultado trazable con hallazgos, validaciones y metadatos de visualización.

**Las cinco ideas que sostienen el diseño:**

1. **Reutilizar, no reconstruir.** El Handler se apoya en el registro de métodos y en la función de ejecución que el motor ya tiene. No se modifica ningún algoritmo existente; lo que falta se agrega en archivos nuevos.
2. **El conocimiento científico es dato, no código.** Los 73 fenómenos, las variables y sus incompatibilidades, las recetas de análisis, las 18 reglas de calidad y las fuentes viven en archivos JSON versionados, revisables por la ingeniera química.
3. **Un solo contrato de entrada.** Formulario y asistente producen el mismo `AnalysisRequest`; los valores por defecto los aplica solo el backend. De ahí sale la paridad y la reproducibilidad.
4. **La honestidad científica está en el contrato.** Cada hallazgo declara su tipo (anomalía, tendencia, evento, asociación, pronóstico), su nivel de evidencia y las afirmaciones permitidas y prohibidas tomadas de la planilla. Un pronóstico no puede llamarse validado sin evidencia de backtesting.
5. **Se construye por recorridos completos.** Cuatro recorridos de punta a punta, cada uno demostrable antes de ampliar el siguiente.

**Lo que hay que saber antes de empezar:**

- **El camino crítico del MVP es convertir AppEEARS en series.** Siete de los trece fenómenos prioritarios dependen por completo de eso.
- **Hoy no existe ningún modelo predictivo ambiental.** Hay funciones de pronóstico genéricas sin validación fuera de muestra ni incertidumbre. Todo horizonte de la planilla es un horizonte *de prueba*.
- **Faltan documentos** que el superprompt da por existentes (anexo matemático, tabla de fuentes y conectores) y con ellos faltan los umbrales numéricos de historia mínima y horizontes. Esos valores quedan marcados como propuestos.
- **Hay 26 decisiones pendientes**; cinco bloquean el inicio (`21_RIESGOS_Y_DECISIONES.md`).

---

## 2. Arquitectura por capas

| Capa | Qué contiene | Estado | Dónde |
|---|---|---|---|
| **Presentación** | Mapa, gráficos, vistas de resultado, «Cómo se calculó» | Existe la base; faltan vistas científicas | `src/lib/components/` |
| **Interacción** | Configurador avanzado y asistente conversacional | Existen; hay que ampliarlos y hacerlos converger | `Settings.svelte`, `Assistant.svelte` |
| **Contratos** | `AnalysisRequest`, `AnalysisPlan`, `AnalysisResult`, `JobStatus`, descriptores, errores | **Nueva** | `handler/contracts.py` + JSON Schema |
| **Orquestación** | Algorithm Handler: intención, planificador, ejecutor | **Nueva** | `handler/` |
| **Conocimiento científico** | Fenómenos, variables, recetas, reglas QA, registros de algoritmos, modelos y fuentes | **Nueva** (derivada de los documentos) | `knowledge/` |
| **Datos** | Conectores, selección de fuentes y estaciones, preparación, QA de datos | Conectores existen; el resto es nuevo | `services/`, `dataprep/` |
| **Matemática** | Métodos estadísticos y numéricos | **Existe**; faltan ~9 algoritmos para el MVP | `models/` |
| **Predictiva** | Modelos, backtesting, intervalos, elegibilidad | Solo funciones genéricas; el resto es nuevo | `models/forecasting/`, `handler/model_registry.py` |
| **Validación** | Controles Q01–Q18, construcción de hallazgos | **Nueva** | `handler/validators.py`, `dataprep/qa.py` |
| **Ejecución** | Jobs, caché, reintentos, cancelación, progreso | **Nueva** (reusa la cancelación del motor) | `handler/jobs.py`, `cache.py`, `retry.py` |
| **Resultados** | Serialización, trazabilidad, metadatos de visualización | Serialización existe; el resto es nuevo | `handler/findings.py` |

No hay una clase o servicio por concepto: son once responsabilidades en **tres paquetes nuevos** (`handler/`, `knowledge/`, `dataprep/`) más ampliaciones acotadas de lo existente. Diagramas en `04_DIAGRAMAS.md`.

---

## 3. Decisiones de diseño y su justificación

| Tema | Decisión | Por qué | Alternativa descartada |
|---|---|---|---|
| **Modularidad** | Handler fuera de `models/`, como paquete propio | `models/` tiene reglas de protección y un alcance (algoritmos) distinto del de orquestar | Meter la orquestación dentro de `models/`: mezclaría responsabilidades y obligaría a tocar archivos protegidos |
| **Interfaces** | Contratos Pydantic en el borde; JSON Schema exportado para frontend e IA | Pydantic y jsonschema ya son dependencias; una sola fuente de verdad para tres consumidores | Mantener dicts sin esquema (estado actual): es la causa de las tres listas de fuentes divergentes |
| **Registros** | `AlgorithmRegistry` como vista sobre el registro existente; `ModelRegistry` separado | Una función matemática no es un modelo ambiental validado; mezclarlos invitaría a ofrecer pronósticos porque "existe SARIMA" | Un registro único |
| **Conocimiento** | Datos declarativos en JSON, verificados al arrancar | Lo revisa quien sabe de ciencia sin leer código; la IA y el formulario lo consumen igual | Reglas escritas en código o en un prompt |
| **Recetas** | Los fenómenos referencian recetas; las recetas referencian métodos | 73 fenómenos comparten ~17 patrones de análisis; agregar un fenómeno no requiere programar | Una función por fenómeno |
| **Separación de responsabilidades** | La IA propone, el backend decide, el motor calcula, el frontend muestra | Cada pieza se puede probar y reemplazar por separado; el sistema funciona sin IA | Que la IA elija métodos o que el frontend calcule |
| **Gestión de datos** | Los conectores se envuelven; la preparación es una capa común con operaciones registradas | Los conectores funcionan; lo que falta es uniformidad, trazabilidad y robustez | Reescribir conectores |
| **Selección de fuentes** | Filtros excluyentes por magnitud física + ordenamiento explicable; sustituciones siempre declaradas | La mayoría de los productos "requeridos" no está disponible como serie; sustituir en silencio sería deshonesto y rechazar todo, inútil | Tomar la primera fuente que responde |
| **Planificación** | DAG con nodos identificados por huella | Da deduplicación, reutilización, orden, paralelismo y procedencia con un solo mecanismo | Secuencia fija de pasos |
| **Caché** | Memoria por job + disco por huella, sin base de datos | Aplicación de escritorio de un usuario; los archivos alcanzan | SQLite o un servicio de caché |
| **Persistencia** | Archivos en el directorio de datos de la aplicación | El patrón de escritura atómica ya existe | Base de datos |
| **Trabajos** | Gestor en memoria con hilos y sondeo | `desktop.py` ya ejecuta en hilos con anyio; el motor ya soporta cancelación | Cola de tareas o procesos separados |
| **API** | Comandos PyTauri nuevos; ningún servidor HTTP | Es el puente que la aplicación ya usa | Agregar una API REST local |
| **Versionado** | `schema_version` por contrato; versión de `knowledge/`; versión de cada método y modelo en el resultado | Reproducir un análisis exige saber con qué se hizo | — |
| **Testing** | Conectores simulados + series sintéticas; las 21 pruebas de aceptación automatizadas | Permite CI sin red ni credenciales | Probar solo a mano con datos reales |
| **Seguridad** | Listas blancas de ids; `extra="forbid"`; sin evaluación dinámica; límites de recursos | Un JSON solo puede referenciar lo registrado | Aceptar nombres de función o expresiones en la solicitud |
| **Escalabilidad futura** | Interfaces que admiten crecer (más recetas, más fuentes, modelos regionales) sin tocar el núcleo | El primer objetivo es que funcione de punta a punta | Diseñar hoy para carga que no existe |
| **Tecnologías nuevas** | **Ninguna** para el Handler. Solo se discuten las opcionales ya probadas (D-06) y una posible biblioteca de ráster (D-10) | El pedido exige evaluar primero lo existente | — |

---

## 4. Cómo responde el diseño a las 20 preguntas de control

| # | Pregunta | Respuesta | Detalle |
|---|---|---|---|
| 1 | ¿Cómo se pasa de una consulta a un plan ejecutable? | Solicitud JSON → validación → forma canónica → resolución de intención → planificador (recetas → DAG). Cuatro pasos deterministas y sin red | `03` §3–§9 |
| 2 | ¿Cómo sabe qué variables necesita? | Las declara el fenómeno en `phenomena.json`, con su rol; en modalidad general, las da el usuario | `03` §6.1 |
| 3 | ¿Cómo determina qué fuentes puede usar? | `SourceSelector` sobre `sources.json`: magnitud exacta, estado de conexión, credenciales, geometría y cobertura temporal | `07` §5 |
| 4 | ¿Cómo distingue variables compatibles de las que no deben mezclarse? | Relaciones `not_interchangeable_with` en `variables.json`, con motivo; las aplica el selector, la intención y el formulario | `03` §6.2 |
| 5 | ¿Cómo selecciona los algoritmos? | No los elige libremente: los fija la receta; donde hay alternativas, la regla está escrita | `03` §7 |
| 6 | ¿Cómo reutiliza los algoritmos anteriores? | `AlgorithmDescriptor` → `scientific_registry()` → `analyze()`, mediante adaptadores; sin modificar el motor | `06` §7 |
| 7 | ¿Cómo relaciona los 73 fenómenos con las bibliotecas? | Fenómeno → receta(s) → métodos registrados | `05`, `03` §6.3 |
| 8 | ¿Cómo determina el análisis multivariable? | Cada fenómeno N2 declara hipótesis, roles, transformaciones, desfases y método | `05` (reglas de cruce) |
| 9 | ¿Cómo resuelve desfases y dependencias? | Desfases predefinidos por fenómeno + control de pruebas múltiples; dependencias por DAG | `03` §9; `05` |
| 10 | ¿Cómo integra los modelos predictivos? | `ModelRegistry` + receta `R-FORECAST` + dependencias M0–M6 ordenadas por el planificador | `08` |
| 11 | ¿Cómo define si una predicción está validada? | Puerta de elegibilidad de siete pasos; exige evidencia de backtesting con habilidad positiva | `03` §8.2; `08` §6 |
| 12 | ¿Cómo gestiona datos insuficientes o inaccesibles? | Errores tipados con alternativas; ramas independientes continúan; resultado parcial | `09` §9; `10` casos 7 y 4 |
| 13 | ¿Cómo propaga la incertidumbre? | Intervalos desde residuales fuera de muestra; miembros de ensemble compartidos aguas abajo; si no se propaga, se declara | `08` §7–§8 |
| 14 | ¿Cómo produce resultados reproducibles? | Huella canónica, plan determinista, versiones registradas, caché con fecha de obtención | `03` §13 |
| 15 | ¿Cómo convierte los resultados en JSON? | `findings.build` + serialización estricta existente → `AnalysisResult` | `09` §6 |
| 16 | ¿Cómo los interpreta la IA? | Recibe solo hallazgos, validaciones y procedencia; una guardia determinista verifica lo que redacta | `11` §A7–§A8 |
| 17 | ¿Cómo los visualiza el frontend? | Despachador por `VizHint.kind`; los algoritmos no conocen componentes gráficos | `11` §B3 |
| 18 | ¿Cómo se coordinan los cinco? | Propiedad por archivo, contratos primero, tablero por ID de tarea, demostración por recorrido | `18` |
| 19 | ¿Qué se programa primero? | CI y verificación de conectores → contratos → conocimiento → recorrido 1 | `12`; orden en cada backlog |
| 20 | ¿Qué pruebas demuestran la integración? | Diez casos end-to-end, 21 pruebas de aceptación, paridad T17, y capacidades que coinciden con lo ejecutable | `19` §11 |

**Preguntas que no pueden responderse del todo** y qué falta:

- **11 y 13, en lo numérico:** el mecanismo está definido, pero no los umbrales (historia mínima, tolerancia de cobertura, número de orígenes). Falta `ANEXO_MATEMATICO.md` o una definición de la ingeniera química (D-03, D-21).
- **8 y 9, para 32 fenómenos N2:** la estructura está; los desfases y las variables de confusión concretas de cada uno se completan cuando entran en una ola (D-03).

---

## 5. Qué se puede prometer y qué no

| Se puede | No se puede (hoy) |
|---|---|
| Tendencias de temperatura del aire y precipitación con Sen, Mann-Kendall e intervalo de confianza, al cerrar el recorrido 1 | Promedios sobre un área: hoy los datos son puntuales o de estación |
| Déficit y exceso pluviométrico (SPI), humedad del suelo modelada y nivel de agua, al cerrar el recorrido 2 | NDVI, LST, área quemada y cobertura hasta tener el procesador de AppEEARS |
| Los 73 fenómenos **clasificados** con su estado real desde la Fase 1 | Los 73 fenómenos **ejecutables**: 17 quedan fuera de alcance en la v1 |
| Un primer pronóstico (temperatura mensual) con su comparación honesta contra la climatología | Afirmar que ese pronóstico supera a la climatología antes de medirlo |
| Rechazos claros con alternativas | Predicción del lugar de una ignición, alertas operacionales, detección de floraciones tóxicas |

---

## 6. Próximos pasos

1. Los cinco leen `00_INDICE.md`, este documento y su propio backlog.
2. Reunión de decisiones: las cinco bloqueantes de `21` (D-01, D-04, D-06, D-15, D-16).
3. Revisión con la ingeniera química de `05_MATRIZ_FENOMENOS.md` (roles de N2, sustituciones de producto, decisiones científicas).
4. Aprobado el plan: versionar esta carpeta, activar protección de `main`, y comenzar por `EZE-18`, `EZE-19` y `EMA-01`.
