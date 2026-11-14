package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryScrollableTabRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.Composicion
import io.github.shredia.afkcommunity.logica.NOMBRES_APLICA
import io.github.shredia.afkcommunity.logica.OPTIMO_GLOBAL
import io.github.shredia.afkcommunity.logica.describir
import io.github.shredia.afkcommunity.logica.formatoTiempo
import io.github.shredia.afkcommunity.logica.normalizar
import io.github.shredia.afkcommunity.ui.CampoNumero
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.Desplegable
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Iconos
import io.github.shredia.afkcommunity.ui.ImagenJuego
import io.github.shredia.afkcommunity.ui.Interruptor
import io.github.shredia.afkcommunity.ui.Seccion
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import io.github.shredia.afkcommunity.ui.Titulo

private val RELLENO = PaddingValues(horizontal = 14.dp, vertical = 12.dp)

/** Sin servidores con runs: qué hacer. */
@Composable
private fun SinRuns(estado: EstadoApp) {
    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Titulo(tr("Todavía no hay runs"))
        Tenue(tr("Importa tu afk-inventory.json y luego tu afk-runs.json (Importar / exportar). Después vuelve aquí."))
        Button({ estado.ir(Seccion.IMPORTAR) }) { Text(tr("Importar datos")) }
    }
}

@Composable
fun PantallaOptimizador(estado: EstadoApp) {
    val opt = estado.optimizador
    LaunchedEffect(estado.versionDatos) { opt.preparar() }
    var detalle by remember { mutableStateOf<Composicion?>(null) }
    var alternativas by remember { mutableStateOf<Int?>(null) }
    var verOpciones by rememberSaveable { mutableStateOf(false) }

    var pestana by rememberSaveable { mutableStateOf(0) }

    if (opt.carpeta == null && !opt.ocupado && opt.servidores.isEmpty()) return SinRuns(estado)

    Column(Modifier.fillMaxSize()) {
        PrimaryScrollableTabRow(pestana, containerColor = Colores.FONDO, contentColor = Colores.DORADO, edgePadding = 8.dp) {
            listOf("Optimizar", "★ Resumen", "🎯 Qué me falta", "📊 Estadísticas").forEachIndexed { i, t ->
                Tab(pestana == i, { pestana = i }, text = { Text(tr(t)) }, selectedContentColor = Colores.DORADO,
                    unselectedContentColor = Colores.MUTED)
            }
        }
        when (pestana) {
            1 -> PestanaResumen(estado) { detalle = it }
            2 -> PestanaFalta(estado) { detalle = it }
            3 -> PestanaEstadisticas(estado) { detalle = it }
            else -> ContenidoOptimizar(estado, verOpciones, { verOpciones = it }, { detalle = it }, { alternativas = it })
        }
    }

    alternativas?.let { pos ->
        val lista = opt.resultado?.candidatos?.get(pos).orEmpty()
        val boss = opt.rotacionResultado.getOrElse(pos - 1) { "" }
        ListaEquiposDialogo(estado, "$pos. ${estado.nombreJefe(boss)}", lista, { alternativas = null }, { detalle = it })
    }
    detalle?.let { DetalleEquipo(estado, it) { detalle = null } }
}

@Composable
private fun ContenidoOptimizar(estado: EstadoApp, verOpciones: Boolean, alVerOpciones: (Boolean) -> Unit,
                               alDetalle: (Composicion) -> Unit, alAlternativas: (Int) -> Unit) {
    val opt = estado.optimizador
    LazyColumn(Modifier.fillMaxSize(), contentPadding = RELLENO, verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            if (opt.servidores.size > 1) {
                Desplegable(tr("Servidor"), opt.servidores, opt.servidores.firstOrNull { it.carpeta == opt.carpeta },
                    { it.etiqueta }, { opt.cargarServidor(it.carpeta) })
            } else opt.servidores.firstOrNull()?.let { Tenue(it.etiqueta) }
        }
        item { TarjetaRotacion(estado) }
        item {
            Tarjeta {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(tr("Opciones de búsqueda"), fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                    IconButton({ alVerOpciones(!verOpciones) }) { Icon(if (verOpciones) Iconos.contraer else Iconos.expandir, null) }
                }
                if (verOpciones) Opciones(estado) else Tenue(resumenOpciones(estado), maxLineas = 2)
            }
        }
        item {
            Desplegable(tr("Optimizar con"), opt.fuentes, opt.fuente, { it.etiqueta }, { opt.fuente = it })
        }
        item {
            if (opt.ocupado) {
                Column {
                    LinearProgressIndicator(Modifier.fillMaxWidth(), color = Colores.DORADO)
                    OutlinedButton({ opt.cancelar() }, Modifier.fillMaxWidth().padding(top = 8.dp)) { Text(tr("Cancelar")) }
                }
            } else {
                Button({ opt.optimizar() }, Modifier.fillMaxWidth(), enabled = opt.comps.isNotEmpty() && opt.rotacion.all { it.isNotEmpty() },
                    colors = ButtonDefaults.buttonColors(containerColor = Colores.DORADO, contentColor = Colores.SOBRE_DORADO)) {
                    Icon(Iconos.jugar, null)
                    Text(" " + tr("Optimizar"), fontWeight = FontWeight.Bold)
                }
            }
        }
        opt.mensaje?.let { m -> item { Text(m.texto, color = m.color, fontSize = 13.sp) } }

        val res = opt.resultado
        if (res != null && res.elegidas.isNotEmpty()) {
            item {
                Tarjeta {
                    Text(tr("★ Óptimo: {0}", formatoTiempo(res.total)), color = Colores.DORADO, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Tenue(tr(res.estado) + " · " + tr("{0} equipos considerados", res.consideradas),
                        color = if (res.estado == OPTIMO_GLOBAL) Colores.OK else Colores.WARN)
                }
            }
            itemsIndexed(res.elegidas) { i, comp ->
                val boss = opt.rotacionResultado.getOrElse(i) { comp.bossId }
                Column {
                    TarjetaEquipo(estado, comp, "${i + 1}. ${estado.nombreJefe(boss)}", { alDetalle(comp) })
                    TextButton({ alAlternativas(i + 1) }) {
                        Text(tr("Ver alternativas ({0})", res.candidatos[i + 1]?.size ?: 0), fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

private fun resumenOpciones(estado: EstadoApp): String {
    val o = estado.optimizador.opciones
    val partes = mutableListOf<String>()
    partes += if (o.soloCompletas) tr("Solo runs completas") else tr("Incluye runs incompletas")
    if (o.prohibirRepetirMascota) partes += tr("sin repetir mascotas")
    if (o.excluirTemporales) partes += tr("sin prestados / de prueba")
    if (o.excluirFueraRoster) partes += tr("sin héroes que ya no tienes")
    if (o.limitePorJefe > 0) partes += tr("{0} equipos por jefe", o.limitePorJefe)
    partes += tr("máximo {0} s", o.tiempoMaximo.toInt())
    return partes.joinToString(" · ")
}

@Composable
private fun Opciones(estado: EstadoApp) {
    val opt = estado.optimizador
    val o = opt.opciones
    Interruptor(tr("Solo runs completas"), o.soloCompletas, { opt.cambiarOpciones(o.copy(soloCompletas = it)) },
        tr("Ignora los equipos de runs donde no derrotaste a los 6 jefes."))
    Interruptor(tr("No repetir mascotas"), o.prohibirRepetirMascota, { opt.cambiarOpciones(o.copy(prohibirRepetirMascota = it)) })
    Interruptor(tr("Excluir héroes prestados / de prueba"), o.excluirTemporales, { opt.cambiarOpciones(o.copy(excluirTemporales = it)) })
    Interruptor(tr("Excluir héroes que ya no están en tu roster"), o.excluirFueraRoster, { opt.cambiarOpciones(o.copy(excluirFueraRoster = it)) })
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.padding(top = 6.dp)) {
        CampoNumero(tr("Equipos por jefe (0 = todos)"), o.limitePorJefe, { opt.cambiarOpciones(o.copy(limitePorJefe = it)) }, Modifier.weight(1f))
        CampoNumero(tr("Tiempo máximo (s)"), o.tiempoMaximo.toInt(), { opt.cambiarOpciones(o.copy(tiempoMaximo = it.coerceAtLeast(1).toDouble())) }, Modifier.weight(1f))
    }
}

@Composable
private fun TarjetaRotacion(estado: EstadoApp) {
    val opt = estado.optimizador
    val vis = estado.visuales
    Tarjeta {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(tr("Rotación de la semana"), fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
            TextButton({ opt.usarRotacionReciente() }) { Text(tr("La más reciente"), fontSize = 12.sp) }
        }
        for (i in 0 until 6) {
            val boss = opt.rotacion[i]
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 3.dp)) {
                Text("${i + 1}.", color = Colores.MUTED, modifier = Modifier.padding(end = 6.dp))
                ImagenJuego(vis?.jefe(boss)?.second, 34.dp, alternativo = boss.ifEmpty { "?" })
                Box(Modifier.weight(1f).padding(start = 8.dp)) {
                    Desplegable("", opt.jefes, boss.takeIf { it.isNotEmpty() }, { "${estado.nombreJefe(it)} · $it" },
                        { opt.ponerJefe(i, it) })
                }
            }
        }
        if (opt.rotacion.filter { it.isNotEmpty() }.toSet().size < opt.rotacion.count { it.isNotEmpty() }) {
            Tenue(tr("Hay jefes repetidos en la rotación."), color = Colores.ERR)
        }
    }
}

/** Una lista de equipos en un diálogo (alternativas de un jefe). */
@Composable
fun ListaEquiposDialogo(estado: EstadoApp, titulo: String, lista: List<Composicion>, alCerrar: () -> Unit, alElegir: (Composicion) -> Unit) {
    Dialog(alCerrar, DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxWidth().padding(10.dp).heightIn(max = 760.dp), shape = RoundedCornerShape(12.dp),
            color = Colores.FONDO, contentColor = Colores.TEXTO) {
            Column(Modifier.padding(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(titulo, fontWeight = FontWeight.SemiBold, fontSize = 17.sp, modifier = Modifier.weight(1f))
                    IconButton(alCerrar) { Icon(Iconos.cerrar, tr("Cerrar")) }
                }
                Tenue(tr("{0} equipos, del más rápido al más lento.", lista.size))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    itemsIndexed(lista.take(200)) { i, c ->
                        TarjetaEquipo(estado, c, "#${i + 1}", { alElegir(c) })
                    }
                }
            }
        }
    }
}

// ============================================================
// Explorar equipos
// ============================================================

@Composable
fun PantallaExplorar(estado: EstadoApp) {
    val opt = estado.optimizador
    LaunchedEffect(estado.versionDatos) { opt.preparar() }
    var jefe by rememberSaveable { mutableStateOf<String?>(null) }
    var filtro by rememberSaveable { mutableStateOf("") }
    var detalle by remember { mutableStateOf<Composicion?>(null) }
    if (opt.carpeta == null && !opt.ocupado && opt.servidores.isEmpty()) return SinRuns(estado)
    val boss = jefe?.takeIf { it in opt.jefes } ?: opt.rotacion.firstOrNull { it.isNotEmpty() } ?: opt.jefes.firstOrNull()
    val todos = remember(boss, opt.comps, opt.opciones, opt.reglas) { boss?.let { opt.candidatosDe(it) }.orEmpty() }
    val terminos = normalizar(filtro).split(" ").filter { it.isNotEmpty() }
    val lista = if (terminos.isEmpty()) todos else todos.filter { c ->
        val texto = normalizar((c.heroes.map { it["name"].textoO() } + c.mascota["name"].textoO()).joinToString(" "))
        terminos.all { it in texto }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = RELLENO, verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Desplegable(tr("Jefe"), opt.jefes, boss, { "${estado.nombreJefe(it)} · $it" }, { jefe = it })
        }
        item {
            OutlinedTextField(filtro, { filtro = it }, Modifier.fillMaxWidth(), label = { Text(tr("Filtrar por héroe o mascota")) },
                singleLine = true)
        }
        item { Tenue(tr("{0} equipos contra este jefe (cada equipo distinto una vez, con su mejor tiempo).", lista.size)) }
        itemsIndexed(lista.take(300)) { i, c ->
            TarjetaEquipo(estado, c, "#${i + 1}", { detalle = c })
        }
    }
    detalle?.let { DetalleEquipo(estado, it) { detalle = null } }
}
