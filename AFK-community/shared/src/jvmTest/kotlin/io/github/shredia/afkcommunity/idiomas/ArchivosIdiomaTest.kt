package io.github.shredia.afkcommunity.idiomas

import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Los idiomas que van dentro de la app son los de NC/idiomas/ (los de la app Python). */
class ArchivosIdiomaTest {
    @Test fun incluyeLosIdiomasDeLaAppPython() = runTest {
        val idiomas = idiomasDisponibles()
        assertEquals("es", idiomas.first().first)
        assertTrue("en" to "English" in idiomas, "idiomas: $idiomas")
    }

    @Test fun traduceConElArchivoReal() = runTest {
        try {
            assertEquals("en", cambiarIdioma("en"))
            assertEquals("Optimizer", tr("Optimizador"))
            assertEquals("Home", tr("Inicio"))
            assertEquals("es", cambiarIdioma("xx"))
            assertEquals("Optimizador", tr("Optimizador"))
        } finally {
            Idiomas.usar(null, null)
        }
    }
}
