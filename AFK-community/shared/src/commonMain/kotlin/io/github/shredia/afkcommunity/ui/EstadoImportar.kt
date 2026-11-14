package io.github.shredia.afkcommunity.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import io.github.shredia.afkcommunity.datos.LectorZip
import io.github.shredia.afkcommunity.datos.nombre
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.idiomas.formatear
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.FuenteRuns
import io.github.shredia.afkcommunity.logica.InfoCopia
import io.github.shredia.afkcommunity.logica.InfoRuns
import io.github.shredia.afkcommunity.logica.PersonajeInventario
import io.github.shredia.afkcommunity.logica.TipoArchivo
import io.github.shredia.afkcommunity.logica.amigos
import io.github.shredia.afkcommunity.logica.analizarRuns
import io.github.shredia.afkcommunity.logica.carpetaAmigo
import io.github.shredia.afkcommunity.logica.carpetasServidor
import io.github.shredia.afkcommunity.logica.detectar
import io.github.shredia.afkcommunity.logica.exportarCopia
import io.github.shredia.afkcommunity.logica.importarCopia
import io.github.shredia.afkcommunity.logica.importarCopiaDeAmigo
import io.github.shredia.afkcommunity.logica.importarInventario
import io.github.shredia.afkcommunity.logica.importarRuns
import io.github.shredia.afkcommunity.logica.importarRunsApp
import io.github.shredia.afkcommunity.logica.infoCopia
import io.github.shredia.afkcommunity.logica.personajeDeInventario
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject

/** Lo que la importación necesita preguntar (los diálogos de ventana_importar.py). */
sealed class Pregunta {
    /** Personaje nuevo del afk-inventory.json: ¿cómo se llama? (el archivo no trae el nombre). */
    class NombrePersonaje(val info: PersonajeInventario, val respuesta: CompletableDeferred<String?>) : Pregunta()

    /** ¿De quién son estas runs? */
    class DuenoRuns(val analisis: InfoRuns, val personajes: List<Pair<String, String>>,
                    val respuesta: CompletableDeferred<Dueno?>) : Pregunta()

    /** ¿De quién es esta copia (.zip)? */
    class DuenoCopia(val info: InfoCopia, val respuesta: CompletableDeferred<Dueno?>) : Pregunta()
}

/** La respuesta: tus runs (en [carpeta]), de un amigo, una simulación, o tu copia para restaurar. */
sealed class Dueno {
    class Mio(val carpeta: String) : Dueno()
    class Amigo(val nombre: String, val servidor: String, val simulada: Boolean = false) : Dueno()
    data object Restaurar : Dueno()
}

class LineaLog(val texto: String, val color: androidx.compose.ui.graphics.Color = Colores.TEXTO)

class OpcionExportar(val carpeta: String, val texto: String, val amigo: Boolean, val runs: Int)

class EstadoImportar(private val app: EstadoApp) {
    private val datos get() = app.datos

    var ocupado by mutableStateOf(false)
        private set
    var pregunta by mutableStateOf<Pregunta?>(null)
        private set
    val log = mutableStateListOf<LineaLog>()

    private fun escribir(texto: String, color: androidx.compose.ui.graphics.Color = Colores.TEXTO) {
        log += LineaLog(texto, color)
        if (log.size > 200) log.removeAt(0)
    }

    private suspend fun <T> preguntar(crear: (CompletableDeferred<T>) -> Pregunta): T {
        val respuesta = CompletableDeferred<T>()
        pregunta = crear(respuesta)
        try {
            return respuesta.await()
        } finally {
            pregunta = null
        }
    }

    fun elegirEImportar() {
        if (ocupado) return
        app.alcance.launch {
            val archivo = app.plataforma.elegirArchivo() ?: return@launch
            ocupado = true
            log.clear()
            try {
                escribir(tr("Leyendo {0}...", archivo.nombre))
                if (archivo.nombre.lowercase().endsWith(".zip")) {
                    val zip = archivo.abrirZip() ?: throw IllegalArgumentException(tr("El .zip no es una copia de la app."))
                    zip.use { importarZip(it) }
                    return@launch
                }
                val bytes = archivo.leerBytes()
                val detectado = withContext(Dispatchers.Default) { detectar(archivo.nombre, bytes, false) }
                when (detectado.tipo) {
                    TipoArchivo.INVENTARIO -> importarInventarioUi(detectado.datos!!)
                    TipoArchivo.RUNS -> importarRunsUi(detectado.runs!!)
                    TipoArchivo.RUNS_APP -> {
                        val d = detectado.datos!!
                        escribir(tr("Runs compartidas de {0} (con SP y estadísticas).", d["nombre"].textoO("?")))
                        val runs = FuenteRuns.deRuns(d["runs"].objetos())
                        val dueno = preguntarDueno(runs) ?: return@launch cancelado()
                        val carpeta = carpetaDe(dueno)
                        val r = importarRunsApp(datos, d, carpeta) { escribir(it, Colores.MUTED) }
                        escribir(tr("Runs nuevas: {0} · ya las tenías: {1} · completadas con SP / estadísticas: {2}",
                            r.nuevas, r.yaEstaban, r.completadas))
                        terminar()
                    }
                    TipoArchivo.COPIA, null -> throw IllegalArgumentException(tr(
                        "El archivo no es afk-runs.json, afk-inventory.json, runs compartidas ni una copia (.zip) de la app."))
                }
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Throwable) {
                escribir(tr("Error: {0}", e.message ?: e::class.simpleName), Colores.ERR)
            } finally {
                ocupado = false
                pregunta = null
            }
        }
    }

    private fun cancelado() = escribir(tr("Importación cancelada."), Colores.WARN)

    private fun terminar() {
        escribir(tr("Importación terminada."), Colores.OK)
        app.datosCambiaron()
    }

    private suspend fun importarInventarioUi(inv: JsonObject) {
        val info = personajeDeInventario(datos, inv)
        var nombrePj: String? = null
        if (info.carpeta == null) {
            escribir(tr("Personaje nuevo: UID {0} · servidor {1}.", info.uid, info.servidor))
            nombrePj = preguntar<String?> { Pregunta.NombrePersonaje(info, it) } ?: return cancelado()
        } else {
            escribir(tr("Personaje: {0} · servidor {1} · UID {2}", info.nombre.ifEmpty { "?" }, info.servidor, info.uid))
        }
        val r = importarInventario(datos, inv, app.visuales, nombrePj) { escribir(it, Colores.MUTED) }
        escribir(tr("Mi cuenta actualizada: {0} héroes, {1} colecciones, {2} objetos.", r.heroes, r.colecciones, r.objetos), Colores.OK)
        escribir(tr("Ahora puedes importar las runs de este personaje (afk-runs.json) y elegirlo en «Son mías»."))
        terminar()
    }

    private suspend fun preguntarDueno(runs: FuenteRuns): Dueno? {
        val analisis = analizarRuns(datos, runs)
        if (analisis.nc == 0) {
            escribir(tr("El archivo no trae runs de NC (solo de otros modos)."), Colores.ERR)
            return null
        }
        escribir(describirRuns(analisis))
        escribir(tr("Elige de quién son..."), Colores.MUTED)
        val personajes = carpetasServidor(datos)
        return preguntar { Pregunta.DuenoRuns(analisis, personajes, it) }
    }

    private suspend fun carpetaDe(dueno: Dueno): String = when (dueno) {
        is Dueno.Mio -> dueno.carpeta
        is Dueno.Amigo -> carpetaAmigo(datos, dueno.nombre, dueno.servidor, dueno.simulada)
        Dueno.Restaurar -> error("no aplica")
    }

    private suspend fun importarRunsUi(runs: FuenteRuns) {
        val dueno = preguntarDueno(runs) ?: return cancelado()
        val carpeta = carpetaDe(dueno)
        escribir(tr("Destino: {0}", carpeta))
        val r = importarRuns(datos, runs, carpeta, app.visuales) { escribir(it, Colores.MUTED) }
        escribir(tr("Runs nuevas: {0} · ya las tenías: {1} · reimportadas: {2} · otros modos omitidos: {3}",
            r.nuevas, r.yaEstaban, r.actualizadas, r.otrosModos), Colores.OK)
        if (r.conEstadisticas > 0) escribir(tr("Estadísticas agregadas a {0} runs que ya tenías del sitio.", r.conEstadisticas))
        escribir(tr("Ábrelas en el Optimizador NC eligiendo «{0}».",
            if (r.amigo) tr("Amigo: {0}", nombre(carpeta)) else tr("Servidor {0}", nombre(carpeta))))
        terminar()
    }

    private suspend fun importarZip(zip: LectorZip) {
        val info = infoCopia(datos, zip)
        val dueno = preguntar<Dueno?> { Pregunta.DuenoCopia(info, it) } ?: return cancelado()
        when (dueno) {
            is Dueno.Amigo -> {
                escribir(tr("Runs de {0} ({1} en la copia)...", dueno.nombre, info.runs))
                val r = importarCopiaDeAmigo(datos, zip, dueno.nombre, dueno.servidor) { escribir(it, Colores.MUTED) }
                escribir(tr("Runs nuevas: {0} · ya las tenías: {1}", r.nuevas, r.yaEstaban), Colores.OK)
                escribir(tr("Ábrelas en el Optimizador NC eligiendo «{0}».", tr("Amigo: {0}", dueno.nombre)))
            }
            Dueno.Restaurar -> {
                escribir(tr("La copia trae: {0}", info.carpetas.joinToString(", ") { "${it.first}/${it.second}" }))
                val n = importarCopia(datos, zip) { escribir(it, Colores.MUTED) }
                escribir(tr("{0} archivos restaurados.", n), Colores.OK)
            }
            is Dueno.Mio -> return
        }
        terminar()
    }

    // ---------------- exportar ----------------

    /** Lo que se puede guardar: tus personajes y tus amigos. */
    suspend fun opcionesExportar(): List<OpcionExportar> {
        val salida = mutableListOf<OpcionExportar>()
        for ((c, _) in carpetasServidor(datos)) {
            val ficha = datos.ficha(c)
            val runs = datos.numeroRuns(c)
            salida += OpcionExportar(c, tr("{0} · servidor {1} · {2} runs", ficha?.get("name").textoO("?"), nombre(c), runs), false, runs)
        }
        for (a in amigos(datos)) salida += OpcionExportar(a.carpeta, tr("Amigo: {0} · {1} runs", a.nombre, a.runs), true, a.runs)
        return salida
    }

    fun exportar(carpeta: String) {
        if (ocupado) return
        app.alcance.launch {
            ocupado = true
            log.clear()
            try {
                val ficha = datos.ficha(carpeta)
                val nombrePj = ficha?.get("name").textoO(nombre(carpeta)).replace(Regex("[^A-Za-z0-9_-]+"), "_")
                val sugerido = "AFK-Community_${nombrePj}_${nombre(carpeta)}.zip"
                escribir(tr("Comprimiendo {0}...", sugerido))
                var n = 0
                val destino = app.plataforma.guardarZip(sugerido) { zip ->
                    n = exportarCopia(datos, carpeta, zip) { escribir(it, Colores.MUTED) }
                }
                if (destino == null) cancelado() else escribir(tr("Listo: {0} archivos en {1}", n, destino), Colores.OK)
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Throwable) {
                escribir(tr("Error: {0}", e.message ?: e::class.simpleName), Colores.ERR)
            } finally {
                ocupado = false
            }
        }
    }
}

/** 'Una run de NC del…' / '297 runs de NC, del … al …' (describir_runs de Python). */
fun describirRuns(a: InfoRuns): String {
    var texto = if (a.nc == 1 && a.una != null) {
        val res = a.una["result"].o()
        tr("Una run de NC del {0}: {1} jefes en {2} s (batalla {3}).", a.desde.ifEmpty { "?" },
            res["bossesKilled"].textoO("?"), formatear("{0:.3f}", listOf((res["timeMs"].real() ?: 0.0) / 1000)),
            a.una["battleId"].textoO("?"))
    } else tr("{0} runs de NC, del {1} al {2}.", a.nc, a.desde.ifEmpty { "?" }, a.hasta.ifEmpty { "?" })
    if (a.otros > 0) texto += " " + tr("{0} de otros modos se omiten.", a.otros)
    if (a.yaEstan > 0) texto += " " + if (a.nc == 1) tr("Ya la tienes: se completa, no se duplica.")
    else tr("Ya tienes {0}: se completan, no se duplican.", a.yaEstan)
    return texto
}
