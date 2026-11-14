package io.github.shredia.afkcommunity.idiomas

private fun toFixed(x: Double, d: Int): String = js("x.toFixed(d)")

actual fun formatoFijo(valor: Double, decimales: Int): String =
    fijoDesdeExacto(valor, decimales, ::toFixed)
