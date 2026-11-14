package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryScrollableTabRow
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.shredia.afkcommunity.datos.Servidor
import io.github.shredia.afkcommunity.datos.con
import io.github.shredia.afkcommunity.datos.mutable
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.N_
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.APLICA_TODO
import io.github.shredia.afkcommunity.logica.CAMPOS_COLECCION
import io.github.shredia.afkcommunity.logica.CAMPOS_HEROE
import io.github.shredia.afkcommunity.logica.CAMPOS_PERFIL
import io.github.shredia.afkcommunity.logica.EntradaPerfil
import io.github.shredia.afkcommunity.logica.MODO_ROSTER_CASI
import io.github.shredia.afkcommunity.logica.MODO_ROSTER_OK
import io.github.shredia.afkcommunity.logica.MODO_ROSTER_TODOS
import io.github.shredia.afkcommunity.logica.NOMBRES_APLICA
import io.github.shredia.afkcommunity.logica.Visuales
import io.github.shredia.afkcommunity.logica.cargarCorrecciones
import io.github.shredia.afkcommunity.logica.catalogo
import io.github.shredia.afkcommunity.logica.correccionDe
import io.github.shredia.afkcommunity.logica.describir
import io.github.shredia.afkcommunity.logica.guardarCorrecciones
import io.github.shredia.afkcommunity.logica.normalizar
import io.github.shredia.afkcommunity.logica.nuevaReglaBaneo
import io.github.shredia.afkcommunity.logica.nuevaReglaLimite
import io.github.shredia.afkcommunity.ui.CampoNumero
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.Desplegable
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Iconos
import io.github.shredia.afkcommunity.ui.Seccion
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject

private val PESTANAS_CONFIGURAR = listOf(N_("Bloqueos"), N_("Mi roster"), N_("Fuentes"), N_("Búsqueda"))

/** «Configurar optimizador»: bloqueos, mi roster, fuentes y búsqueda (la ventana ⚙ Configurar de Python). */
@Composable
fun PantallaBloqueos(estado: EstadoApp) {
    val opt = estado.optimizador
    LaunchedEffect(estado.versionDatos) { opt.preparar() }
    var pestana by rememberSaveable { mutableIntStateOf(0) }
    if (opt.carpeta == null && !opt.ocupado && opt.servidores.isEmpty()) {
        Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(tr("Todavía no hay runs"), fontWeight = FontWeight.SemiBold, fontSize = 18.sp)
            Button({ estado.ir(Seccion.IMPORTAR) }) { Text(tr("Importar datos")) }
        }
        return
    }
    Column(Modifier.fillMaxSize()) {
        PrimaryScrollableTabRow(pestana, containerColor = Colores.FONDO, contentColor = Colores.DORADO, edgePadding = 8.dp) {
            PESTANAS_CONFIGURAR.forEachIndexed { i, t ->
                Tab(pestana == i, { pestana = i }, text = { Text(tr(t)) }, selectedContentColor = Colores.DORADO,
                    unselectedContentColor = Colores.MUTED)
            }
        }
        when (pestana) {
            0 -> Reglas(estado)
            1 -> MiRoster(estado)
            2 -> Fuentes(estado)
            else -> Busqueda(estado)
        }
    }
}

// ============================================================
// Bloqueos: lista y nueva regla
// ============================================================

private val TIPOS = listOf("HEROE" to N_("Héroe"), "MASCOTA" to N_("Mascota"), "COLECCION" to N_("Colección"))

/** [(clave, texto)] de condiciones para el tipo elegido. */
private fun campos(objeto: String): List<Pair<String, String>> = when (objeto) {
    "MASCOTA" -> listOf("banear" to tr("No usar"))
    "COLECCION" -> listOf("no_tengo" to tr("No la tengo")) + CAMPOS_COLECCION.map { (k, v) -> k to tr("{0} máximo", tr(v)) }
    else -> listOf("banear" to tr("No usar (o no lo tengo)"), "copia" to tr("No usar la copia prestada/prueba")) +
        CAMPOS_HEROE.map { (k, v) -> k to tr("{0} máximo", tr(v)) }
}

private fun ayuda(campo: String, valor: Int): String = when (campo) {
    "quality" -> tr("Ascensión máxima: {0}", Visuales.nombreCalidad(kotlinx.serialization.json.JsonPrimitive(valor)))
    "estrellas" -> tr("★ de habilidad de la colección (0 a 3)")
    "muebles" -> tr("Piezas de mueble (0 a 9)")
    "sig" -> tr("Nivel del artículo exclusivo (SI): 0, 10, 20, 30…")
    "engraving" -> tr("Grabado: 30, 60, 80…")
    "mythic" -> tr("Cantidad de afijos míticos")
    "level" -> tr("Nivel de la colección")
    "banear" -> tr("Descarta cualquier equipo que lo use.")
    "copia" -> tr("Solo descarta los equipos donde se usó prestado o de prueba.")
    "no_tengo" -> tr("Descarta los equipos que usan esa colección.")
    else -> ""
}

@Composable
private fun Reglas(estado: EstadoApp) {
    val opt = estado.optimizador
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Tenue(tr("Todo lo que el optimizador no debe usar: héroes o mascotas que no quieres, colecciones que no tienes y builds hasta las que llegas (SI, grabado, muebles, ascensión). Cada regla puede valer para todos los equipos, solo los tuyos o solo los de amigos."))
        }
        item { NuevaRegla(estado) }
        if (opt.reglas.isEmpty()) item { Tenue(tr("No hay bloqueos."), color = Colores.TENUE) }
        itemsIndexed(opt.reglas) { i, r ->
            Tarjeta {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(describir(r) { estado.nombreJefe(it) }, color = if (r["activo"]?.verdad() != false) Colores.TEXTO else Colores.TENUE)
                        Tenue(tr(NOMBRES_APLICA[r["aplica"].textoO(APLICA_TODO)] ?: ""))
                    }
                    Switch(r["activo"]?.verdad() != false, { opt.alternarRegla(i) },
                        colors = SwitchDefaults.colors(checkedThumbColor = Colores.SOBRE_DORADO, checkedTrackColor = Colores.DORADO))
                    IconButton({ opt.borrarRegla(i) }) { Icon(Iconos.borrar, tr("Quitar"), Modifier.size(20.dp), tint = Colores.MUTED) }
                }
            }
        }
        opt.mensaje?.let { m -> item { Text(m.texto, color = m.color, fontSize = 13.sp) } }
    }
}

@Composable
private fun NuevaRegla(estado: EstadoApp) {
    val opt = estado.optimizador
    var objeto by rememberSaveable { mutableStateOf("HEROE") }
    var nombre by rememberSaveable { mutableStateOf("") }
    var campo by rememberSaveable { mutableStateOf("banear") }
    var maximo by rememberSaveable { mutableIntStateOf(2) }
    var jefe by rememberSaveable { mutableStateOf("TODOS") }
    var aplica by rememberSaveable { mutableStateOf(APLICA_TODO) }
    var aviso by remember { mutableStateOf<Pair<String, Boolean>?>(null) }
    val cat = remember(opt.comps) { catalogo(opt.comps) }
    val nombres = remember(opt.comps, objeto) {
        when (objeto) {
            "COLECCION" -> opt.comps.flatMap { c -> c.heroes.mapNotNull { h -> h["collection"].o()["name"].textoO().ifEmpty { null } } }.toSet()
            else -> cat[objeto]?.keys.orEmpty()
        }.sortedBy { normalizar(it) }
    }
    val opcionesCampo = campos(objeto)
    if (opcionesCampo.none { it.first == campo }) campo = opcionesCampo.first().first
    Tarjeta {
        Text(tr("NUEVA REGLA"), color = Colores.MUTED, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            for ((valor, texto) in TIPOS) FilterChip(objeto == valor, { objeto = valor; nombre = "" }, { Text(tr(texto)) },
                colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Colores.SELECCION, selectedLabelColor = Colores.DORADO))
        }
        OutlinedTextField(nombre, { nombre = it }, Modifier.fillMaxWidth(), label = { Text(tr("Nombre")) }, singleLine = true,
            placeholder = { if (objeto != "MASCOTA") Text(tr("(cualquiera)")) })
        val q = normalizar(nombre)
        if (q.isNotEmpty() && nombre !in nombres) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (n in nombres.filter { q in normalizar(it) }.take(8)) {
                    Text(n, Modifier.clickable { nombre = n }.padding(vertical = 4.dp, horizontal = 2.dp), color = Colores.INFO, fontSize = 13.sp)
                }
            }
        }
        Desplegable(tr("Condición"), opcionesCampo, opcionesCampo.first { it.first == campo }, { it.second }, { campo = it.first },
            Modifier.padding(top = 6.dp))
        val conMaximo = campo !in setOf("banear", "copia", "no_tengo")
        if (conMaximo) CampoNumero(tr("Máximo"), maximo, { maximo = it }, Modifier.padding(top = 6.dp))
        Tenue(ayuda(campo, maximo), Modifier.padding(top = 2.dp))
        Desplegable(tr("Jefe"), listOf("TODOS") + opt.jefes, jefe, { if (it == "TODOS") tr("Todos los jefes") else "${estado.nombreJefe(it)} · $it" },
            { jefe = it }, Modifier.padding(top = 6.dp))
        Desplegable(tr("Aplica a"), NOMBRES_APLICA.keys.toList(), aplica, { tr(NOMBRES_APLICA.getValue(it)) }, { aplica = it },
            Modifier.padding(top = 6.dp))
        Button({
            var n = nombre.trim()
            if (n.isEmpty() || n == tr("(cualquiera)")) {
                if (campo in setOf("banear", "copia") || objeto == "MASCOTA") { aviso = tr("Elige un nombre de la lista.") to false; return@Button }
                n = "*"
            }
            val nueva = if (campo in setOf("banear", "copia")) nuevaReglaBaneo(objeto, n, cat[objeto]?.get(n).orEmpty(), jefe, campo == "copia", aplica)
            else nuevaReglaLimite(objeto, n, if (campo == "no_tengo") "estrellas" else campo, if (campo == "no_tengo") -1 else maximo, jefe, aplica)
            opt.agregarRegla(nueva)
            aviso = tr("✓ Agregada: {0}", describir(nueva, conJefe = false)) to true
            nombre = ""
        }, Modifier.fillMaxWidth().padding(top = 8.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Colores.DORADO, contentColor = Colores.SOBRE_DORADO)) {
            Text(tr("+ Agregar"))
        }
        aviso?.let { (t, ok) -> Text(t, color = if (ok) Colores.OK else Colores.WARN, fontSize = 13.sp) }
    }
}

// ============================================================
// Mi roster: lo que tienes, y correcciones a mano
// ============================================================

@Composable
private fun MiRoster(estado: EstadoApp) {
    val opt = estado.optimizador
    val alcance = rememberCoroutineScope()
    var tipo by rememberSaveable { mutableStateOf("HEROE") }
    var buscar by rememberSaveable { mutableStateOf("") }
    var soloNo by rememberSaveable { mutableStateOf(false) }
    var correcciones by remember { mutableStateOf<JsonObject?>(null) }
    var editar by remember { mutableStateOf<Pair<String, EntradaPerfil>?>(null) }
    val carpeta = opt.carpeta
    LaunchedEffect(carpeta) { correcciones = carpeta?.let { cargarCorrecciones(estado.datos, it) } }
    val perfil = opt.perfil

    fun guardar(clave: String, entrada: EntradaPerfil?) {
        val c = carpeta ?: return
        val actuales = correcciones ?: JsonObject(emptyMap())
        val delTipo = actuales[tipo].o().mutable()
        if (entrada == null) delTipo.remove(clave) else delTipo[clave] = correccionDe(entrada)
        val nuevas = actuales.con(tipo to JsonObject(delTipo))
        correcciones = nuevas
        alcance.launch {
            guardarCorrecciones(estado.datos, c, nuevas)
            opt.recargarPerfil()
        }
    }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        item {
            Tenue(tr("Lo que tienes según tu afk-inventory.json. Corrige lo que no sepa (p. ej. un héroe que ya subiste): se usa para saber si puedes copiar el equipo de otro jugador."))
            if (perfil?.conInventario != true) Tenue(tr("Sin captura de la cuenta: importa el afk-inventory.json de este personaje."), color = Colores.WARN)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for ((valor, texto) in TIPOS) FilterChip(tipo == valor, { tipo = valor }, { Text(tr(texto)) },
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Colores.SELECCION, selectedLabelColor = Colores.DORADO))
            }
            OutlinedTextField(buscar, { buscar = it }, Modifier.fillMaxWidth(), label = { Text(tr("Buscar")) }, singleLine = true)
            Row(Modifier.clickable { soloNo = !soloNo }, verticalAlignment = Alignment.CenterVertically) {
                Checkbox(soloNo, { soloNo = it }, colors = CheckboxDefaults.colors(checkedColor = Colores.DORADO))
                Text(tr("Solo lo que no tengo / corregido"))
            }
        }
        val q = normalizar(buscar)
        val entradas = perfil?.de(tipo).orEmpty().entries.filter { (_, d) ->
            (q.isEmpty() || q in normalizar(d.nombre)) && (!soloNo || !d.tengo || d.manual)
        }.sortedBy { normalizar(it.value.nombre) }
        items(entradas) { (clave, d) ->
            Row(Modifier.fillMaxWidth().clickable { editar = clave to d }.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(d.nombre, color = if (d.tengo) Colores.TEXTO else Colores.ERR)
                    Tenue(if (!d.tengo) tr("No lo tengo") else textoValores(tipo, d))
                }
                if (d.manual) Text(tr("corregido a mano"), color = Colores.INFO, fontSize = 11.sp)
            }
        }
    }

    editar?.let { (clave, d) ->
        var tengo by remember(clave) { mutableStateOf(d.tengo) }
        val valores = remember(clave) { mutableStateOf(d.valores.toMap()) }
        AlertDialog(
            onDismissRequest = { editar = null },
            title = { Text(d.nombre) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(Modifier.clickable { tengo = !tengo }, verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(tengo, { tengo = it }, colors = CheckboxDefaults.colors(checkedColor = Colores.DORADO))
                        Text(tr("Lo tengo"))
                    }
                    if (tengo) for ((campo, etiqueta) in CAMPOS_PERFIL.getValue(tipo)) {
                        CampoNumero(tr(etiqueta), valores.value[campo] ?: 0, { valores.value = valores.value + (campo to it) })
                    }
                }
            },
            confirmButton = {
                TextButton({
                    guardar(clave, EntradaPerfil(d.nombre, tengo, valores.value.toMutableMap()))
                    editar = null
                }) { Text(tr("Aplicar corrección")) }
            },
            dismissButton = {
                Row {
                    if (d.manual) TextButton({ guardar(clave, null); editar = null }) { Text(tr("Volver a lo del inventario")) }
                    TextButton({ editar = null }) { Text(tr("Cancelar")) }
                }
            },
        )
    }
}

private fun textoValores(tipo: String, d: EntradaPerfil): String =
    CAMPOS_PERFIL.getValue(tipo).mapNotNull { (campo, etiqueta) ->
        val v = d.valores[campo] ?: return@mapNotNull null
        if (tipo == "HEROE" && campo == "quality") Visuales.nombreCalidad(kotlinx.serialization.json.JsonPrimitive(v)) else "${tr(etiqueta)} $v"
    }.joinToString(" · ")

// ============================================================
// Fuentes: «Tu selección»
// ============================================================

@Composable
private fun Fuentes(estado: EstadoApp) {
    val opt = estado.optimizador
    var carpetas by remember { mutableStateOf<List<Servidor>>(emptyList()) }
    LaunchedEffect(opt.carpeta) { carpetas = opt.todasLasCarpetas() }
    val elegidas = opt.seleccion ?: carpetas.filter { it.carpeta == opt.carpeta || it.amigo }.map { it.carpeta }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        item {
            Tenue(tr("Las carpetas de «Tu selección» en «Optimizar con»: tus servidores (de cualquier cuenta) y tus amigos. Si incluye este servidor, el óptimo puede tomar cada jefe de tus equipos o de los de otros."))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton({ opt.guardarSeleccion(carpetas.map { it.carpeta }) }) { Text(tr("Todas")) }
                TextButton({ opt.guardarSeleccion(emptyList()) }) { Text(tr("Ninguna")) }
            }
        }
        if (carpetas.isEmpty()) item { Tenue(tr("No hay carpetas con runs.")) }
        items(carpetas) { s ->
            val marcada = s.carpeta in elegidas
            Row(Modifier.fillMaxWidth().clickable {
                opt.guardarSeleccion(if (marcada) elegidas - s.carpeta else elegidas + s.carpeta)
            }, verticalAlignment = Alignment.CenterVertically) {
                Checkbox(marcada, null, colors = CheckboxDefaults.colors(checkedColor = Colores.DORADO))
                Text(s.etiqueta + if (s.carpeta == opt.carpeta) "  ·  " + tr("este servidor") else "")
            }
        }
    }
}

// ============================================================
// Búsqueda: equipos de amigos según tu roster
// ============================================================

@Composable
private fun Busqueda(estado: EstadoApp) {
    val opt = estado.optimizador
    Column(Modifier.fillMaxSize().padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Tarjeta {
            Text(tr("EQUIPOS DE AMIGOS Y DE TUS OTROS SERVIDORES"), color = Colores.MUTED, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
            Tenue(tr("Se comparan con 'Mi roster' para saber si puedes copiarlos."))
            for ((valor, texto) in listOf(MODO_ROSTER_TODOS to N_("Usar todos"),
                MODO_ROSTER_CASI to N_("Solo los que puedes armar o casi (✅ 🟡): tienes los héroes"),
                MODO_ROSTER_OK to N_("Solo los que puedes armar tal cual (✅)"))) {
                Row(Modifier.fillMaxWidth().clickable { opt.cambiarModoRoster(valor) }, verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(opt.modoRoster == valor, { opt.cambiarModoRoster(valor) }, colors = RadioButtonDefaults.colors(selectedColor = Colores.DORADO))
                    Text(tr(texto))
                }
            }
        }
        Tenue(tr("Las demás opciones de búsqueda (runs completas, mascotas, prestados, tiempo) están en el Optimizador."))
    }
}
