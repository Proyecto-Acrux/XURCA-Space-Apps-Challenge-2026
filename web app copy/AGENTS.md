# Web de presentación de XURCA

XURCA es el proyecto del equipo Acrux para el desafío Earth System Trend Detective de NASA Space Apps Challenge 2026. Esta carpeta contiene la web pública de presentación. La aplicación de análisis científico se desarrolla por separado.

- El contenido y la navegación viven en `index.html`. Usá `style.css` para el diseño adaptable, `src/main.js` para las interacciones y `assets/` para los recursos visuales.
- Trabajá con HTML semántico, CSS y JavaScript nativo. Mantené el contenido principal accesible con teclado y disponible con JavaScript desactivado. Respetá la preferencia de movimiento reducido.
- La referencia visual es Coinbase para la navegación, el espacio en blanco, la tipografía y el uso del azul. Mantené la identidad de XURCA y acreditá las imágenes y las fuentes científicas.
- Configurá el video y la descarga con URLs públicas HTTPS en `src/media.js`. Hasta entonces, la web indica el estado de la descarga y oculta el enlace al video. Distinguí las funciones previstas de las implementadas.
- Registrá los cambios en la rama de trabajo de GitHub. En Vercel, importá el repositorio y seleccioná `web app` como Root Directory. El sitio usa el preset Other, sin compilación y con salida en el propio directorio.
- Para revisar localmente, ejecutá `npx --yes serve . -l 8000` desde esta carpeta y abrí `http://localhost:8000`. Revisá la portada en escritorio y móvil, la navegación por teclado, las anclas y el estado de video y descarga cuando cambien.
