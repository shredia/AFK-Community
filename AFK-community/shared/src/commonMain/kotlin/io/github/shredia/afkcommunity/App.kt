package io.github.shredia.afkcommunity

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.NavigationDrawerItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.shredia.afkcommunity.datos.Plataforma
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Iconos
import io.github.shredia.afkcommunity.ui.Seccion
import io.github.shredia.afkcommunity.ui.TemaApp
import io.github.shredia.afkcommunity.ui.pantallas.PantallaAjustes
import io.github.shredia.afkcommunity.ui.pantallas.PantallaAmigos
import io.github.shredia.afkcommunity.ui.pantallas.PantallaBloqueos
import io.github.shredia.afkcommunity.ui.pantallas.PantallaCuenta
import io.github.shredia.afkcommunity.ui.pantallas.PantallaExplorar
import io.github.shredia.afkcommunity.ui.pantallas.PantallaFractura
import io.github.shredia.afkcommunity.ui.pantallas.PantallaProgreso
import io.github.shredia.afkcommunity.ui.pantallas.PantallaImportar
import io.github.shredia.afkcommunity.ui.pantallas.PantallaInicio
import io.github.shredia.afkcommunity.ui.pantallas.PantallaOptimizador
import kotlinx.coroutines.launch

const val NOMBRE_APP = "Esperian NC"

private fun icono(s: Seccion): ImageVector = when (s) {
    Seccion.INICIO -> Iconos.inicio
    Seccion.OPTIMIZADOR -> Iconos.optimizador
    Seccion.EXPLORAR -> Iconos.explorar
    Seccion.BLOQUEOS -> Iconos.ajustar
    Seccion.PROGRESO -> Iconos.progreso
    Seccion.CUENTA -> Iconos.cuenta
    Seccion.AMIGOS -> Iconos.amigos
    Seccion.FRACTURA -> Iconos.fractura
    Seccion.IMPORTAR -> Iconos.importar
    Seccion.AJUSTES -> Iconos.ajustes
}

/**
 * La app completa. Cada plataforma la abre con su [Plataforma]; [alCrear] le entrega el estado
 * (Android lo usa para el botón atrás).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun App(plataforma: Plataforma, alCrear: (EstadoApp) -> Unit = {}) {
    val alcance = rememberCoroutineScope()
    val estado = remember { EstadoApp(plataforma, alcance).also(alCrear) }
    LaunchedEffect(Unit) { estado.iniciar() }

    TemaApp {
        if (!estado.listo) {
            Box(Modifier.fillMaxSize().background(Colores.FONDO), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Colores.DORADO)
            }
            return@TemaApp
        }
        // al cambiar de idioma se vuelve a dibujar todo con los textos nuevos
        key(estado.idioma) {
            val cajon = rememberDrawerState(DrawerValue.Closed)
            ModalNavigationDrawer(
                drawerState = cajon,
                drawerContent = {
                    ModalDrawerSheet(drawerContainerColor = Colores.LATERAL, modifier = Modifier.width(290.dp)) {
                        Column(Modifier.verticalScroll(rememberScrollState()).padding(12.dp)) {
                            Text(tr(NOMBRE_APP), Modifier.padding(start = 12.dp, top = 8.dp), color = Colores.DORADO,
                                fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
                            Spacer(Modifier.height(12.dp))
                            var grupo: String? = null
                            for (s in Seccion.entries) {
                                if (s.grupo != grupo) {
                                    grupo = s.grupo
                                    if (grupo != null) Text(tr(grupo), Modifier.padding(start = 12.dp, top = 14.dp, bottom = 4.dp),
                                        color = Colores.TENUE, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                                }
                                NavigationDrawerItem(
                                    label = { Text(tr(s.texto)) },
                                    icon = { Icon(icono(s), null) },
                                    selected = estado.seccion == s,
                                    onClick = { estado.ir(s); alcance.launch { cajon.close() } },
                                    colors = NavigationDrawerItemDefaults.colors(
                                        selectedContainerColor = Colores.SELECCION, selectedTextColor = Colores.DORADO,
                                        selectedIconColor = Colores.DORADO, unselectedContainerColor = Colores.LATERAL,
                                        unselectedTextColor = Colores.TEXTO, unselectedIconColor = Colores.MUTED),
                                )
                            }
                        }
                    }
                },
            ) {
                Scaffold(
                    containerColor = Colores.FONDO,
                    topBar = {
                        TopAppBar(
                            title = { Text(if (estado.seccion == Seccion.INICIO) tr(NOMBRE_APP) else tr(estado.seccion.texto)) },
                            navigationIcon = {
                                IconButton({ alcance.launch { cajon.open() } }) { Icon(Iconos.menu, tr("Menú")) }
                            },
                            colors = TopAppBarDefaults.topAppBarColors(containerColor = Colores.LATERAL,
                                titleContentColor = Colores.TEXTO, navigationIconContentColor = Colores.TEXTO),
                        )
                    },
                ) { relleno ->
                    Box(Modifier.padding(relleno).fillMaxSize()) {
                        when (estado.seccion) {
                            Seccion.INICIO -> PantallaInicio(estado)
                            Seccion.OPTIMIZADOR -> PantallaOptimizador(estado)
                            Seccion.EXPLORAR -> PantallaExplorar(estado)
                            Seccion.BLOQUEOS -> PantallaBloqueos(estado)
                            Seccion.PROGRESO -> PantallaProgreso(estado)
                            Seccion.CUENTA -> PantallaCuenta(estado)
                            Seccion.AMIGOS -> PantallaAmigos(estado)
                            Seccion.FRACTURA -> PantallaFractura(estado)
                            Seccion.IMPORTAR -> PantallaImportar(estado)
                            Seccion.AJUSTES -> PantallaAjustes(estado)
                        }
                    }
                }
            }
        }
    }
}
