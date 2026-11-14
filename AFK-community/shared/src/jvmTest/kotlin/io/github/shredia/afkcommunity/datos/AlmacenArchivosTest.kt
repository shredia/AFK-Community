package io.github.shredia.afkcommunity.datos

import kotlinx.coroutines.test.runTest
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class AlmacenArchivosTest {
    private val raiz = Files.createTempDirectory("almacen").toFile().apply { deleteOnExit() }
    private val almacen = AlmacenArchivos(raiz)

    @Test fun escribeLeeYLista() = runTest {
        val ruta = unir("cuentas", "local", "146", "runs.json")
        assertNull(almacen.leerTexto(ruta))
        almacen.escribirTexto(ruta, """[{"nombre": "Ñandú ★"}]""")
        assertEquals("""[{"nombre": "Ñandú ★"}]""", almacen.leerTexto(ruta))
        almacen.escribirTexto(unir("cuentas", "local", "146", "a.json"), "{}")
        assertEquals(listOf("a.json", "runs.json"), almacen.listar("cuentas/local/146"))   // sin el .tmp
        assertTrue(almacen.esCarpeta("cuentas/local"))
        assertFalse(almacen.esCarpeta(ruta))
        assertTrue(almacen.modificado(ruta)!! > 1.6e9)
        assertNull(almacen.modificado("no/existe.json"))
        assertEquals(emptyList(), almacen.listar("no/existe"))
    }

    @Test fun reemplazaYBorra() = runTest {
        almacen.escribirTexto("x/y.json", "1")
        almacen.escribirTexto("x/y.json", "2")
        assertEquals("2", almacen.leerTexto("x/y.json"))
        almacen.borrar("x")
        assertFalse(almacen.existe("x/y.json"))
        almacen.borrar("x")   // no falla si ya no existe
    }

    @Test fun noSaleDeLaCarpeta() = runTest {
        assertFailsWith<IllegalArgumentException> { almacen.leerTexto("../fuera.txt") }
        assertFailsWith<IllegalArgumentException> { almacen.borrar("") }
    }

    @Test fun rutas() {
        assertEquals("cuentas/x/runs.json", unir("cuentas", "x", "", "runs.json"))
        assertEquals("cuentas/x", padre("cuentas/x/runs.json"))
        assertEquals("", padre("runs.json"))
        assertEquals("runs.json", nombre("cuentas/x/runs.json"))
    }
}
