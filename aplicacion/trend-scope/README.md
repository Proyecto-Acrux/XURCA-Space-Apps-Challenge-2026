# Earth Detective

Primera versión de la aplicación de escritorio de XURCA para el desafío Earth System Trend Detective. El mapa detallado usa MapLibre y OpenFreeMap con datos de OpenStreetMap. Disponible con conexión y WebGL. El globo sin conexión usa Natural Earth a escala 1:110m. La app consulta NASA POWER, NOAA NCEI, SWOT Hydrocron y Open-Meteo (ERA5 y ERA5-Land) desde Python.

## Ejecutar en Windows

Con las dependencias preparadas, abrí **Iniciar Earth Detective.cmd**. En el panel derecho podés conectar Google Gemini u OpenAI con tu API key, describir una investigación y pedir explicaciones sobre los resultados. Seguí la [guía del chat de IA](docs/chat-ia.md).

Desde esta carpeta, con Node.js, pnpm, Rust con toolchain MSVC, Microsoft C++ Build Tools, WebView2 y una instalación de Python compatible con PyTauri:

```powershell
pnpm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .\src-tauri
$env:PYO3_PYTHON = (Get-Command python).Source
pnpm tauri dev
```

Tauri 2.8.3 se fija por compatibilidad con PyTauri 0.8. El archivo Cargo.lock conserva las versiones de las dependencias indirectas.

Para probar la interfaz en el navegador, usá `pnpm dev` y abrí `http://localhost:1420`. Este modo guarda la sesión en el almacenamiento del navegador. La aplicación nativa escribe `cfg_data.json` y `cfg_visual.json` en `%LOCALAPPDATA%\com.xurca.trend-scope`. El menú Proyecto permite guardar y recuperar ambos archivos. El menú Exportar permite descargar copias separadas.

## Consultar datos

1. Para POWER u Open-Meteo, marcá un punto, ingresá coordenadas o buscá una localidad o provincia argentina en Configuración geográfica. Georef centra el mapa y marca el centroide.
2. Elegí el período y agregá variables por fuente. NOAA requiere el ID de estación y SWOT el ID de tramo o lago.
3. Pulsá **Consultar datos** desde la app de escritorio.
4. Explorá la serie. Los resultados muestran unidades, cobertura mensual y el enlace a la solicitud original.
`pnpm check` comprueba el frontend y `pnpm build` genera `dist/`. Ambos son independientes del empaquetado de Python. Para distribución nativa consultá `scripts/README.md`.

La interfaz usa D3 Geo y Natural Earth para el globo ortográfico, Chart.js para las gráficas y Lucide para los iconos. Las configuraciones base están en `config/`. Los recursos científicos del desafío están en `Memoria/General/Recursos_Earth_System_Trend_Detective.txt` desde la raíz del repositorio.

Mirá [fuentes de datos](docs/fuentes-de-datos.md) para los requisitos de acceso y los campos de configuración.
