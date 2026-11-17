"""Lógica de descarga (sin ventana) del Descargador.

Usa yt-dlp para bajar el vídeo o el audio, el ffmpeg de imageio-ffmpeg para
juntar imagen y sonido o convertir a MP3, y deno para que yt-dlp pueda
resolver los vídeos de YouTube. Todo se instala desde PyPI; no hay que
bajar nada de webs raras.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable

import yt_dlp

MODOS = {
    'video': 'Vídeo MP4',
    'mp3': 'Audio MP3',
    'm4a': 'Audio M4A (original, sin recomprimir)',
}

# Altura máxima en píxeles; None = la mejor que haya.
CALIDADES = {
    'Máxima disponible': None,
    '2160p (4K)': 2160,
    '1440p (2K)': 1440,
    '1080p (Full HD)': 1080,
    '720p (HD)': 720,
    '480p': 480,
}


class Cancelado(Exception):
    pass


@dataclass
class Progreso:
    porcentaje: float | None  # 0-100, o None si no se sabe
    texto: str


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None  # yt-dlp buscará un ffmpeg instalado en el sistema


def _deno() -> str | None:
    try:
        import deno
        return deno.find_deno_bin()
    except Exception:
        return None


def _bytes(n: float | None) -> str:
    if not n:
        return '?'
    for unidad in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unidad == 'GB':
            return f'{n:.0f} {unidad}' if unidad == 'B' else f'{n:.1f} {unidad}'
        n /= 1024
    return '?'


def construir_opciones(modo: str, altura: int | None, carpeta: str, lista: bool,
                       hook: Callable[[dict], None], pp_hook: Callable[[dict], None]) -> dict:
    opts: dict = {
        'paths': {'home': carpeta},
        'outtmpl': '%(title)s.%(ext)s',
        'windowsfilenames': True,
        'noplaylist': not lista,
        'progress_hooks': [hook],
        'postprocessor_hooks': [pp_hook],
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'retries': 5,
        'fragment_retries': 5,
        'concurrent_fragment_downloads': 4,
    }
    ffmpeg = _ffmpeg()
    if ffmpeg:
        opts['ffmpeg_location'] = ffmpeg
    deno = _deno()
    if deno:
        opts['js_runtimes'] = {'deno': {'path': deno}}

    if modo == 'video':
        # Mejor imagen + mejor sonido por separado y luego se juntan en un MP4.
        # A igual resolución se prefiere H.264, que se abre en cualquier reproductor.
        orden = [f'res:{altura}'] if altura else ['res']
        opts['format'] = 'bv*+ba/b'
        opts['format_sort'] = orden + ['vcodec:h264', 'acodec:m4a']
        opts['merge_output_format'] = 'mp4'
    elif modo == 'mp3':
        opts['format'] = 'ba/b'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0',  # VBR de máxima calidad
        }, {'key': 'FFmpegMetadata'}]
    elif modo == 'm4a':
        opts['format'] = 'ba[ext=m4a]/ba/b'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }, {'key': 'FFmpegMetadata'}]
    else:
        raise ValueError(f'modo desconocido: {modo}')
    return opts


def descargar(url: str, modo: str, altura: int | None, carpeta: str, lista: bool,
              al_progresar: Callable[[Progreso], None],
              cancelar: threading.Event) -> list[str]:
    """Descarga y devuelve las rutas de los archivos terminados.

    Lanza Cancelado si se pulsa cancelar y yt_dlp.utils.DownloadError si falla.
    """
    terminados: list[str] = []
    a_medias: set[str] = set()  # archivos temporales, para borrarlos si se cancela

    def hook(d: dict) -> None:
        if cancelar.is_set():
            raise Cancelado()
        estado = d.get('status')
        if d.get('tmpfilename'):
            a_medias.add(d['tmpfilename'])
        if estado == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            hecho = d.get('downloaded_bytes') or 0
            pct = (hecho / total * 100) if total else None
            vel = d.get('speed')
            texto = f'Descargando… {_bytes(hecho)} de {_bytes(total)}'
            if vel:
                texto += f'  ·  {_bytes(vel)}/s'
            al_progresar(Progreso(pct, texto))
        elif estado == 'finished':
            al_progresar(Progreso(100, 'Descarga terminada, preparando el archivo…'))

    def pp_hook(d: dict) -> None:
        if cancelar.is_set():
            raise Cancelado()
        if d.get('status') == 'started':
            nombres = {
                'Merger': 'Juntando imagen y sonido…',
                'ExtractAudio': 'Convirtiendo el audio…',
                'Metadata': 'Guardando título y artista…',
            }
            texto = nombres.get(d.get('postprocessor', ''), 'Procesando…')
            al_progresar(Progreso(None, texto))

    opts = construir_opciones(modo, altura, carpeta, lista, hook, pp_hook)
    opts['post_hooks'] = [terminados.append]  # recibe la ruta final de cada archivo
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as err:
        causa = getattr(err, 'exc_info', None)
        if isinstance(err, Cancelado) or (causa and isinstance(causa[1], Cancelado)):
            for ruta in a_medias:
                for sobra in (ruta, ruta + '.ytdl'):
                    try:
                        os.remove(sobra)
                    except OSError:
                        pass
            raise Cancelado() from None
        raise
    return terminados
