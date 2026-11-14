package io.github.shredia.afkcommunity.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.Plataforma
import io.github.shredia.afkcommunity.datos.leerJsonTexto
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.idiomas.N_
import io.github.shredia.afkcommunity.idiomas.cambiarIdioma
import io.github.shredia.afkcommunity.logica.ARCHIVO_TABLAS
import io.github.shredia.afkcommunity.logica.Visuales
import io.github.shredia.afkcommunity.recursos.Res
import kotlinx.coroutines.CoroutineScope
import kotlinx.serialization.json.JsonObject
import org.jetbrains.compose.resources.ExperimentalResourceApi

/** Secciones del menú (el mismo orden que el menú lateral de la app Python). */
enum class Seccion(val texto: String, val grupo: String?) {
    INICIO(N_("Inicio"), null),
    OPTIMIZADOR(N_("Optimizador"), N_("NIGHTMARE CORRIDOR")),
    EXPLORAR(N_("Explorar equipos"), N_("NIGHTMARE CORRIDOR")),
    BLOQUEOS(N_("Configurar optimizador"), N_("NIGHTMARE CORRIDOR")),
    PROGRESO(N_("Progreso semanal"), N_("NIGHTMARE CORRIDOR")),
    CUENTA(N_("Mi cuenta"), N_("CUENTA")),
    AMIGOS(N_("Amigos"), N_("CUENTA")),
    FRACTURA(N_("Fractura temporal"), N_("OTROS")),
    IMPORTAR(N_("Importar / exportar"), N_("DATOS")),
    AJUSTES(N_("Ajustes"), N_("DATOS")),
}

const val URL_SITIO = "https://esperianarchive.com"
const val URL_RUNS = "$URL_SITIO/my-runs"
const val URL_INVENTARIO = "$URL_SITIO/inventory"
const val URL_DISCORD = "https://discord.gg/bX5nQpZX6q"

/** El estado de toda la app. Cada plataforma solo aporta su [Plataforma]. */
class EstadoApp(val plataforma: Plataforma, val alcance: CoroutineScope) {
    val datos = Datos(plataforma.almacen)

    var seccion by mutableStateOf(Seccion.INICIO)
    var idioma by mutableStateOf("es")
        private set
    var visuales by mutableStateOf<Visuales?>(null)
        private set
    var listo by mutableStateOf(false)
        private set

    /** Sube cada vez que cambian los datos (una importación, un amigo borrado...): las pantallas se recargan. */
    var versionDatos by mutableIntStateOf(0)
        private set

    val optimizador = EstadoOptimizador(this)
    val importar = EstadoImportar(this)

    init {
        CacheImagenes.almacen = plataforma.almacen
    }

    suspend fun iniciar() {
        idioma = cambiarIdioma(datos.preferencia("idioma").s())
        visuales = Visuales(cargarTablas())
        listo = true
    }

    /** tablas_sitio.json: la descargada por el usuario si existe; si no, la que viene con la app. */
    @OptIn(ExperimentalResourceApi::class)
    private suspend fun cargarTablas(): JsonObject {
        val propia = datos.leerObjeto("assets/$ARCHIVO_TABLAS")
        if (propia != null && propia.isNotEmpty()) return propia
        return runCatching { leerJsonTexto(Res.readBytes("files/assets/$ARCHIVO_TABLAS").decodeToString()).o() }
            .getOrDefault(JsonObject(emptyMap()))
    }

    suspend fun usarIdioma(codigo: String) {
        idioma = cambiarIdioma(codigo)
        datos.guardarPreferencia("idioma", idioma)
        versionDatos++
    }

    fun datosCambiaron() {
        versionDatos++
        optimizador.invalidar()
    }

    fun ir(destino: Seccion) {
        seccion = destino
    }

    /** Botón atrás del teléfono: vuelve a Inicio. Devuelve false si ya estaba en Inicio (la app se cierra). */
    fun atras(): Boolean {
        if (seccion == Seccion.INICIO) return false
        seccion = Seccion.INICIO
        return true
    }

    fun nombreJefe(boss: String): String = visuales?.nombreJefe(boss) ?: boss
}
