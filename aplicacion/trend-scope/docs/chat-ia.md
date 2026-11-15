# Trabajar con el chat de Earth Detective

Abrí `Iniciar Earth Detective.cmd` en la carpeta de la app. Inicia la versión de escritorio con Python; la primera compilación puede tardar. Conservá la terminal abierta mientras trabajás.

1. En el panel derecho, abrí **Conectar IA / cambiar proveedor**.
2. Elegí Google Gemini u OpenAI. El modelo propuesto puede reemplazarse por otro modelo del mismo proveedor que admita respuestas estructuradas.
3. Ingresá una API key obtenida en el portal del proveedor y pulsá **Conectar y verificar**. Se realiza una consulta breve que puede consumir cuota. Un correo o una cuenta del chat del proveedor no reemplazan la clave API.
4. Pedí, por ejemplo: «Quiero ver cómo cambió la temperatura en un punto de la ciudad de San Luis, Argentina, entre 2000 y 2024». El asistente pregunta cuando falta una precisión importante.
5. Los cambios válidos aparecen en los controles. Podés inspeccionar el JSON de cambios en el mensaje, modificar los controles o continuar: «Mejor desde 2010».
6. Pulsá **Procesar investigación**. La app consulta las fuentes y grafica una pestaña por serie.
7. Pulsá **Explicar resultados** o pedí conclusiones. La IA recibe estadísticas calculadas en Python sobre la serie completa, sus unidades, procedencia y límites. Si cambiás la investigación, hay que procesarla de nuevo.
8. Guardá desde **Proyecto**; el menú Exportar permite obtener los JSON completos. El JSON mostrado dentro del chat contiene solo el cambio aplicado, no el proyecto entero.

## Credenciales y proveedores

La clave ingresada se conserva únicamente en memoria de Python hasta cerrar el proceso o pulsar **Olvidar clave de esta sesión**. No se guarda en los JSON, el historial, el repositorio ni el instalador. Un intento de conexión fallido conserva la conexión anterior. Si hay claves configuradas en variables de entorno, olvidar la clave de sesión vuelve a esa configuración.

La app envía al proveedor elegido la pregunta, el contexto reciente, la configuración relevante y los resúmenes de resultados. Las series completas se procesan localmente. Los únicos adaptadores directos habilitados son Google y OpenAI; no se hace sustitución automática entre proveedores. Si no hay conexión propia, sigue disponible el servicio del equipo definido por `VITE_ASSISTANT_ENDPOINT`, cuando fue configurado durante la compilación.

## Qué hace y qué todavía no hace

- Configura variables del catálogo, punto o entidad, fechas y opciones visuales. Las fuentes se eligen por el catálogo, no por código generado por el modelo.
- Valida la propuesta en Python y el cambio completo en la interfaz antes de aplicarlo. La adquisición valida la configuración antes de consultar proveedores.
- Calcula cantidad de valores válidos/faltantes, promedio no ponderado, mínimo, máximo y pendiente lineal descriptiva sobre fechas reales, sin reducir la serie para el cálculo.
- Una pendiente no demuestra significancia estadística, causalidad ni constituye un pronóstico. No hay ajuste estacional, corrección de autocorrelación ni intervalo de confianza. El promedio no es un acumulado anual ni un promedio provincial. En series por pasada, fechas ausentes no necesariamente figuran como faltantes.
- Promedios por polígonos, pronósticos y selección/ejecución de métodos estadísticos personalizados siguen pendientes. Una consulta provincial no se sustituye implícitamente por un punto.
- El contexto del modelo incluye hasta cuatro resúmenes; si excede el presupuesto, se informa cuántas series se omitieron. El historial del chat dura la sesión del panel, mientras que la investigación se guarda desde Proyecto.

## Desarrollo y comprobaciones

El contrato común está en `services/assistant-contract.json` dentro de Python. `assistant_providers.py` implementa los transportes; OpenAI usa Responses y transforma los campos opcionales a nulables para su esquema estricto. `assistant.py` valida la salida. `evidence.py` calcula evidencia reproducible. `AssistantConnection.svelte` administra la conexión; `Assistant.svelte` comparte el estado con los controles y recibe solo resultados vigentes.

Desde la carpeta de la app:

```powershell
pnpm check
pnpm build
node --test src/lib/services/assistantConfiguration.test.js
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Las pruebas de proveedores simulan respuestas; no verifican credenciales, cuotas ni calidad de interpretación de un modelo real. La prueba en vivo se hace mediante **Conectar y verificar** y una conversación con la clave propia.

Referencias: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output), [prerrequisitos de Tauri](https://v2.tauri.app/start/prerequisites/).
