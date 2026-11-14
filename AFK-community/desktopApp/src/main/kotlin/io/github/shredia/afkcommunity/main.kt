package io.github.shredia.afkcommunity

import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import androidx.compose.ui.window.rememberWindowState

fun main() = application {
    // Ventana angosta, del tamaño de un teléfono: la interfaz está pensada para Android
    Window(
        onCloseRequest = ::exitApplication,
        title = NOMBRE_APP,
        state = rememberWindowState(size = DpSize(420.dp, 860.dp)),
    ) {
        App(PlataformaEscritorio())
    }
}
