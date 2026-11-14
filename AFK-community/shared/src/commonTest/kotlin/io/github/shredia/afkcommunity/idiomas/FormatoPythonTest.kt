package io.github.shredia.afkcommunity.idiomas

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** Los valores esperados salen de Python 3.14 (str.format). Corre en JVM, JS y Wasm. */
class FormatoPythonTest {
    private fun f(plantilla: String, vararg args: Any?) = formatear(plantilla, args.toList())

    /** En Kotlin/JS 3.0 es indistinguible de 3 (ver esEntero). */
    private val jsSinDecimales = (3.0 as Any) is Int

    @Test fun strDeValores() {
        assertEquals("True", f("{0}", true))
        assertEquals("None", f("{0}", null))
        assertEquals(if (jsSinDecimales) "12" else "12.0", f("{0}", 12.0))
        assertEquals("12", f("{0}", 12))
        assertEquals("1e+16", f("{0}", 1e16))
        assertEquals("2.5e-05", f("{0}", 2.5e-05))
        assertEquals("0.0001", f("{0}", 0.0001))
        assertEquals("123456789012345.6", f("{0}", 123456789012345.6))
        if (!jsSinDecimales) assertEquals("-0.0", f("{0}", -0.0))
        assertEquals("0.1", f("{0}", 0.1))
        assertEquals("a y 3", f("{0} y {1}", "a", 3))
        assertEquals("1 2", f("{} {}", 1, 2))
        assertEquals("{literal} 1", f("{{literal}} {0}", 1))
    }

    @Test fun decimalesConRedondeoDePython() {
        assertEquals("2.675", f("{0:.3f}", 2.675))
        assertEquals("2.67", f("{0:.2f}", 2.675))      // 2.675 en binario es 2.67499…
        assertEquals("0.12", f("{0:.2f}", 0.125))      // empate exacto: al par
        assertEquals("0.38", f("{0:.2f}", 0.375))
        assertEquals("2", f("{0:.0f}", 2.5))
        assertEquals("4", f("{0:.0f}", 3.5))
        assertEquals("1.00", f("{0:.2f}", 1.005))
        assertEquals("60.0", f("{0:.1f}", 59.95))
        assertEquals("12.345", f("{0:.3f}", 12.345))
        assertEquals("100000000000000000000.000", f("{0:.3f}", 1e20))
    }

    @Test fun redondeoSobreDigitosExactos() {
        // 2.675 en binario, con todos sus dígitos
        assertEquals("2.67", redondearAlPar("2.67499999999999982236431605997495353221893310546875", 2))
        assertEquals("0.12", redondearAlPar("0.1250000000", 2))
        assertEquals("0.38", redondearAlPar("0.375", 2))
        assertEquals("10.00", redondearAlPar("9.995", 2))
        assertEquals("100.0", redondearAlPar("99.96", 1))
        assertEquals("2", redondearAlPar("2.5", 0))
        assertEquals("4", redondearAlPar("3.5", 0))
        assertEquals("3", redondearAlPar("2.5000001", 0))
        assertEquals("7.000", redondearAlPar("7", 3))
    }

    @Test fun signoAnchoYAlineacion() {
        assertEquals("-0.000", f("{0:.3f}", -0.0001))
        assertEquals("+1.500", f("{1:+.3f}", 0, 1.5))
        assertEquals("-1.500", f("{1:+.3f}", 0, -1.5))
        assertEquals("+0.000", f("{1:+.3f}", 0, 0.0))
        assertEquals("  3.142", f("{0:7.3f}", 3.14159))
        assertEquals(" -3.142", f("{1:7.3f}", 0, -3.14159))
        assertEquals("05", f("{0:02d}", 5))
        assertEquals("123", f("{0:02d}", 123))
        assertEquals("-5", f("{0:02d}", -5))
        assertEquals("Dracula             |", f("{0:<20}|", "Dracula"))
        assertEquals("   ab|", f("{0:>5}|", "ab"))
        assertEquals("   ab    |", f("{0:^9}|", "ab"))
    }

    @Test fun erroresComoPython() {
        assertFailsWith<IllegalArgumentException> { f("{2}", 1) }
        assertFailsWith<IllegalArgumentException> { f("{0:d}", 1.5) }
        assertFailsWith<IllegalArgumentException> { f("abre { sin cerrar") }
    }

    @Test fun trConTraduccionYRespaldo() {
        val en = """{"_meta": {"codigo": "en", "nombre": "English"}, "traducciones": {
            "Optimizador": "Optimizer", "Vacía": "", "Descargados: {0} de {1}": "Downloaded: {0} of {1}",
            "Mal: {0}": "Bad: {3}"}}"""
        try {
            assertEquals("en", Idiomas.usar("en", en))
            assertEquals("Optimizer", tr("Optimizador"))
            assertEquals("Vacía", tr("Vacía"))                         // vacía: queda en español
            assertEquals("Sin traducir", tr("Sin traducir"))
            assertEquals("Downloaded: 3 of 10", tr("Descargados: {0} de {1}", 3, 10))
            assertEquals("Mal: 1", tr("Mal: {0}", 1))                   // traducción rota: el original
            assertEquals("English", Idiomas.nombre(en))
            assertEquals("es", Idiomas.usar("fr", "no es json"))       // no se entiende: español
            assertEquals("Optimizador", tr("Optimizador"))
        } finally {
            Idiomas.usar(null, null)
        }
    }

    @Test fun ordenDeIdiomas() {
        assertEquals(listOf("es", "en", "fr"),
            ordenarIdiomas(listOf("fr" to "Français", "en" to "English", "es" to "Español")).map { it.first })
    }
}
