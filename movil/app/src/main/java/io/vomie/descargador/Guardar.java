package io.vomie.descargador;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/** Copia el archivo terminado a la galería (Películas) o a Música, donde lo ven las demás apps. */
final class Guardar {
    private Guardar() {}

    static Uri enGaleria(Context c, File archivo, String titulo, String ext, boolean video) throws IOException {
        String mime = mime(ext, video);
        ContentValues v = new ContentValues();
        v.put(MediaStore.MediaColumns.DISPLAY_NAME, nombre(titulo) + "." + ext);
        v.put(MediaStore.MediaColumns.MIME_TYPE, mime);
        v.put(MediaStore.MediaColumns.RELATIVE_PATH,
                (video ? Environment.DIRECTORY_MOVIES : Environment.DIRECTORY_MUSIC) + "/Descargador");
        v.put(MediaStore.MediaColumns.IS_PENDING, 1);

        Uri coleccion = video
                ? MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
                : MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        ContentResolver cr = c.getContentResolver();
        Uri uri = cr.insert(coleccion, v);
        if (uri == null) throw new IOException("no se pudo crear el archivo en el móvil");

        try (InputStream in = new FileInputStream(archivo);
             OutputStream out = cr.openOutputStream(uri)) {
            if (out == null) throw new IOException("no se pudo escribir el archivo");
            byte[] buf = new byte[1 << 16];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        } catch (IOException e) {
            cr.delete(uri, null, null);
            throw e;
        }
        v.clear();
        v.put(MediaStore.MediaColumns.IS_PENDING, 0);
        cr.update(uri, v, null, null);
        return uri;
    }

    static String mime(String ext, boolean video) {
        switch (ext) {
            case "mp4": return video ? "video/mp4" : "audio/mp4";
            case "m4a": return "audio/mp4";
            case "webm": return video ? "video/webm" : "audio/webm";
            case "ogg":
            case "opus": return "audio/ogg";
            case "mp3": return "audio/mpeg";
            case "mov": return "video/quicktime";
            default: return video ? "video/*" : "audio/*";
        }
    }

    /** Quita los caracteres que no valen en un nombre de archivo y lo recorta. */
    static String nombre(String titulo) {
        String n = titulo == null ? "" : titulo.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]+", " ").trim();
        if (n.isEmpty()) n = "descarga";
        if (n.length() > 100) {
            int corte = Character.isHighSurrogate(n.charAt(99)) ? 99 : 100; // no partir un emoji
            n = n.substring(0, corte).trim();
        }
        return n;
    }
}
