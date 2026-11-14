package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
import io.github.shredia.afkcommunity.datos.esNulo
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.APLICA_AMIGOS
import io.github.shredia.afkcommunity.logica.APLICA_YO
import io.github.shredia.afkcommunity.logica.Composicion
import io.github.shredia.afkcommunity.logica.NOMBRES_ORIGEN
import io.github.shredia.afkcommunity.logica.PROPIO
import io.github.shredia.afkcommunity.logica.SP_DESCONOCIDO
import io.github.shredia.afkcommunity.logica.Visuales
import io.github.shredia.afkcommunity.logica.formatoTiempo
import io.github.shredia.afkcommunity.logica.leerFecha
import io.github.shredia.afkcommunity.logica.nuevaReglaBaneo
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Etiqueta
import io.github.shredia.afkcommunity.ui.Iconos
import io.github.shredia.afkcommunity.ui.ImagenJuego
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import kotlinx.serialization.json.JsonObject
import kotlin.time.ExperimentalTime

private val ORIGEN_CORTO = mapOf("prestado" to "prestado", "prueba" to "prueba", "temporal" to "prestado/prueba",
    "fuera_roster" to "ya no lo tienes")

/** 'SI 30 · G 80 · Timeline Watch 3M' (lo que define la build de un héroe en una ronda). */
fun textoBuild(h: JsonObject): String {
    val partes = mutableListOf<String>()
    if (!h["sig"].esNulo()) partes += "SI ${h["sig"].py()}"
    if (!h["engraving"].esNulo()) partes += "G ${h["engraving"].py()}"
    val col = h["collection"].o()
    if (col.isNotEmpty()) partes += "${col["name"].textoO("?")} ${col["mythic"].int(0)}M"
    return partes.joinToString(" · ")
}

/** Fecha local corta de un texto ISO ("2026-10-06 23:28"). */
@OptIn(ExperimentalTime::class)
fun fechaCorta(iso: String?): String {
    val t = leerFecha(iso) ?: return iso?.take(16)?.replace("T", " ") ?: "—"
    return t.toString().take(16).replace("T", " ")
}

/** Retrato de héroe con su nombre debajo y, si no es propio, de dónde salió la copia. */
@Composable
fun RetratoHeroe(h: JsonObject, golden: kotlinx.serialization.json.JsonElement?, ancho: Int = 58) {
    Column(Modifier.width(ancho.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box {
            val origen = h["origen"].textoO(PROPIO)
            val borde = if (origen != PROPIO) Colores.WARN else Colores.BORDE
            ImagenJuego(h["imageUrl"].s(), (ancho - 6).dp, Modifier.border(1.dp, borde, RoundedCornerShape(6.dp)),
                alternativo = h["name"].textoO("?"))
            val sp = Visuales.usaSp(h, golden)
            if (sp == true || (h["hyper"].verdad() && golden.py() == SP_DESCONOCIDO)) {
                Box(Modifier.align(Alignment.TopEnd).background(if (sp == true) Colores.DORADO else Colores.TENUE, RoundedCornerShape(3.dp))
                    .padding(horizontal = 3.dp)) {
                    Text(if (sp == true) "SP" else "SP?", fontSize = 8.sp, color = Colores.SOBRE_DORADO, fontWeight = FontWeight.Bold)
                }
            }
        }
        Text(h["name"].textoO("?").split(" - ")[0], fontSize = 10.sp, color = Colores.TEXTO, maxLines = 1,
            overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
        val origen = h["origen"].textoO(PROPIO)
        if (origen != PROPIO) Text(tr(ORIGEN_CORTO[origen] ?: origen), fontSize = 9.sp, color = Colores.WARN, maxLines = 1,
            overflow = TextOverflow.Ellipsis)
    }
}

/** Tarjeta de un equipo contra un jefe: jefe, tiempo, 5 héroes y mascota. */
@Composable
fun TarjetaEquipo(estado: EstadoApp, comp: Composicion, titulo: String, alPulsar: () -> Unit, extra: String? = null) {
    val vis = estado.visuales
    Tarjeta(alPulsar = alPulsar) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ImagenJuego(vis?.jefe(comp.bossId)?.second, 38.dp, alternativo = comp.bossId)
            Column(Modifier.weight(1f).padding(start = 10.dp)) {
                Text(titulo, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Tenue(tr("Boss {0} · run del {1}", comp.bossId, fechaCorta(comp.fecha).take(10)), maxLineas = 1)
            }
            Text(formatoTiempo(comp.tiempo), color = Colores.DORADO, fontWeight = FontWeight.Bold, fontSize = 16.sp)
        }
        Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            for (h in comp.heroes) RetratoHeroe(h, comp.golden)
        }
        Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            if (comp.mascota.isNotEmpty()) {
                ImagenJuego(comp.mascota["imageUrl"].s(), 24.dp, alternativo = comp.mascota["name"].textoO("?"))
                Text(" " + comp.mascota["name"].textoO("—"), fontSize = 12.sp, color = Colores.MUTED, maxLines = 1,
                    overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            } else Box(Modifier.weight(1f))
            val partes = mutableListOf<String>()
            if (comp.veces > 1) partes += tr("usado {0} veces", comp.veces)
            comp.dueno?.let { partes += it }
            extra?.let { partes += it }
            if (partes.isNotEmpty()) Tenue(partes.joinToString(" · "), maxLineas = 1)
        }
    }
}

/** El detalle de un equipo: build de cada héroe, banear, marcar el Special Power. */
@Composable
fun DetalleEquipo(estado: EstadoApp, comp: Composicion, alCerrar: () -> Unit) {
    val vis = estado.visuales
    var version by remember { mutableIntStateOf(0) }
    var aviso by remember { mutableStateOf<String?>(null) }
    Dialog(alCerrar, DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxWidth().padding(10.dp).heightIn(max = 760.dp), shape = RoundedCornerShape(12.dp),
            color = Colores.FONDO, contentColor = Colores.TEXTO) {
            Column(Modifier.verticalScroll(rememberScrollState()).padding(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    ImagenJuego(vis?.jefe(comp.bossId)?.second, 44.dp, alternativo = comp.bossId)
                    Column(Modifier.weight(1f).padding(start = 10.dp)) {
                        Text(estado.nombreJefe(comp.bossId), fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
                        Tenue(tr("Boss {0} · posición {1} en su run", comp.bossId, comp.posicion))
                    }
                    IconButton(alCerrar) { Icon(Iconos.cerrar, tr("Cerrar")) }
                }
                Text(formatoTiempo(comp.tiempo), color = Colores.DORADO, fontWeight = FontWeight.Bold, fontSize = 22.sp)
                Tenue(tr("Run del {0} · rotación {1}", fechaCorta(comp.fecha), comp.rotacion))
                if (comp.veces > 1) Tenue(tr("Este mismo equipo se usó {0} veces contra este jefe.", comp.veces))
                comp.dueno?.let { Tenue(tr("Equipo de {0}", it), color = Colores.INFO) }
                aviso?.let { Text(it, color = Colores.OK, fontSize = 13.sp, modifier = Modifier.padding(top = 6.dp)) }

                val especiales = comp.heroes.filter { it["hyper"].verdad() }
                key(version) {
                    for (h in comp.heroes) {
                        HorizontalDivider(Modifier.padding(vertical = 10.dp), color = Colores.BORDE)
                        FichaHeroe(estado, h, comp)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                            val lado = if (comp.dueno == null) APLICA_YO else APLICA_AMIGOS
                            OutlinedButton({
                                estado.optimizador.agregarRegla(nuevaReglaBaneo("HEROE", h["name"].textoO("?"), h["tid"].textoO(), aplica = lado))
                                aviso = tr("{0}: no usar. Pulsa ▶ Optimizar para recalcular.", h["name"].textoO("?").split(" - ")[0])
                            }) { Text(tr("No usar"), fontSize = 12.sp) }
                            if (especiales.size > 1 && h["hyper"].verdad()) {
                                val marcado = comp.golden.py() == h["slot"].py()
                                OutlinedButton({
                                    estado.optimizador.marcarSp(comp, if (marcado) null else h["slot"].int(0))
                                    version++
                                }) { Text(if (marcado) tr("Quitar SP") else tr("Usó el SP"), fontSize = 12.sp) }
                            }
                        }
                    }
                }
                if (comp.mascota.isNotEmpty()) {
                    HorizontalDivider(Modifier.padding(vertical = 10.dp), color = Colores.BORDE)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        ImagenJuego(comp.mascota["imageUrl"].s(), 40.dp, alternativo = comp.mascota["name"].textoO("?"))
                        Column(Modifier.padding(start = 10.dp)) {
                            Text(comp.mascota["name"].textoO("—"), fontWeight = FontWeight.SemiBold)
                            val trabajos = comp.mascota["jobs"].a().map { it.py() }
                            Tenue(tr("Mascota") + if (trabajos.isNotEmpty()) " · " + trabajos.joinToString("/") else "")
                        }
                    }
                }
                TextButton(alCerrar, Modifier.align(Alignment.End)) { Text(tr("Cerrar")) }
            }
        }
    }
}

/** Ficha de un héroe en una ronda: calidad, SI, grabado, muebles, colección y equipo. */
@Composable
fun FichaHeroe(estado: EstadoApp, h: JsonObject, comp: Composicion?) {
    val vis = estado.visuales
    Row {
        RetratoHeroe(h, comp?.golden, ancho = 64)
        Column(Modifier.weight(1f).padding(start = 10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(h["name"].textoO("?"), fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f, fill = false))
                vis?.faccion(h["faction"])?.let { ImagenJuego(it, 18.dp, Modifier.padding(start = 6.dp)) }
            }
            val origen = h["origen"].textoO(PROPIO)
            if (origen != PROPIO) Etiqueta(tr(NOMBRES_ORIGEN[origen] ?: origen), Colores.WARN)
            val partes = mutableListOf(Visuales.nombreCalidad(h["quality"]))
            if (!h["sig"].esNulo()) partes += tr("SI {0}", h["sig"].py())
            if (!h["engraving"].esNulo()) partes += tr("Grabado {0}", h["engraving"].py())
            val muebles = h["furniture"].o()["pieces"].int(0)
            partes += tr("Muebles {0}/9", muebles)
            Tenue(partes.joinToString(" · "))
            val col = h["collection"].o()
            if (col.isNotEmpty()) {
                val estrellas = vis?.estrellasColeccion(col)
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
                    ImagenJuego(vis?.imagenColeccion(col["tid"]), 26.dp, alternativo = col["name"].textoO("?"))
                    Text(" " + col["name"].textoO("?") + (estrellas?.let { " ★$it" } ?: "") + " · " +
                        tr("{0} míticos", col["mythic"].int(0)), fontSize = 12.sp, color = Colores.TEXTO)
                }
            }
            val equipo = h["gear"].objetos()
            if (equipo.isNotEmpty()) {
                FlowRow(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for (g in equipo) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            ImagenJuego(vis?.imagenEquipo(g), 22.dp, alternativo = g["part"].textoO())
                            val tier = vis?.tierEquipo(g)
                            Text(" " + listOfNotNull(tier, g["stars"].int(0).takeIf { it > 0 }?.let { "★$it" }).joinToString(" "),
                                fontSize = 11.sp, color = Colores.MUTED)
                        }
                    }
                }
            }
        }
    }
}
