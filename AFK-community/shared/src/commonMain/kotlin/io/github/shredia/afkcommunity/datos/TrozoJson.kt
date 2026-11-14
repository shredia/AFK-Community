package io.github.shredia.afkcommunity.datos

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/*
 * Lectura de JSON grandes sin armar el árbol completo en memoria.
 *
 * Los archivos del sitio pesan ~75 MB (afk-runs.json, afk-inventory.json). Python los carga enteros sin problema,
 * pero un árbol de kotlinx de ese tamaño no cabe en la memoria de un teléfono. Aquí se recorre el texto UTF-8 tal
 * cual (los caracteres de estructura son ASCII) y se parsea solo el trozo que hace falta: cada run por separado, o
 * las partes pequeñas del inventario.
 */
class TrozoJson(val bytes: ByteArray, val inicio: Int = saltarEspacios(bytes, 0), val fin: Int = finValor(bytes, inicio)) {

    val tamano: Int get() = fin - inicio

    /** El primer carácter: '{', '[', '"', o el de un número / true / false / null. */
    val primero: Char get() = if (inicio < bytes.size) bytes[inicio].toInt().toChar() else ' '

    fun texto(): String = bytes.decodeToString(inicio, fin)

    fun parsear(): JsonElement = JSON.parseToJsonElement(texto())

    /** Los elementos de una lista, sin parsearlos. */
    fun elementos(): Sequence<TrozoJson> = sequence {
        if (primero != '[') return@sequence
        var p = saltarEspacios(bytes, inicio + 1)
        while (p < fin && bytes[p] != ']'.code.toByte()) {
            val f = finValor(bytes, p)
            yield(TrozoJson(bytes, p, f))
            p = saltarEspacios(bytes, f)
            if (p < fin && bytes[p] == ','.code.toByte()) p = saltarEspacios(bytes, p + 1)
        }
    }

    /** Los pares (clave, valor) de un objeto, sin parsear los valores. */
    fun pares(): Sequence<Pair<String, TrozoJson>> = sequence {
        if (primero != '{') return@sequence
        var p = saltarEspacios(bytes, inicio + 1)
        while (p < fin && bytes[p] != '}'.code.toByte()) {
            val finClave = finValor(bytes, p)
            val clave = (JSON.parseToJsonElement(bytes.decodeToString(p, finClave)) as JsonPrimitive).content
            p = saltarEspacios(bytes, finClave)
            if (p < fin && bytes[p] == ':'.code.toByte()) p = saltarEspacios(bytes, p + 1)
            val f = finValor(bytes, p)
            yield(clave to TrozoJson(bytes, p, f))
            p = saltarEspacios(bytes, f)
            if (p < fin && bytes[p] == ','.code.toByte()) p = saltarEspacios(bytes, p + 1)
        }
    }

    /**
     * El valor parseado, pero las partes de más de [limite] bytes quedan reducidas: un objeto grande conserva solo
     * sus campos pequeños (recursivamente) y una lista grande queda vacía.
     */
    fun podado(limite: Int = 2_000_000): JsonElement = when {
        tamano <= limite -> parsear()
        primero == '{' -> JsonObject(LinkedHashMap<String, JsonElement>().apply {
            for ((k, v) in pares()) put(k, v.podado(limite))
        })
        primero == '[' -> JsonArray(emptyList())
        else -> parsear()
    }

    companion object {
        fun saltarEspacios(b: ByteArray, desde: Int): Int {
            var p = desde
            while (p < b.size) {
                val c = b[p].toInt()
                if (c == 0x20 || c == 0x0A || c == 0x0D || c == 0x09) p++
                else if (p == 0 && b.size >= 3 && c == 0xEF.toByte().toInt() && b[1] == 0xBB.toByte() && b[2] == 0xBF.toByte()) p += 3   // BOM
                else break
            }
            return p
        }

        /** Posición justo después del valor que empieza en [desde]. */
        fun finValor(b: ByteArray, desde: Int): Int {
            if (desde >= b.size) return desde
            val comillas = '"'.code.toByte()
            val barra = '\\'.code.toByte()
            when (b[desde].toInt().toChar()) {
                '"' -> {
                    var p = desde + 1
                    while (p < b.size) {
                        if (b[p] == barra) p += 2
                        else if (b[p] == comillas) return p + 1
                        else p++
                    }
                    return b.size
                }
                '{', '[' -> {
                    var nivel = 0
                    var p = desde
                    while (p < b.size) {
                        when (b[p].toInt().toChar()) {
                            '"' -> { p = finValor(b, p); continue }
                            '{', '[' -> nivel++
                            '}', ']' -> { nivel--; if (nivel == 0) return p + 1 }
                        }
                        p++
                    }
                    return b.size
                }
                else -> {
                    var p = desde
                    while (p < b.size) {
                        val c = b[p].toInt().toChar()
                        if (c == ',' || c == '}' || c == ']' || c == ' ' || c == '\n' || c == '\r' || c == '\t') break
                        p++
                    }
                    return p
                }
            }
        }
    }
}
