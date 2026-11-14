package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.shredia.afkcommunity.datos.con
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.leerJsonTexto
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.obj
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.idiomas.N_
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.CalculoFractura
import io.github.shredia.afkcommunity.logica.ObjetoBolsa
import io.github.shredia.afkcommunity.logica.calcularFractura
import io.github.shredia.afkcommunity.logica.cargarBaseFractura
import io.github.shredia.afkcommunity.logica.cargarCuentaActual
import io.github.shredia.afkcommunity.logica.cargarEstadoFractura
import io.github.shredia.afkcommunity.logica.carpetasServidor
import io.github.shredia.afkcommunity.logica.fmtFractura
import io.github.shredia.afkcommunity.logica.guardarBaseFractura
import io.github.shredia.afkcommunity.logica.guardarEstadoFractura
import io.github.shredia.afkcommunity.logica.haceCuanto
import io.github.shredia.afkcommunity.logica.imagenObjetoTienda
import io.github.shredia.afkcommunity.logica.imagenRecurso
import io.github.shredia.afkcommunity.logica.inventarioFractura
import io.github.shredia.afkcommunity.logica.normalizar
import io.github.shredia.afkcommunity.logica.objetosBolsa
import io.github.shredia.afkcommunity.logica.pisosValidos
import io.github.shredia.afkcommunity.logica.proximoViernes
import io.github.shredia.afkcommunity.recursos.Res
import io.github.shredia.afkcommunity.ui.CampoNumero
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.Desplegable
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.ImagenJuego
import io.github.shredia.afkcommunity.ui.Interruptor
import io.github.shredia.afkcommunity.ui.Seccion
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.jetbrains.compose.resources.ExperimentalResourceApi

private val PESTANAS_FRACTURA = listOf(N_("Resumen por recurso"), N_("Cofres de elección"), N_("Tiendas de medallas"), N_("Recompensas por piso"))

@OptIn(ExperimentalResourceApi::class)
@Composable
fun PantallaFractura(estado: EstadoApp) {
    val alcance = rememberCoroutineScope()
    var personajes by remember { mutableStateOf<List<Pair<String, String>>?>(null) }
    var carpeta by rememberSaveable { mutableStateOf<String?>(null) }
    var base by remember { mutableStateOf<JsonObject?>(null) }
    var progreso by remember { mutableStateOf<JsonObject?>(null) }
    var cuenta by remember { mutableStateOf<JsonObject?>(null) }
    var cuentas by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var pestana by rememberSaveable { mutableIntStateOf(0) }
    var vincular by remember { mutableStateOf<String?>(null) }
    var reiniciar by remember { mutableStateOf(false) }
    var verCabecera by rememberSaveable { mutableStateOf(false) }

    LaunchedEffect(estado.versionDatos) {
        val lista = carpetasServidor(estado.datos)
        personajes = lista
        if (lista.none { it.first == carpeta }) carpeta = estado.optimizador.carpeta?.takeIf { c -> lista.any { it.first == c } } ?: lista.firstOrNull()?.first
        base = cargarBaseFractura(estado.datos)
            ?: runCatching { leerJsonTexto(Res.readBytes("files/fractura_temporal_base.json").decodeToString()) as? JsonObject }.getOrNull()
        cuentas = lista.mapNotNull { cargarCuentaActual(estado.datos, it.first) }
    }
    LaunchedEffect(carpeta, estado.versionDatos) {
        val c = carpeta ?: return@LaunchedEffect
        progreso = cargarEstadoFractura(estado.datos, c)
        cuenta = cargarCuentaActual(estado.datos, c)
    }

    val lista = personajes ?: return
    if (lista.isEmpty()) {
        Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(tr("Fractura temporal"), fontWeight = FontWeight.SemiBold, fontSize = 20.sp)
            Tenue(tr("El avance de la Fractura se guarda por personaje. Importa primero el afk-inventory.json de tu personaje."))
            Button({ estado.ir(Seccion.IMPORTAR) }) { Text(tr("Importar datos")) }
        }
        return
    }
    val b = base
    val e = progreso
    if (b == null || e == null || b["pisos"].objetos().isEmpty()) {
        Tenue(tr("No hay datos de la Fractura."), Modifier.padding(20.dp))
        return
    }
    val inv = remember(cuenta, b) { inventarioFractura(cuenta, b) }
    val calc = remember(b, e, inv) { calcularFractura(b, e, inv) }
    val imagenesDe = remember(cuenta, cuentas) { listOfNotNull(cuenta) + cuentas }

    /** Guarda el avance (cada cambio se guarda en el momento). */
    fun cambiar(nuevo: JsonObject) {
        progreso = nuevo
        val c = carpeta ?: return
        alcance.launch { guardarEstadoFractura(estado.datos, c, nuevo) }
    }

    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            if (lista.size > 1) Desplegable(tr("Cuenta:"), lista, lista.firstOrNull { it.first == carpeta }, { it.second }, { carpeta = it.first })
            // Resumen de una línea; al tocarlo se despliega para editar piso, meta y medallas
            Row(Modifier.fillMaxWidth().clickable { verCabecera = !verCabecera }, verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(tr("Piso {0} · meta {1} · saldo {2} medallas", calc.piso, e["meta"].int(0), calc.medallas.saldo),
                        fontWeight = FontWeight.SemiBold)
                    val sig = calc.siguiente
                    Tenue(if (sig != null) tr("Próximo piso {0}: {1}", sig["piso"].int(), sig["recompensas"].o().entries.joinToString(", ") { "${it.key} ×${fmtFractura(it.value.real())}" })
                    else tr("¡Fractura completa! Ya alcanzaste el último piso."), maxLineas = if (verCabecera) 4 else 1)
                }
                androidx.compose.material3.Icon(if (verCabecera) io.github.shredia.afkcommunity.ui.Iconos.contraer else io.github.shredia.afkcommunity.ui.Iconos.expandir, null, tint = Colores.MUTED)
            }
            for (a in calc.avisos) Text("⚠ $a", color = Colores.ERR, fontSize = 12.sp, maxLines = if (verCabecera) 4 else 1, overflow = TextOverflow.Ellipsis)
            if (verCabecera) Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                CampoNumero(tr("Piso alcanzado:"), calc.piso, { cambiar(e.con("piso" to it)) }, Modifier.weight(1f))
                CampoNumero(tr("Meta"), e["meta"].int(0), { cambiar(e.con("meta" to it)) }, Modifier.weight(1f))
                TextButton({
                    val tope = pisosValidos(b).maxOrNull() ?: 0
                    cambiar(e.con("meta" to minOf(tope, calc.piso + 20)))
                }) { Text("+20", fontSize = 12.sp) }
            }
            if (verCabecera) Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                val juego = e["medallas_juego"]?.takeIf { it is JsonPrimitive && it !is kotlinx.serialization.json.JsonNull && !it.isString }?.int(0)
                OutlinedTextField(juego?.toString() ?: "", { t ->
                    val limpio = t.filter { it.isDigit() }.take(9)
                    cambiar(e.con("medallas_juego" to limpio.toLongOrNull()))
                }, Modifier.weight(1f), label = { Text(tr("Medallas en el juego:")) }, singleLine = true)
                OutlinedButton({ reiniciar = true }) { Text(tr("⟲ Reiniciar"), fontSize = 12.sp) }
            }
            if (verCabecera) calc.meta?.let { meta ->
                val rec = LinkedHashMap(meta.recompensas)
                val partes = mutableListOf<String>()
                rec.remove("Medallas")?.takeIf { it != 0.0 }?.let { partes += tr("{0} medallas", fmtFractura(it)) }
                for (k in listOf("Cofre 1", "Cofre 2", "Cofre 3")) rec.remove(k)?.let { partes += "$k ×${fmtFractura(it)}" }
                partes += rec.map { (k, v) -> "$k ×${fmtFractura(v)}" }
                Text(tr("🎯 Meta para el viernes {0}:", proximoViernes().let { "${it.day.toString().padStart(2, '0')}/${(it.month.ordinal + 1).toString().padStart(2, '0')}" }) + " " +
                    tr("Del piso {0} al {1} ({2} pisos) ganarás: {3}", meta.desde, meta.piso, meta.piso - meta.desde, partes.joinToString(", ")),
                    color = Colores.DORADO, fontSize = 13.sp)
            } ?: Tenue(tr("Elige una meta mayor que tu piso actual para ver lo que ganarás."))
        }
        PrimaryScrollableTabRow(pestana, containerColor = Colores.FONDO, contentColor = Colores.DORADO, edgePadding = 8.dp) {
            PESTANAS_FRACTURA.forEachIndexed { i, t ->
                Tab(pestana == i, { pestana = i }, text = { Text(tr(t)) }, selectedContentColor = Colores.DORADO, unselectedContentColor = Colores.MUTED)
            }
        }
        when (pestana) {
            0 -> Resumen(b, calc, cuenta, imagenesDe) { vincular = it }
            1 -> Cofres(b, e, calc, inv, imagenesDe, ::cambiar) { vincular = it }
            2 -> Tiendas(b, e, calc, imagenesDe, ::cambiar)
            else -> Pisos(b, calc) { cambiar(e.con("piso" to it)) }
        }
    }

    vincular?.let { recurso ->
        DialogoVincular(recurso, b, cuenta, { vincular = null }) { ident ->
            val nuevaBase = b.con("bolsa" to b["bolsa"].o().con(recurso to ident))
            base = nuevaBase
            vincular = null
            alcance.launch { guardarBaseFractura(estado.datos, nuevaBase) }
        }
    }
    if (reiniciar) DialogoReiniciar(b, e, { reiniciar = false }) { nuevo -> cambiar(nuevo); reiniciar = false }
}

private fun colorSaldo(v: Long): Color = if (v < 0) Colores.ERR else Colores.OK

// ---------------- Resumen por recurso ----------------

@Composable
private fun Resumen(base: JsonObject, calc: CalculoFractura, cuenta: JsonObject?, imagenes: List<JsonObject>, alVincular: (String) -> Unit) {
    var soloClave by rememberSaveable { mutableStateOf(false) }
    val claves = remember(base) {
        base["cofres"].o().values.flatMap { it.o().keys }.toSet() + base["tiendas"].objetos().flatMap { t -> t["objetos"].objetos().map { it["objeto"].py() } }
    }
    val filas = calc.recursos.entries.sortedWith(compareBy({ it.key !in claves }, { it.key.lowercase() }))
        .filter { !soloClave || it.key in claves }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            val m = calc.medallas
            Tarjeta {
                Text(tr("Medallas"), fontWeight = FontWeight.SemiBold)
                val filas = listOf(
                    listOf(Triple(N_("Medallas ganadas"), m.ganadas, Colores.TEXTO), Triple(N_("Gastadas"), m.gastadas, Colores.TEXTO),
                        Triple(N_("Saldo actual"), m.saldo, colorSaldo(m.saldo))),
                    listOf(Triple(N_("Por ganar en pisos"), m.porGanar, Colores.TEXTO), Triple(N_("Compras planeadas"), m.planeadas, Colores.TEXTO),
                        Triple(N_("Saldo al terminar"), m.saldoFinal, colorSaldo(m.saldoFinal))),
                )
                for (fila in filas) {
                    Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
                        for ((titulo, valor, color) in fila) Column(Modifier.weight(1f)) {
                            Text(tr(titulo), color = Colores.MUTED, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(fmtFractura(valor.toDouble()).let { if (valor == 0L) "0" else it }, color = color, fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                        }
                    }
                }
            }
            val cuando = cuenta?.get("capturedAt").s()
            Tenue(if (cuando != null) tr("Bolsa del último fetch: {0}", haceCuanto(cuando)) else tr("Sin datos de la bolsa: importa el afk-inventory.json de este personaje."))
            Interruptor(tr("Solo recursos de tiendas y cofres"), soloClave, { soloClave = it })
            Tenue(tr("Tendrás = lo que hay en tu bolsa + lo que falta (pisos que faltan + compras y cofres planeados). Hasta la meta = lo que dan los pisos entre el actual y la meta. Toca un recurso para vincularlo con un objeto de tu bolsa."))
        }
        items(filas) { (nombre, x) ->
            Row(Modifier.fillMaxWidth().clickable { alVincular(nombre) }.padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                ImagenJuego(imagenRecurso(imagenes, base, nombre), 34.dp, alternativo = nombre)
                Column(Modifier.weight(1f).padding(start = 10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(nombre, color = if (nombre in claves) Colores.DORADO else Colores.TEXTO, fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                        x.tendras?.let { Text(tr("Tendrás {0}", fmtFractura(it)), fontSize = 12.sp, color = Colores.OK) }
                    }
                    val partes = mutableListOf<String>()
                    partes += if (x.bolsa != null) "🔗 " + (if (x.bolsa != 0.0) fmtFractura(x.bolsa) else "0") else if (nombre in calc.recursos && x.bolsa == null) "" else ""
                    if (x.hastaMeta != 0.0) partes += tr("+{0} hasta la meta", fmtFractura(x.hastaMeta))
                    partes += tr("aún obtenible {0}", fmtFractura(x.aunObtenible))
                    partes += tr("conseguido {0}", fmtFractura(x.conseguido))
                    Tenue(partes.filter { it.isNotEmpty() }.joinToString(" · "), maxLineas = 2)
                    Text(tr("Pisos {0}/{1} · Tienda {2}/{3}/{4} · Cofres {5}/{6}", fmtFractura(x.pisosObtenido), fmtFractura(x.pisosFaltante),
                        fmtFractura(x.tiendaComprado), fmtFractura(x.tiendaPlaneado), fmtFractura(x.tiendaPendiente),
                        fmtFractura(x.cofresAhora), fmtFractura(x.cofresPlaneado)), fontSize = 11.sp, color = Colores.TENUE)
                }
            }
        }
    }
}

// ---------------- Cofres de elección ----------------

/** Botones − n + */
@Composable
private fun Contador(etiqueta: String, valor: Int, alCambiar: (Int) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(etiqueta, fontSize = 11.sp, color = Colores.MUTED)
        TextButton({ alCambiar(-1) }, Modifier.size(34.dp), contentPadding = PaddingValues(0.dp)) { Text("−", fontSize = 18.sp) }
        Text(valor.toString(), Modifier.width(26.dp), fontWeight = FontWeight.SemiBold, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        TextButton({ alCambiar(1) }, Modifier.size(34.dp), contentPadding = PaddingValues(0.dp)) { Text("+", fontSize = 18.sp) }
    }
}

@Composable
private fun Cofres(base: JsonObject, estado: JsonObject, calc: CalculoFractura, inv: Map<String, Double?>, imagenes: List<JsonObject>,
                   cambiar: (JsonObject) -> Unit, alVincular: (String) -> Unit) {
    var aviso by remember { mutableStateOf<String?>(null) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        aviso?.let { item { Text(it, color = Colores.WARN, fontSize = 13.sp) } }
        for ((nombre, opcionesE) in base["cofres"].o()) {
            val opciones = opcionesE.o()
            val c = calc.cofres[nombre] ?: continue
            item {
                Tarjeta {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        ImagenJuego(imagenRecurso(imagenes, base, nombre), 34.dp, alternativo = nombre)
                        Text(nombre, Modifier.weight(1f).padding(start = 10.dp), fontWeight = FontWeight.SemiBold)
                    }
                    var texto = tr("Conseguidos {0} · por conseguir {1} · elegidos {2} · gastados sin registrar {3} · planeados {4}/{1}",
                        c.disponibles, c.restantes, c.usadosAhora, c.gastados, c.usadosPlaneados)
                    if (c.libres > 0) texto += tr("  ·  ¡{0} sin abrir!", c.libres)
                    if (c.hastaMeta != 0) texto += tr("  ·  +{0} hasta la meta", c.hastaMeta)
                    val bien = c.libres >= 0 && c.usadosPlaneados <= c.restantes
                    Text(texto, fontSize = 12.sp, color = if (!bien) Colores.ERR else if (c.libres > 0) Colores.WARN else Colores.TEXTO)
                    val enBolsa = inv[nombre]
                    if (enBolsa == null) Tenue(if (nombre in inv) tr("No aparece en tu bolsa (puede que no tengas o que el nombre sea otro)")
                    else tr("(vincula el cofre con la bolsa para comparar)"), Modifier.clickable { alVincular(nombre) })
                    else Text(tr("En tu bolsa: {0} sin abrir", fmtFractura(enBolsa).let { if (enBolsa == 0.0) "0" else it }), fontSize = 12.sp,
                        color = if (enBolsa.toInt() == maxOf(0, c.libres)) Colores.OK else Colores.WARN)

                    val elegidos = estado["cofres"].o()[nombre].o()
                    for ((op, cant) in opciones) {
                        HorizontalDivider(Modifier.padding(vertical = 6.dp), color = Colores.BORDE)
                        val sel = elegidos[op].o()
                        val a = sel["ahora"].int(0); val p = sel["planeado"].int(0)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            ImagenJuego(imagenRecurso(imagenes, base, op), 30.dp, alternativo = op)
                            Column(Modifier.weight(1f).padding(start = 8.dp)) {
                                Text(op, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                                val partes = mutableListOf(tr("{0} por cofre", fmtFractura(cant.real())))
                                if (a > 0) partes += tr("{0} ya", fmtFractura(a * (cant.real() ?: 0.0)))
                                if (p > 0) partes += tr("{0} planeado", fmtFractura(p * (cant.real() ?: 0.0)))
                                Tenue(partes.joinToString(" · "))
                            }
                        }
                        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                            for ((campo, etiqueta, actual) in listOf(Triple("ahora", tr("Ahora"), a), Triple("planeado", tr("Planeado"), p))) {
                                Contador(etiqueta, actual) { delta ->
                                    val tope = if (campo == "ahora") actual + maxOf(0, c.libres) else actual + maxOf(0, c.restantes - c.usadosPlaneados)
                                    val nuevo = if (delta > 0) minOf(tope, actual + delta) else maxOf(0, actual + delta)
                                    if (nuevo == actual) { if (delta > 0) aviso = tr("No quedan cofres {0} para eso.", nombre); return@Contador }
                                    aviso = null
                                    val cofres = estado["cofres"].o()
                                    val delCofre = cofres[nombre].o()
                                    cambiar(estado.con("cofres" to cofres.con(nombre to delCofre.con(op to delCofre[op].o().con(campo to nuevo)))))
                                }
                            }
                        }
                    }
                    HorizontalDivider(Modifier.padding(vertical = 6.dp), color = Colores.BORDE)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CampoNumero(tr("Ya gastados (no sé en qué):"), c.gastados, { n ->
                            cambiar(estado.con("cofres_gastados" to estado["cofres_gastados"].o().con(nombre to maxOf(0, n))))
                        }, Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        TextButton({
                            cambiar(estado.con("cofres_gastados" to estado["cofres_gastados"].o().con(nombre to maxOf(0, c.disponibles - c.usadosAhora))))
                        }) { Text(tr("Ya me gasté los que faltan"), fontSize = 12.sp) }
                        if (enBolsa != null) TextButton({
                            cambiar(estado.con("cofres_gastados" to estado["cofres_gastados"].o().con(nombre to maxOf(0, c.disponibles - c.usadosAhora - enBolsa.toInt()))))
                        }) { Text(tr("Usar lo que hay en la bolsa"), fontSize = 12.sp) }
                    }
                }
            }
        }
    }
}

// ---------------- Tiendas de medallas ----------------

@Composable
private fun Tiendas(base: JsonObject, estado: JsonObject, calc: CalculoFractura, imagenes: List<JsonObject>, cambiar: (JsonObject) -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        for (t in base["tiendas"].objetos()) {
            item {
                val nombreTienda = t["nombre"].py()
                val objetos = t["objetos"].objetos()
                var gasto = 0L; var plan = 0L
                for ((i, o) in objetos.withIndex()) {
                    val c = estado["compras"].o()["$nombreTienda|$i"].o()
                    gasto += c["hechas"].int(0) * o["precio"].int(0).toLong()
                    plan += c["planeadas"].int(0) * o["precio"].int(0).toLong()
                }
                val bloqueada = calc.piso < t["piso"].int(0)
                Tarjeta {
                    Text(nombreTienda, fontWeight = FontWeight.SemiBold)
                    Text((if (bloqueada) tr("🔒 Se abre en el piso {0}", t["piso"].int()) else tr("Abierta desde el piso {0}", t["piso"].int())) +
                        tr("  ·  gastado {0} · planeado {1} medallas", fmtFractura(gasto.toDouble()), fmtFractura(plan.toDouble())),
                        fontSize = 12.sp, color = if (bloqueada) Colores.MUTED else Colores.TEXTO)
                    for ((i, o) in objetos.withIndex()) {
                        HorizontalDivider(Modifier.padding(vertical = 6.dp), color = Colores.BORDE)
                        val clave = "$nombreTienda|$i"
                        val c = estado["compras"].o()[clave].o()
                        val h = c["hechas"].int(0); val p = c["planeadas"].int(0)
                        val maximo = o["maximo"].int(0); val precio = o["precio"].int(0); val unidades = o["unidades"].real() ?: 1.0
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            ImagenJuego(imagenObjetoTienda(imagenes, base, o), 34.dp, alternativo = o["objeto"].py())
                            Column(Modifier.weight(1f).padding(start = 8.dp)) {
                                Text(o["objeto"].py() + if (unidades != 1.0) " ×${fmtFractura(unidades)}" else "", fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                                val quedan = maximo - h - p
                                Tenue(tr("{0} medallas · máximo {1}", fmtFractura(precio.toDouble()), maximo) +
                                    (if (h + p > 0) " · " + tr("recibes {0}", fmtFractura((h + p) * unidades)) else "") +
                                    (if (quedan > 0) tr("  (quedan {0})", quedan) else ""),
                                    color = if (h + p > maximo) Colores.ERR else Colores.MUTED)
                            }
                        }
                        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                            // como cambiar_compra de Python: se respetan los máximos
                            fun compra(dh: Int, dp: Int) {
                                val hechas = minOf(maximo, maxOf(0, h + dh))
                                val planeadas = minOf(maximo - hechas, maxOf(0, p + dp))
                                cambiar(estado.con("compras" to estado["compras"].o().con(clave to obj("hechas" to hechas, "planeadas" to planeadas))))
                            }
                            Contador(tr("Compradas"), h) { compra(it, 0) }
                            Contador(tr("Planeadas"), p) { compra(0, it) }
                        }
                    }
                }
            }
        }
    }
}

// ---------------- Recompensas por piso ----------------

@Composable
private fun Pisos(base: JsonObject, calc: CalculoFractura, alElegir: (Int) -> Unit) {
    val sig = calc.siguiente?.get("piso").int(-1)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        item { Tenue(tr("Toca un piso para marcarlo como alcanzado.")) }
        items(base["pisos"].objetos()) { p ->
            val n = p["piso"].int()
            val rec = LinkedHashMap(p["recompensas"].o())
            val medallas = rec.remove("Medallas")?.real()
            val cofres = listOf("Cofre 1", "Cofre 2", "Cofre 3").mapNotNull { k -> rec.remove(k)?.let { "$k ×${fmtFractura(it.real())}" } }
            val (marca, color) = when {
                n <= calc.piso -> tr("✓ Logrado") to Colores.OK
                n == sig -> tr("➜ Siguiente") to Colores.DORADO
                else -> "" to Colores.TEXTO
            }
            Row(Modifier.fillMaxWidth().clickable { alElegir(n) }.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(n.toString(), Modifier.width(44.dp), fontWeight = FontWeight.Bold, color = color)
                Column(Modifier.weight(1f)) {
                    Text(rec.entries.joinToString(", ") { "${it.key} ×${fmtFractura(it.value.real())}" }.ifEmpty { "—" }, fontSize = 13.sp)
                    val extra = listOfNotNull(medallas?.takeIf { it != 0.0 }?.let { tr("{0} medallas", fmtFractura(it)) }) + cofres
                    if (extra.isNotEmpty()) Tenue(extra.joinToString(" · "))
                }
                if (marca.isNotEmpty()) Text(marca, fontSize = 12.sp, color = color)
            }
        }
    }
}

// ---------------- Vincular con la bolsa y reinicios ----------------

@Composable
private fun DialogoVincular(recurso: String, base: JsonObject, cuenta: JsonObject?, alCerrar: () -> Unit, alElegir: (String) -> Unit) {
    var buscar by remember { mutableStateOf("") }
    val objetos = remember(cuenta) { objetosBolsa(cuenta) }
    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text(tr("Vincular «{0}» con la bolsa", recurso)) },
        text = {
            Column {
                if (objetos.isEmpty()) {
                    Tenue(tr("No hay datos de tu bolsa: importa el afk-inventory.json de este personaje."))
                    return@Column
                }
                val actual = io.github.shredia.afkcommunity.logica.vinculos(base)[recurso]
                if (actual != null) Tenue(tr("Vinculado ahora: {0}", actual))
                OutlinedTextField(buscar, { buscar = it }, Modifier.fillMaxWidth(), label = { Text(tr("Buscar")) }, singleLine = true)
                val q = normalizar(buscar)
                LazyColumn(Modifier.heightIn(max = 380.dp)) {
                    items(objetos.filter { q.isEmpty() || q in normalizar(it.nombre) }.take(200)) { o: ObjetoBolsa ->
                        Row(Modifier.fillMaxWidth().clickable { alElegir(o.id) }.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                            ImagenJuego(o.imagen, 28.dp, alternativo = o.nombre)
                            Text(o.nombre, Modifier.weight(1f).padding(start = 8.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(fmtFractura(o.cantidad.toDouble()), color = Colores.MUTED, fontSize = 12.sp)
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(alCerrar) { Text(tr("Cerrar")) } },
        dismissButton = { TextButton({ alElegir("-") }) { Text(tr("Quitar vínculo")) } },
    )
}

@Composable
private fun DialogoReiniciar(base: JsonObject, estado: JsonObject, alCerrar: () -> Unit, alAplicar: (JsonObject) -> Unit) {
    var temporada by remember { mutableStateOf(false) }
    var piso by remember { mutableIntStateOf(0) }
    var confirmar by remember { mutableStateOf<String?>(null) }
    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text(tr("⟲ Reiniciar")) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                TextButton({ confirmar = "compras" }) { Text(tr("Reiniciar compras (hechas y planeadas)…")) }
                TextButton({
                    val compras = estado["compras"].o().mapValues { (_, v) -> v.o().con("planeadas" to 0) }
                    alAplicar(estado.con("compras" to JsonObject(compras)))
                }) { Text(tr("Quitar solo las compras planeadas")) }
                Row(Modifier.clickable { temporada = !temporada }, verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(temporada, { temporada = it }, colors = CheckboxDefaults.colors(checkedColor = Colores.DORADO))
                    Text(tr("Reiniciar toda la Fractura (nueva temporada)…"))
                }
                if (temporada) {
                    Tenue(tr("Se borran compras, cofres elegidos y gastados.\n\n¿En qué piso estás ahora?"))
                    CampoNumero(tr("Piso alcanzado:"), piso, { piso = it })
                    Button({
                        val tope = pisosValidos(base).maxOrNull() ?: 0
                        alAplicar(obj("piso" to piso, "meta" to minOf(tope, piso + 20), "cofres" to obj(), "compras" to obj(),
                            "cofres_gastados" to obj(), "medallas_juego" to null))
                    }) { Text(tr("Nueva temporada")) }
                }
            }
        },
        confirmButton = { TextButton(alCerrar) { Text(tr("Cancelar")) } },
    )
    if (confirmar == "compras") {
        AlertDialog(
            onDismissRequest = { confirmar = null },
            title = { Text(tr("Fractura temporal")) },
            text = { Text(tr("¿Borrar todas las compras (hechas y planeadas) de esta cuenta?")) },
            confirmButton = { TextButton({ alAplicar(estado.con("compras" to obj())); confirmar = null }) { Text(tr("Borrar"), color = Colores.ERR) } },
            dismissButton = { TextButton({ confirmar = null }) { Text(tr("Cancelar")) } },
        )
    }
}
