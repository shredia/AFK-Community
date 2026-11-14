package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.shredia.afkcommunity.idiomas.idiomasDisponibles
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.ui.Desplegable
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Iconos
import io.github.shredia.afkcommunity.ui.Seccion
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import io.github.shredia.afkcommunity.ui.Titulo
import io.github.shredia.afkcommunity.ui.URL_DISCORD
import kotlinx.coroutines.launch

const val VERSION_APP = "1.2.5"

@Composable
fun PantallaAjustes(estado: EstadoApp) {
    val alcance = rememberCoroutineScope()
    val enlaces = LocalUriHandler.current
    var idiomas by remember { mutableStateOf<List<Pair<String, String>>>(emptyList()) }
    LaunchedEffect(Unit) { idiomas = idiomasDisponibles() }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Titulo(tr("Ajustes"))
        Tarjeta {
            Text(tr("General"), fontWeight = FontWeight.SemiBold)
            Desplegable(tr("Idioma:"), idiomas, idiomas.firstOrNull { it.first == estado.idioma }, { it.second },
                { alcance.launch { estado.usarIdioma(it.first) } }, Modifier.padding(top = 8.dp))
        }
        Tarjeta {
            Text(tr("Tus datos"), fontWeight = FontWeight.SemiBold)
            Tenue(tr("Se guardan solo en este dispositivo, con el mismo formato que la app de escritorio. Para respaldarlos o pasarlos a otro dispositivo, guarda un .zip."))
            OutlinedButton({ estado.ir(Seccion.IMPORTAR) }, Modifier.padding(top = 8.dp)) {
                androidx.compose.material3.Icon(Iconos.importar, null)
                Text(" " + tr("Importar / exportar"))
            }
        }
        Tarjeta {
            Text(tr("Acerca de"), fontWeight = FontWeight.SemiBold)
            Tenue(tr("Versión instalada: {0}", VERSION_APP))
            OutlinedButton({ enlaces.openUri(URL_DISCORD) }, Modifier.padding(top = 8.dp)) { Text(tr("💬 Comunidad en Discord")) }
        }
    }
}
