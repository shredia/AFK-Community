package io.github.shredia.afkcommunity.idiomas

actual fun formatoFijo(valor: Double, decimales: Int): String =
    fijoDesdeExacto(valor, decimales) { x: Double, d: Int -> x.asDynamic().toFixed(d) as String }
