"""Descargador: pega un link y bájate el vídeo en HD o el audio en MP3.

Se abre con "Abrir descargador.bat" (Windows), que instala lo necesario.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yt_dlp

import nucleo

AJUSTES = Path.home() / '.descargador-ajustes.json'


def carpeta_por_defecto() -> str:
    descargas = Path.home() / 'Downloads'
    return str(descargas if descargas.is_dir() else Path.home())


def leer_ajustes() -> dict:
    try:
        return json.loads(AJUSTES.read_text(encoding='utf-8'))
    except Exception:
        return {}


def guardar_ajustes(datos: dict) -> None:
    try:
        AJUSTES.write_text(json.dumps(datos, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass


def abrir_carpeta(ruta: str) -> None:
    try:
        if sys.platform.startswith('win'):
            os.startfile(ruta)  # type: ignore[attr-defined]
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', ruta])
        else:
            subprocess.Popen(['xdg-open', ruta])
    except Exception:
        pass


def mensaje_de_error(err: Exception) -> str:
    texto = str(err).replace('ERROR: ', '')
    bajo = texto.lower()
    if 'unsupported url' in bajo or 'is not a valid url' in bajo:
        return 'Ese link no lo reconozco. Copia el link completo del vídeo y vuelve a probar.'
    if 'private video' in bajo:
        return 'Ese vídeo es privado, no se puede descargar.'
    if 'sign in to confirm your age' in bajo:
        return 'Ese vídeo tiene restricción de edad y YouTube pide iniciar sesión.'
    if 'video unavailable' in bajo:
        return 'Ese vídeo no está disponible (borrado, bloqueado en tu país o privado).'
    if 'sign in to confirm' in bajo or 'not a bot' in bajo:
        return ('YouTube está pidiendo comprobar que no eres un robot. Espera un rato, '
                'cierra y vuelve a abrir el descargador (así se actualiza) y prueba otra vez.')
    if 'ip address is blocked' in bajo or 'not available in your' in bajo:
        return 'Ese vídeo no está disponible en tu país.'
    if 'account is private' in bajo:
        return 'Esa cuenta es privada, no se pueden descargar sus vídeos.'
    if 'unable to extract' in bajo or 'unable to find' in bajo:
        return ('No pude leer ese vídeo; puede que la web haya cambiado algo. Cierra y vuelve a abrir '
                'el descargador (así se actualiza) y prueba otra vez.')
    if 'unable to download' in bajo or 'getaddrinfo' in bajo or 'timed out' in bajo:
        return 'No pude conectarme. Revisa tu internet y vuelve a probar.'
    return texto


class App:
    def __init__(self, raiz: tk.Tk) -> None:
        self.raiz = raiz
        self.cola: queue.Queue = queue.Queue()
        self.cancelar = threading.Event()
        self.trabajando = False
        ajustes = leer_ajustes()

        raiz.title('Descargador')
        raiz.minsize(520, 0)
        raiz.columnconfigure(0, weight=1)

        marco = ttk.Frame(raiz, padding=16)
        marco.grid(sticky='nsew')
        marco.columnconfigure(1, weight=1)

        ttk.Label(marco, text='Link del vídeo:').grid(row=0, column=0, sticky='w')
        self.url = tk.StringVar()
        entrada = ttk.Entry(marco, textvariable=self.url)
        entrada.grid(row=0, column=1, sticky='ew', padx=(8, 8))
        ttk.Button(marco, text='Pegar', command=self.pegar).grid(row=0, column=2)
        entrada.focus_set()
        entrada.bind('<Return>', lambda _e: self.empezar())

        ttk.Label(marco, text='Quiero:').grid(row=1, column=0, sticky='w', pady=(12, 0))
        self.modo = tk.StringVar(value=ajustes.get('modo', 'video'))
        filas_modo = ttk.Frame(marco)
        filas_modo.grid(row=1, column=1, columnspan=2, sticky='w', padx=(8, 0), pady=(12, 0))
        for clave, nombre in nucleo.MODOS.items():
            ttk.Radiobutton(filas_modo, text=nombre, value=clave, variable=self.modo,
                            command=self.actualizar_calidad).pack(anchor='w')

        ttk.Label(marco, text='Calidad:').grid(row=2, column=0, sticky='w', pady=(12, 0))
        self.calidad = tk.StringVar(value=ajustes.get('calidad', '1080p (Full HD)'))
        if self.calidad.get() not in nucleo.CALIDADES:
            self.calidad.set('1080p (Full HD)')
        self.combo_calidad = ttk.Combobox(marco, textvariable=self.calidad, state='readonly',
                                          values=list(nucleo.CALIDADES))
        self.combo_calidad.grid(row=2, column=1, sticky='w', padx=(8, 0), pady=(12, 0))

        ttk.Label(marco, text='Guardar en:').grid(row=3, column=0, sticky='w', pady=(12, 0))
        carpeta = ajustes.get('carpeta') or carpeta_por_defecto()
        if not Path(carpeta).is_dir():
            carpeta = carpeta_por_defecto()
        self.carpeta = tk.StringVar(value=carpeta)
        ttk.Entry(marco, textvariable=self.carpeta, state='readonly').grid(
            row=3, column=1, sticky='ew', padx=(8, 8), pady=(12, 0))
        ttk.Button(marco, text='Cambiar…', command=self.elegir_carpeta).grid(
            row=3, column=2, pady=(12, 0))

        self.lista = tk.BooleanVar(value=False)
        ttk.Checkbutton(marco, text='Si el link es una playlist o un perfil, bajarla entera',
                        variable=self.lista).grid(row=4, column=1, columnspan=2, sticky='w',
                                                  padx=(8, 0), pady=(10, 0))

        botones = ttk.Frame(marco)
        botones.grid(row=5, column=0, columnspan=3, sticky='ew', pady=(16, 0))
        self.boton = ttk.Button(botones, text='Descargar', command=self.empezar)
        self.boton.pack(side='left')
        self.boton_cancelar = ttk.Button(botones, text='Cancelar', command=self.pedir_cancelar,
                                         state='disabled')
        self.boton_cancelar.pack(side='left', padx=(8, 0))
        ttk.Button(botones, text='Abrir carpeta',
                   command=lambda: abrir_carpeta(self.carpeta.get())).pack(side='right')

        self.barra = ttk.Progressbar(marco, mode='determinate', maximum=100)
        self.barra.grid(row=6, column=0, columnspan=3, sticky='ew', pady=(14, 4))
        self.estado = tk.StringVar(value='Pega un link de YouTube, TikTok… y dale a Descargar.')
        ttk.Label(marco, textvariable=self.estado, wraplength=480).grid(
            row=7, column=0, columnspan=3, sticky='w')

        self.actualizar_calidad()
        raiz.after(100, self.revisar_cola)

    # --- acciones ---
    def pegar(self) -> None:
        try:
            self.url.set(self.raiz.clipboard_get().strip())
        except tk.TclError:
            pass

    def elegir_carpeta(self) -> None:
        ruta = filedialog.askdirectory(initialdir=self.carpeta.get(), title='¿Dónde lo guardo?')
        if ruta:
            self.carpeta.set(ruta)
            self.guardar()

    def actualizar_calidad(self) -> None:
        self.combo_calidad.configure(state='readonly' if self.modo.get() == 'video' else 'disabled')

    def guardar(self) -> None:
        guardar_ajustes({'modo': self.modo.get(), 'calidad': self.calidad.get(),
                         'carpeta': self.carpeta.get()})

    def empezar(self) -> None:
        if self.trabajando:
            return
        url = self.url.get().strip()
        if not url.lower().startswith(('http://', 'https://')):
            messagebox.showinfo('Descargador', 'Pega primero el link completo del vídeo (empieza por https://).')
            return
        self.guardar()
        self.trabajando = True
        self.cancelar.clear()
        self.boton.configure(state='disabled')
        self.boton_cancelar.configure(state='normal')
        self.poner_progreso(nucleo.Progreso(None, 'Buscando el vídeo…'))
        datos = (url, self.modo.get(), nucleo.CALIDADES[self.calidad.get()],
                 self.carpeta.get(), self.lista.get())
        threading.Thread(target=self.trabajo, args=datos, daemon=True).start()

    def pedir_cancelar(self) -> None:
        self.cancelar.set()
        self.estado.set('Cancelando…')

    # --- hilo de descarga ---
    def trabajo(self, url, modo, altura, carpeta, lista) -> None:
        try:
            archivos = nucleo.descargar(url, modo, altura, carpeta, lista,
                                        lambda p: self.cola.put(('progreso', p)), self.cancelar)
            self.cola.put(('hecho', archivos))
        except nucleo.Cancelado:
            self.cola.put(('cancelado', None))
        except nucleo.EsLista:
            self.cola.put(('error', 'Ese link es una playlist o un perfil con varios vídeos. '
                                    'Si los quieres todos, marca «bajarla entera» y dale otra vez. '
                                    'Si solo quieres uno, abre ese vídeo y copia su link.'))
        except yt_dlp.utils.DownloadError as err:
            if isinstance(getattr(err, 'exc_info', [None, None])[1], nucleo.Cancelado):
                self.cola.put(('cancelado', None))
            else:
                self.cola.put(('error', mensaje_de_error(err)))
        except Exception as err:  # noqa: BLE001 — se le enseña al usuario
            self.cola.put(('error', mensaje_de_error(err)))

    # --- de vuelta en la ventana ---
    def revisar_cola(self) -> None:
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == 'progreso':
                    self.poner_progreso(dato)
                else:
                    self.terminar(tipo, dato)
        except queue.Empty:
            pass
        self.raiz.after(100, self.revisar_cola)

    def poner_progreso(self, p: nucleo.Progreso) -> None:
        if p.porcentaje is None:
            if self.barra['mode'] != 'indeterminate':
                self.barra.configure(mode='indeterminate')
                self.barra.start(12)
        else:
            if self.barra['mode'] != 'determinate':
                self.barra.stop()
                self.barra.configure(mode='determinate')
            self.barra['value'] = p.porcentaje
        self.estado.set(p.texto)

    def terminar(self, tipo: str, dato) -> None:
        self.trabajando = False
        self.barra.stop()
        self.barra.configure(mode='determinate')
        self.boton.configure(state='normal')
        self.boton_cancelar.configure(state='disabled')
        if tipo == 'hecho':
            self.barra['value'] = 100
            if len(dato) == 1:
                self.estado.set(f'¡Listo! Guardado como «{Path(dato[0]).name}».')
            elif dato:
                self.estado.set(f'¡Listo! {len(dato)} archivos guardados.')
            else:
                self.estado.set('¡Listo! (ya lo tenías descargado en esa carpeta)')
            self.url.set('')
        elif tipo == 'cancelado':
            self.barra['value'] = 0
            self.estado.set('Descarga cancelada.')
        else:
            self.barra['value'] = 0
            self.estado.set('No se pudo descargar.')
            messagebox.showerror('Descargador', dato)


def main() -> None:
    raiz = tk.Tk()
    try:
        ttk.Style().theme_use('vista' if sys.platform.startswith('win') else 'clam')
    except tk.TclError:
        pass
    App(raiz)
    raiz.mainloop()


if __name__ == '__main__':
    main()
