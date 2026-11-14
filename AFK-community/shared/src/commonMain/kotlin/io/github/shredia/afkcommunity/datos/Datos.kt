package io.github.shredia.afkcommunity.datos

import io.github.shredia.afkcommunity.idiomas.tr
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/*
 * Acceso a la carpeta de datos (port de rutas.py y de los ayudantes de importar.py).
 * Las rutas son relativas al almacén: "cuentas/<cuenta>/<servidor>/runs.json", igual que datos_usuario/.
 */

const val ARCHIVO_PREFERENCIAS = "preferencias.json"
const val CARPETA_CUENTAS = "cuentas"
const val CARPETA_SIN_ASIGNAR = "_sin_asignar"
const val CARPETA_AMIGOS = "_amigos"
const val CARPETA_LOCAL = "local"
val CARPETAS_ESPECIALES = setOf(CARPETA_AMIGOS, CARPETA_SIN_ASIGNAR)

class Datos(val almacen: Almacen) {

    suspend fun leerJson(ruta: String): JsonElement? = leerJsonTexto(almacen.leerTexto(ruta))

    suspend fun leerObjeto(ruta: String): JsonObject? = leerJson(ruta) as? JsonObject

    suspend fun leerLista(ruta: String): JsonArray? = leerJson(ruta) as? JsonArray

    /** Escritura atómica (la hace el almacén: archivo .tmp y luego reemplazar). */
    suspend fun escribirJson(ruta: String, datos: JsonElement, indentado: Boolean = false) =
        almacen.escribirTexto(ruta, aTexto(datos, indentado))

    // ---------------- preferencias.json ----------------

    suspend fun preferencia(clave: String): JsonElement? = leerObjeto(ARCHIVO_PREFERENCIAS)?.get(clave)

    suspend fun guardarPreferencia(clave: String, valor: Any?) {
        val datos = (leerObjeto(ARCHIVO_PREFERENCIAS) ?: VACIO).con(clave to valor)
        runCatching { escribirJson(ARCHIVO_PREFERENCIAS, datos, indentado = true) }
    }

    // ---------------- carpetas ----------------

    /** Subcarpetas de [carpeta] (nombres). */
    suspend fun subcarpetas(carpeta: String): List<String> =
        almacen.listar(carpeta).filter { almacen.esCarpeta(unir(carpeta, it)) }

    /** La ficha del personaje: <carpeta>/<servidor>.json */
    suspend fun ficha(carpeta: String): JsonObject? = leerObjeto(unir(carpeta, "${nombre(carpeta)}.json"))

    suspend fun numeroRuns(carpeta: String): Int = leerLista(unir(carpeta, "runs.json"))?.size ?: 0

    /**
     * {uid_personaje: carpeta_del_servidor} leyendo cuentas/<cuenta>/<servidor>/<servidor>.json.
     * Si el mismo personaje aparece en varias cuentas, gana la cuenta con 'fetchedAt' más reciente.
     */
    suspend fun mapaPersonajes(): Map<String, String> {
        val mapa = LinkedHashMap<String, Pair<String, String>>()
        for (cuenta in almacen.listar(CARPETA_CUENTAS)) {
            val carpetaCuenta = unir(CARPETA_CUENTAS, cuenta)
            val datosCuenta = leerObjeto(unir(carpetaCuenta, "account.json")) ?: continue
            val fetched = datosCuenta["fetchedAt"].textoO()
            for (servidor in almacen.listar(carpetaCuenta)) {
                val carpeta = unir(carpetaCuenta, servidor)
                val personaje = leerObjeto(unir(carpeta, "$servidor.json")) ?: continue
                val uid = personaje["uid"].textoO()
                val previo = mapa[uid]
                if (uid.isNotEmpty() && (previo == null || fetched > previo.first)) mapa[uid] = fetched to carpeta
            }
        }
        return mapa.mapValues { it.value.second }
    }

    /** Carpeta del servidor del personaje; si no se conoce, cuentas/_sin_asignar/<character>. */
    fun carpetaPersonaje(mapa: Map<String, String>, character: String?): String {
        val c = character?.takeIf { it.isNotEmpty() } ?: "desconocido"
        return mapa[c] ?: unir(CARPETA_CUENTAS, CARPETA_SIN_ASIGNAR, c)
    }

    /** Mueve vieja -> nueva. Si las dos son carpetas, junta el contenido (lo que ya está en nueva se queda). */
    suspend fun mover(vieja: String, nueva: String) {
        if (!almacen.existe(nueva)) {
            copiar(vieja, nueva)
            almacen.borrar(vieja)
        } else if (almacen.esCarpeta(vieja) && almacen.esCarpeta(nueva)) {
            for (hijo in almacen.listar(vieja)) mover(unir(vieja, hijo), unir(nueva, hijo))
            if (almacen.listar(vieja).isEmpty()) almacen.borrar(vieja)
        }
    }

    private suspend fun copiar(origen: String, destino: String) {
        if (almacen.esCarpeta(origen)) {
            for (hijo in almacen.listar(origen)) copiar(unir(origen, hijo), unir(destino, hijo))
        } else {
            almacen.leerBytes(origen)?.let { almacen.escribirBytes(destino, it) }
        }
    }

    /** Todos los archivos de una carpeta (rutas completas), recorriendo subcarpetas. */
    suspend fun archivosDe(carpeta: String): List<String> {
        val salida = mutableListOf<String>()
        for (hijo in almacen.listar(carpeta)) {
            val ruta = unir(carpeta, hijo)
            if (almacen.esCarpeta(ruta)) salida += archivosDe(ruta) else salida += ruta
        }
        return salida
    }
}

/** Un servidor (tuyo o de un amigo) con runs. */
data class Servidor(val carpeta: String, val etiqueta: String, val nombre: String, val amigo: Boolean, val runs: Int)

/** Las carpetas cuentas/<cuenta>/<servidor>/ que tienen detalles (listar_servidores de Python). */
suspend fun Datos.listarServidores(): List<Servidor> {
    val resultado = mutableListOf<Servidor>()
    for (cuenta in almacen.listar(CARPETA_CUENTAS).sorted()) {
        val carpetaCuenta = unir(CARPETA_CUENTAS, cuenta)
        if (!almacen.esCarpeta(carpetaCuenta)) continue
        for (servidor in almacen.listar(carpetaCuenta).sorted()) {
            val carpeta = unir(carpetaCuenta, servidor)
            val detalles = unir(carpeta, "detalles")
            if (!almacen.esCarpeta(detalles)) continue
            val n = almacen.listar(detalles).count { it.endsWith(".json") }
            if (n == 0) continue
            val ficha = ficha(carpeta) ?: VACIO
            val nombre = ficha["name"].textoO(servidor)
            if (ficha["amigo"].verdad()) {
                val srv = if (ficha["svr_id"].verdad()) " · ${tr("Servidor")} ${ficha["svr_id"].py()}" else ""
                resultado += Servidor(carpeta, tr("Amigo: {0}{1} ({2} runs)", nombre, srv, n), nombre, true, n)
            } else {
                resultado += Servidor(carpeta, "$nombre · Servidor $servidor ($n runs)", nombre, false, n)
            }
        }
    }
    // primero tus servidores, luego los amigos (sort estable, como Python)
    return resultado.sortedBy { nombre(padre(it.carpeta)) == CARPETA_AMIGOS }
}
