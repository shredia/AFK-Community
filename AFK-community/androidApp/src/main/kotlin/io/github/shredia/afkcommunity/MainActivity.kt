package io.github.shredia.afkcommunity

import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import io.github.shredia.afkcommunity.ui.EstadoApp
import kotlinx.coroutines.CompletableDeferred

class MainActivity : ComponentActivity() {
    private var estado: EstadoApp? = null
    private var esperaAbrir: CompletableDeferred<Uri?>? = null
    private var esperaGuardar: CompletableDeferred<Uri?>? = null

    // El selector de archivos del sistema: abrir (importar) y crear (guardar .zip)
    private val abrir = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        esperaAbrir?.complete(uri)
        esperaAbrir = null
    }
    private val guardar = registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri ->
        esperaGuardar?.complete(uri)
        esperaGuardar = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // La app siempre es oscura: íconos claros en las barras del sistema
        enableEdgeToEdge(SystemBarStyle.dark(Color.TRANSPARENT), SystemBarStyle.dark(Color.TRANSPARENT))
        super.onCreate(savedInstanceState)
        val plataforma = PlataformaAndroid(this)

        // Atrás: vuelve a Inicio; desde Inicio, cierra la app como siempre
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (estado?.atras() != true) {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                    isEnabled = true
                }
            }
        })

        setContent {
            App(plataforma) { estado = it }
        }
    }

    suspend fun pedirArchivo(): Uri? {
        val espera = CompletableDeferred<Uri?>()
        esperaAbrir?.complete(null)
        esperaAbrir = espera
        abrir.launch(arrayOf("application/json", "application/zip", "application/octet-stream", "text/plain", "*/*"))
        return espera.await()
    }

    suspend fun pedirDestino(nombre: String): Uri? {
        val espera = CompletableDeferred<Uri?>()
        esperaGuardar?.complete(null)
        esperaGuardar = espera
        guardar.launch(nombre)
        return espera.await()
    }
}
