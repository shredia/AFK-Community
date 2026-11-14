package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryScrollableTabRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import io.github.shredia.afkcommunity.datos.a
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.Visuales
import io.github.shredia.afkcommunity.logica.cargarCuentaActual
import io.github.shredia.afkcommunity.logica.carpetasServidor
import io.github.shredia.afkcommunity.logica.esArrendadoCuenta
import io.github.shredia.afkcommunity.logica.formatoTiempo
import io.github.shredia.afkcommunity.logica.haceCuanto
import io.github.shredia.afkcommunity.logica.normalizar
import io.github.shredia.afkcommunity.logica.ordenBoss
import io.github.shredia.afkcommunity.logica.usoEnNc
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.Desplegable
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Iconos
import io.github.shredia.afkcommunity.ui.ImagenJuego
import io.github.shredia.afkcommunity.ui.Seccion
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import io.github.shredia.afkcommunity.ui.Titulo
import kotlinx.serialization.json.JsonObject

private val PESTANAS = listOf("Héroes", "Colecciones", "Mascotas", "Recursos")

@Composable
fun PantallaCuenta(estado: EstadoApp) {
    var personajes by remember { mutableStateOf<List<Pair<String, String>>?>(null) }
    var carpeta by rememberSaveable { mutableStateOf<String?>(null) }
    var cuenta by remember { mutableStateOf<JsonObject?>(null) }
    var pestana by rememberSaveable { mutableIntStateOf(0) }
    LaunchedEffect(estado.versionDatos) {
        val lista = carpetasServidor(estado.datos)
        personajes = lista
        if (carpeta == null || lista.none { it.first == carpeta }) carpeta = estado.optimizador.carpeta?.takeIf { c -> lista.any { it.first == c } } ?: lista.firstOrNull()?.first
    }
    LaunchedEffect(carpeta, estado.versionDatos) { cuenta = carpeta?.let { cargarCuentaActual(estado.datos, it) } }

    val lista = personajes ?: return
    if (lista.isEmpty()) {
        Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Titulo(tr("Sin personajes"))
            Tenue(tr("Importa el afk-inventory.json de tu personaje para ver aquí tus héroes, colecciones y recursos."))
            Button({ estado.ir(Seccion.IMPORTAR) }) { Text(tr("Importar datos")) }
        }
        return
    }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
            if (lista.size > 1) Desplegable(tr("Personaje"), lista, lista.firstOrNull { it.first == carpeta }, { it.second }, { carpeta = it.first })
            val c = cuenta
            if (c == null) {
                Tenue(tr("Este personaje no tiene captura de la cuenta: importa su afk-inventory.json."), Modifier.padding(top = 8.dp),
                    color = Colores.WARN)
                return@Column
            }
            val datosCuenta = c["cuenta"].o()
            Row(Modifier.padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(lista.firstOrNull { it.first == carpeta }?.second ?: "", fontWeight = FontWeight.SemiBold, maxLines = 1,
                        overflow = TextOverflow.Ellipsis)
                    Tenue(tr("Nivel {0} · captura {1}", datosCuenta["level"].textoO("?"), haceCuanto(c["capturedAt"].s())))
                }
            }
        }
        val c = cuenta ?: return@Column
        PrimaryScrollableTabRow(pestana, containerColor = Colores.FONDO, contentColor = Colores.DORADO, edgePadding = 8.dp) {
            PESTANAS.forEachIndexed { i, t ->
                Tab(pestana == i, { pestana = i }, text = { Text(tr(t)) }, selectedContentColor = Colores.DORADO,
                    unselectedContentColor = Colores.MUTED)
            }
        }
        when (pestana) {
            0 -> Heroes(estado, c, carpeta)
            1 -> Colecciones(estado, c)
            2 -> Mascotas(c)
            else -> Recursos(c)
        }
    }
}

@Composable
private fun Heroes(estado: EstadoApp, cuenta: JsonObject, carpeta: String?) {
    var filtro by rememberSaveable { mutableStateOf("") }
    var elegido by remember { mutableStateOf<JsonObject?>(null) }
    val heroes = remember(cuenta) {
        cuenta["roster"].objetos().filter { !it["temporal"].verdad() || esArrendadoCuenta(it, cuenta) }
            .sortedWith(compareByDescending<JsonObject> { it["quality"].int(0) }.thenByDescending { it["sig"].int(0) }
                .thenBy { it["name"].textoO() })
    }
    val terminos = normalizar(filtro)
    val visibles = if (terminos.isEmpty()) heroes else heroes.filter { terminos in normalizar(it["name"].textoO()) }
    Column {
        OutlinedTextField(filtro, { filtro = it }, Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 6.dp),
            label = { Text(tr("Buscar héroe")) }, singleLine = true)
        Tenue(tr("{0} héroes", visibles.size), Modifier.padding(horizontal = 14.dp))
        LazyVerticalGrid(GridCells.Adaptive(76.dp), contentPadding = PaddingValues(10.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(visibles) { h ->
                Surface(onClick = { elegido = h }, color = Colores.FONDO) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(2.dp)) {
                        ImagenJuego(h["imageUrl"].s(), 64.dp, alternativo = h["name"].textoO("?"))
                        Text(h["name"].textoO("?").split(" - ")[0], fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis,
                            textAlign = TextAlign.Center)
                        val estrellas = Visuales.numeroEstrellas(h["quality"])
                        val calidad = if (h["quality"].int(0) >= 10) "A" + (if (estrellas > 0) "$estrellas★" else "")
                        else Visuales.nombreCalidad(h["quality"])
                        Text(listOfNotNull(calidad, h["sig"].int(-1).takeIf { it >= 0 }?.let { "SI $it" }).joinToString(" · "),
                            fontSize = 10.sp, color = Colores.MUTED, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
    }
    elegido?.let { h ->
        Dialog({ elegido = null }, DialogProperties(usePlatformDefaultWidth = false)) {
            Surface(Modifier.fillMaxWidth().padding(10.dp).heightIn(max = 700.dp), shape = RoundedCornerShape(12.dp),
                color = Colores.FONDO, contentColor = Colores.TEXTO) {
                Column(Modifier.verticalScroll(rememberScrollState()).padding(14.dp)) {
                    Row { Spacer(Modifier.weight(1f)); IconButton({ elegido = null }) { Icon(Iconos.cerrar, tr("Cerrar")) } }
                    FichaHeroe(estado, h, null)
                    // cómo lo usaste en NC (con las runs del servidor abierto en el optimizador)
                    val opt = estado.optimizador
                    if (opt.carpeta == carpeta && opt.comps.isNotEmpty()) {
                        val uso = usoEnNc(opt.comps, tid = h["tid"].py())
                        Text(tr("En tus runs de NC"), color = Colores.DORADO, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 12.dp))
                        if (uso.equipos == 0) Tenue(tr("No lo usaste en ninguna run."))
                        for ((boss, par) in uso.porJefe.entries.sortedWith(compareBy(ordenBoss) { it.key })) {
                            Tenue("${estado.nombreJefe(boss)}: ${tr("{0} veces · mejor {1}", par.second, formatoTiempo(par.first))}")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Colecciones(estado: EstadoApp, cuenta: JsonObject) {
    val vis = estado.visuales
    val lista = remember(cuenta) {
        cuenta["colecciones"].objetos().sortedWith(compareByDescending<JsonObject> { it["mythic"].int(0) }.thenBy { it["name"].textoO() })
    }
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        item { Tenue(tr("{0} colecciones ({1} libres)", lista.size, lista.count { !it["equipada_en"].verdad() })) }
        items(lista) { c ->
            Tarjeta {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    ImagenJuego(vis?.imagenColeccion(c["tid"]), 40.dp, alternativo = c["name"].textoO("?"))
                    Column(Modifier.weight(1f).padding(start = 10.dp)) {
                        val estrellas = vis?.estrellasColeccion(c)
                        Text(c["name"].textoO("?") + (estrellas?.let { "  ★$it" } ?: ""), fontWeight = FontWeight.SemiBold)
                        Tenue(tr("Nivel {0} · {1} míticos", c["level"].int(0), c["mythic"].int(0)) + " · " +
                            (c["equipada_en"].s()?.let { tr("en {0}", it) } ?: tr("libre")))
                        Row(horizontalArrangement = Arrangement.spacedBy(3.dp), modifier = Modifier.padding(top = 3.dp)) {
                            for (af in c["affixes"].objetos()) ImagenJuego(vis?.afijo(af["nature"], af["quality"])?.second, 20.dp)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Mascotas(cuenta: JsonObject) {
    val lista = cuenta["mascotas"].objetos()
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        item { Tenue(tr("{0} mascotas", lista.size)) }
        items(lista) { p ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                ImagenJuego(p["imageUrl"].s(), 40.dp, alternativo = p["nombre"].textoO("?"))
                Column(Modifier.padding(start = 10.dp)) {
                    Text(p["nombre"].textoO("?"), fontWeight = FontWeight.SemiBold)
                    Tenue(tr("Nivel {0}", p["nivel"].textoO("?")) + " · " + p["trabajos"].a().joinToString("/") { it.py() })
                }
            }
        }
    }
}

@Composable
private fun Recursos(cuenta: JsonObject) {
    val monedas = cuenta["monedas"].objetos()
    val objetos = cuenta["objetos"].objetos().sortedBy { it["nombre"].textoO() }
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        item { Text(tr("Monedas"), color = Colores.DORADO, fontWeight = FontWeight.SemiBold) }
        items(monedas) { Fila(it) }
        item { Text(tr("Objetos"), color = Colores.DORADO, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 10.dp)) }
        items(objetos) { Fila(it) }
    }
}

@Composable
private fun Fila(o: JsonObject) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        ImagenJuego(o["imageUrl"].s(), 28.dp, alternativo = o["nombre"].textoO("?"))
        Text(o["nombre"].textoO("?"), Modifier.weight(1f).padding(start = 8.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(miles(o["cantidad"].py()), color = Colores.TEXTO, fontWeight = FontWeight.SemiBold)
    }
}

/** 1234567 -> "1 234 567" */
private fun miles(texto: String): String {
    val n = texto.toLongOrNull() ?: return texto
    return n.toString().reversed().chunked(3).joinToString(" ").reversed()
}
