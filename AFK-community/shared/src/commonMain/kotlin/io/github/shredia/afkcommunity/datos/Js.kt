package io.github.shredia.afkcommunity.datos

import io.github.shredia.afkcommunity.idiomas.pyReprDouble
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.JsonUnquotedLiteral
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.ExperimentalSerializationApi

/*
 * Los JSON de la app se manejan como en Python: objetos genéricos (dict / list) que se leen con tolerancia.
 * Estas funciones reproducen lo que hace el código Python con ellos:
 *
 *   d.get("x") or {}          ->  d["x"].o()
 *   d.get("x") or []          ->  d["x"].a()
 *   bool(d.get("x"))          ->  d["x"].verdad()
 *   str(d.get("x"))           ->  d["x"].py()            (None -> "None", como Python)
 *   d.get("x") or ""          ->  d["x"].textoO()
 *   _entero(d.get("x"))       ->  d["x"].entero()
 *
 * Así cada función Kotlin se compara línea a línea con su original.
 */

val JSON = Json { ignoreUnknownKeys = true; isLenient = true; allowSpecialFloatingPointValues = true }
private val JSON_INDENTADO = Json { prettyPrint = true; prettyPrintIndent = "  "; allowSpecialFloatingPointValues = true }

fun leerJsonTexto(texto: String?): JsonElement? =
    if (texto == null) null else runCatching { JSON.parseToJsonElement(texto) }.getOrNull()

fun aTexto(e: JsonElement, indentado: Boolean = false): String =
    if (indentado) JSON_INDENTADO.encodeToString(JsonElement.serializer(), e)
    else JSON.encodeToString(JsonElement.serializer(), e)

val VACIO = JsonObject(emptyMap())
val LISTA_VACIA = JsonArray(emptyList())

fun JsonElement?.esNulo(): Boolean = this == null || this is JsonNull

/** Verdad de Python: None, False, 0, "", [] y {} son falsos. */
fun JsonElement?.verdad(): Boolean = when (this) {
    null, JsonNull -> false
    is JsonPrimitive -> when {
        isString -> content.isNotEmpty()
        booleanOrNull != null -> booleanOrNull!!
        else -> doubleOrNull?.let { it != 0.0 } ?: true
    }
    is JsonArray -> isNotEmpty()
    is JsonObject -> isNotEmpty()
}

/** `x or {}` (solo si es un objeto). */
fun JsonElement?.o(): JsonObject = this as? JsonObject ?: VACIO

/** `x or []` (solo si es una lista). */
fun JsonElement?.a(): JsonArray = this as? JsonArray ?: LISTA_VACIA

/** Los elementos de la lista que son objetos (`[x for x in lista if isinstance(x, dict)]`). */
fun JsonElement?.objetos(): List<JsonObject> = a().filterIsInstance<JsonObject>()

/** El texto de un valor simple (texto o número tal como está escrito), o null. */
fun JsonElement?.s(): String? = (this as? JsonPrimitive)?.takeIf { it !is JsonNull }?.let {
    if (it.isString) it.content
    else it.booleanOrNull?.let { b -> if (b) "True" else "False" } ?: it.content
}

/** str(valor) de Python: None -> "None"; los números enteros sin ".0". */
fun JsonElement?.py(): String = when (this) {
    null, JsonNull -> "None"
    is JsonPrimitive -> s() ?: "None"
    else -> aTexto(this)
}

/** `valor or ""` convertido a texto. */
fun JsonElement?.textoO(defecto: String = ""): String = if (verdad()) py() else defecto

/** int(v) de Python con valor por defecto si no se puede (como _entero). */
fun JsonElement?.entero(defecto: Long? = 0): Long? {
    val p = this as? JsonPrimitive ?: return defecto
    if (p is JsonNull) return defecto
    if (p.isString) return p.content.trim().replace("_", "").toLongOrNull() ?: defecto
    p.booleanOrNull?.let { return if (it) 1 else 0 }
    return p.content.toLongOrNull() ?: p.doubleOrNull?.takeIf { it.isFinite() }?.toLong() ?: defecto
}

fun JsonElement?.int(defecto: Int = 0): Int = entero(defecto.toLong())?.toInt() ?: defecto

/** float(v) de Python, o null. */
fun JsonElement?.real(): Double? {
    val p = this as? JsonPrimitive ?: return null
    if (p is JsonNull) return null
    if (p.isString) return p.content.trim().toDoubleOrNull()
    p.booleanOrNull?.let { return if (it) 1.0 else 0.0 }
    return p.doubleOrNull
}

fun JsonElement?.bool(): Boolean = verdad()

/** Un número que se escribe igual que en Python (23.391, 1762963000.1234567, 5). */
@OptIn(ExperimentalSerializationApi::class)
fun numeroPy(x: Double): JsonElement = if (x.isFinite()) JsonUnquotedLiteral(pyReprDouble(x)) else JsonPrimitive(x)

/** Convierte valores Kotlin (texto, números, listas, mapas, JsonElement) a JSON. */
fun aJson(v: Any?): JsonElement = when (v) {
    null -> JsonNull
    is JsonElement -> v
    is String -> JsonPrimitive(v)
    is Boolean -> JsonPrimitive(v)
    is Int -> JsonPrimitive(v)
    is Long -> JsonPrimitive(v)
    is Double -> numeroPy(v)
    is Float -> numeroPy(v.toDouble())
    is Number -> JsonPrimitive(v)
    is Map<*, *> -> JsonObject(v.entries.associate { (k, x) -> k.toString() to aJson(x) })
    is Iterable<*> -> JsonArray(v.map { aJson(it) })
    is Array<*> -> JsonArray(v.map { aJson(it) })
    else -> JsonPrimitive(v.toString())
}

/** obj("a" to 1, "b" to "x") — un dict de Python escrito en Kotlin (mantiene el orden). */
fun obj(vararg pares: Pair<String, Any?>): JsonObject = JsonObject(linkedMapOf(*pares.map { it.first to aJson(it.second) }.toTypedArray()))

/** {**d, "k": v} */
fun JsonObject.con(vararg pares: Pair<String, Any?>): JsonObject {
    val m = LinkedHashMap<String, JsonElement>(this)
    for ((k, v) in pares) m[k] = aJson(v)
    return JsonObject(m)
}

/** Copia sin las claves dadas. */
fun JsonObject.sin(vararg claves: String): JsonObject = JsonObject(LinkedHashMap(this).apply { claves.forEach { remove(it) } })

fun JsonObject.mutable(): LinkedHashMap<String, JsonElement> = LinkedHashMap(this)

/** _clave de Python: str(valor or "").strip().upper() (0 y False cuentan como valor). */
fun clave(v: JsonElement?): String = if (v.esNulo()) "" else v.py().trim().uppercase()

fun clave(v: String?): String = (v ?: "").trim().uppercase()
