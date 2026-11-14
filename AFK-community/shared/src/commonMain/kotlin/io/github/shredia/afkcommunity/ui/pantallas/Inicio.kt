package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.shredia.afkcommunity.NOMBRE_APP
import io.github.shredia.afkcommunity.datos.listarServidores
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.idiomas.N_
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.amigos
import io.github.shredia.afkcommunity.logica.cargarCuentaActual
import io.github.shredia.afkcommunity.logica.carpetasServidor
import io.github.shredia.afkcommunity.logica.haceCuanto
import io.github.shredia.afkcommunity.ui.Cifra
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Seccion
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import io.github.shredia.afkcommunity.ui.Titulo
import io.github.shredia.afkcommunity.ui.URL_DISCORD
import io.github.shredia.afkcommunity.ui.URL_INVENTARIO
import io.github.shredia.afkcommunity.ui.URL_RUNS

private class Resumen(val cuenta: String, val cuentaDetalle: String, val detalles: Int, val servidores: Int,
                      val amigos: Int, val runsAmigos: Int)

private suspend fun resumen(estado: EstadoApp): Resumen {
    val datos = estado.datos
    // la captura más reciente de tus personajes
    var mejor: Pair<String, String>? = null
    for ((c, _) in carpetasServidor(datos)) {
        val captura = cargarCuentaActual(datos, c)?.get("capturedAt").textoO()
        if (captura.isNotEmpty() && (mejor == null || captura > mejor.second)) mejor = c to captura
    }
    val servidores = datos.listarServidores().filter { !it.amigo }
    val lista = amigos(datos)
    return Resumen(
        if (mejor != null) tr("Sincronizada") else tr("Sin sincronizar"),
        if (mejor != null) tr("captura {0}", haceCuanto(mejor.second)) else tr("Importa tu afk-inventory.json"),
        servidores.sumOf { it.runs }, servidores.size, lista.size, lista.sumOf { it.runs },
    )
}

@Composable
fun PantallaInicio(estado: EstadoApp) {
    val enlaces = LocalUriHandler.current
    var r by remember { mutableStateOf<Resumen?>(null) }
    LaunchedEffect(estado.versionDatos) { r = resumen(estado) }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Titulo(tr(NOMBRE_APP))
        Tenue(tr("Arma tu mejor rotación de Nightmare Corridor con los héroes que de verdad tienes."))
        r?.let { e ->
            Cifra(tr("Cuenta"), e.cuenta, e.cuentaDetalle)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Cifra(tr("Runs con detalle"), e.detalles.toString(), tr("en {0} servidores", e.servidores), Modifier.weight(1f))
                Cifra(tr("Amigos"), e.amigos.toString(), tr("con {0} runs importadas", e.runsAmigos), Modifier.weight(1f))
            }
        }

        Text(tr("Cómo empezar"), color = Colores.DORADO, fontWeight = FontWeight.SemiBold, fontSize = 17.sp,
            modifier = Modifier.padding(top = 10.dp))
        val pasos = listOf(
            Triple(Seccion.IMPORTAR, N_("Importar tus datos"), N_("Descarga afk-inventory.json y afk-runs.json del sitio e impórtalos en Ajustes → Importar / exportar, primero el inventario.")),
            Triple(Seccion.CUENTA, N_("Mi cuenta"), N_("Tus héroes, colecciones y mascotas: el optimizador sabe qué tienes.")),
            Triple(Seccion.AMIGOS, N_("Amigos"), N_("Importa las runs de tus amigos para copiar sus mejores equipos.")),
            Triple(Seccion.OPTIMIZADOR, N_("Optimizador"), N_("El mejor equipo por jefe sin repetir héroes, y qué te falta para mejorar.")),
        )
        for ((i, paso) in pasos.withIndex()) {
            val (destino, titulo, texto) = paso
            Tarjeta(alPulsar = { estado.ir(destino) }) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(28.dp).background(Colores.DORADO, CircleShape), contentAlignment = Alignment.Center) {
                        Text("${i + 1}", color = Colores.SOBRE_DORADO, fontWeight = FontWeight.Bold)
                    }
                    Column(Modifier.weight(1f).padding(start = 12.dp)) {
                        Text(tr(titulo), fontWeight = FontWeight.SemiBold)
                        Tenue(tr(texto))
                    }
                }
                if (destino == Seccion.IMPORTAR) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                        OutlinedButton({ enlaces.openUri(URL_INVENTARIO) }) { Text("Inventory") }
                        OutlinedButton({ enlaces.openUri(URL_RUNS) }) { Text("My runs") }
                    }
                }
            }
        }
        Tarjeta {
            Text(tr("💬 Comunidad en Discord"), fontWeight = FontWeight.SemiBold)
            Tenue(tr("Únete para hacer consultas, avisar de problemas, proponer ideas o compartir equipos."))
            Button({ enlaces.openUri(URL_DISCORD) }, Modifier.padding(top = 8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Colores.DORADO, contentColor = Colores.SOBRE_DORADO)) {
                Text(tr("Unirse al Discord  →"))
            }
        }
        Tarjeta {
            Text(tr("🚧 Conexión con el sitio: en desarrollo"), color = Colores.WARN, fontWeight = FontWeight.SemiBold)
            Tenue(tr("Iniciar sesión, hacer fetch y descargar runs desde esperianarchive.com está desactivado mientras se adapta al nuevo acceso del sitio. Todo lo demás funciona con los archivos importados."))
        }
    }
}
