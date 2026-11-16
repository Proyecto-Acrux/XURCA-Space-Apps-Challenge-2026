# Plan maestro XURCA — Índice

**Arquitectura, integración científica y plan de desarrollo del Algorithm Handler.**

Fecha: 2026-11-15 · Commit auditado: `c8f6555` (`main`) · Estado: **propuesta para revisión; no aprobada**.

> Esta carpeta contiene **solo documentación de planificación**. No se modificó código de producción, no se tocó ningún algoritmo, no se ejecutaron tests ni benchmarks, y nada fue confirmado ni publicado en GitHub.

## Cómo leerlo

| Si sos… | Leé en este orden |
|---|---|
| **Cualquiera de los cinco** | `01` (plan maestro) → `21` (decisiones pendientes) → tu backlog → `18` (responsabilidades) |
| **Ema** | + `03`, `06`, `08`, `05`, `09`, `13` |
| **Eze** | + `07`, `03` §10, `09`, `14` |
| **JP** | + `11` parte A, `09`, `10`, `15` |
| **Juan** | + `11` parte B, `09` §6, `10`, `16` |
| **José** | + `11` parte B, `09` §2–§4 y §12, `10`, `17` |
| **Ingeniera química** | `05` (matriz de fenómenos y reglas de cruce) → `08` → `21` parte A, decisiones científicas |

## Documentos

| # | Documento | Contenido | Entregable del pedido |
|---|---|---|---|
| 00 | `00_INDICE.md` | Este índice | Índice |
| 01 | [`01_PLAN_MAESTRO.md`](01_PLAN_MAESTRO.md) | Resumen, capas, decisiones de diseño justificadas, respuesta a las 20 preguntas de control | 62 · arquitectura definitiva |
| 02 | [`02_AUDITORIA.md`](02_AUDITORIA.md) | Inventario del repositorio y de los documentos; hechos, faltantes y 22 contradicciones | 61 · informe de auditoría |
| 03 | [`03_ALGORITHM_HANDLER.md`](03_ALGORITHM_HANDLER.md) | Módulos, interfaces, registros, intención, planificador, ejecutor, validadores, seguridad | 63 · diseño interno del Handler |
| 04 | [`04_DIAGRAMAS.md`](04_DIAGRAMAS.md) | Nueve diagramas Mermaid (los ocho obligatorios y un DAG de ejemplo) | 69 · diagramas de flujo y DAG |
| 05 | [`05_MATRIZ_FENOMENOS.md`](05_MATRIZ_FENOMENOS.md) | Los 73 fenómenos: tabla científica, tabla de integración y reglas de cruce | 64 · matriz de 73 fenómenos |
| 06 | [`06_MATRIZ_ALGORITMOS.md`](06_MATRIZ_ALGORITMOS.md) | Inventario clasificado A–E, algoritmos faltantes, adaptadores | 65 · matriz de algoritmos |
| 07 | [`07_MATRIZ_FUENTES.md`](07_MATRIZ_FUENTES.md) | 16 conectores, productos X01–X29, descriptor, selección de fuentes y estaciones, preparación | 66 · matriz de fuentes |
| 08 | [`08_MATRIZ_PREDICTIVA.md`](08_MATRIZ_PREDICTIVA.md) | PRED-01 a 08, familias M0–M6, elegibilidad, validación, incertidumbre | 67 · matriz predictiva |
| 09 | [`09_CONTRATOS_JSON_API.md`](09_CONTRATOS_JSON_API.md) | Contratos con campos, tipos y ejemplos; errores; comandos | 68 · contratos JSON y API |
| 10 | [`10_CASOS_DE_USO.md`](10_CASOS_DE_USO.md) | Diez casos end-to-end con sus diez apartados | Parte XIV |
| 11 | [`11_INTEGRACION_IA_FRONTEND.md`](11_INTEGRACION_IA_FRONTEND.md) | Asistente, capacidades, guardia de afirmaciones, configurador, vistas, «Cómo se calculó» | Partes XI y XII |
| 12 | [`12_ROADMAP.md`](12_ROADMAP.md) | Fases, recorridos, olas de fenómenos, estados de madurez | 70 · roadmap técnico |
| 13 | [`13_BACKLOG_EMA.md`](13_BACKLOG_EMA.md) | 32 tareas | 71, 73 |
| 14 | [`14_BACKLOG_EZE.md`](14_BACKLOG_EZE.md) | 22 tareas | 71, 73 |
| 15 | [`15_BACKLOG_JP.md`](15_BACKLOG_JP.md) | 12 tareas | 71, 73 |
| 16 | [`16_BACKLOG_JUAN.md`](16_BACKLOG_JUAN.md) | 14 tareas | 71, 73 |
| 17 | [`17_BACKLOG_JOSE.md`](17_BACKLOG_JOSE.md) | 13 tareas | 71, 73 |
| 18 | [`18_MATRIZ_RESPONSABILIDADES.md`](18_MATRIZ_RESPONSABILIDADES.md) | Propietario y colaboradores por componente; coordinación | 72 · matriz de responsabilidades |
| 19 | [`19_PLAN_TESTING.md`](19_PLAN_TESTING.md) | Niveles de prueba; Q01–Q18 y T01–T21 convertidos en pruebas | Partes X y XVIII |
| 20 | [`20_PLAN_INTEGRACION_GITHUB.md`](20_PLAN_INTEGRACION_GITHUB.md) | Ramas, PR, revisión, protección de algoritmos, conexión de componentes | 74 · plan de integración |
| 21 | [`21_RIESGOS_Y_DECISIONES.md`](21_RIESGOS_Y_DECISIONES.md) | 26 decisiones pendientes y 42 riesgos | 75 · riesgos y decisiones |
| 22 | [`22_BARRIDO_CIENCIA_VS_CODIGO.md`](22_BARRIDO_CIENCIA_VS_CODIGO.md) | Contraste método por método entre la planilla y el código; origen de la cola de trabajo de Codex (`trend_scope/models/AGENTS.md`) | Pedido posterior |

## Lo esencial en diez líneas

1. El motor matemático existe y está probado, pero **la aplicación no lo usa**; el catálogo de 73 fenómenos **no está en el código**.
2. El **Algorithm Handler** es un paquete nuevo que orquesta sin reescribir: reutiliza el registro de métodos y la función de ejecución existentes.
3. El conocimiento científico (fenómenos, variables, recetas, reglas, fuentes) pasa a ser **datos versionados**.
4. Formulario y asistente producen **el mismo JSON**; el backend aplica los valores por defecto.
5. Cada resultado dice **qué tipo de hallazgo es, con qué evidencia, y qué se puede y no se puede afirmar**.
6. No hay API HTTP: son **comandos PyTauri** nuevos, con jobs asíncronos por sondeo.
7. **Diez de dieciséis conectores** dan series; el procesador de AppEEARS es el **camino crítico** del MVP.
8. **No existe ningún modelo predictivo ambiental**; un pronóstico solo será "validado" con evidencia de backtesting.
9. Se construye en **cuatro recorridos de punta a punta**; el frontend y la IA trabajan desde el inicio contra contratos y ejemplos fijos.
10. Hay **cinco decisiones que bloquean el arranque** y faltan documentos con los umbrales numéricos.

## Identificadores usados en el plan

| Prefijo | Significado | Dónde se definen |
|---|---|---|
| `N1.x`, `Bx.y` | Fenómenos del catálogo (ids originales) | `05` |
| `X01`–`X29`, `C01`–`C13` | Productos y recursos de competencia de la planilla | `07` |
| `PRED-01`–`08`, `M0`–`M6B`, `F1`, `F5` | Líneas y familias predictivas | `08` |
| `Q01`–`Q18`, `T01`–`T21` | Controles de calidad y pruebas de aceptación | `19` |
| `N01`–`N16` | Algoritmos faltantes | `06` §5 |
| `R-…` | Recetas de análisis | `03` §6.3 |
| `R1`–`R4` | Recorridos end-to-end | `12` |
| `O1`–`O7`, `X` | Olas de desarrollo de fenómenos | `12` §3 |
| `L1`–`L4` | Preparación de un fenómeno para integrarse | `05` |
| `EMA-`, `EZE-`, `JP-`, `JUAN-`, `JOSE-` | Tareas de backlog | `13`–`17` |
| `C01`–`C22` (en `02`) | Contradicciones entre documentos | `02` §10 |
| `D-01`–`D-26` | Decisiones pendientes | `21` parte A |
| `R-01`–`R-42` | Riesgos | `21` parte B |

*Nota: `C01`–`C13` designa recursos de competencia en la planilla y `C01`–`C22` contradicciones en la auditoría; el contexto los distingue (los primeros aparecen solo en `07` y `05`).*

## Qué se verificó y qué no

| Verificado leyendo código o documentos | No verificado |
|---|---|
| Estructura del repositorio, comandos, conectores, motor, asistente, frontend | Que los tests existentes pasen: **no se ejecutaron** (las cifras citadas son las que declaran los documentos del repositorio) |
| Contenido de las 8 hojas de la planilla, el catálogo, el superprompt y el inventario | El comportamiento real de los conectores contra los proveedores |
| Coherencia de los 73 ids entre catálogo, texto simplificado y planilla | El defecto de `geometryId` nulo: está **inferido** del código, no reproducido |
| Discrepancia de huella de `multi_ode.py` | Rendimiento de cualquier componente |

Documentos que el pedido menciona y **no existen** en el repositorio: `ANEXO_MATEMATICO.md`, `FUENTES_Y_CONECTORES.csv`, la hoja `Ruteo_Competencia_73` y la imagen del esquema conceptual. Su efecto sobre el diseño está en `02` §9.
