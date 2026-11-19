package io.vomie.descargador;

import android.content.Context;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Hace las descargas en segundo plano y guarda el estado, para que no se
 * pierda si se gira la pantalla o se sale y se vuelve a la app.
 * Todo lo que toca la pantalla pasa por el hilo principal.
 */
public final class Trabajo {

    interface Oyente {
        /** porcentaje = -1: barra sin porcentaje. */
        void cambio(int porcentaje, String texto, boolean trabajando, Uri resultado, boolean resultadoEsVideo);
    }

    /** Lo que Python llama mientras descarga. Tiene que ser público para Chaquopy. */
    public static final class Puente {
        private final Trabajo t;
        Puente(Trabajo t) { this.t = t; }
        public void progreso(int porcentaje, String texto) { t.avisar(porcentaje, texto); }
        public boolean cancelado() { return t.cancelar; }
    }

    private static final Trabajo YO = new Trabajo();
    static Trabajo get() { return YO; }

    private final ExecutorService descargas = Executors.newSingleThreadExecutor();
    private final ExecutorService fondo = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    // Solo se tocan desde el hilo principal:
    private Oyente oyente;
    private boolean trabajando;
    private int porcentaje = 0;
    private String texto = "Preparando…";
    private Uri resultado;
    private boolean resultadoEsVideo;

    private volatile boolean cancelar;
    private volatile String version = "";
    private boolean pythonListo; // protegido por synchronized(this)

    private Trabajo() {}

    void setOyente(Oyente o) {
        oyente = o;
        refrescar();
    }

    boolean trabajando() { return trabajando; }
    String version() { return version; }

    /** Arranca Python y busca actualizaciones de yt-dlp. Se puede llamar varias veces. */
    void calentar(Context ctx) {
        Context app = ctx.getApplicationContext();
        fondo.execute(() -> {
            try {
                asegurarPython(app);
                ui.post(() -> {
                    if (!trabajando && "Preparando…".equals(texto)) {
                        texto = "Pega un link y dale a Descargar.";
                        refrescar();
                    }
                });
                Python.getInstance().getModule("movil").callAttr("actualizar", app.getFilesDir().getPath());
            } catch (Throwable e) {
                // sin internet o GitHub caído: se sigue con la versión que hay
            }
        });
    }

    /** Empieza una descarga. Devuelve false si ya hay una en marcha. */
    boolean empezar(Context ctx, String url, boolean audio, int altura) {
        if (trabajando) return false;
        Context app = ctx.getApplicationContext();
        trabajando = true;
        cancelar = false;
        resultado = null;
        porcentaje = -1;
        texto = "Preparando…";
        refrescar();
        descargas.execute(() -> hacer(app, url, audio, altura));
        return true;
    }

    void cancelar() {
        if (!trabajando) return;
        cancelar = true;
        avisar(-1, "Cancelando…");
    }

    // ------------------------------------------------------------------

    private synchronized void asegurarPython(Context app) {
        if (!Python.isStarted()) Python.start(new AndroidPlatform(app));
        if (!pythonListo) {
            PyObject v = Python.getInstance().getModule("movil")
                    .callAttr("preparar", app.getFilesDir().getPath(), app.getCacheDir().getPath());
            version = v.toString();
            pythonListo = true;
        }
    }

    private void hacer(Context app, String url, boolean audio, int altura) {
        File carpeta = new File(app.getCacheDir(), "trabajo");
        PyObject movil = null;
        try {
            asegurarPython(app);
            movil = Python.getInstance().getModule("movil");
            movil.callAttr("limpiar", carpeta.getPath());
            String qjs = new File(app.getApplicationInfo().nativeLibraryDir, "libqjs.so").getPath();

            String json = movil.callAttr("descargar", url, audio ? "audio" : "video", altura,
                    carpeta.getPath(), qjs, new Puente(this)).toString();
            JSONObject r = new JSONObject(json);
            if (r.optBoolean("cancelado")) { terminar(0, "Descarga cancelada.", null, false); return; }
            if (r.has("error")) { terminar(0, r.getString("error"), null, false); return; }
            if (cancelar) { terminar(0, "Descarga cancelada.", null, false); return; }

            String titulo = r.optString("titulo", "descarga");
            JSONArray partes = r.getJSONArray("partes");
            Uri uri;
            String donde;
            boolean esVideo;
            if (partes.length() >= 2) {
                avisar(-1, "Juntando imagen y sonido…");
                File v = new File(partes.getJSONObject(0).getString("ruta"));
                File a = new File(partes.getJSONObject(1).getString("ruta"));
                if (!partes.getJSONObject(0).optBoolean("video", true)) { File x = v; v = a; a = x; }
                File unido = new File(carpeta, "final.mp4");
                Muxer.unir(v, a, unido);
                avisar(-1, "Guardando en la galería…");
                uri = Guardar.enGaleria(app, unido, titulo, "mp4", true);
                donde = "Películas/Descargador";
                esVideo = true;
            } else {
                JSONObject p = partes.getJSONObject(0);
                File f = new File(p.getString("ruta"));
                String ext = p.optString("ext", "mp4");
                boolean tieneVideo = Muxer.tiene(f, "video/");
                if (audio && tieneVideo) {
                    avisar(-1, "Sacando el sonido…");
                    String nueva = Muxer.soloAudio(f, new File(carpeta, "final"));
                    f = new File(carpeta, "final." + nueva);
                    ext = nueva;
                    tieneVideo = false;
                } else if (audio && "mp4".equals(ext)) {
                    ext = "m4a"; // MP4 que solo lleva sonido
                }
                avisar(-1, "Guardando…");
                uri = Guardar.enGaleria(app, f, titulo, ext, tieneVideo);
                donde = tieneVideo ? "Películas/Descargador" : "Música/Descargador";
                esVideo = tieneVideo;
            }
            terminar(100, "¡Listo! Guardado en " + donde + ".", uri, esVideo);
        } catch (Throwable e) {
            String msg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
            terminar(0, "No se pudo descargar: " + msg, null, false);
        } finally {
            if (movil != null) {
                try { movil.callAttr("limpiar", carpeta.getPath()); } catch (Throwable ignorado) { }
            }
        }
    }

    private void avisar(int pct, String t) {
        ui.post(() -> {
            if (!trabajando) return;
            porcentaje = pct;
            texto = t;
            refrescar();
        });
    }

    private void terminar(int pct, String t, Uri uri, boolean esVideo) {
        ui.post(() -> {
            trabajando = false;
            porcentaje = pct;
            texto = t;
            resultado = uri;
            resultadoEsVideo = esVideo;
            refrescar();
        });
    }

    private void refrescar() {
        if (oyente != null) oyente.cambio(porcentaje, texto, trabajando, resultado, resultadoEsVideo);
    }
}
