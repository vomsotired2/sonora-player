package io.vomie.descargador;

import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.media.MediaMuxer;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;

/**
 * Junta y separa pistas con las herramientas que trae Android (sin ffmpeg).
 * No recomprime nada: copia los datos tal cual, así que es rápido y no pierde calidad.
 */
final class Muxer {
    private Muxer() {}

    /** Junta la imagen de {@code video} y el sonido de {@code audio} en un MP4. */
    static void unir(File video, File audio, File salida) throws IOException {
        MediaExtractor ev = new MediaExtractor();
        MediaExtractor ea = new MediaExtractor();
        MediaMuxer mux = null;
        boolean empezado = false;
        try {
            ev.setDataSource(video.getPath());
            ea.setDataSource(audio.getPath());
            int pv = pista(ev, "video/");
            int pa = pista(ea, "audio/");
            if (pv < 0) throw new IOException("el archivo de imagen no tiene vídeo");
            if (pa < 0) throw new IOException("el archivo de sonido no tiene audio");
            ev.selectTrack(pv);
            ea.selectTrack(pa);
            MediaFormat fv = ev.getTrackFormat(pv);
            MediaFormat fa = ea.getTrackFormat(pa);

            mux = new MediaMuxer(salida.getPath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
            if (fv.containsKey(MediaFormat.KEY_ROTATION)) {
                mux.setOrientationHint(fv.getInteger(MediaFormat.KEY_ROTATION));
            }
            int sv = mux.addTrack(fv);
            int sa = mux.addTrack(fa);
            mux.start();
            empezado = true;
            copiarIntercalado(ev, sv, ea, sa, mux, Math.max(tamano(fv), tamano(fa)));
        } finally {
            cerrar(mux, empezado);
            ev.release();
            ea.release();
        }
    }

    /** ¿Tiene el archivo alguna pista que empiece por {@code tipo} ("video/" o "audio/")? */
    static boolean tiene(File archivo, String tipo) {
        MediaExtractor ex = new MediaExtractor();
        try {
            ex.setDataSource(archivo.getPath());
            return pista(ex, tipo) >= 0;
        } catch (IOException e) {
            return false;
        } finally {
            ex.release();
        }
    }

    /** Tipo MIME de la primera pista de audio, o null. */
    static String mimeAudio(File archivo) {
        MediaExtractor ex = new MediaExtractor();
        try {
            ex.setDataSource(archivo.getPath());
            int p = pista(ex, "audio/");
            return p < 0 ? null : ex.getTrackFormat(p).getString(MediaFormat.KEY_MIME);
        } catch (IOException e) {
            return null;
        } finally {
            ex.release();
        }
    }

    /**
     * Saca solo el sonido de {@code entrada}. Devuelve la extensión del archivo creado
     * ("m4a" para AAC, "ogg" para Opus) o lanza IOException si el formato no se puede copiar.
     */
    static String soloAudio(File entrada, File salidaSinExtension) throws IOException {
        MediaExtractor ex = new MediaExtractor();
        MediaMuxer mux = null;
        boolean empezado = false;
        try {
            ex.setDataSource(entrada.getPath());
            int p = pista(ex, "audio/");
            if (p < 0) throw new IOException("ese vídeo no tiene sonido");
            MediaFormat f = ex.getTrackFormat(p);
            String mime = f.getString(MediaFormat.KEY_MIME);
            String ext;
            int formato;
            if (MediaFormat.MIMETYPE_AUDIO_AAC.equals(mime)) {
                ext = "m4a";
                formato = MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4;
            } else if (MediaFormat.MIMETYPE_AUDIO_OPUS.equals(mime)) {
                ext = "ogg";
                formato = MediaMuxer.OutputFormat.MUXER_OUTPUT_OGG;
            } else {
                throw new IOException("formato de audio no compatible: " + mime);
            }
            ex.selectTrack(p);
            File salida = new File(salidaSinExtension.getPath() + "." + ext);
            mux = new MediaMuxer(salida.getPath(), formato);
            int s = mux.addTrack(f);
            mux.start();
            empezado = true;
            copiarIntercalado(ex, s, null, -1, mux, tamano(f));
            return ext;
        } finally {
            cerrar(mux, empezado);
            ex.release();
        }
    }

    // ------------------------------------------------------------------

    private static int pista(MediaExtractor ex, String tipo) {
        for (int i = 0; i < ex.getTrackCount(); i++) {
            String mime = ex.getTrackFormat(i).getString(MediaFormat.KEY_MIME);
            if (mime != null && mime.startsWith(tipo)) return i;
        }
        return -1;
    }

    private static int tamano(MediaFormat f) {
        int t = f.containsKey(MediaFormat.KEY_MAX_INPUT_SIZE) ? f.getInteger(MediaFormat.KEY_MAX_INPUT_SIZE) : 0;
        return Math.max(t, 4 * 1024 * 1024);
    }

    /** Copia muestras de una o dos fuentes, siempre la que va más atrasada, para que queden intercaladas. */
    private static void copiarIntercalado(MediaExtractor a, int sa, MediaExtractor b, int sb,
                                          MediaMuxer mux, int tamano) {
        ByteBuffer buf = ByteBuffer.allocateDirect(tamano);
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        boolean finA = false, finB = (b == null);
        while (!finA || !finB) {
            boolean usarA;
            if (finB) usarA = true;
            else if (finA) usarA = false;
            else usarA = a.getSampleTime() <= b.getSampleTime();

            MediaExtractor ex = usarA ? a : b;
            int n = ex.readSampleData(buf, 0);
            if (n < 0) {
                if (usarA) finA = true; else finB = true;
                continue;
            }
            info.offset = 0;
            info.size = n;
            info.presentationTimeUs = Math.max(0, ex.getSampleTime());
            info.flags = (ex.getSampleFlags() & MediaExtractor.SAMPLE_FLAG_SYNC) != 0
                    ? MediaCodec.BUFFER_FLAG_KEY_FRAME : 0;
            mux.writeSampleData(usarA ? sa : sb, buf, info);
            ex.advance();
        }
    }

    private static void cerrar(MediaMuxer mux, boolean empezado) {
        if (mux == null) return;
        try {
            if (empezado) mux.stop();
        } catch (IllegalStateException ignorado) {
            // si falló a medias, el archivo se descarta igualmente
        }
        mux.release();
    }
}
