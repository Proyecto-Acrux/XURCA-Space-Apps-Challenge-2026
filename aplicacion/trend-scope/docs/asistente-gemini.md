# Prototipo del asistente con Gemini

## Probar la clave

Desde `aplicacion/trend-scope`, con el entorno virtual de la app preparado, ejecutá en PowerShell:

```powershell
.\.venv\Scripts\python.exe -m trend_scope.services.gemini
```

Pegá la clave de Google AI Studio cuando la terminal la pida y presioná Enter. La entrada se oculta. Si ya existe `GEMINI_API_KEY` en el entorno, el comando la usa directamente. La prueba manda a Google una pregunta de ejemplo y muestra la respuesta. La clave viaja en la cabecera de autenticación y queda fuera del código y de los archivos de proyecto.

Gemini 3.1 Flash-Lite tiene un nivel gratuito con cuotas por proyecto. Revisá el nivel y el consumo en Google AI Studio. Google indica que puede usar el contenido del nivel gratuito para mejorar sus productos. Para las primeras pruebas usá preguntas y datos públicos. [Precios](https://ai.google.dev/gemini-api/docs/pricing) · [Cuotas](https://ai.google.dev/gemini-api/docs/rate-limits)

## Primer flujo dentro de Earth Detective

El **Asistente de IA** aparece a la derecha del mapa. Escribí en el campo inferior. Podés seguir la conversación con aclaraciones o cambios sobre lo que ya configuraste.

1. Svelte envía la pregunta a Python por PyTauri con el catálogo, la configuración editable y el historial reciente. Gemini responde con texto y cambios estructurados.
2. Earth Detective valida las fuentes, las fechas, las selecciones geográficas y las preferencias visuales. Los cambios válidos actualizan el mismo estado editable que usan los controles manuales de `cfg_data.json` y `cfg_visual.json`. Podés revisar esos controles y guardar el proyecto desde el menú habitual.
3. **Procesar** consulta las fuentes configuradas y abre una pestaña por serie. La adquisición, el promedio por área y el cálculo estadístico son operaciones distintas. Los promedios por área y la ejecución de métodos estadísticos siguen pendientes. El comportamiento científico se rige por [SOUL.md](SOUL.md).

Para usar Gemini durante el desarrollo, leé la clave en la misma terminal que inicia Tauri. Por ejemplo, desde `aplicacion/trend-scope`, con Python y pnpm preparados como en el README:

```powershell
$earthGeminiSecret = Read-Host "Clave de Gemini" -AsSecureString
try {
    $env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $earthGeminiSecret).Password
    pnpm tauri dev
} finally {
    Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
    $earthGeminiSecret.Dispose()
}
```

## Publicar sin pedir una clave al usuario

El servicio para Cloudflare Workers está en [assistant-worker](../assistant-worker). Usá una cuenta del equipo en Workers Free y un proyecto Gemini que siga en el nivel gratuito. En AI Studio verificá los límites por minuto y día del modelo. Elegí topes conservadores que también respeten el límite de tokens por minuto. El Worker exige ambos topes y reserva cada pedido en un Durable Object. Una IP puede usar hasta un cuarto de la cuota configurada por día, redondeado hacia arriba.

Desde `aplicacion/trend-scope/assistant-worker`:

```powershell
npx.cmd --yes wrangler@4 login
$earthDaily = Read-Host "Tope de pedidos diarios del Worker"
$earthMinute = Read-Host "Tope de pedidos por minuto del Worker"
npx.cmd --yes wrangler@4 deploy --var "GEMINI_DAILY_LIMIT:$earthDaily" --var "GEMINI_MINUTE_LIMIT:$earthMinute"
npx.cmd --yes wrangler@4 secret put GEMINI_API_KEY
```

El último comando pide la clave de forma interactiva. Guardá la URL pública que imprime el despliegue y agregale `/interpret`. Para la prueba y el empaquetado, configurá esa URL en `VITE_ASSISTANT_ENDPOINT` antes de ejecutar `pnpm tauri dev` o el script de empaquetado. Vite incorpora la URL pública en la app. Las personas que instalen ese paquete usan el asistente sin cargar credenciales. Si el servicio llega a su cuota, pueden seguir configurando y procesando consultas desde los controles manuales. [Documentación de Wrangler](https://developers.cloudflare.com/workers/wrangler/commands/) · [Cuotas de Gemini](https://ai.google.dev/gemini-api/docs/rate-limits)

## Cobertura antes de consultar

Ampliar el catálogo existente para que cada combinación de producto y variable declare su cobertura temporal, alcance geográfico, resolución, tipo de selección, identificadores requeridos y estado del conector. Registrar la fuente de los metadatos y la fecha de verificación. Para fechas finales variables, registrar el retraso publicado o la última fecha comprobada.

Python cruza esos metadatos con la pregunta ya interpretada y devuelve el motivo de cada decisión. Puede señalar cobertura compatible según catálogo, cobertura parcial, selección incompatible, parámetros faltantes o cobertura sin verificar. Gemini explica esas opciones y pide las aclaraciones necesarias. La evaluación del catálogo puede ejecutarse localmente.

Los metadatos publicados permiten descartar combinaciones incompatibles sin descargar todas las series. La continuidad efectiva de una variable en una estación NOAA o las fechas observadas para un tramo SWOT pueden requerir un índice del proveedor o una consulta acotada. Una respuesta sin datos se distingue de un fallo del servicio. La app puede conservar el resultado de una comprobación local con su fecha y alcance.

Preparar el catálogo antes de empaquetar la app, con documentación oficial, índices del proveedor y comprobaciones directas en Python. Este mantenimiento se hace sin Gemini. El asistente recibe las conclusiones que produce la comprobación local. La app consulta al proveedor cuando necesita los valores o cuando el índice deja una duda que afecta la respuesta.

El inventario que usa Python está en [source-coverage.json](../src-tauri/src-python/trend_scope/services/source-coverage.json). Cubre las variables predefinidas de los cuatro conectores activos. Los códigos libres del proveedor y las entidades que no se hayan comprobado quedan con disponibilidad sin verificar. `collectionFrom` indica el inicio publicado para la colección. La disponibilidad efectiva de una variable de NOAA o SWOT depende de la estación, tramo o lago.

Ejemplo de prueba: ante «humedad de San Luis de 2000 a 2025», aclarar si se trata de humedad del aire o del suelo y si se pide un punto o un promedio provincial. Para humedad del suelo por punto, evaluar las capas de ERA5-Land y su cobertura antes de ofrecer una consulta. Para un promedio provincial, indicar que los conectores actuales trabajan por punto o identificador y explicar qué alcance tendría consultar un punto representativo.
