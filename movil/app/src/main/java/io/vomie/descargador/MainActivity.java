package io.vomie.descargador;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class MainActivity extends Activity implements Trabajo.Oyente {

    private static final String[] CALIDADES = {"La mejor (hasta 1080p)", "720p", "480p", "360p"};
    private static final int[] ALTURAS = {1080, 720, 480, 360};
    private static final Pattern LINK = Pattern.compile("https?://\\S+");

    private EditText url;
    private RadioButton modoAudio;
    private Spinner calidad;
    private View filaCalidad;
    private Button descargar, cancelar, abrir;
    private ProgressBar barra;
    private TextView estado, version;
    private SharedPreferences ajustes;

    private Uri resultado;
    private boolean resultadoEsVideo;
    private boolean estabaTrabajando;

    @Override
    protected void onCreate(Bundle guardado) {
        super.onCreate(guardado);
        setContentView(R.layout.activity_main);
        ajustes = getSharedPreferences("ajustes", MODE_PRIVATE);

        url = findViewById(R.id.url);
        modoAudio = findViewById(R.id.modo_audio);
        RadioButton modoVideo = findViewById(R.id.modo_video);
        calidad = findViewById(R.id.calidad);
        filaCalidad = findViewById(R.id.fila_calidad);
        descargar = findViewById(R.id.descargar);
        cancelar = findViewById(R.id.cancelar);
        abrir = findViewById(R.id.abrir);
        barra = findViewById(R.id.barra);
        estado = findViewById(R.id.estado);
        version = findViewById(R.id.version);

        ArrayAdapter<String> opciones = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, CALIDADES);
        opciones.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        calidad.setAdapter(opciones);
        calidad.setSelection(Math.min(ajustes.getInt("calidad", 0), CALIDADES.length - 1));
        calidad.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> p, View v, int pos, long id) {
                ajustes.edit().putInt("calidad", pos).apply();
            }
            @Override public void onNothingSelected(AdapterView<?> p) { }
        });

        if (ajustes.getBoolean("audio", false)) modoAudio.setChecked(true); else modoVideo.setChecked(true);
        modoAudio.setOnCheckedChangeListener((b, marcado) -> {
            ajustes.edit().putBoolean("audio", marcado).apply();
            filaCalidad.setVisibility(marcado ? View.GONE : View.VISIBLE);
        });
        filaCalidad.setVisibility(modoAudio.isChecked() ? View.GONE : View.VISIBLE);

        findViewById(R.id.pegar).setOnClickListener(v -> pegar());
        descargar.setOnClickListener(v -> empezar());
        cancelar.setOnClickListener(v -> Trabajo.get().cancelar());
        abrir.setOnClickListener(v -> abrirResultado());
        url.setOnEditorActionListener((v, accion, e) -> {
            if (accion == EditorInfo.IME_ACTION_GO) { empezar(); return true; }
            return false;
        });

        Trabajo.get().calentar(this);
        recibir(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        recibir(intent);
    }

    @Override
    protected void onStart() {
        super.onStart();
        Trabajo.get().setOyente(this);
    }

    @Override
    protected void onStop() {
        Trabajo.get().setOyente(null);
        super.onStop();
    }

    /** Si nos han compartido un link desde otra app, se pone y se empieza solo. */
    private void recibir(Intent intent) {
        if (intent == null || !Intent.ACTION_SEND.equals(intent.getAction())) return;
        String texto = intent.getStringExtra(Intent.EXTRA_TEXT);
        String link = sacarLink(texto);
        intent.setAction(Intent.ACTION_MAIN); // que no se repita al girar o volver
        if (link == null) {
            Toast.makeText(this, "Eso no parece un link de vídeo", Toast.LENGTH_SHORT).show();
            return;
        }
        url.setText(link);
        if (Trabajo.get().trabajando()) {
            Toast.makeText(this, "Espera a que termine la descarga de ahora", Toast.LENGTH_LONG).show();
        } else {
            empezar();
        }
    }

    private static String sacarLink(String texto) {
        if (texto == null) return null;
        Matcher m = LINK.matcher(texto);
        return m.find() ? m.group() : null;
    }

    private void pegar() {
        ClipboardManager cm = getSystemService(ClipboardManager.class);
        ClipData clip = cm == null ? null : cm.getPrimaryClip();
        if (clip == null || clip.getItemCount() == 0) {
            Toast.makeText(this, "No hay nada copiado", Toast.LENGTH_SHORT).show();
            return;
        }
        CharSequence t = clip.getItemAt(0).coerceToText(this);
        String link = sacarLink(t == null ? null : t.toString());
        url.setText(link != null ? link : (t == null ? "" : t.toString().trim()));
    }

    private void empezar() {
        String link = sacarLink(url.getText().toString());
        if (link == null) {
            Toast.makeText(this, "Pega primero el link del vídeo", Toast.LENGTH_SHORT).show();
            return;
        }
        InputMethodManager imm = getSystemService(InputMethodManager.class);
        if (imm != null) imm.hideSoftInputFromWindow(url.getWindowToken(), 0);
        int altura = ALTURAS[Math.max(0, calidad.getSelectedItemPosition())];
        Trabajo.get().empezar(this, link, modoAudio.isChecked(), altura);
    }

    private void abrirResultado() {
        if (resultado == null) return;
        Intent ver = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(resultado, resultadoEsVideo ? "video/*" : "audio/*")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            startActivity(ver);
        } catch (Exception e) {
            Toast.makeText(this, "No encontré una app para abrirlo", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void cambio(int porcentaje, String texto, boolean trabajando, Uri res, boolean esVideo) {
        estado.setText(texto);
        barra.setIndeterminate(trabajando && porcentaje < 0);
        if (porcentaje >= 0) barra.setProgress(porcentaje);
        descargar.setEnabled(!trabajando);
        cancelar.setEnabled(trabajando);
        url.setEnabled(!trabajando);
        resultado = res;
        resultadoEsVideo = esVideo;
        abrir.setVisibility(res != null && !trabajando ? View.VISIBLE : View.GONE);
        if (estabaTrabajando && !trabajando && res != null) url.setText(""); // recién terminada
        estabaTrabajando = trabajando;
        String v = Trabajo.get().version();
        version.setText(v.isEmpty() ? "" : "Motor yt-dlp " + v);
        // Mientras descarga, que la pantalla no se apague (si no, Android puede cortarla).
        if (trabajando) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
}
