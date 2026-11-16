# 20 — Plan de integración y flujo en GitHub

## 1. Situación actual

- Ramas remotas: `main`, `ema_workspace`, `eze_w`, `API`, `Primeros_pasos_Appweb`. **`main` contiene a todas**: ninguna tiene commits pendientes.
- Los documentos científicos de la raíz y `models/CLAUDE.md`, `models/stats/AGENTS.md` están **sin versionar**.
- No hay CI de pruebas; el flujo de publicación está en una subcarpeta donde GitHub probablemente no lo detecta.
- Esta carpeta `docs/plan-maestro/` es nueva y **no fue confirmada ni publicada**.

## 2. Principios

1. **Preservar todo el trabajo existente.** Sin cambios destructivos, sin reescritura de historia, **sin `push --force`** en ramas compartidas.
2. **`main` siempre utilizable.** Lo nuevo convive con lo heredado (`acquire_data` sigue funcionando) hasta que el recorrido correspondiente esté completo.
3. **Integración frecuente y pequeña.** Ramas cortas, una tarea por PR.
4. **Los contratos mandan.** Nadie cambia un contrato sin avisar a quien lo consume.

## 3. Estructura de ramas

```
main                          protegida; solo por PR
 └─ feat/<persona>/<ID>-<descripcion-corta>     una por tarea del backlog
 └─ fix/<persona>/<descripcion-corta>
 └─ docs/<descripcion-corta>
```

Ejemplos: `feat/ema/EMA-01-contratos`, `feat/eze/EZE-06-seleccion-estaciones`, `feat/juan/JUAN-04-serie-tendencia`.

- **Sin rama de integración intermedia.** Con cinco personas, contratos estables y vía heredada intacta, una rama `dev` solo agregaría fusiones. Si en la Fase 7 hiciera falta estabilizar, se crea una rama `release/…` temporal.
- Las ramas personales existentes (`ema_workspace`, `eze_w`) pueden seguir como espacio de trabajo local, pero **no se integran directamente**: se abre una rama de tarea desde `main`.
- Las ramas `API` y `Primeros_pasos_Appweb` no tienen nada que `main` no tenga: se pueden archivar cuando el equipo lo decida (no es urgente ni necesario).

## 4. Propiedad de módulos

Archivo `CODEOWNERS` en la raíz, derivado de `18_MATRIZ_RESPONSABILIDADES.md`. GitHub pedirá revisión automática al propietario.

| Ruta | Propietario |
|---|---|
| `aplicacion/trend-scope/src-tauri/src-python/trend_scope/models/` | Ema |
| `…/trend_scope/handler/` | Ema (salvo los archivos de Eze) |
| `…/handler/jobs.py`, `cache.py`, `retry.py`, `source_registry.py` | Eze |
| `…/trend_scope/knowledge/` | Ema (`sources.json`: Eze) |
| `…/trend_scope/dataprep/`, `…/services/` (salvo `assistant*`) | Eze |
| `…/services/assistant*`, `gemini.py`, `assistant-contract.json` | JP (+ Ema como revisora) |
| `…/handler/contracts.py`, `schemas/`, `fixtures/` | Ema **+ una persona de IA/frontend** |
| `aplicacion/trend-scope/src/lib/components/results/`, `services/analysisApi*`, `stores/analysis.js` | Juan |
| `…/components/Settings.svelte`, `components/config/`, `services/requestBuilder.js`, `configuration.js`, `i18n.js`, `stores/workspace.js`, `routes/` | José |
| `…/components/Assistant*.svelte`, `services/assistantConfiguration.js`, `assistant-worker/` | JP |
| `.github/`, `pyproject.toml`, `package.json` | Eze (frontend: Juan como revisor) |

## 5. Pull Requests

**Título:** `[ID] descripción` (p. ej. `[EZE-06] Selección de estaciones por puntaje`).

**Plantilla del cuerpo:**

```markdown
## Qué hace
## Tarea(s) del backlog
## Contratos afectados          (ninguno / cuáles y por qué)
## Cómo se probó                (pruebas automáticas + prueba manual con fecha)
## Archivos protegidos          (¿toca algo de PRESERVATION.json? Debe ser "no")
## Capturas                     (si hay cambios de interfaz)
## Pendiente / fuera de alcance
```

**Tamaño:** una tarea por PR. Un algoritmo por PR (regla de `models/CLAUDE.md`). Los cambios de contrato van en un PR propio, antes del código que los usa.

## 6. Revisión de código

| Tipo de cambio | Revisores mínimos |
|---|---|
| Backend general | 1: la otra persona de backend |
| Algoritmo nuevo en `models/` | 1 de backend, **distinta del autor**, que verifique la prueba contra referencia independiente |
| Contratos, esquemas, ejemplos fijos | 1 de backend + 1 de IA/frontend |
| Frontend general | 1 del equipo IA/frontend |
| Asistente (instrucciones, guardia) | 1 de IA/frontend + Ema para lo que toque `services/` |
| `knowledge/phenomena.json`, `qa_rules.json` | Ema + revisión de la ingeniera química (puede ser fuera de GitHub, registrada en el PR) |
| Dependencias, CI, empaquetado | Eze + 1 más |

Qué mira el revisor: que el cambio corresponda a la tarea; pruebas con casos extremos; que no haya valores científicos inventados (todo umbral cita su origen); que no se toquen archivos ajenos sin acuerdo; que no haya credenciales.

## 7. Pruebas previas a la integración

Puertas automáticas (CI, tarea EZE-18), obligatorias para fusionar:

1. `pytest` sin pruebas de red.
2. `pnpm check` y `node --test`.
3. Validación de ejemplos fijos contra los JSON Schema.
4. Verificación de integridad de `knowledge/` (73 fenómenos, referencias resueltas).
5. Verificación de que ningún archivo listado en `PRESERVATION.json` cambió (salvo PR con la etiqueta de excepción aprobada).

Puertas manuales según el caso: prueba con datos reales para conectores; guion funcional para cambios de interfaz.

## 8. Protección de los algoritmos existentes

| Medida | Detalle |
|---|---|
| `PRESERVATION.json` como fuente de verdad | Lista de archivos protegidos y sus huellas |
| Verificación en CI | Recalcula las huellas con finales de línea normalizados (el repositorio usa CRLF en Windows) y falla si alguna difiere |
| Excepción explícita | Modificar un archivo protegido requiere: decisión registrada en `21`, etiqueta en el PR, dos revisores y actualización de la huella en el mismo PR |
| Código nuevo siempre en archivos nuevos | Los algoritmos faltantes no editan los existentes |
| Primer paso | Resolver la discrepancia ya existente de `dynamical/multi_ode.py` (D-07) para que la verificación arranque en verde |

## 9. Resolución de conflictos

1. **Prevenir:** propiedad de archivos, PR pequeños, y sincronizar la rama con `main` antes de pedir revisión (`git merge main` o `git rebase main` **solo en la rama propia y antes de compartirla**).
2. **Quién resuelve:** el autor del PR, consultando al propietario del archivo en conflicto.
3. **Conflictos en contratos o en `knowledge/`:** se resuelven en conversación entre los involucrados, no eligiendo "la mía" o "la suya".
4. **Nunca** `push --force` a `main` ni a una rama que otra persona esté usando.
5. Si una fusión rompe `main`: se revierte el commit de fusión (`git revert`), se corrige en la rama y se vuelve a abrir el PR.

## 10. Política de incorporación a `main`

- `main` protegida: sin push directo; PR con las revisiones de §6 y CI en verde.
- Fusión con commit de fusión o *squash* según prefiera el equipo, de forma uniforme; el ID de la tarea queda en el mensaje.
- Mensajes de commit descriptivos, en el estilo que ya usa el repositorio.
- **Etiquetas** al cerrar cada recorrido (`r1-una-variable`, `r2-multivariable`, …) para poder volver a un estado conocido.
- El código nuevo que todavía no completa un recorrido puede integrarse si **no altera** el comportamiento existente (los comandos nuevos devuelven ejemplos fijos o `UNSUPPORTED` hasta estar listos).

## 11. Cómo se conectan los componentes desarrollados en paralelo

| Paso | Qué se conecta | Cómo se comprueba |
|---|---|---|
| 1 | Contratos ↔ todos | Ejemplos fijos validan en CI en ambos lenguajes |
| 2 | Frontend ↔ comandos esqueleto | La interfaz corre en la aplicación de escritorio contra ejemplos servidos por el backend (ya no por la simulación del navegador) |
| 3 | Planificador ↔ selector de fuentes | `plan_analysis` del Caso 1 coincide con el ejemplo |
| 4 | Ejecutor ↔ JobManager ↔ caché | Caso 1 con conector simulado; cancelación; segunda ejecución desde caché |
| 5 | Ejecutor ↔ conector real | Caso 1 con NASA POWER (prueba con red) |
| 6 | Resultado real ↔ vistas | Comparación del resultado real con el ejemplo fijo; se corrige el que esté mal |
| 7 | Asistente ↔ capacidades reales | Suite de comportamiento contra capacidades reales |
| 8 | Asistente ↔ formulario ↔ backend | T17 |
| 9 | Línea predictiva ↔ vistas | Caso 3 |
| 10 | Todo | Los 10 casos en la aplicación empaquetada |

**Regla de sustitución de simulaciones:** cada simulación del frontend se retira en el mismo PR que demuestra que el comando real devuelve algo equivalente al ejemplo.

## 12. Primeras acciones en el repositorio (cuando el equipo apruebe el plan)

1. Decidir si se versionan los documentos científicos de la raíz (D-04). Recomendado: sí, porque `knowledge/` deriva de ellos.
2. Confirmar esta carpeta `docs/plan-maestro/` en una rama `docs/plan-maestro` y abrir PR para revisión de los cinco. **No se ha hecho: el plan está solo en el disco local.**
3. Activar la protección de `main` y agregar `CODEOWNERS`.
4. EZE-18 (CI) antes que cualquier otra tarea de código.
