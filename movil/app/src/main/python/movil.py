"""Cerebro del Descargador para Android.

Lo llama MainActivity (Java) a través de Chaquopy. Aquí solo se elige el
formato y se descarga con yt-dlp; juntar imagen y sonido y guardar en la
galería lo hace Java (Muxer.java y Guardar.java), porque en el móvil no
hay ffmpeg.

Funciones que usa Java:
  preparar(files_dir, cache_dir) -> versión de yt-dlp en uso
  actualizar(files_dir)          -> texto con lo que pasó (se aplica al reabrir)
  descargar(url, modo, altura, carpeta, qjs, cb) -> JSON con el resultado
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request

ZIP = 'yt-dlp-actual.zip'
URL_ZIP = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp'
URL_SUMAS = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS'
CADA = 12 * 3600  # como mucho, buscar actualización cada 12 horas


class Cancelado(Exception):
    pass


# ---------------------------------------------------------------- arranque

def preparar(files_dir: str, cache_dir: str) -> str:
    """Pone a punto Python. Hay que llamarla antes que nada."""
    os.environ['TMPDIR'] = cache_dir
    tempfile.tempdir = cache_dir
    os.environ.setdefault('HOME', files_dir)

    zip_nuevo = os.path.join(files_dir, ZIP)
    if os.path.exists(zip_nuevo):
        sys.path.insert(0, zip_nuevo)
        try:
            modulo = importlib.import_module('yt_dlp')
            bueno = (getattr(modulo, '__file__', '') or '').startswith(zip_nuevo)
        except Exception:
            bueno = False
        if not bueno:
            # La actualización está rota: se vuelve a la versión que trae la APK.
            sys.path.remove(zip_nuevo)
            for nombre in [m for m in sys.modules if m.split('.')[0] in ('yt_dlp', 'yt_dlp_ejs')]:
                del sys.modules[nombre]
            os.remove(zip_nuevo)
    import yt_dlp
    return yt_dlp.version.__version__


def _bajar(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': 'Descargador-Android'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def actualizar(files_dir: str) -> str:
    """Baja la última versión oficial de yt-dlp si hay una nueva.

    Se comprueba con el SHA-256 que publica yt-dlp. Se usa al abrir la app
    la próxima vez (Python no puede cambiar yt-dlp en caliente).
    """
    marca = os.path.join(files_dir, 'ultima-comprobacion')
    try:
        if time.time() - os.path.getmtime(marca) < CADA:
            return 'comprobado hace poco'
    except OSError:
        pass

    sumas = _bajar(URL_SUMAS, 30).decode('utf-8', 'replace')
    esperado = next((linea.split()[0] for linea in sumas.splitlines()
                     if linea.strip().endswith(' yt-dlp')), None)
    if not esperado:
        return 'no encontré la suma de comprobación'

    destino = os.path.join(files_dir, ZIP)
    actual = None
    if os.path.exists(destino):
        with open(destino, 'rb') as f:
            actual = hashlib.sha256(f.read()).hexdigest()
    if actual == esperado:
        _tocar(marca)
        return 'ya tienes la última'

    datos = _bajar(URL_ZIP, 120)
    if hashlib.sha256(datos).hexdigest() != esperado:
        return 'la descarga no coincide con la suma; no se instala'
    temporal = destino + '.nuevo'
    with open(temporal, 'wb') as f:
        f.write(datos)
    os.replace(temporal, destino)
    _tocar(marca)
    return 'actualizado (se usará al volver a abrir la app)'


def _tocar(ruta: str) -> None:
    with open(ruta, 'w') as f:
        f.write(str(time.time()))


# ---------------------------------------------------------------- descarga

def _formato(modo: str, altura: int) -> tuple[str, list[str]]:
    """Formatos que Android sabe juntar sin ffmpeg: H.264 + AAC en MP4."""
    h264 = "[vcodec~='^(avc|h264)']"
    if modo == 'audio':
        return "ba[acodec^=mp4a]/ba[ext=m4a]/b[ext=mp4]/ba/b", ['acodec:aac', 'abr']
    filtro = f'[height<={altura}]' if altura else ''
    spec = '/'.join([
        f'bv*{h264}[ext=mp4]{filtro}+ba[acodec^=mp4a]',
        f'b{h264}[ext=mp4]{filtro}',
        f'b[ext=mp4]{filtro}',
        f'bv*{h264}[ext=mp4]+ba[acodec^=mp4a]',
        'b[ext=mp4]',
        'b',
    ])
    orden = [f'res:{altura}'] if altura else ['res']
    return spec, orden + ['vcodec:h264', 'acodec:aac']


def _texto_error(err: Exception) -> str:
    texto = str(err).replace('ERROR: ', '')
    texto = re.sub(r'^\[[^\]]+\] [^:]*: ', '', texto)        # "[youtube] abc123: "
    texto = re.sub(r'\s*\(caused by .*$', '', texto, flags=re.S)  # detalles técnicos
    bajo = texto.lower()
    if 'http error 404' in bajo or 'http error 410' in bajo:
        return 'Ese link no existe o ya no está disponible.'
    if 'unsupported url' in bajo or 'is not a valid url' in bajo:
        return 'Ese link no lo reconozco. Copia el link completo del vídeo.'
    if 'private video' in bajo or 'account is private' in bajo:
        return 'Ese vídeo o esa cuenta es privada.'
    if 'confirm your age' in bajo:
        return 'Ese vídeo tiene restricción de edad y pide iniciar sesión.'
    if 'video unavailable' in bajo or 'not available in your' in bajo or 'ip address is blocked' in bajo:
        return 'Ese vídeo no está disponible (borrado, privado o bloqueado en tu país).'
    if 'not a bot' in bajo or 'sign in to confirm' in bajo:
        return 'YouTube pide comprobar que no eres un robot. Espera un rato y prueba otra vez.'
    if ('unable to extract' in bajo or 'unable to find' in bajo or 'challenge' in bajo
            or 'extractor error' in bajo):
        return ('No pude leer ese vídeo; la web habrá cambiado algo. Cierra la app del todo, '
                'ábrela otra vez (así se actualiza) y prueba de nuevo.')
    if 'getaddrinfo' in bajo or 'timed out' in bajo or 'network is unreachable' in bajo:
        return 'No pude conectarme. Revisa tu internet.'
    return texto


def _bytes(n) -> str:
    if not n:
        return '?'
    n = float(n)
    for unidad in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unidad == 'GB':
            return f'{n:.0f} {unidad}' if unidad == 'B' else f'{n:.1f} {unidad}'
        n /= 1024
    return '?'


def descargar(url: str, modo: str, altura: int, carpeta: str, qjs: str | None, cb) -> str:
    """Descarga a `carpeta` y devuelve un JSON.

    cb es un objeto Java con progreso(int porcentaje, String texto) y
    cancelado() -> boolean. porcentaje = -1 significa "sin porcentaje".

    Respuesta: {"titulo": ..., "partes": [{"ruta", "video", "audio", "ext"}]}
               o {"error": "..."} o {"cancelado": true}
    """
    import yt_dlp

    paso = {'n': 1, 'de': 1}

    def hook(d):
        if cb.cancelado():
            raise Cancelado()
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            hecho = d.get('downloaded_bytes') or 0
            pct = int(hecho * 100 / total) if total else -1
            texto = f'Descargando… {_bytes(hecho)} de {_bytes(total)}'
            if d.get('speed'):
                texto += f'  ·  {_bytes(d["speed"])}/s'
            if paso['de'] > 1:
                texto = ('Imagen' if paso['n'] == 1 else 'Sonido') + f' ({paso["n"]}/{paso["de"]})  ·  ' + texto
            cb.progreso(pct, texto)

    spec, orden = _formato(modo, int(altura or 0))
    opts = {
        'format': spec,
        'format_sort': orden,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'progress_hooks': [hook],
        'retries': 5,
        'fragment_retries': 5,
        'cachedir': os.path.join(os.environ.get('HOME') or carpeta, 'cache-yt-dlp'),
        'remote_components': ['ejs:github'],
    }
    if qjs and os.path.exists(qjs):
        opts['js_runtimes'] = {'quickjs': {'path': qjs}}

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            cb.progreso(-1, 'Buscando el vídeo…')
            info = ydl.extract_info(url, download=False, process=False)
            if info and info.get('_type') in ('playlist', 'multi_video'):
                return json.dumps({'error': 'Ese link es una playlist o un perfil. '
                                            'Abre el vídeo que quieras y copia su link.'})
            info = ydl.process_ie_result(info, download=False)
            if info and info.get('_type') in ('playlist', 'multi_video'):
                return json.dumps({'error': 'Ese link es una playlist o un perfil. '
                                            'Abre el vídeo que quieras y copia su link.'})

            partes = info.get('requested_formats') or [info]
            paso['de'] = len(partes)
            resultado = []
            for i, f in enumerate(partes, 1):
                paso['n'] = i
                datos = dict(info)
                datos.pop('requested_formats', None)
                datos.update(f)
                ext = f.get('ext') or 'mp4'
                ruta = os.path.join(carpeta, f'parte{i}.{ext}')
                ok, _ = ydl.dl(ruta, datos)
                if not ok or not os.path.exists(ruta):
                    return json.dumps({'error': 'La descarga se cortó. Prueba otra vez.'})
                resultado.append({
                    'ruta': ruta,
                    'ext': ext,
                    # None = no se sabe; Java mira las pistas reales del archivo.
                    'video': f.get('vcodec') != 'none',
                    'audio': f.get('acodec') != 'none',
                })
            return json.dumps({'titulo': info.get('title') or info.get('id') or 'video',
                               'partes': resultado}, ensure_ascii=False)
    except Cancelado:
        return json.dumps({'cancelado': True})
    except Exception as err:  # noqa: BLE001 — el mensaje se le enseña al usuario
        causa = getattr(err, 'exc_info', None)
        if causa and isinstance(causa[1], Cancelado):
            return json.dumps({'cancelado': True})
        return json.dumps({'error': _texto_error(err)}, ensure_ascii=False)


def limpiar(carpeta: str) -> None:
    shutil.rmtree(carpeta, ignore_errors=True)
    os.makedirs(carpeta, exist_ok=True)
