package io.github.shredia.afkcommunity.idiomas

/*
 * El subconjunto de str.format de Python que usan las frases de los archivos de idioma, con el mismo resultado:
 *   {0} {1}...   {}            el dato como lo escribe Python (str): True, None, 12.0, 1e+16...
 *   {0:.3f}  {1:+.3f}  {0:7.3f}   decimales fijos (redondeo exacto, como Python), signo, ancho
 *   {0:02d}                    entero con ceros a la izquierda
 *   {0:<20}  {0:>5}  {0:^9}     alineación con relleno
 *   {{  }}                     llaves literales
 */

/** El texto con los datos insertados. Lanza IllegalArgumentException donde Python lanzaría un error. */
fun formatear(plantilla: String, args: List<Any?>): String {
    val salida = StringBuilder()
    var i = 0
    var automatico = 0
    while (i < plantilla.length) {
        val c = plantilla[i]
        when {
            c == '{' && plantilla.getOrNull(i + 1) == '{' -> { salida.append('{'); i += 2 }
            c == '}' && plantilla.getOrNull(i + 1) == '}' -> { salida.append('}'); i += 2 }
            c == '}' -> throw IllegalArgumentException("'}' suelta en «$plantilla»")
            c == '{' -> {
                val fin = plantilla.indexOf('}', i)
                if (fin < 0) throw IllegalArgumentException("'{' sin cerrar en «$plantilla»")
                val campo = plantilla.substring(i + 1, fin)
                val dosPuntos = campo.indexOf(':')
                val nombre = if (dosPuntos >= 0) campo.substring(0, dosPuntos) else campo
                val spec = if (dosPuntos >= 0) campo.substring(dosPuntos + 1) else ""
                val indice = if (nombre.isEmpty()) automatico++ else
                    nombre.toIntOrNull() ?: throw IllegalArgumentException("campo no numérico {$nombre}")
                if (indice !in args.indices) throw IllegalArgumentException("falta el dato {$indice}")
                salida.append(aplicarFormato(args[indice], spec))
                i = fin + 1
            }
            else -> { salida.append(c); i++ }
        }
    }
    return salida.toString()
}

private class Spec(
    val relleno: Char, val alineacion: Char?, val signo: Char?, val ceros: Boolean,
    val ancho: Int, val precision: Int?, val tipo: Char?,
)

private fun leerSpec(spec: String): Spec {
    var i = 0
    var relleno = ' '
    var alineacion: Char? = null
    if (spec.length >= 2 && spec[1] in "<>=^") {
        relleno = spec[0]; alineacion = spec[1]; i = 2
    } else if (spec.isNotEmpty() && spec[0] in "<>=^") {
        alineacion = spec[0]; i = 1
    }
    var signo: Char? = null
    if (i < spec.length && spec[i] in "+- ") signo = spec[i++]
    var ceros = false
    if (i < spec.length && spec[i] == '0') { ceros = true; i++ }
    val inicioAncho = i
    while (i < spec.length && spec[i].isDigit()) i++
    val ancho = spec.substring(inicioAncho, i).toIntOrNull() ?: 0
    var precision: Int? = null
    if (i < spec.length && spec[i] == '.') {
        val inicio = ++i
        while (i < spec.length && spec[i].isDigit()) i++
        precision = spec.substring(inicio, i).toIntOrNull() ?: throw IllegalArgumentException("precisión vacía")
    }
    val tipo = if (i < spec.length) spec[i++] else null
    if (i != spec.length || (tipo != null && tipo !in "dfs")) throw IllegalArgumentException("formato no soportado: $spec")
    return Spec(relleno, alineacion, signo, ceros, ancho, precision, tipo)
}

private fun aplicarFormato(valor: Any?, spec: String): String {
    if (spec.isEmpty()) return pyStr(valor)
    val s = leerSpec(spec)
    val numero = valor is Number || valor is Boolean
    val texto: String = when (s.tipo) {
        'd' -> {
            val entero = when (valor) {
                is Boolean -> if (valor) 1L else 0L
                is Number -> valor.toDouble().let { d ->
                    if (d.isNaN() || d.isInfinite() || d != kotlin.math.floor(d) || !esEntero(valor))
                        throw IllegalArgumentException("{:d} necesita un entero, no $valor")
                    valor.toLong()
                }
                else -> throw IllegalArgumentException("{:d} necesita un entero, no $valor")
            }
            conSigno(entero < 0, if (entero < 0) (-entero).toString() else entero.toString(), s.signo)
        }
        'f' -> {
            val x = when (valor) {
                is Number -> valor.toDouble()
                is Boolean -> if (valor) 1.0 else 0.0
                else -> throw IllegalArgumentException("{:f} necesita un número, no $valor")
            }
            val negativo = x < 0 || (x == 0.0 && 1.0 / x < 0)   // -0.0 también lleva signo, como en Python
            val cuerpo = when {
                x.isNaN() -> "nan"
                x.isInfinite() -> "inf"
                else -> formatoFijo(kotlin.math.abs(x), s.precision ?: 6)
            }
            conSigno(negativo && !x.isNaN(), cuerpo, s.signo)
        }
        else -> {
            if (s.precision != null && !numero) pyStr(valor).take(s.precision) else pyStr(valor)
        }
    }
    if (texto.length >= s.ancho) return texto
    val falta = s.ancho - texto.length
    val alineacion = s.alineacion ?: when {
        s.ceros && numero -> '='
        numero -> '>'
        else -> '<'
    }
    val relleno = if (s.ceros && s.alineacion == null) '0' else s.relleno
    return when (alineacion) {
        '<' -> texto + relleno.toString().repeat(falta)
        '>' -> relleno.toString().repeat(falta) + texto
        '^' -> relleno.toString().repeat(falta / 2) + texto + relleno.toString().repeat(falta - falta / 2)
        else -> {   // '=': el relleno va entre el signo y los dígitos
            val conSigno = texto.firstOrNull()?.let { it in "+- " } == true
            if (conSigno) texto[0] + relleno.toString().repeat(falta) + texto.substring(1)
            else relleno.toString().repeat(falta) + texto
        }
    }
}

private fun conSigno(negativo: Boolean, cuerpo: String, signo: Char?) = when {
    negativo -> "-$cuerpo"
    signo == '+' -> "+$cuerpo"
    signo == ' ' -> " $cuerpo"
    else -> cuerpo
}

/**
 * ¿Es un entero de Kotlin (Int, Long...)? En Kotlin/JS los números son todos de JavaScript y 3.0 no se distingue
 * de 3: ahí un decimal sin parte fraccionaria cuenta como entero (str da "3", no "3.0"). En JVM, Android y Wasm
 * se distinguen como en Python.
 */
internal fun esEntero(valor: Any?): Boolean = when (valor) {
    is Long -> true
    // En JS «is Int» (y «is Short», «is Byte») es verdadero para cualquier número (2.5e-05, 1e16): un Int de
    // verdad no tiene decimales y cabe en 32 bits
    is Int, is Short, is Byte -> (valor as Number).toDouble().let {
        it == kotlin.math.floor(it) && it in Int.MIN_VALUE.toDouble()..Int.MAX_VALUE.toDouble()
    }
    else -> false
}

/** El valor como lo escribe str() de Python. */
fun pyStr(valor: Any?): String = when {
    valor == null -> "None"
    valor is Boolean -> if (valor) "True" else "False"
    esEntero(valor) -> valor.toString()
    else -> pyStrNoEntero(valor)
}

private fun pyStrNoEntero(valor: Any): String = when (valor) {
    is Double -> pyReprDouble(valor)
    is Float -> pyReprDouble(valor.toDouble())
    else -> valor.toString()
}

/**
 * repr() de un float de Python: los dígitos más cortos que lo identifican, en notación fija si
 * 1e-4 <= |x| < 1e16 y si no científica (1e+16, 2.5e-05). Siempre con ".0" si es entero.
 */
fun pyReprDouble(x: Double): String {
    if (x.isNaN()) return "nan"
    if (x.isInfinite()) return if (x > 0) "inf" else "-inf"
    if (x == 0.0) return if (1.0 / x < 0) "-0.0" else "0.0"
    // Dígitos y exponente a partir del texto de la plataforma (JVM y navegadores dan los más cortos)
    val crudo = kotlin.math.abs(x).toString().lowercase()
    val (mantisa, exp) = crudo.split('e').let { it[0] to (it.getOrNull(1)?.toInt() ?: 0) }
    val punto = mantisa.indexOf('.').let { if (it < 0) mantisa.length else it }
    var digitos = mantisa.replace(".", "")
    var exponente = exp + punto - 1          // x = d.ddd × 10^exponente
    val ceros = digitos.indexOfFirst { it != '0' }
    digitos = digitos.substring(ceros).trimEnd('0').ifEmpty { "0" }
    exponente -= ceros
    val signo = if (x < 0) "-" else ""
    return if (exponente in -4..15) {
        val texto = if (exponente >= 0) {
            val entera = digitos.padEnd(exponente + 1, '0')
            val parteEntera = entera.substring(0, exponente + 1)
            val decimales = entera.substring(exponente + 1)
            parteEntera + "." + decimales.ifEmpty { "0" }
        } else {
            "0." + "0".repeat(-exponente - 1) + digitos
        }
        signo + texto
    } else {
        val m = if (digitos.length > 1) digitos[0] + "." + digitos.substring(1) else digitos
        val e = if (exponente < 0) "-" + (-exponente).toString().padStart(2, '0')
                else "+" + exponente.toString().padStart(2, '0')
        "$signo${m}e$e"
    }
}

/**
 * Un número NO negativo con [decimales] decimales, redondeado como Python: según su valor binario exacto
 * y, si queda justo a la mitad, al par (format(2.675, '.2f') = '2.67'; format(0.125, '.2f') = '0.12').
 */
expect fun formatoFijo(valor: Double, decimales: Int): String

/**
 * Para la web. toFixed() de JavaScript redondea los empates hacia arriba (0.125 → '0.13'); Python, al par
 * ('0.12'). No sirve detectar el empate con valor·10^d: 2.675·100 da 267.5 en coma flotante, aunque 2.675 sea
 * en realidad 2.67499…
 *
 * Por eso se pide a toFixed el valor con 100 decimales, que son sus dígitos binarios EXACTOS (un double con
 * hasta 100 bits fraccionarios, es decir, cualquiera ≥ 1e-14, tiene una expansión decimal de ≤ 100 cifras), y
 * se redondea ese texto al par, igual que Python.
 */
internal fun fijoDesdeExacto(valor: Double, decimales: Int, aFijo: (Double, Int) -> String): String {
    val exacto = aFijo(valor, 100)
    if ('e' in exacto) return aFijo(valor, decimales)   // ≥ 1e21: JavaScript usa notación científica
    return redondearAlPar(exacto, decimales)
}

/** "2.674999…" con [decimales] decimales, redondeando al par solo cuando el resto es exactamente la mitad. */
internal fun redondearAlPar(texto: String, decimales: Int): String {
    val punto = texto.indexOf('.').let { if (it < 0) texto.length else it }
    val entera = texto.substring(0, punto)
    val fraccion = if (punto < texto.length) texto.substring(punto + 1) else ""
    val conservada = fraccion.take(decimales).padEnd(decimales, '0')
    val resto = fraccion.drop(decimales)
    val subir = when {
        resto.isEmpty() || resto[0] < '5' -> false
        resto[0] > '5' -> true
        resto.drop(1).any { it != '0' } -> true                   // más de la mitad
        else -> ((conservada.lastOrNull() ?: entera.last()) - '0') % 2 == 1   // justo la mitad: al par
    }
    var digitos = (entera + conservada).toCharArray()
    if (subir) {
        var i = digitos.size - 1
        while (i >= 0 && digitos[i] == '9') { digitos[i] = '0'; i-- }
        if (i >= 0) digitos[i] = digitos[i] + 1 else digitos = charArrayOf('1') + digitos
    }
    val todo = digitos.concatToString()
    return if (decimales == 0) todo else todo.dropLast(decimales) + "." + todo.takeLast(decimales)
}
