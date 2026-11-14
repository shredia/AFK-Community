package io.github.shredia.afkcommunity.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/** Paleta de la app Python (aplicacion/tema.py): oscuro neutro (grafito azulado) con acento dorado. */
object Colores {
    val FONDO = Color(0xFF0D1118)
    val LATERAL = Color(0xFF10151E)
    val PANEL = Color(0xFF151B26)
    val PANEL2 = Color(0xFF1C2433)
    val BORDE = Color(0xFF273247)
    val TEXTO = Color(0xFFE7E9EF)
    val MUTED = Color(0xFF8A93A6)
    val TENUE = Color(0xFF5B6478)
    val DORADO = Color(0xFFE9B949)
    val DORADO_OSCURO = Color(0xFFB98A2C)
    val SOBRE_DORADO = Color(0xFF1A1306)
    val OK = Color(0xFF6FCF8F)
    val WARN = Color(0xFFF0B44C)
    val ERR = Color(0xFFF27272)
    val INFO = Color(0xFF6AA8FF)
    val SELECCION = Color(0xFF2A3852)
}

private val esquema = darkColorScheme(
    primary = Colores.DORADO,
    onPrimary = Colores.SOBRE_DORADO,
    primaryContainer = Colores.DORADO_OSCURO,
    onPrimaryContainer = Colores.SOBRE_DORADO,
    secondary = Colores.INFO,
    onSecondary = Colores.FONDO,
    secondaryContainer = Colores.SELECCION,
    onSecondaryContainer = Colores.TEXTO,
    background = Colores.FONDO,
    onBackground = Colores.TEXTO,
    surface = Colores.FONDO,
    onSurface = Colores.TEXTO,
    surfaceVariant = Colores.PANEL2,
    onSurfaceVariant = Colores.MUTED,
    surfaceContainerLowest = Colores.FONDO,
    surfaceContainerLow = Colores.PANEL,
    surfaceContainer = Colores.PANEL,
    surfaceContainerHigh = Colores.PANEL2,
    surfaceContainerHighest = Colores.PANEL2,
    outline = Colores.BORDE,
    outlineVariant = Colores.BORDE,
    error = Colores.ERR,
    onError = Colores.FONDO,
)

@Composable
fun TemaApp(contenido: @Composable () -> Unit) {
    MaterialTheme(colorScheme = esquema, typography = Typography(), content = contenido)
}
