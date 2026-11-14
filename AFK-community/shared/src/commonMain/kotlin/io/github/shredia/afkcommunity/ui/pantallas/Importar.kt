package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.Desplegable
import io.github.shredia.afkcommunity.ui.Dueno
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Iconos
import io.github.shredia.afkcommunity.ui.OpcionExportar
import io.github.shredia.afkcommunity.ui.Pregunta
import io.github.shredia.afkcommunity.ui.describirRuns
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import io.github.shredia.afkcommunity.ui.Titulo
import io.github.shredia.afkcommunity.ui.URL_INVENTARIO
import io.github.shredia.afkcommunity.ui.URL_RUNS

@Composable
fun PantallaImportar(estado: EstadoApp) {
    val imp = estado.importar
    val enlaces = LocalUriHandler.current
    var opcionesExportar by remember { mutableStateOf<List<OpcionExportar>>(emptyList()) }
    var exportarElegida by remember { mutableStateOf<OpcionExportar?>(null) }
    LaunchedEffect(estado.versionDatos) {
        opcionesExportar = imp.opcionesExportar()
        exportarElegida = opcionesExportar.firstOrNull { it.carpeta == exportarElegida?.carpeta } ?: opcionesExportar.firstOrNull()
    }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Titulo(tr("Importar / exportar datos"))
            Tenue(paso(opcionesExportar))
        }
        item {
            Tarjeta {
                Text(tr("Importar"), fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                Tenue(tr("afk-inventory.json, afk-runs.json, una run suelta (afk-NC-….json) o una copia .zip de la app."))
                Button({ imp.elegirEImportar() }, Modifier.fillMaxWidth().padding(top = 8.dp), enabled = !imp.ocupado,
                    colors = ButtonDefaults.buttonColors(containerColor = Colores.DORADO, contentColor = Colores.SOBRE_DORADO)) {
                    Icon(Iconos.importar, null)
                    Text(" " + tr("Elegir archivo…"), fontWeight = FontWeight.Bold)
                }
            }
        }
        item {
            Tarjeta {
                Text(tr("Compartir o respaldar"), fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                Tenue(tr("Guarda un personaje (o un amigo) en un .zip: sirve de respaldo, para pasar tus datos a otro dispositivo o para mandárselo a un amigo."))
                if (opcionesExportar.isEmpty()) Tenue(tr("(todavía no hay nada que guardar)"), color = Colores.TENUE)
                else {
                    Desplegable(tr("¿Qué quieres guardar?"), opcionesExportar, exportarElegida, { it.texto }, { exportarElegida = it },
                        Modifier.padding(top = 8.dp))
                    OutlinedButton({ exportarElegida?.let { imp.exportar(it.carpeta) } }, Modifier.fillMaxWidth().padding(top = 8.dp),
                        enabled = !imp.ocupado && exportarElegida != null) {
                        Icon(Iconos.exportar, null)
                        Text(" " + tr("Guardar .zip…"))
                    }
                }
            }
        }
        if (imp.ocupado) item { LinearProgressIndicator(Modifier.fillMaxWidth(), color = Colores.DORADO) }
        if (imp.log.isNotEmpty()) {
            item {
                Tarjeta {
                    for (l in imp.log) Text(l.texto, color = l.color, fontSize = 13.sp)
                }
            }
        }
        item {
            Tarjeta {
                Text(tr("¿Dónde consigo los archivos del sitio?"), fontWeight = FontWeight.SemiBold)
                Tenue(tr("En esperianarchive.com, con tu sesión iniciada: «Inventory» descarga afk-inventory.json (tu cuenta) y «My runs» descarga afk-runs.json (tus runs). Importa primero el inventario."))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    OutlinedButton({ enlaces.openUri(URL_INVENTARIO) }) { Text("Inventory") }
                    OutlinedButton({ enlaces.openUri(URL_RUNS) }) { Text("My runs") }
                }
            }
        }
    }

    when (val p = imp.pregunta) {
        is Pregunta.NombrePersonaje -> DialogoNombre(p)
        is Pregunta.DuenoRuns -> DialogoDuenoRuns(p)
        is Pregunta.DuenoCopia -> DialogoDuenoCopia(p)
        null -> {}
    }
}

/** Qué hacer ahora (el mismo aviso que la ventana de importar de Python). */
private fun paso(opciones: List<OpcionExportar>): String {
    val personajes = opciones.filter { !it.amigo }
    return when {
        personajes.isEmpty() -> tr("👉 Para empezar, importa el afk-inventory.json de tu personaje (abajo se explica dónde conseguirlo).")
        personajes.all { it.runs == 0 } -> tr("👉 Siguiente paso: importa tu afk-runs.json y elige «Son mías».")
        else -> tr("✔ Tienes {0} personajes y {1} amigos. Vuelve a importar cuando juegues runs nuevas o actualices tu cuenta.",
            personajes.size, opciones.size - personajes.size)
    }
}

@Composable
private fun Opcion(texto: String, elegida: Boolean, alElegir: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = alElegir), verticalAlignment = Alignment.CenterVertically) {
        RadioButton(elegida, alElegir, colors = RadioButtonDefaults.colors(selectedColor = Colores.DORADO))
        Text(texto)
    }
}

@Composable
private fun DialogoNombre(p: Pregunta.NombrePersonaje) {
    var nombre by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { p.respuesta.complete(null) },
        title = { Text(tr("Personaje nuevo")) },
        text = {
            Column {
                Text(tr("UID {0} · servidor {1}. El archivo no trae el nombre del personaje: escríbelo para reconocerlo en la app.",
                    p.info.uid, p.info.servidor))
                OutlinedTextField(nombre, { nombre = it }, Modifier.fillMaxWidth().padding(top = 8.dp), label = { Text(tr("Nombre:")) },
                    singleLine = true)
            }
        },
        confirmButton = { TextButton({ p.respuesta.complete(nombre.trim()) }) { Text(tr("Importar")) } },
        dismissButton = { TextButton({ p.respuesta.complete(null) }) { Text(tr("Cancelar")) } },
    )
}

@Composable
private fun DialogoDuenoRuns(p: Pregunta.DuenoRuns) {
    val a = p.analisis
    val sugeridaMia = a.sugerida?.takeIf { !a.amigo }
    var tipo by remember { mutableStateOf(if (a.amigo) "amigo" else if (p.personajes.isNotEmpty()) "propia" else "amigo") }
    var personaje by remember { mutableStateOf(p.personajes.firstOrNull { it.first == sugeridaMia } ?: p.personajes.firstOrNull()) }
    var nombre by remember { mutableStateOf(if (a.amigo) a.nombre.removeSuffix(" (simulación)") else "") }
    var servidor by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { p.respuesta.complete(null) },
        title = { Text(tr("¿De quién son estas runs?")) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Tenue(describirRuns(a))
                Opcion(tr("Son mías"), tipo == "propia") { tipo = "propia" }
                if (tipo == "propia") {
                    if (p.personajes.isEmpty()) Tenue(tr("Aún no tienes personajes. Importa primero el afk-inventory.json de ese personaje: así la app sabe quién es."), color = Colores.WARN)
                    else {
                        Desplegable(tr("Personaje"), p.personajes, personaje, { it.second }, { personaje = it })
                        Tenue(when {
                            sugeridaMia != null && a.motivo == "fechas" -> tr("✔ Sugerido: {0} · servidor {1} ({2} de estas runs ya están ahí).", a.nombre, sugeridaMia.substringAfterLast('/'), a.yaEstan)
                            sugeridaMia != null -> tr("✔ Sugerido: {0} · servidor {1} (los héroes de estas runs son de ese personaje).", a.nombre, sugeridaMia.substringAfterLast('/'))
                            !a.conIds -> tr("Elige el personaje que la jugó.")
                            else -> tr("No coincide con ninguno de tus personajes: elige uno, o márcalas como de un amigo.")
                        }, color = if (sugeridaMia != null) Colores.OK else Colores.MUTED)
                    }
                }
                Opcion(tr("Son de un amigo"), tipo == "amigo") { tipo = "amigo" }
                Opcion(tr("Es una simulación de la página"), tipo == "simulada") { tipo = "simulada" }
                if (tipo == "amigo" || tipo == "simulada") {
                    OutlinedTextField(nombre, { nombre = it }, Modifier.fillMaxWidth(), label = { Text(tr("Nombre:")) }, singleLine = true)
                    if (tipo == "amigo") OutlinedTextField(servidor, { servidor = it }, Modifier.fillMaxWidth(),
                        label = { Text(tr("Servidor (opcional):")) }, singleLine = true)
                }
            }
        },
        confirmButton = {
            val valido = (tipo == "propia" && personaje != null) || (tipo != "propia" && nombre.isNotBlank())
            TextButton({
                p.respuesta.complete(when (tipo) {
                    "propia" -> Dueno.Mio(personaje!!.first)
                    else -> Dueno.Amigo(nombre.trim(), servidor.trim(), simulada = tipo == "simulada")
                })
            }, enabled = valido) { Text(tr("Importar")) }
        },
        dismissButton = { TextButton({ p.respuesta.complete(null) }) { Text(tr("Cancelar")) } },
    )
}

@Composable
private fun DialogoDuenoCopia(p: Pregunta.DuenoCopia) {
    val info = p.info
    var tipo by remember { mutableStateOf(if (info.mio) "mia" else "amigo") }
    var nombre by remember { mutableStateOf(info.nombre.removeSuffix(" (simulación)")) }
    var servidor by remember { mutableStateOf(info.servidor) }
    AlertDialog(
        onDismissRequest = { p.respuesta.complete(null) },
        title = { Text(tr("¿De quién es esta copia?")) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Tenue(if (info.carpetas.size == 1) tr("Personaje: {0} · servidor {1} · {2} runs.", info.nombre.ifEmpty { "?" },
                    info.servidor.ifEmpty { "?" }, info.runs)
                else tr("La copia trae varios personajes: {0}.", info.carpetas.joinToString(", ") { "${it.first}/${it.second}" }))
                Opcion(tr("De un amigo"), tipo == "amigo") { tipo = "amigo" }
                if (tipo == "amigo") {
                    OutlinedTextField(nombre, { nombre = it }, Modifier.fillMaxWidth(), label = { Text(tr("Nombre:")) }, singleLine = true)
                    OutlinedTextField(servidor, { servidor = it }, Modifier.fillMaxWidth(), label = { Text(tr("Servidor (opcional):")) }, singleLine = true)
                }
                Opcion(tr("Es mía: restaurar la copia (otro PC o respaldo)"), tipo == "mia") { tipo = "mia" }
            }
        },
        confirmButton = {
            TextButton({
                p.respuesta.complete(if (tipo == "mia") Dueno.Restaurar else Dueno.Amigo(nombre.trim(), servidor.trim()))
            }, enabled = tipo == "mia" || nombre.isNotBlank()) { Text(tr("Importar")) }
        },
        dismissButton = { TextButton({ p.respuesta.complete(null) }) { Text(tr("Cancelar")) } },
    )
}
