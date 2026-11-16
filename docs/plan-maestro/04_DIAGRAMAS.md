# 04 — Diagramas

Todos los diagramas están en Mermaid. Los componentes con borde punteado **no existen todavía**.

## D1 — Arquitectura general de componentes

```mermaid
flowchart TB
  subgraph PRES["Presentación (SvelteKit)"]
    MAP["Mapa y capas"]
    CFG["Configurador avanzado"]
    CHAT["Chat del asistente"]
    RES["Vistas de resultados"]
    HOW["Panel «Cómo se calculó»"]
  end

  subgraph INTER["Interacción"]
    RB["requestBuilder<br/>(formulario → AnalysisRequest)"]
    AI["Asistente IA<br/>(texto → AnalysisRequest)"]
  end

  subgraph API["Comandos PyTauri"]
    CMD["get_capabilities · validate_request · plan_analysis<br/>submit_analysis · job_status · job_result · cancel_job"]
  end

  subgraph HANDLER["Algorithm Handler"]
    CON["Contratos y forma canónica"]
    INT["Resolución de intención"]
    PLAN["Planificador DAG"]
    EXEC["Ejecutor y jobs"]
    VAL["Validadores Q01–Q18"]
    FIND["Hallazgos y resultado"]
  end

  subgraph KNOW["Conocimiento científico (JSON)"]
    PH["73 fenómenos"]
    VARS["Variables"]
    REC["Recetas"]
    QA["Reglas QA"]
    AR["AlgorithmRegistry"]
    MR["ModelRegistry y elegibilidad"]
    SRC["SourceRegistry"]
  end

  subgraph DATA["Datos"]
    SEL["Selección de fuentes y estaciones"]
    CONN["16 conectores"]
    PREP["Preparación: unidades, calendario,<br/>agregación, alineación, QA"]
    CACHE["Caché en disco"]
  end

  subgraph MATH["Motor matemático existente (models/)"]
    REG["scientific_registry()"]
    ANA["analyze()"]
    NEW["Algoritmos nuevos<br/>(archivos nuevos)"]
  end

  subgraph PRED["Predicción"]
    BT["Backtesting e intervalos"]
    FC["forecast (existente)"]
  end

  CFG --> RB
  CHAT --> AI
  RB --> CMD
  AI --> CMD
  CMD --> CON --> INT --> PLAN --> EXEC --> VAL --> FIND --> CMD
  CMD --> RES
  CMD --> HOW
  RES --> MAP

  INT -.consulta.-> PH
  INT -.consulta.-> VARS
  PLAN -.consulta.-> REC
  PLAN -.consulta.-> AR
  PLAN -.consulta.-> MR
  PLAN -.consulta.-> SRC
  VAL -.consulta.-> QA

  EXEC --> SEL --> CONN
  CONN --> PREP
  PREP --> CACHE
  EXEC --> ANA
  AR -.envuelve.-> REG
  REG --> ANA
  NEW -.registro aditivo.-> REG
  EXEC --> BT --> FC

  AI -.contexto.-> CMD

  classDef nuevo stroke-dasharray: 5 5;
  class RB,HOW,CMD,CON,INT,PLAN,EXEC,VAL,FIND,PH,VARS,REC,QA,AR,MR,SRC,SEL,PREP,CACHE,NEW,BT nuevo;
```

## D2 — Flujo de una consulta

```mermaid
flowchart TD
  A["Solicitud JSON<br/>(manual o IA)"] --> B{"¿Cumple el esquema?"}
  B -- No --> E1["INVALID_REQUEST"]
  B -- Sí --> C["Normalización canónica<br/>defaults + huella"]
  C --> D{"¿Falta información<br/>que se pueda preguntar?"}
  D -- Sí --> M["missing[] → aclaración<br/>(IA) o campo marcado (formulario)"]
  D -- No --> F{"¿Hay fenómeno<br/>del catálogo?"}
  F -- Sí --> G["Recetas del fenómeno"]
  F -- No --> H{"¿Viable como<br/>análisis general?"}
  H -- No --> E2["UNSUPPORTED<br/>+ alternativas viables"]
  H -- Sí --> G2["Receta general<br/>(exploratoria)"]
  G --> I["Selección de fuentes<br/>por variable"]
  G2 --> I
  I --> J{"¿Fuente utilizable?"}
  J -- "Portal / sin API" --> E3["NOT_AUTOMATABLE"]
  J -- "Sin credencial" --> E4["CREDENTIALS_MISSING"]
  J -- "Período no cubierto" --> E5["TEMPORAL_INCOMPATIBLE<br/>+ fuente alternativa"]
  J -- Sí --> K["Construcción del DAG<br/>+ controles + elegibilidad"]
  K --> L["AnalysisPlan"]
  L --> N["Ejecución<br/>(caché, reintentos, cancelación)"]
  N --> O["Controles Q sobre datos y resultados"]
  O --> P["Hallazgos con afirmaciones<br/>permitidas y prohibidas"]
  P --> Q["AnalysisResult"]
  Q --> R["Gráficos, mapas, advertencias"]
  Q --> S["Explicación de la IA"]
  E3 --> PART["Rama bloqueada;<br/>las demás continúan"]
  E4 --> PART
  E5 --> PART
  PART --> K
```

## D3 — Dependencias científicas (familias predictivas)

```mermaid
flowchart LR
  ING["Ingesta, QA, climatologías,<br/>fechas de disponibilidad"]
  M1["M1 · Meteorología<br/>T2m, precipitación"]
  M0["M0 · Indicadores<br/>anomalías, SPI"]
  M2["M2 · Estado hídrico<br/>humedad del suelo"]
  M3["M3 · Vegetación<br/>NDVI, EVI"]
  M4["M4 · Temperatura superficial<br/>LST"]
  F1["F1 · Histórico de fuego<br/>detecciones, FRP, área (capas separadas)"]
  M5["M5 · FWI diario"]
  M6A["M6A · Actividad de fuego<br/>(probabilidad de evento)"]
  M6B["M6B · Área quemada regional"]
  F5["F5 · Recuperación espectral"]
  GATE["Calibración y puerta<br/>de elegibilidad por horizonte"]

  ING --> M1
  ING --> F1
  M1 --> M0
  M1 --> M2
  M1 --> M3
  M2 --> M3
  M1 --> M4
  M2 --> M4
  M3 --> M4
  M1 --> M5
  M5 --> M6A
  M2 --> M6A
  M3 --> M6A
  F1 --> M6A
  M6A --> M6B
  F1 --> M6B
  M3 --> F5
  F1 --> F5
  M0 --> GATE
  M3 --> GATE
  M4 --> GATE
  M6A --> GATE
  M6B --> GATE
  F5 --> GATE
```

Sin ciclos: no hay realimentación fuego → clima. M3 y M4 no requieren ejecutar M5 ni M6B.

## D4 — Módulos del backend

```mermaid
flowchart TB
  DESK["desktop.py<br/>comandos PyTauri"]

  subgraph H["handler/"]
    SVC["service.py"]
    CONT["contracts.py · errors.py"]
    CAN["canonical.py"]
    KN["knowledge.py"]
    INTE["intent.py"]
    PL["planner.py"]
    EX["executor.py"]
    VA["validators.py"]
    FI["findings.py"]
    CAP["capabilities.py"]
    ALR["algorithm_registry.py"]
    MOR["model_registry.py"]
    SOR["source_registry.py"]
    JB["jobs.py"]
    CA["cache.py"]
    RT["retry.py"]
    AD["adapters/"]
    OPS["ops/"]
  end

  subgraph K["knowledge/"]
    KJ["phenomena · variables · recipes<br/>qa_rules · models · sources (.json)"]
  end

  subgraph DP["dataprep/"]
    DPS["series · units · calendar · aggregate<br/>align · qa · zonal · stations"]
  end

  subgraph SV["services/ (existente)"]
    ACQ["acquisition.py y conectores"]
    AST["assistant*.py"]
    EVI["evidence.py"]
  end

  subgraph MM["models/ (existente, protegido)"]
    SR["extended_registry.scientific_registry"]
    AN["execution.analyze"]
    CT["contracts.py (v1)"]
    NW["archivos nuevos:<br/>climate/ · forecasting/ · stats/…"]
  end

  DESK --> SVC
  DESK --> AST
  DESK --> ACQ
  SVC --> CONT
  SVC --> CAN --> INTE --> PL --> EX
  SVC --> CAP
  SVC --> JB --> EX
  EX --> OPS
  EX --> CA
  EX --> RT
  EX --> VA --> FI
  KN --> KJ
  INTE --> KN
  PL --> KN
  PL --> ALR
  PL --> MOR
  PL --> SOR
  CAP --> KN
  OPS --> DPS
  OPS --> AD
  OPS --> SOR
  SOR --> ACQ
  AD --> CT
  AD --> AN
  ALR --> SR
  NW --> SR
```

Propiedad: **Ema** — `service`, `contracts`, `errors`, `canonical`, `knowledge`, `intent`, `planner`, `executor`, `validators`, `findings`, `capabilities`, `algorithm_registry`, `model_registry`, `adapters/`, y todo `models/`. **Eze** — `source_registry`, `jobs`, `cache`, `retry`, `dataprep/`, `services/` (conectores). **`ops/`** se reparte por archivo. **JP** — `services/assistant*.py` y `assistant-contract.json` (decisión D-15).

## D5 — Integración frontend / IA / backend

```mermaid
flowchart LR
  subgraph FE["Frontend"]
    WS["store workspace<br/>(cfg_data v2)"]
    FORM["Configurador<br/>(José)"]
    ASSIST["Chat<br/>(JP)"]
    BUILD["requestBuilder<br/>(José)"]
    APIJS["analysisApi.js<br/>(Juan)"]
    JOBS["store de jobs<br/>(Juan)"]
    VIEWS["Vistas de resultado<br/>(Juan)"]
  end

  subgraph BE["Backend"]
    CAPS["get_capabilities"]
    VALI["validate_request"]
    PLANC["plan_analysis"]
    SUB["submit_analysis"]
    STAT["job_status / job_result"]
    INTERP["interpret_question"]
  end

  LLM["Proveedor de LLM<br/>(Gemini / OpenAI / otro)"]

  FORM --> WS
  ASSIST -- "propuesta validada" --> WS
  WS --> BUILD --> APIJS
  APIJS --> VALI
  APIJS --> PLANC
  APIJS --> SUB
  SUB --> JOBS
  JOBS --> STAT
  STAT --> VIEWS

  CAPS --> FORM
  CAPS --> ASSIST
  ASSIST --> INTERP --> LLM
  INTERP -. "esquema de AnalysisRequest<br/>+ capacidades" .-> LLM
  VIEWS -- "AnalysisResult" --> ASSIST
```

Punto clave: **el asistente y el formulario escriben en el mismo store**; la solicitud siempre la arma `requestBuilder`. La IA no tiene un camino propio hacia el backend.

## D6 — Secuencia: modo manual

```mermaid
sequenceDiagram
  actor U as Usuario avanzado
  participant F as Configurador
  participant B as requestBuilder
  participant A as analysisApi
  participant H as Handler
  participant D as Conectores
  participant M as Motor matemático

  F->>A: get_capabilities()
  A->>H: get_capabilities
  H-->>F: fenómenos, variables, fuentes, límites
  U->>F: elige ubicación, período, fenómeno, opciones
  F->>B: cfg_data v2
  B->>A: AnalysisRequest
  A->>H: validate_request
  H-->>F: defaults aplicados, faltantes, advertencias
  U->>F: «Ver plan»
  A->>H: plan_analysis
  H-->>F: AnalysisPlan (fuentes, pasos, bloqueos)
  U->>F: «Procesar»
  A->>H: submit_analysis(wait_ms)
  H-->>A: JobStatus (job_id)
  loop hasta terminar
    A->>H: job_status
    H->>D: fetch (caché / reintentos)
    D-->>H: series
    H->>M: analyze()
    M-->>H: AnalysisResult interno
    H-->>A: progreso
  end
  A->>H: job_result
  H-->>F: AnalysisResult
  F-->>U: gráficos, hallazgos, advertencias, «Cómo se calculó»
```

## D7 — Secuencia: modo conversacional

```mermaid
sequenceDiagram
  actor U as Usuario
  participant C as Chat
  participant I as interpret_question
  participant L as LLM
  participant H as Handler
  participant W as store workspace
  participant B as requestBuilder

  U->>C: pregunta en lenguaje natural
  C->>H: get_capabilities(scope)
  H-->>C: capacidades vigentes
  C->>I: pregunta + capacidades + estado actual
  I->>L: instrucciones + esquema de salida
  L-->>I: { message, request_patch, clarifications }
  I->>I: validación de esquema
  I-->>C: propuesta
  alt faltan datos
    C-->>U: pregunta de aclaración
    U->>C: respuesta
  else propuesta completa
    C->>H: validate_request(propuesta)
    H-->>C: válido / faltantes / UNSUPPORTED + alternativas
    C->>W: aplicar propuesta
    C-->>U: resumen de lo que se va a analizar
    U->>C: confirma
    W->>B: cfg_data v2
    B->>H: submit_analysis
    H-->>C: AnalysisResult
    C->>I: resultado (hallazgos, validaciones, afirmaciones permitidas)
    I->>L: instrucciones de explicación
    L-->>I: explicación
    I->>I: guardia de afirmaciones
    I-->>C: explicación verificada
    C-->>U: explicación + enlaces a gráficos y a «Cómo se calculó»
  end
```

## D8 — Ejecución predictiva

```mermaid
flowchart TD
  A["Solicitud con horizonte"] --> B{"¿El fenómeno admite<br/>predicción en el catálogo?"}
  B -- "historical_only" --> X1["No se planifica predicción;<br/>análisis histórico"]
  B -- Sí --> C{"¿Hay ModelDescriptor para<br/>variable, frecuencia y escala?"}
  C -- No --> X2["MODEL_NOT_ELIGIBLE<br/>+ alternativa histórica"]
  C -- Sí --> D["Datos históricos:<br/>fetch → normalize → qa"]
  D --> E{"¿Historia y cobertura<br/>suficientes?"}
  E -- No --> X3["Descriptivo o baseline rotulado"]
  E -- Sí --> F["Predictores con available_at"]
  F --> G{"¿Disponibles en<br/>la fecha de emisión?"}
  G -- "No" --> X4["LEAKAGE_BLOCKED:<br/>se excluye el predictor"]
  X4 --> H
  G -- Sí --> H{"¿Backtest en caché para<br/>esta serie, modelo y horizonte?"}
  H -- No --> I["Backtest rolling-origin<br/>(transformaciones dentro de cada pliegue)"]
  H -- Sí --> J
  I --> J{"¿Skill > 0 vs baseline<br/>y cobertura en tolerancia?"}
  J -- No --> X5["Se muestra el baseline<br/>not_superior_to_baseline"]
  J -- Sí --> K{"¿Horizonte pedido ≤<br/>horizonte validado?"}
  K -- No --> L["Tramo validado: validated_forecast<br/>Resto: exploratory_extrapolation (sin intervalo)"]
  K -- Sí --> N["Ajuste final + predicción"]
  L --> N
  N --> O["Intervalos desde residuales<br/>fuera de muestra"]
  O --> P{"¿Alimenta a otro modelo?"}
  P -- Sí --> Q["Mismos member_id aguas abajo;<br/>horizonte = mínimo de la cadena"]
  P -- No --> R["ForecastBlock:<br/>modo, cuantiles, skill, cobertura, baseline"]
  Q --> R
  S["Supuestos explícitos<br/>del usuario"] --> T["conditional_scenario"]
  T --> R
```

## D9 — DAG del Caso 2 (precipitación, humedad del suelo y NDVI)

Ilustra reutilización de nodos y ramas independientes.

```mermaid
flowchart LR
  f1["fetch P<br/>(Open-Meteo/ERA5)"] --> n1["normalize<br/>mm/día → mm/mes"] --> q1["qa Q01 Q05 Q11"]
  f2["fetch humedad 28–100 cm<br/>(ERA5-Land)"] --> n2["normalize"] --> q2["qa Q01 Q11"]
  f3["fetch NDVI<br/>(AppEEARS MOD13Q1)"] --> n3["normalize + máscara QA"] --> q3["qa Q01 Q06"]

  q1 --> c1["climatología"] --> a1["anomalía P"]
  q2 --> c2["climatología"] --> a2["anomalía humedad"]
  q3 --> c3["climatología"] --> a3["anomalía NDVI"]

  q1 --> t1["tendencia P<br/>Sen + MK"]

  a1 --> al["align<br/>mensual, escala más gruesa"]
  a2 --> al
  a3 --> al

  al --> lc["correlación con<br/>desfases predefinidos"]
  lc --> fdr["FDR"]
  al --> reg["regresión con rezagos<br/>(multivariable)"]
  fdr --> v["validate<br/>Q03 Q04 Q09 Q10 Q13 Q17"]
  reg --> v
  t1 --> v
  v --> as["assemble"]
```

El nodo de precipitación se descarga **una vez** y alimenta la tendencia y la asociación. Si falla NDVI, la rama de tendencia de precipitación igual se completa y el resultado es `partial`; el planificador genera además un nodo `align` por cada subconjunto de variables que la receta declare analizable por separado (aquí, precipitación–humedad), de modo que esa asociación no dependa de NDVI.
