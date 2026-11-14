package io.github.shredia.afkcommunity.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import io.github.shredia.afkcommunity.datos.CARPETA_AMIGOS
import io.github.shredia.afkcommunity.datos.CARPETA_CUENTAS
import io.github.shredia.afkcommunity.datos.Servidor
import io.github.shredia.afkcommunity.datos.a
import io.github.shredia.afkcommunity.datos.con
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.listarServidores
import io.github.shredia.afkcommunity.datos.obj
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.unir
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.APLICA_AMIGOS
import io.github.shredia.afkcommunity.logica.APLICA_YO
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.logica.Composicion
import io.github.shredia.afkcommunity.logica.Falta
import io.github.shredia.afkcommunity.logica.MODO_ROSTER_CASI
import io.github.shredia.afkcommunity.logica.MODO_ROSTER_OK
import io.github.shredia.afkcommunity.logica.MODO_ROSTER_TODOS
import io.github.shredia.afkcommunity.logica.Nivel
import io.github.shredia.afkcommunity.logica.Perfil
import io.github.shredia.afkcommunity.logica.anotarEstrellas
import io.github.shredia.afkcommunity.logica.armarPerfil
import io.github.shredia.afkcommunity.logica.cargarCorrecciones
import io.github.shredia.afkcommunity.logica.evaluarEquipo
import io.github.shredia.afkcommunity.logica.OPTIMO_GLOBAL
import io.github.shredia.afkcommunity.logica.Opciones
import io.github.shredia.afkcommunity.logica.Resultado
import io.github.shredia.afkcommunity.logica.aplicarSpManual
import io.github.shredia.afkcommunity.logica.arrendadosDe
import io.github.shredia.afkcommunity.logica.candidatosPorJefe
import io.github.shredia.afkcommunity.logica.cargarBloqueos
import io.github.shredia.afkcommunity.logica.cargarCuentaActual
import io.github.shredia.afkcommunity.logica.cargarIndice
import io.github.shredia.afkcommunity.logica.construirComposiciones
import io.github.shredia.afkcommunity.logica.formatoTiempo
import io.github.shredia.afkcommunity.logica.guardarBloqueos
import io.github.shredia.afkcommunity.logica.guardarSpManual
import io.github.shredia.afkcommunity.logica.optimizar
import io.github.shredia.afkcommunity.logica.ordenBoss
import io.github.shredia.afkcommunity.logica.para
import io.github.shredia.afkcommunity.logica.quitarBaneadas
import io.github.shredia.afkcommunity.logica.rotacionMasReciente
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject

/** De dónde salen los equipos al optimizar (el combo «Optimizar con» de la app Python). */
class Fuente(val clave: String, val etiqueta: String, val nombre: String, val carpetas: List<String>, val mezcla: Boolean = false) {
    val propia get() = clave == CLAVE_PROPIA

    companion object {
        const val CLAVE_PROPIA = "propia"
    }
}

class Mensaje(val texto: String, val color: Color)

class EstadoOptimizador(private val app: EstadoApp) {
    private val datos get() = app.datos

    var servidores by mutableStateOf<List<Servidor>>(emptyList())
        private set
    var carpeta by mutableStateOf<String?>(null)
        private set
    var comps by mutableStateOf<List<Composicion>>(emptyList())
        private set
    var runs by mutableStateOf(0)
        private set
    var reglas by mutableStateOf<List<JsonObject>>(emptyList())
        private set
    var jefes by mutableStateOf<List<String>>(emptyList())
        private set
    var rotacion by mutableStateOf(List(6) { "" })
    var opciones by mutableStateOf(Opciones())
        private set
    var fuentes by mutableStateOf<List<Fuente>>(emptyList())
        private set
    var fuente by mutableStateOf<Fuente?>(null)
    var resultado by mutableStateOf<Resultado?>(null)
        private set
    /** La rotación con la que se calculó [resultado]. */
    var rotacionResultado by mutableStateOf<List<String>>(emptyList())
        private set
    var ocupado by mutableStateOf(false)
        private set
    var mensaje by mutableStateOf<Mensaje?>(null)
        private set

    /** Tu roster (inventario + correcciones): para saber si puedes copiar un equipo de otro. */
    var perfil by mutableStateOf<Perfil?>(null)
        private set
    /** 'todos' | 'casi' | 'ok': qué equipos de otros se usan al optimizar con ellos (equipos_otros_roster). */
    var modoRoster by mutableStateOf(MODO_ROSTER_TODOS)
        private set
    /** Carpetas de «Tu selección» (rutas como las guarda Python: 'cuentas/<cuenta>/<servidor>'). */
    var seleccion by mutableStateOf<List<String>?>(null)
        private set
    /** {boss: equipos de todas las demás carpetas} para Resumen y Qué me falta; null mientras se cargan. */
    var otros by mutableStateOf<Map<String, List<Composicion>>?>(null)
        private set
    var hayOtros by mutableStateOf(false)
        private set

    private val cargadas = HashMap<String, List<Composicion>>()
    private val evaluaciones = HashMap<Composicion, Pair<Nivel?, List<Falta>>>()
    private var trabajo: Job? = null
    private var cargadoVersion = -1

    // ---------------- carga ----------------

    /** Al abrir la sección: lista de servidores y el primero (o el que estaba). */
    fun preparar() {
        if (cargadoVersion == app.versionDatos && carpeta != null) return
        cargadoVersion = app.versionDatos
        app.alcance.launch {
            opciones = leerOpciones()
            modoRoster = datos.preferencia("equipos_otros_roster").s() ?: MODO_ROSTER_TODOS
            seleccion = datos.preferencia("seleccion_fuentes").a().map { it.py() }.takeIf { datos.preferencia("seleccion_fuentes") != null }
            cacheServidores = null
            servidores = datos.listarServidores().filter { !it.amigo }
            val elegida = carpeta?.takeIf { c -> servidores.any { it.carpeta == c } } ?: servidores.firstOrNull()?.carpeta
            if (elegida != null) cargarServidor(elegida, forzar = true) else {
                carpeta = null; comps = emptyList()
            }
        }
    }

    fun invalidar() {
        cargadas.clear()
        otros = null
        cargadoVersion = -1
    }

    /** Se cambiaron las opciones, bloqueos o la rotación: lo calculado contra otros se rehace. */
    private fun cambioDeFiltros() {
        otros = null
        evaluaciones.clear()
    }

    /** Vuelve a leer tu roster (después de corregirlo). */
    fun recargarPerfil() {
        val c = carpeta ?: return
        app.alcance.launch {
            perfil = armarPerfil(cargarCuentaActual(datos, c), app.visuales, cargarCorrecciones(datos, c))
            evaluaciones.clear()
        }
    }

    /** (nivel, faltas) de un equipo según tu roster (en caché). */
    fun evaluar(comp: Composicion): Pair<Nivel?, List<Falta>> = evaluaciones.getOrPut(comp) { evaluarEquipo(comp, perfil) }

    fun cargarServidor(nueva: String, forzar: Boolean = false) {
        if (ocupado || (!forzar && nueva == carpeta)) return
        trabajo = app.alcance.launch {
            ocupado = true
            mensaje = Mensaje(tr("Cargando runs del servidor..."), Colores.INFO)
            try {
                val (lista, n) = withContext(Dispatchers.Default) { cargarComps(nueva, null) }
                carpeta = nueva
                comps = lista
                runs = n
                reglas = cargarBloqueos(datos, nueva, unir(CARPETA_CUENTAS, CARPETA_AMIGOS))
                perfil = armarPerfil(cargarCuentaActual(datos, nueva), app.visuales, cargarCorrecciones(datos, nueva))
                evaluaciones.clear()
                otros = null
                jefes = lista.map { it.bossId }.toSet().sortedWith(ordenBoss)
                resultado = null
                prepararFuentes()
                usarRotacionReciente()
                val completas = lista.filter { it.runCompleta }.map { it.runId }.toSet().size
                mensaje = Mensaje(tr("✓ {0} runs cargadas ({1} completas), {2} composiciones, {3} jefes distintos.",
                    n, completas, lista.size, jefes.size), Colores.OK)
            } catch (e: Exception) {
                mensaje = Mensaje(tr("Error al cargar: {0}", e.message ?: e::class.simpleName), Colores.ERR)
            } finally {
                ocupado = false
            }
        }
    }

    private var ultimasRuns: List<JsonObject> = emptyList()

    /** Las composiciones de una carpeta (índice + cuenta actual + SP manual). */
    private suspend fun cargarComps(c: String, dueno: String?): Pair<List<Composicion>, Int> {
        val indice = cargarIndice(datos, c) { m -> mensaje = Mensaje(m, Colores.INFO) }
        val actual = cargarCuentaActual(datos, c) ?: obj()
        val lista = construirComposiciones(indice.runs, actual["heroes_temporales"].a().map { it.py() }, arrendadosDe(actual))
        aplicarSpManual(lista, datos, c)
        anotarEstrellas(lista, app.visuales)
        lista.forEach { it.dueno = dueno; it.carpetaOrigen = c }
        if (dueno == null) ultimasRuns = indice.runs
        return lista to indice.runs.size
    }

    /** Todas las carpetas con runs (tus servidores y amigos). */
    suspend fun todasLasCarpetas(): List<Servidor> = servidoresTodos()

    private suspend fun prepararFuentes() {
        val otrosServidores = servidoresTodos().filter { it.carpeta != carpeta }
        val amigos = otrosServidores.filter { it.amigo }
        hayOtros = otrosServidores.isNotEmpty()
        val lista = mutableListOf(Fuente(Fuente.CLAVE_PROPIA, tr("Tus runs (este servidor)"), tr("Tú"), emptyList()))
        lista += otrosServidores.map { Fuente(it.carpeta, it.etiqueta, it.nombre, listOf(it.carpeta)) }
        if (amigos.size > 1 && otrosServidores.size > amigos.size) lista += Fuente("amigos",
            tr("Todos los amigos ({0})", amigos.size), tr("Todos los amigos"), amigos.map { it.carpeta })
        if (otrosServidores.isNotEmpty()) lista += Fuente("otros",
            if (otrosServidores.size > amigos.size) tr("Todos los demás: amigos y otros servidores ({0})", otrosServidores.size)
            else tr("Todos los amigos ({0})", amigos.size), tr("Todos los demás"), otrosServidores.map { it.carpeta })
        if (amigos.isNotEmpty()) lista += Fuente("yo+amigos", tr("Tus runs + todos los amigos ({0})", amigos.size),
            tr("Tú + todos los amigos"), amigos.map { it.carpeta }, mezcla = true)
        // «Tu selección»: por defecto este servidor + todos los amigos
        val elegidas = seleccion?.let { s -> servidoresTodos().filter { it.carpeta in s } }
            ?: servidoresTodos().filter { it.carpeta == carpeta || it.amigo }
        val incluyeActual = elegidas.any { it.carpeta == carpeta }
        lista += Fuente("personal", tr("Tu selección ({0} carpetas)", elegidas.size), tr("Tu selección"),
            elegidas.map { it.carpeta }.filter { it != carpeta }, mezcla = incluyeActual)
        fuentes = lista
        fuente = lista.firstOrNull { it.clave == fuente?.clave } ?: lista.first()
    }

    fun guardarSeleccion(carpetas: List<String>) {
        seleccion = carpetas
        app.alcance.launch {
            datos.guardarPreferencia("seleccion_fuentes", carpetas)
            prepararFuentes()
        }
    }

    fun cambiarModoRoster(modo: String) {
        modoRoster = modo
        app.alcance.launch { datos.guardarPreferencia("equipos_otros_roster", modo) }
        if (resultado != null) mensaje = Mensaje(tr("Opciones cambiadas. Pulsa ▶ Optimizar para recalcular."), Colores.WARN)
    }

    /** Equipos de otros que puedes armar (según el modo de roster). */
    private fun filtroRoster(lista: List<Composicion>): List<Composicion> {
        if (modoRoster !in setOf(MODO_ROSTER_CASI, MODO_ROSTER_OK) || perfil?.hayDatos != true) return lista
        val permitidos = if (modoRoster == MODO_ROSTER_OK) setOf(Nivel.PUEDO) else setOf(Nivel.PUEDO, Nivel.CASI)
        return lista.filter { evaluar(it).first in permitidos }
    }

    /** Equipos de [carpetas] (las carga si hace falta). */
    private suspend fun equiposDe(carpetas: List<String>): List<Composicion> {
        val salida = mutableListOf<Composicion>()
        for (c in carpetas) {
            salida += cargadas[c] ?: run {
                mensaje = Mensaje(tr("Cargando runs para comparar..."), Colores.INFO)
                val nombre = servidoresTodos().firstOrNull { it.carpeta == c }?.nombre ?: c.substringAfterLast('/')
                withContext(Dispatchers.Default) { cargarComps(c, nombre).first }.also { cargadas[c] = it }
            }
        }
        return salida
    }

    /** Carga (una vez) los equipos de todas las demás carpetas por jefe de la rotación, sin filtro de roster. */
    fun cargarOtros() {
        if (otros != null || carpeta == null || cargandoOtros) return
        cargandoOtros = true
        app.alcance.launch {
            try {
                val carpetas = servidoresTodos().filter { it.carpeta != carpeta }.map { it.carpeta }
                val lista = equiposDe(carpetas)
                val rot = (rotacion + List(6) { "" }).take(6)
                val (cands, _) = withContext(Dispatchers.Default) { candidatosPorJefe(lista, rot, opciones, baneosAmigos) }
                otros = rot.withIndex().filter { it.value.isNotEmpty() }.associate { (i, b) -> b to cands[i + 1].orEmpty() }
                if (mensaje?.texto == tr("Cargando runs para comparar...")) mensaje = null
            } catch (e: Exception) {
                mensaje = Mensaje(tr("Error al cargar: {0}", e.message ?: e::class.simpleName), Colores.ERR)
            } finally {
                cargandoOtros = false
            }
        }
    }

    private var cargandoOtros = false

    /** Tus equipos y los de las carpetas ya cargadas (para Estadísticas). */
    fun equiposCargados(): List<Composicion> = comps + cargadas.values.flatten()

    /** {boss: tus equipos} de la rotación, con las opciones y bloqueos actuales. */
    fun candidatosYo(): Map<String, List<Composicion>> {
        val rot = (rotacion + List(6) { "" }).take(6)
        val (cands, _) = candidatosPorJefe(comps, rot, opciones, baneosYo)
        return rot.withIndex().filter { it.value.isNotEmpty() }.associate { (i, b) -> b to cands[i + 1].orEmpty() }
    }

    // ---------------- rotación y opciones ----------------

    fun usarRotacionReciente() {
        val r = rotacionMasReciente(ultimasRuns)
        rotacion = (r + List(6) { "" }).take(6)
        cambioDeFiltros()
    }

    fun ponerJefe(posicion: Int, boss: String) {
        rotacion = rotacion.toMutableList().also { it[posicion] = boss }
        cambioDeFiltros()
    }

    fun cambiarOpciones(nuevas: Opciones) {
        opciones = nuevas
        cambioDeFiltros()
        app.alcance.launch {
            datos.guardarPreferencia("solo_completas", nuevas.soloCompletas)
            datos.guardarPreferencia("prohibir_repetir_mascota", nuevas.prohibirRepetirMascota)
            datos.guardarPreferencia("excluir_temporales", nuevas.excluirTemporales)
            datos.guardarPreferencia("excluir_fuera_roster", nuevas.excluirFueraRoster)
            datos.guardarPreferencia("limite_por_jefe", nuevas.limitePorJefe)
            datos.guardarPreferencia("tiempo_busqueda", nuevas.tiempoMaximo.toInt())
        }
        if (resultado != null) mensaje = Mensaje(tr("Opciones cambiadas. Pulsa ▶ Optimizar para recalcular."), Colores.WARN)
    }

    private suspend fun leerOpciones(): Opciones {
        val o = Opciones()
        suspend fun b(k: String, d: Boolean) = datos.preferencia(k)?.verdad() ?: d
        return Opciones(
            soloCompletas = b("solo_completas", o.soloCompletas),
            prohibirRepetirMascota = b("prohibir_repetir_mascota", o.prohibirRepetirMascota),
            limitePorJefe = datos.preferencia("limite_por_jefe")?.int(0) ?: 0,
            tiempoMaximo = datos.preferencia("tiempo_busqueda")?.real()?.coerceAtLeast(1.0) ?: o.tiempoMaximo,
            excluirTemporales = b("excluir_temporales", o.excluirTemporales),
            excluirFueraRoster = b("excluir_fuera_roster", o.excluirFueraRoster),
        )
    }

    // ---------------- bloqueos ----------------

    val baneosYo get() = para(reglas, APLICA_YO)
    val baneosAmigos get() = para(reglas, APLICA_AMIGOS)

    fun guardarReglas(nuevas: List<JsonObject>, aviso: String? = null) {
        val c = carpeta ?: return
        reglas = nuevas
        cambioDeFiltros()
        app.alcance.launch {
            guardarBloqueos(datos, c, nuevas)
            mensaje = Mensaje(aviso ?: tr("Bloqueos guardados. Pulsa ▶ Optimizar para recalcular."), Colores.WARN)
        }
    }

    fun agregarRegla(regla: JsonObject) = guardarReglas(reglas + regla)

    fun alternarRegla(i: Int) =
        guardarReglas(reglas.mapIndexed { j, r -> if (j == i) r.con("activo" to !(r["activo"]?.verdad() ?: true)) else r })

    fun borrarRegla(i: Int) = guardarReglas(reglas.filterIndexed { j, _ -> j != i })

    // ---------------- SP manual ----------------

    fun marcarSp(comp: Composicion, slot: Int?) {
        val c = comp.carpetaOrigen ?: carpeta ?: return
        app.alcance.launch {
            guardarSpManual(datos, c, comp, slot)
            comp.golden = slot?.let { kotlinx.serialization.json.JsonPrimitive(it) }
            comp.spManual = slot != null
            mensaje = Mensaje(tr("Special Power guardado."), Colores.OK)
        }
    }

    // ---------------- optimizar ----------------

    /** (equipos, baneos) de una fuente; carga lo que falte. */
    private suspend fun pool(f: Fuente): Pair<List<Composicion>, List<JsonObject>> {
        if (f.propia) return comps to baneosYo
        val deOtros = equiposDe(f.carpetas)
        if (f.mezcla) {
            // cada equipo con las reglas de su lado: 'tus equipos' / 'amigos' (+ las de 'todos')
            return quitarBaneadas(comps, rotacion, baneosYo) + filtroRoster(quitarBaneadas(deOtros, rotacion, baneosAmigos)) to emptyList()
        }
        return filtroRoster(deOtros) to baneosAmigos
    }

    private var cacheServidores: List<Servidor>? = null
    private suspend fun servidoresTodos() = cacheServidores ?: datos.listarServidores().also { cacheServidores = it }

    fun optimizar() {
        val f = fuente ?: return
        if (ocupado || comps.isEmpty()) return
        val rot = rotacion.toList()
        trabajo = app.alcance.launch {
            ocupado = true
            try {
                val (pool, baneos) = pool(f)
                mensaje = Mensaje(tr("Optimizando rotación {0} con {1}...", rot.joinToString("-"), f.etiqueta), Colores.INFO)
                val res = withContext(Dispatchers.Default) { optimizar(pool, rot, opciones, baneos) }
                resultado = res
                rotacionResultado = rot
                val ok = res.elegidas.isNotEmpty()
                val color = if (res.estado == OPTIMO_GLOBAL) Colores.OK else if (ok) Colores.WARN else Colores.ERR
                var texto = "${f.nombre}: ${tr(res.estado)} — ${res.detalle}"
                if (ok) texto += " · " + formatoTiempo(res.total)
                else {
                    val vacios = rot.filterIndexed { i, b -> b.isNotEmpty() && res.candidatos[i + 1].isNullOrEmpty() }.map { app.nombreJefe(it) }
                    texto += "  " + if (vacios.isNotEmpty()) tr("Sin equipos para: {0}. Revisa los bloqueos de ⚙ Configurar.", vacios.joinToString(", "))
                    else if (opciones.soloCompletas) tr("Prueba desmarcando 'Solo runs completas' o revisa los bloqueos.")
                    else tr("Revisa los bloqueos o la rotación.")
                }
                mensaje = Mensaje(texto, color)
            } catch (e: kotlinx.coroutines.CancellationException) {
                mensaje = Mensaje(tr("Búsqueda cancelada."), Colores.WARN)
                throw e
            } catch (e: Exception) {
                mensaje = Mensaje(tr("Error: {0}", e.message ?: e::class.simpleName), Colores.ERR)
            } finally {
                ocupado = false
            }
        }
    }

    fun cancelar() {
        trabajo?.cancel()
    }

    /** Equipos contra un jefe (por ID, de cualquier rotación), con las opciones y bloqueos actuales. */
    fun candidatosDe(boss: String, lista: List<Composicion> = comps, baneos: List<JsonObject> = baneosYo): List<Composicion> {
        if (lista.isEmpty() || boss.isEmpty()) return emptyList()
        val rot = if (boss in rotacion) rotacion else listOf(boss, "", "", "", "", "")
        val (cands, _) = candidatosPorJefe(lista, rot, opciones, baneos)
        return cands[rot.indexOf(boss) + 1].orEmpty()
    }
}
