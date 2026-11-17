# Descargador

Pega un link de YouTube (o de muchas otras webs) y bájate el **vídeo en MP4 hasta 4K** o el **audio en MP3/M4A**. Sin anuncios, sin webs raras: todo se instala desde PyPI, el repositorio oficial de Python.

## Instalación (solo la primera vez)

1. Instala **Python** desde <https://www.python.org/downloads/>.
   Durante la instalación marca la casilla **"Add python.exe to PATH"**.
2. Haz doble clic en **`Abrir descargador.bat`**.
   La primera vez tarda un par de minutos porque instala lo necesario.

Después, siempre se abre con ese mismo doble clic. Cada vez que lo abres se actualiza solo, para seguir funcionando cuando YouTube cambia cosas.

## Uso

1. Copia el link del vídeo y pulsa **Pegar**.
2. Elige **Vídeo MP4**, **Audio MP3** o **Audio M4A**.
3. Si es vídeo, elige la calidad (por defecto 1080p).
4. Pulsa **Descargar**. Se guarda en tu carpeta de Descargas, o en la que elijas con **Cambiar…**.

- **MP3:** se oye en cualquier sitio.
- **M4A:** es el audio tal cual viene de YouTube, sin recomprimir. Suena un poquito mejor y pesa menos.
- **Vídeo:** a igual resolución se prefiere H.264, que abre cualquier reproductor. En 1440p y 4K YouTube solo da VP9/AV1. Si tu reproductor no los abre, usa VLC.

## Qué usa por dentro

- [yt-dlp](https://github.com/yt-dlp/yt-dlp): la descarga.
- [imageio-ffmpeg](https://pypi.org/project/imageio-ffmpeg/): ffmpeg, para juntar imagen y sonido y para convertir a MP3.
- [deno](https://pypi.org/project/deno/): lo necesita yt-dlp para los vídeos de YouTube.

Se instala todo en `%LOCALAPPDATA%\Descargador`. Para desinstalarlo, borra esa carpeta y esta.

## Ojo

Descarga solo lo que tengas derecho a guardar: tus vídeos, contenido con licencia libre (Creative Commons, dominio público) o vídeos cuyo autor lo permita. Descargar de YouTube va contra sus condiciones de uso, y bajar música con copyright sin permiso no es legal.
