# Descargador para Android

App para bajar vídeos de **YouTube** y **TikTok** al móvil, en MP4 hasta 1080p o solo el audio en M4A.

## Instalar

1. Desde el móvil, abre la página de la versión **descargador-movil** en *Releases* del repo y toca **Descargador.apk**.
2. Ábrela. Si Android pregunta, permite instalar apps de esa fuente (Chrome o Archivos).
3. Para actualizar, instala la APK nueva encima. No hace falta desinstalar.

Necesita **Android 10** o más nuevo.

## Usar

- **Desde YouTube o TikTok:** toca *Compartir* → **Descargador**, y se pone a descargar sola.
- **O a mano:** copia el link, abre la app, toca **Pegar** y luego **Descargar**.
- Los vídeos van a **Películas/Descargador** (salen en la galería) y el audio a **Música/Descargador**.
- Mientras descarga, la pantalla se queda encendida para que Android no la corte.

## Cómo funciona por dentro

- **yt-dlp** (Python, metido en la app con [Chaquopy](https://chaquo.com/chaquopy/)) busca el vídeo y lo descarga.
  La app se baja sola la última versión oficial de yt-dlp, como mucho cada 12 horas, comprobada con su SHA-256. Se usa la próxima vez que abras la app.
- **QuickJS** es un motor de JavaScript pequeñito que yt-dlp necesita para YouTube. Se compila para el móvil al hacer la APK.
- **Android (MediaMuxer)** junta imagen y sonido sin recomprimir. Por eso el vídeo es H.264 (hasta 1080p en YouTube) y el audio es AAC (M4A): son los formatos que Android sabe juntar sin ffmpeg.

| Archivo | Qué hace |
|---|---|
| `app/src/main/python/movil.py` | Elige formato y descarga (yt-dlp) |
| `app/src/main/java/.../Trabajo.java` | Descarga en segundo plano y estado |
| `app/src/main/java/.../Muxer.java` | Junta vídeo + audio / saca solo el audio |
| `app/src/main/java/.../Guardar.java` | Guarda en la galería o en Música |
| `app/src/main/java/.../MainActivity.java` | La pantalla y el "Compartir" |
| `../.github/workflows/apk-descargador.yml` | Compila QuickJS y la APK, y la publica |

La clave de firma (`app/descargador.keystore`) está en el repo a propósito, para que todas las versiones tengan la misma firma y se actualicen encima. Al ser pública, **instala la app solo desde este repo**.

## Ojo

Descarga solo lo que tengas derecho a guardar. Bajar de YouTube va contra sus condiciones, y la música con copyright no se puede descargar sin permiso.
