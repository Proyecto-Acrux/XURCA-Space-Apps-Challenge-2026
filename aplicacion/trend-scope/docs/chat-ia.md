# Trabajar con el chat de Earth Detective

Abrí `Iniciar Earth Detective.cmd` en la carpeta de la app. Inicia la versión de escritorio con Python; la primera compilación puede tardar. Conservá la terminal abierta mientras trabajás.

1. Escribí en el panel derecho, por ejemplo «Quiero ver la radiación solar en San Luis capital y 9 de Julio, Buenos Aires, de 2005 a 2024».
2. Los cambios válidos aparecen en los controles. Podés continuar con «Mejor desde 2010».
3. Pulsá **Procesar investigación** para consultar las fuentes. Las pestañas muestran el nombre del lugar cuando la selección tiene uno. Para etiquetar un área dibujada, editá la selección y completá **Nombre del lugar**.
4. Pulsá **Explicar resultados** o pedí conclusiones. Si cambiás la investigación, procesala de nuevo.
5. Guardá desde **Proyecto**.

Ante una interrupción temporal o una propuesta inválida, la app intenta recuperar la consulta una vez. Si el problema sigue, **Reintentar consulta** vuelve a enviar el pedido y conserva el historial.

## Servicio del equipo

La app usa Gemini a través de https://gemini-tauri-api.bilbaojuani.workers.dev. Envía un POST con `prompt` y valida la propuesta contenida en `answer`. La clave `GEMINI_API_KEY` se guarda como secreto del Worker.

## Qué hace y qué todavía no hace

- Configura variables del catálogo, punto o entidad, fechas y opciones visuales. Las fuentes se eligen por el catálogo, no por código generado por el modelo.
- Valida la propuesta en Python y el cambio completo en la interfaz antes de aplicarlo. La adquisición valida la configuración antes de consultar proveedores.
- Calcula cantidad de valores válidos/faltantes, promedio no ponderado, mínimo, máximo y pendiente lineal descriptiva sobre fechas reales, sin reducir la serie para el cálculo.
- Una pendiente no demuestra significancia estadística, causalidad ni constituye un pronóstico. No hay ajuste estacional, corrección de autocorrelación ni intervalo de confianza. El promedio no es un acumulado anual ni un promedio provincial. En series por pasada, fechas ausentes no necesariamente figuran como faltantes.
- Promedios por polígonos, pronósticos y selección/ejecución de métodos estadísticos personalizados siguen pendientes. Una consulta provincial no se sustituye implícitamente por un punto.
- El contexto del modelo incluye hasta cuatro resúmenes; si excede el presupuesto, se informa cuántas series se omitieron. El historial del chat dura la sesión del panel, mientras que la investigación se guarda desde Proyecto.

## Desarrollo y comprobaciones

El Worker envía el contrato común a Gemini. Python valida la respuesta y la interfaz valida los cambios antes de aplicarlos. Los cálculos científicos quedan en Python.

Desde la carpeta de la app:

```powershell
pnpm check
pnpm build
node --test src/lib/services/assistantConfiguration.test.js
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Las pruebas de proveedores simulan respuestas; no verifican credenciales, cuotas ni calidad de interpretación de un modelo real. La prueba en vivo se hace mediante **Conectar y verificar** y una conversación con la clave propia.


## Lugares escritos en el chat

El asistente puede resolver uno o varios nombres de localidades mediante el buscador geográfico. Incluí provincia y país cuando haya homónimos. Las coordenadas corresponden a puntos de referencia de las localidades, no a promedios de sus áreas. Para varios lugares se crea una serie por fuente y punto (hasta 25 series). Una búsqueda ambigua o fallida no aplica cambios parciales. La disponibilidad de estaciones NOAA se comprueba al procesar.
