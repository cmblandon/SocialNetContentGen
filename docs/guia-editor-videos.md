# Guía del editor: aprobar guiones y generar videos

Cómo llevar un capítulo desde el guion generado hasta un video listo para
subir a TikTok o Instagram.

El flujo tiene tres pasos separados a propósito. Nada se encadena solo: si un
paso falla, se reintenta ese paso sin rehacer los anteriores.

```
Guion → aprobación → subtítulos → video
```

## Antes de empezar

El panel corre en `http://localhost:3000` y el servicio editorial en
`http://localhost:8000`. Necesitas FFmpeg instalado y las claves de
ElevenLabs en `.env` (ver README, sección "Video generation"). Sin clave de
Unsplash el sistema igual genera video: usa un fondo de color con el texto
encima.

## 1. Revisar y aprobar el guion

Entra a **Guiones** en el menú lateral. Cada tarjeta muestra el guion
completo, las indicaciones visuales, la cita de la fuente y el número de
palabras.

- **Aprobar guion** — habilita los pasos siguientes. Aprueba el guion para
  las cuatro plataformas a la vez, porque es el mismo texto.
- **Rechazar guion** — lo devuelve a pendiente.
- **Editar** — corrige el texto antes de aprobar.

> **Editar siempre reinicia la aprobación**, incluso si ya estaba aprobado.
> Es a propósito: el texto que se narra tiene que ser el texto que alguien
> leyó. Si editas un guion aprobado, vuelve a quedar pendiente y hay que
> aprobarlo de nuevo.

El contador de palabras es la referencia útil: entre **150 y 220 palabras**
es lo que cabe en un reel de 60 a 90 segundos leído a ritmo normal.

Puedes seleccionar varias tarjetas y usar **Aprobar seleccionados** para
aprobar en lote.

## 2. Revisar los subtítulos

En **Pipeline**, abre **Vista previa** en el capítulo. La sección de
subtítulos aparece solo cuando el guion está aprobado.

Pulsa **Generar subtítulos**. El sistema sintetiza la narración, mide cuánto
dura de verdad y reparte los tiempos según el largo de cada frase. Tarda unos
segundos.

Verás las pistas en español e inglés. El inglés es una traducción
automática: **revísalo**, es lo que va a quedar impreso en el video.

- **Editar Español / Editar Inglés** — cambia el texto de cada segmento.
- Los **tiempos no se pueden editar**. Se midieron sobre el audio real; si se
  tocaran, los subtítulos dejarían de coincidir con la voz.
- Ningún segmento puede quedar vacío.

Una pista corregida queda marcada como **Editado**, y esa versión es la que
se graba en el video. Volver a pulsar "Generar subtítulos" no borra tus
correcciones.

## 3. Generar el video

Debajo de los subtítulos, elige plataformas e idiomas.

- Por defecto: **las cuatro plataformas, solo en español**. El inglés se
  activa a mano, después de revisar sus subtítulos — generar los dos idiomas
  duplica el costo de narración.
- Pulsa **Generar video**. La respuesta es inmediata y el estado queda en
  **Generando…**; el video se arma en segundo plano.

El panel consulta el estado cada 5 segundos. Cuando termina, el estado pasa a
**Listo** y aparecen **Ver** (reproducir en el panel) y **Descargar**.

Si algo falla, el estado queda en **Falló** con el motivo (por ejemplo, cuota
de ElevenLabs agotada). Pulsa **Reintentar**: reutiliza el audio y la imagen
que ya se habían generado, así que un fallo al final no vuelve a cobrar la
narración.

> Si el video se queda en **Generando…** más de 5 minutos, el panel deja de
> consultar y ofrece **Actualizar estado**. Suele significar que el servidor
> se reinició a mitad del proceso; en ese caso, usa **Reintentar**.

## 4. Administrar los videos

La sección **Videos** lista todo lo generado, con filtros por plataforma,
idioma, estado y fecha.

- **Descargar** por video, o **Descargar todos** para bajar en lote los que
  estén listos.
- **Eliminar** borra el archivo y retira el video del listado. El registro se
  conserva para el historial. Si el archivo se conserva porque otro video lo
  sigue usando, el panel lo avisa.
- Arriba se ve el espacio usado y el **espacio libre en disco**, con aviso
  cuando queda poco.
- Si dice **"archivo faltante en disco"**, el video se generó pero el archivo
  ya no está: hay que regenerarlo.

## Problemas frecuentes

| Qué ves | Qué pasa |
|---|---|
| No aparece la sección de subtítulos | El guion no está aprobado todavía. |
| "Script must be approved…" | Editaste el guion después de aprobarlo; apruébalo de nuevo. |
| "…already has a 'generated' video…" | Ya existe un video para esa plataforma e idioma. Elimínalo antes de regenerar. |
| El video falla siempre en "visuals step" | Falta Pillow, o no se puede escribir en `data/videos_generated/`. |
| El video falla en "tts step" | Revisa `ELEVENLABS_API_KEY` y la cuota de la cuenta. |
| Todo falla apenas empieza | Comprueba que `ffmpeg` y `ffprobe` estén instalados (`ffmpeg -version`). |
