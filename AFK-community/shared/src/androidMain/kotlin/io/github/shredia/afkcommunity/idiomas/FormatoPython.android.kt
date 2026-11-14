package io.github.shredia.afkcommunity.idiomas

import java.math.BigDecimal
import java.math.RoundingMode

// BigDecimal(double) es el valor binario exacto: el redondeo al par sobre él es el de Python
actual fun formatoFijo(valor: Double, decimales: Int): String =
    BigDecimal(valor).setScale(decimales, RoundingMode.HALF_EVEN).toPlainString()
