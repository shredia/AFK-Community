package io.github.shredia.afkcommunity

import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.window.ComposeViewport
import io.github.shredia.afkcommunity.datos.PlataformaMemoria

// La web queda para después (Etapa 5: OPFS y selector de archivos). Por ahora abre la app sin datos.
@OptIn(ExperimentalComposeUiApi::class)
fun main() {
    ComposeViewport {
        App(PlataformaMemoria())
    }
}
