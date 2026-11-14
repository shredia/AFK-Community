package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.Amigo
import io.github.shredia.afkcommunity.logica.amigos
import io.github.shredia.afkcommunity.logica.borrarAmigo
import io.github.shredia.afkcommunity.logica.renombrarAmigo
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.Etiqueta
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Iconos
import io.github.shredia.afkcommunity.ui.Seccion
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import io.github.shredia.afkcommunity.ui.Titulo
import kotlinx.coroutines.launch

@Composable
fun PantallaAmigos(estado: EstadoApp) {
    val alcance = rememberCoroutineScope()
    var lista by remember { mutableStateOf<List<Amigo>?>(null) }
    var renombrar by remember { mutableStateOf<Amigo?>(null) }
    var borrar by remember { mutableStateOf<Amigo?>(null) }
    LaunchedEffect(estado.versionDatos) { lista = amigos(estado.datos) }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Titulo(tr("Amigos"))
            Tenue(tr("Runs de otros jugadores para copiar sus mejores equipos. No se mezclan con las tuyas: elígelas en «Optimizar con»."))
            OutlinedButton({ estado.ir(Seccion.IMPORTAR) }, Modifier.padding(top = 6.dp)) {
                Icon(Iconos.importar, null)
                Text(" " + tr("Importar runs de un amigo"))
            }
        }
        val l = lista
        if (l != null && l.isEmpty()) item {
            Tenue(tr("Todavía no tienes amigos. Pídele a un amigo su .zip (Importar / exportar → Guardar .zip) o su afk-runs.json, e impórtalo eligiendo «Son de un amigo»."))
        }
        items(l.orEmpty()) { a ->
            Tarjeta {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(a.nombre, fontWeight = FontWeight.SemiBold)
                            if (a.simulada) Etiqueta(tr("simulación"), Colores.INFO)
                        }
                        Tenue(listOfNotNull(a.servidor.takeIf { it.isNotEmpty() }?.let { tr("Servidor {0}", it) },
                            tr("{0} runs", a.runs)).joinToString(" · "))
                    }
                    IconButton({ renombrar = a }) { Icon(Iconos.editar, tr("Renombrar"), tint = Colores.MUTED) }
                    IconButton({ borrar = a }) { Icon(Iconos.borrar, tr("Borrar"), tint = Colores.MUTED) }
                }
                if (a.runs > 0) {
                    Button({
                        val opt = estado.optimizador
                        opt.fuentes.firstOrNull { it.clave == a.carpeta }?.let { opt.fuente = it }
                        estado.ir(Seccion.OPTIMIZADOR)
                    }, Modifier.padding(top = 6.dp)) { Text(tr("Optimizar con sus runs")) }
                }
            }
        }
    }

    renombrar?.let { a ->
        var nombre by remember(a) { mutableStateOf(a.nombre) }
        AlertDialog(
            onDismissRequest = { renombrar = null },
            title = { Text(tr("Renombrar")) },
            text = { OutlinedTextField(nombre, { nombre = it }, Modifier.fillMaxWidth(), singleLine = true) },
            confirmButton = {
                TextButton({
                    alcance.launch { renombrarAmigo(estado.datos, a.carpeta, nombre); renombrar = null; estado.datosCambiaron() }
                }, enabled = nombre.isNotBlank()) { Text(tr("Guardar")) }
            },
            dismissButton = { TextButton({ renombrar = null }) { Text(tr("Cancelar")) } },
        )
    }
    borrar?.let { a ->
        AlertDialog(
            onDismissRequest = { borrar = null },
            title = { Text(tr("Borrar amigo")) },
            text = { Text(tr("¿Borrar a {0} y sus {1} runs? No se puede deshacer.", a.nombre, a.runs)) },
            confirmButton = {
                TextButton({ alcance.launch { borrarAmigo(estado.datos, a.carpeta); borrar = null; estado.datosCambiaron() } }) {
                    Text(tr("Borrar"), color = Colores.ERR)
                }
            },
            dismissButton = { TextButton({ borrar = null }) { Text(tr("Cancelar")) } },
        )
    }
}
