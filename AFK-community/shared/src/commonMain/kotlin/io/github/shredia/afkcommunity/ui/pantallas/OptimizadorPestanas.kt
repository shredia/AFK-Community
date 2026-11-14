package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.formatear
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.Composicion
import io.github.shredia.afkcommunity.logica.Falta
import io.github.shredia.afkcommunity.logica.Nivel
import io.github.shredia.afkcommunity.logica.Visuales
import io.github.shredia.afkcommunity.logica.formatoTiempo
import io.github.shredia.afkcommunity.logica.sumaPy
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.Desplegable
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.ImagenJuego
import io.github.shredia.afkcommunity.ui.Interruptor
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue

private const val MAX_FALTA_POR_JEFE = 8   // equipos más rápidos por jefe en 'Qué me falta'

private fun colorNivel(n: Nivel?): Color = when (n) {
    Nivel.PUEDO -> Colores.OK
    Nivel.CASI -> Colores.WARN
    Nivel.NO_PUEDO -> Colores.ERR
    null -> Colores.MUTED
}

private fun dif(segundos: Double) = formatear("{0:.3f}", listOf(segundos))

/** Fila de retratos pequeños de un equipo (+ mascota). */
@Composable
private fun FilaRetratos(comp: Composicion) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        for (h in comp.heroes) RetratoHeroe(h, comp.golden, ancho = 54)
    }
}

// ============================================================
// ★ Resumen: tu equipo de cada jefe y si alguien lo hace más rápido
// ============================================================

@Composable
fun PestanaResumen(estado: EstadoApp, alElegir: (Composicion) -> Unit) {
    val opt = estado.optimizador
    LaunchedEffect(opt.hayOtros, opt.otros, opt.rotacion) { if (opt.hayOtros) opt.cargarOtros() }
    val res = opt.resultado
    val optimo = if (res != null && res.elegidas.isNotEmpty()) opt.rotacionResultado.zip(res.elegidas).toMap() else null
    val mios = remember(opt.comps, opt.rotacion, opt.opciones, opt.reglas) { opt.candidatosYo() }
    val otros = opt.otros
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Tenue(if (optimo != null) tr("Los equipos que eligió el optimizador, comparados con los de tus amigos y tus otros servidores.")
            else tr("Pulsa ▶ Optimizar para elegir el mejor equipo de cada jefe sin repetir héroes. Mientras tanto se muestra tu mejor equipo de cada jefe."))
        }
        for ((i, boss) in opt.rotacion.withIndex()) {
            if (boss.isEmpty()) continue
            item {
                val lista = mios[boss].orEmpty()
                val comp = optimo?.get(boss) ?: lista.firstOrNull()
                Tarjeta(alPulsar = comp?.let { { alElegir(it) } }) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        ImagenJuego(estado.visuales?.jefe(boss)?.second, 40.dp, alternativo = boss)
                        Column(Modifier.weight(1f).padding(start = 10.dp)) {
                            Text("${i + 1}. ${estado.nombreJefe(boss)}", fontWeight = FontWeight.SemiBold)
                            Tenue(tr("ID {0} · {1}", boss, if (optimo != null) tr("elegido al optimizar") else tr("tu mejor equipo (sin optimizar)")))
                        }
                        Text(comp?.let { formatoTiempo(it.tiempo) } ?: "—", color = Colores.DORADO, fontWeight = FontWeight.Bold)
                    }
                    if (comp == null) {
                        Tenue(tr("Sin equipos con estos filtros y bloqueos."), Modifier.padding(top = 8.dp))
                        return@Tarjeta
                    }
                    FilaRetratos(comp)
                    val dueno = comp.dueno
                    var linea = tr("De: {0}", dueno ?: tr("tú"))
                    var color = Colores.MUTED
                    if (dueno != null) {
                        val (nivel, faltas) = opt.evaluar(comp)
                        if (nivel != null) {
                            color = colorNivel(nivel)
                            val detalle = faltas.take(2).joinToString("; ") { it.texto } + if (faltas.size > 2) "…" else ""
                            linea += "   ${nivel.icono} " + detalle.ifEmpty { tr(nivel.texto) }
                        }
                    }
                    Text(linea, color = color, fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp))
                    val (texto, colorTexto) = when {
                        dueno != null -> if (lista.isNotEmpty())
                            tr("Tu mejor equipo: {0} ({1:+.3f} s)", formatoTiempo(lista[0].tiempo), lista[0].tiempo - comp.tiempo) to Colores.MUTED
                        else tr("No tienes equipos tuyos contra este jefe.") to Colores.MUTED
                        !opt.hayOtros -> "" to Colores.MUTED
                        otros == null -> tr("Cargando equipos de amigos…") to Colores.MUTED
                        else -> {
                            val masRapido = otros[boss].orEmpty().firstOrNull { it.tiempo < comp.tiempo - 0.0005 }
                            if (masRapido == null) tr("✓ Nadie más lo hace más rápido.") to Colores.OK
                            else {
                                val icono = opt.evaluar(masRapido).first?.let { " ${it.icono}" } ?: ""
                                tr("Más rápido: {0} de {1} (−{2:.3f} s){3}", formatoTiempo(masRapido.tiempo), masRapido.dueno ?: "?",
                                    comp.tiempo - masRapido.tiempo, icono) to Colores.WARN
                            }
                        }
                    }
                    if (texto.isNotEmpty()) Text(texto, color = colorTexto, fontSize = 13.sp)
                }
            }
        }
    }
}

// ============================================================
// 🎯 Qué me falta: equipos de otros más rápidos que los tuyos y qué te falta para copiarlos
// ============================================================

private class FilaFalta(val boss: String, val pos: Int, val mi: Composicion?, val comp: Composicion, val nivel: Nivel?,
                        val faltas: List<Falta>, val gana: Double?)

@Composable
fun PestanaFalta(estado: EstadoApp, alElegir: (Composicion) -> Unit) {
    val opt = estado.optimizador
    LaunchedEffect(opt.hayOtros, opt.otros, opt.rotacion) { if (opt.hayOtros) opt.cargarOtros() }
    val otros = opt.otros
    val mios = remember(opt.comps, opt.rotacion, opt.opciones, opt.reglas) { opt.candidatosYo() }
    val filas = remember(otros, mios, opt.perfil) {
        if (otros == null) null else buildList {
            for ((i, boss) in opt.rotacion.withIndex()) {
                if (boss.isEmpty()) continue
                val mi = mios[boss]?.firstOrNull()
                val base = mi?.tiempo
                var n = 0
                for (c in otros[boss].orEmpty()) {
                    if (base != null && c.tiempo >= base - 0.0005) break
                    val (nivel, faltas) = opt.evaluar(c)
                    add(FilaFalta(boss, i + 1, mi, c, nivel, faltas, base?.let { it - c.tiempo }))
                    if (++n >= MAX_FALTA_POR_JEFE) break
                }
            }
        }.sortedBy { -(it.gana ?: 1e6) }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Tenue(tr("Equipos de tus amigos (y de tus otros servidores) más rápidos que tu mejor equipo en cada jefe de esta semana, y qué te falta para copiarlos según 'Mi roster'. Clic en uno para compararlo en su jefe."))
        }
        when {
            !opt.hayOtros -> item {
                Tenue(tr("Aún no hay runs de amigos. Impórtalas en 'Amigos' para ver qué equipos más rápidos podrías copiar."), color = Colores.WARN)
            }
            filas == null -> item { Tenue(tr("Cargando equipos de amigos…"), color = Colores.INFO) }
            else -> {
                item {
                    if (opt.perfil?.hayDatos != true) Tenue(tr("No sé qué tienes: sincroniza 'Mi cuenta', importa afk-inventory.json o márcalo en ⚙ Configurar → Mi roster. Mientras tanto, la columna ¿Puedes? queda en '?'."), color = Colores.WARN)
                    else Tenue(tr("{0} equipos más rápidos que los tuyos · ✅ puedes armarlo · 🟡 tienes los héroes, falta mejorar algo · ❌ te falta algún héroe", filas.size))
                }
                item { Mejoras(estado, filas) }
                items(filas) { f ->
                    Tarjeta(alPulsar = { alElegir(f.comp) }) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("${f.pos}. ${estado.nombreJefe(f.boss)}", fontWeight = FontWeight.SemiBold)
                                Tenue(tr("De {0} · {1} (tu mejor: {2})", f.comp.dueno ?: "?", formatoTiempo(f.comp.tiempo),
                                    f.mi?.let { formatoTiempo(it.tiempo) } ?: "—"))
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text(f.gana?.let { "−${dif(it)} s" } ?: tr("nuevo"), color = Colores.DORADO, fontWeight = FontWeight.Bold)
                                Text(f.nivel?.icono ?: "?", fontSize = 16.sp)
                            }
                        }
                        FilaRetratos(f.comp)
                        val falta = f.faltas.joinToString("; ") { it.texto }.ifEmpty { if (f.nivel != null) tr("Lo tienes todo") else "—" }
                        Text(falta, color = colorNivel(f.nivel), fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp))
                    }
                }
            }
        }
    }
}

/** Lo que ya puedes armar y las mejoras sueltas que más tiempo te dan. */
@Composable
private fun Mejoras(estado: EstadoApp, filas: List<FilaFalta>) {
    Tarjeta {
        Text(tr("LO QUE MÁS TE ACERCA"), color = Colores.MUTED, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
        if (filas.isEmpty()) {
            Text(tr("✓ En los jefes de esta semana nadie tiene un equipo más rápido que el tuyo."), color = Colores.OK)
            return@Tarjeta
        }
        val ya = LinkedHashMap<String, FilaFalta>()
        for (f in filas) if (f.nivel == Nivel.PUEDO && f.boss !in ya) ya[f.boss] = f
        for (f in ya.values) Text(tr("✅ {0}: ya puedes armar el equipo de {1} y ganar {2}", estado.nombreJefe(f.boss),
            f.comp.dueno ?: "?", f.gana?.let { "${dif(it)} s" } ?: "—"), color = Colores.OK, fontSize = 13.sp)
        val sueltas = LinkedHashMap<String, Triple<Double, String, String>>()
        for (f in filas) {
            val gana = f.gana ?: continue
            if (f.faltas.size == 1 && gana != 0.0) {
                val x = f.faltas[0]
                if (x.clave !in sueltas || gana > sueltas.getValue(x.clave).first) sueltas[x.clave] = Triple(gana, x.texto, f.boss)
            }
        }
        for ((gana, texto, boss) in sueltas.values.sortedBy { -it.first }.take(6)) {
            Text(tr("• {0}  →  −{1:.3f} s en {2}", texto, gana, estado.nombreJefe(boss)), fontSize = 13.sp)
        }
        val repetidas = filas.flatMap { f -> f.faltas.map { it.texto } }.groupingBy { it }.eachCount()
            .entries.sortedByDescending { it.value }
        if (repetidas.isNotEmpty()) Tenue(tr("Lo que más se repite en los equipos más rápidos: {0}",
            repetidas.take(4).joinToString(", ") { "${it.key} (${it.value})" }), Modifier.padding(top = 6.dp))
        if (ya.isEmpty() && sueltas.isEmpty() && repetidas.isEmpty()) Tenue(tr("Sin datos de tu roster para decir qué te falta."))
    }
}

// ============================================================
// 📊 Estadísticas: daño, curación y defensa de cada héroe en cada jefe
// ============================================================

private class RunStats(val dueno: String?, val runId: String, val comps: List<Composicion>, val conStats: Boolean)

/** 1234567 -> "1.23M" */
private fun cifra(n: Double?): String {
    val x = n ?: 0.0
    for ((limite, sufijo) in listOf(1e12 to "T", 1e9 to "B", 1e6 to "M", 1e3 to "K")) {
        if (kotlin.math.abs(x) >= limite) return formatear("{0:.2f}", listOf(x / limite)) + sufijo
    }
    return formatear("{0:.0f}", listOf(x))
}

@Composable
fun PestanaEstadisticas(estado: EstadoApp, alElegir: (Composicion) -> Unit) {
    val opt = estado.optimizador
    var soloConStats by rememberSaveable { mutableStateOf(true) }
    var soloSemana by rememberSaveable { mutableStateOf(false) }
    var elegida by remember { mutableStateOf<Pair<String?, String>?>(null) }
    val runs = remember(opt.comps, opt.otros, soloConStats, soloSemana, opt.rotacion) {
        val semana = opt.rotacion.filter { it.isNotEmpty() }.toSet()
        opt.equiposCargados().groupBy { it.dueno to it.runId }.map { (clave, cs) ->
            val orden = cs.sortedBy { it.posicion }
            RunStats(clave.first, clave.second, orden, orden.any { c -> c.heroes.any { it["stats"].verdad() } })
        }.filter { (!soloConStats || it.conStats) && (!soloSemana || semana.isEmpty() || it.comps.map { c -> c.bossId }.toSet() == semana) }
            .sortedByDescending { it.comps[0].fecha }
    }
    val run = runs.firstOrNull { it.dueno to it.runId == elegida } ?: runs.firstOrNull()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Interruptor(tr("Solo runs con estadísticas"), soloConStats, { soloConStats = it })
            Interruptor(tr("Solo jefes de esta semana"), soloSemana, { soloSemana = it })
            if (runs.isNotEmpty()) Desplegable(tr("Run"), runs, run, { r ->
                val hechos = r.comps.filter { it.derrotado }
                "${fechaCorta(r.comps[0].fecha)} · ${formatoTiempo(sumaPy(hechos.map { it.tiempo }))} · ${hechos.size}/${r.comps.size} · ${r.dueno ?: tr("tú")}" +
                    if (r.conStats) "" else " · " + tr("sin estadísticas")
            }, { elegida = it.dueno to it.runId })
        }
        if (run == null) {
            item { Tenue(tr("No hay runs con estadísticas. Las runs descargadas del sitio no traen daño ni curación: importa afk-runs.json (Importar / exportar) y se les suman a las que ya tienes.")) }
            return@LazyColumn
        }
        item {
            Tenue(if (run.conStats) tr("Daño, curación y defensa de cada héroe en cada jefe. Energía y vida: cómo terminó la ronda. SP: ✦ lo usó · — no lo usó · ? no se sabe (márcalo en el detalle del equipo).")
            else tr("Esta run no tiene estadísticas (viene del sitio). Importa afk-runs.json para sumárselas."))
        }
        items(run.comps) { comp -> TarjetaStats(estado, comp) { alElegir(comp) } }
    }
}

@Composable
private fun TarjetaStats(estado: EstadoApp, comp: Composicion, alPulsar: () -> Unit) {
    Tarjeta(alPulsar = alPulsar) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ImagenJuego(estado.visuales?.jefe(comp.bossId)?.second, 34.dp, alternativo = comp.bossId)
            Text("${comp.posicion}. ${estado.nombreJefe(comp.bossId)}", Modifier.weight(1f).padding(start = 10.dp), fontWeight = FontWeight.SemiBold)
            Text(if (comp.derrotado) formatoTiempo(comp.tiempo) else tr("✗ no derrotado"), color = Colores.DORADO, fontWeight = FontWeight.Bold)
        }
        val jefe = comp.estadisticas["jefe"].o()
        if (jefe.isNotEmpty()) Tenue(tr("Jefe: vida al final {0}% · daño que hizo {1}",
            formatear("{0:.1f}", listOf((jefe["hp_pct"].real() ?: 0.0) / 100)), cifra(jefe["damage"].real())))
        val mascota = comp.estadisticas["mascota"].o()
        val total = comp.heroes.sumOf { it["stats"].o()["damage"].real() ?: 0.0 } + (mascota["damage"].real() ?: 0.0)
        for (h in comp.heroes) {
            val s = h["stats"].o()
            val sp = Visuales.usaSp(h, comp.golden)
            val marca = when { !h["hyper"].verdad() -> ""; sp == true -> " ✦"; sp == false -> " —"; else -> " ?" }
            val pct = if (total > 0) 100 * (s["damage"].real() ?: 0.0) / total else 0.0
            FilaStat(h["name"].textoO("?").split(" - ")[0] + marca, if (sp == true) Colores.DORADO else Colores.TEXTO, h["imageUrl"].s(),
                if (s.isEmpty()) "—" else "${cifra(s["damage"].real())} · ${formatear("{0:.1f}", listOf(pct))}%", pct,
                if (s.isEmpty()) "" else tr("Cura {0} · Defensa {1} · Kills {2} · Energía {3}% · Vida {4}%", cifra(s["heal"].real()),
                    cifra(s["defend"].real()), s["kill"].int(0), (s["mp_pct"].int(0) / 100), (s["hp_pct"].int(0) / 100)))
        }
        if (comp.mascota.isNotEmpty()) {
            val pct = if (total > 0 && mascota.isNotEmpty()) 100 * (mascota["damage"].real() ?: 0.0) / total else 0.0
            FilaStat("🐾 " + comp.mascota["name"].textoO("?"), Colores.MUTED, comp.mascota["imageUrl"].s(),
                if (mascota.isEmpty()) "—" else "${cifra(mascota["damage"].real())} · ${formatear("{0:.1f}", listOf(pct))}%", pct,
                if (mascota.isEmpty()) "" else tr("Cura {0}", cifra(mascota["heal"].real())))
        }
    }
}

@Composable
private fun FilaStat(nombre: String, color: Color, imagen: String?, dano: String, pct: Double, detalle: String) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        ImagenJuego(imagen, 30.dp, alternativo = nombre)
        Column(Modifier.weight(1f).padding(start = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(nombre, color = color, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, maxLines = 1,
                    overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                Text(dano, fontSize = 12.sp, color = Colores.TEXTO)
            }
            Box(Modifier.fillMaxWidth().height(5.dp).background(Colores.PANEL2, RoundedCornerShape(3.dp))) {
                Box(Modifier.fillMaxWidth((pct / 100).toFloat().coerceIn(0f, 1f)).fillMaxHeight()
                    .background(Colores.DORADO, RoundedCornerShape(3.dp)))
            }
            if (detalle.isNotEmpty()) Text(detalle, fontSize = 11.sp, color = Colores.MUTED, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}
