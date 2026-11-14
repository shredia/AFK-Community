package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.a
import io.github.shredia.afkcommunity.datos.entero
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.N_
import io.github.shredia.afkcommunity.idiomas.pyReprDouble
import io.github.shredia.afkcommunity.idiomas.tr
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/*
 * Traduce los datos de una run a las imágenes del sitio (port de navegador/visuales.py).
 * Usa tablas_sitio.json (viene con la app; las mismas tablas que usa la página para dibujar a los héroes).
 */

const val ARCHIVO_TABLAS = "tablas_sitio.json"
val NOMBRES_CALIDAD = listOf(N_("Desconocida"), N_("Común"), N_("Raro"), N_("Raro+"), N_("Élite"), N_("Élite+"),
    N_("Legendario"), N_("Legendario+"), N_("Mítico"), N_("Mítico+"))
const val ICONO_MUEBLE = "/game-ui/icon_furniture_quality_{q}.png"

class Visuales(val t: JsonObject) {

    private val equipoPorNombre: Map<String, List<Pair<String, JsonElement?>>> = buildMap<String, MutableList<Pair<String, JsonElement?>>> {
        for ((ident, e) in t["equipo"].o()) {
            getOrPut(e.o()["name"].textoO().trim().lowercase()) { mutableListOf() }.add(ident to e.o()["quality"])
        }
    }

    val disponible: Boolean get() = t.isNotEmpty()

    private fun tabla(nombre: String) = t[nombre].o()

    // ---------------- jefes ----------------

    /** (nombre, imageUrl o null). */
    fun jefe(bossId: String?): Pair<String, String?> {
        val info = tabla("jefes")[bossId ?: "None"].o()
        val nombre = info["name"].textoO("Boss $bossId")
        var url = info["imageUrl"].s()
        if (url.isNullOrEmpty()) {
            // Variantes ("X (Monstrous)") sin imagen: usar la de la versión base
            val base = nombre.replace(Regex("\\s*\\(.*?\\)\\s*$"), "").trim().lowercase()
            for ((_, otro) in tabla("jefes")) {
                val o = otro.o()
                if (o["imageUrl"].verdad() && o["name"].textoO().trim().lowercase() == base) url = o["imageUrl"].s()
            }
            if (url.isNullOrEmpty()) {
                for ((_, nc) in tabla("jefes_nc")) {
                    val n = nc.o()
                    if (n["headUrl"].verdad() && n["name"].textoO().trim().lowercase() in setOf(base, nombre.lowercase())) {
                        url = n["headUrl"].s()
                        break
                    }
                }
            }
        }
        return nombre to url?.takeIf { it.isNotEmpty() }
    }

    fun nombreJefe(bossId: String?): String = if (disponible) jefe(bossId).first else bossId.orEmpty()

    // ---------------- héroe ----------------

    fun estrella(grabado: Long?): String? {
        val umbrales = tabla("estrellas").entries.mapNotNull { (k, v) -> k.toIntOrNull()?.let { it to v.s() } }.sortedBy { it.first }
        var url: String? = null
        for ((minimo, imagen) in umbrales) if ((grabado ?: 0) >= minimo) url = imagen
        return url
    }

    fun marco(calidad: JsonElement?): String? = tabla("marcos")[calidad.py()].s()

    fun faccion(faccion: JsonElement?): String? = tabla("facciones")[faccion.py()].s()

    fun iconoSi(heroTid: JsonElement?, sig: JsonElement?): String? {
        val niveles = tabla("si_iconos")[heroTid.py()].a()
        var url: String? = null
        for (par in niveles) {
            val p = par.a()
            if ((sig.entero(0) ?: 0) >= (p.getOrNull(0).entero(0) ?: 0)) url = p.getOrNull(1).s()
        }
        return url
    }

    fun iconoMueble(calidad: Int = 9) = ICONO_MUEBLE.replace("{q}", calidad.toString())

    /** Marco de SI de la esquina superior izquierda del retrato (SI+10 ... +40). */
    fun marcoSiRetrato(sig: JsonElement?): String? {
        val marcos = tabla("marcos_si_retrato")
        if (sig == null || sig is kotlinx.serialization.json.JsonNull || marcos.isEmpty()) return null
        val claves = marcos.keys.mapNotNull { it.toIntOrNull() }.sorted()
        val nivel = minOf(sig.int(0), claves.last())
        return marcos[nivel.toString()].s()
    }

    /** (insignia, corona) de muebles: 3+ piezas -> lv1, 9 -> lv2, 9 al nivel máximo -> lv3 + corona. */
    fun insigniaMuebles(h: JsonObject): Pair<String?, String?> {
        val piezas = h["furniture"].o()["pieces"].int(0)
        val slots = h["furnitureSlots"].a()
        val maximo = t["mueble_max_nivel"].int(3).takeIf { it != 0 } ?: 3
        val completo = piezas >= 9 && slots.size >= 9 && slots.take(9).all { it.int(0) >= maximo }
        return when {
            completo -> "/game-ui/skill_lv3_1.png" to "/game-ui/skill_lv3_2.png"
            piezas >= 9 -> "/game-ui/skill_lv2.png" to null
            piezas >= 3 -> "/game-ui/skill_lv1.png" to null
            else -> null to null
        }
    }

    // ---------------- colección ----------------

    /** Nivel de habilidad (estrellas) de una colección, igual que el sitio. */
    fun estrellasColeccion(col: JsonObject): Int? {
        val nivelBase = tabla("coleccion_niveles")[col["level"].py()] ?: return null
        if (nivelBase is kotlinx.serialization.json.JsonNull) return null
        val naturalezas = t["coleccion_skill_nature"].a().map { it.int() }.toSet()
        val valores = tabla("coleccion_skill_valores")[col["tid"].py()].o()
        val extra = col["affixes"].objetos().filter { it["nature"].int(0) in naturalezas }
            .sumOf { valores[it["quality"].py()].int(0) }
        return minOf(t["coleccion_max_skill"].int(3).takeIf { it != 0 } ?: 3, nivelBase.int() + extra)
    }

    /** Texto '+1.83%' del afijo, o null. */
    fun valorAfijo(colTid: JsonElement?, nature: JsonElement?, calidad: JsonElement?): String? {
        val atributo = tabla("afijos")[nature.py()].o()["attribute"].s() ?: return null
        val valor = tabla("afijo_valores")[colTid.py()].o()[calidad.py()].o()[atributo].real() ?: return null
        val sufijo = if (".PR" in atributo) "%" else ""
        // f"{round(valor, 2):g}": sin ceros sobrantes (1.5, 2, 1.83)
        val r = kotlin.math.round(valor * 100) / 100
        val texto = if (r == kotlin.math.floor(r)) r.toLong().toString() else pyReprDouble(r)
        return "+$texto$sufijo"
    }

    fun colorCalidadAfijo(calidad: JsonElement?): String? = tabla("afijo_calidades")[calidad.py()].o()["TextColor"].s()

    fun imagenColeccion(tid: JsonElement?): String? = tabla("colecciones_img")[tid.py()].o()["imageUrl"].s()

    /** (nombre, icono) de un afijo de colección. */
    fun afijo(nature: JsonElement?, calidad: JsonElement?): Pair<String, String?> {
        val info = tabla("afijos")[nature.py()].o()
        val nombre = info["name"].textoO("Naturaleza ${nature.py()}")
        val iconos = info["icons"].o()
        val icono = iconos[calidad.py()].s()
            ?: iconos.keys.maxByOrNull { it.toIntOrNull() ?: 0 }?.let { iconos[it].s() }
        return nombre to icono
    }

    fun nombreColeccion(tid: Any?): String {
        val k = tid?.toString() ?: "None"
        return tabla("colecciones")[k].o()["name"].s()?.takeIf { it.isNotEmpty() }
            ?: tabla("colecciones_img")[k].o()["name"].s()?.takeIf { it.isNotEmpty() } ?: "Colección $k"
    }

    // ---------------- equipo ----------------

    private fun idEquipo(gear: JsonObject): String? {
        val candidatos = equipoPorNombre[gear["name"].textoO().trim().lowercase()].orEmpty()
        if (candidatos.isEmpty()) return null
        return candidatos.firstOrNull { it.second == gear["quality"] }?.first ?: candidatos[0].first
    }

    fun imagenEquipo(gear: JsonObject): String? = idEquipo(gear)?.let { tabla("equipo_img")[it].s() }

    fun tierEquipo(gear: JsonObject): String? {
        val tier = idEquipo(gear)?.let { tabla("equipo")[it].o()["tier"] } ?: return null
        val n = tier.entero(null) ?: return null
        return if (n == 0L) "M" else "T$n"
    }

    fun faccionEquipo(tag: JsonElement?): Pair<String?, String?> {
        val info = tabla("facciones_equipo")[tag.py()].o()
        return info["name"].s() to info["icon"].s()
    }

    companion object {
        fun nombreCalidad(calidad: JsonElement?): String {
            val q = calidad.entero(null) ?: return calidad.py()
            if (q >= 10) return if (q == 10L) tr("Ascendido") else tr("Ascendido {0}★", q - 10)
            return if (q in 0 until NOMBRES_CALIDAD.size) tr(NOMBRES_CALIDAD[q.toInt()]) else q.toString()
        }

        fun numeroEstrellas(calidad: JsonElement?): Int = ((calidad.entero(null) ?: return 0) - 10).coerceIn(0, 5).toInt()

        /** Héroes especiales (hyper): true si usan su Special Power en esta ronda; "?" si no se sabe. */
        fun usaSp(h: JsonObject, golden: JsonElement?): Boolean? {
            if (!h["hyper"].verdad()) return null
            if (golden.py() == "?") return null
            return golden != null && golden !is kotlinx.serialization.json.JsonNull && golden.py() == h["slot"].py()
        }
    }
}
