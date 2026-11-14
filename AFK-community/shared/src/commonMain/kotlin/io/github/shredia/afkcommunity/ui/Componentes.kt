package io.github.shredia.afkcommunity.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Tarjeta oscura con borde, como "Tarjeta.TFrame" de la app Python. */
@Composable
fun Tarjeta(modifier: Modifier = Modifier, alPulsar: (() -> Unit)? = null, contenido: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth().let { if (alPulsar != null) it.clickable(onClick = alPulsar) else it },
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = Colores.PANEL, contentColor = Colores.TEXTO),
        border = BorderStroke(1.dp, Colores.BORDE),
    ) {
        Column(Modifier.padding(14.dp), content = contenido)
    }
}

@Composable
fun Titulo(texto: String, modifier: Modifier = Modifier) =
    Text(texto, modifier, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold, color = Colores.TEXTO)

@Composable
fun Seccion(texto: String, modifier: Modifier = Modifier) =
    Text(texto, modifier.padding(top = 8.dp, bottom = 4.dp), style = MaterialTheme.typography.titleMedium,
        fontWeight = FontWeight.SemiBold, color = Colores.DORADO)

@Composable
fun Tenue(texto: String, modifier: Modifier = Modifier, color: Color = Colores.MUTED, maxLineas: Int = Int.MAX_VALUE) =
    Text(texto, modifier, color = color, fontSize = 13.sp, maxLines = maxLineas, overflow = TextOverflow.Ellipsis)

/** Una etiqueta pequeña de color ("prestado", "SP"...). */
@Composable
fun Etiqueta(texto: String, color: Color = Colores.DORADO, modifier: Modifier = Modifier) {
    Box(modifier.background(color.copy(alpha = 0.18f), RoundedCornerShape(4.dp)).padding(horizontal = 5.dp, vertical = 1.dp)) {
        Text(texto, color = color, fontSize = 10.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
    }
}

/** Selector de una lista (combo de la app Python). */
@Composable
fun <T> Desplegable(etiqueta: String, opciones: List<T>, elegida: T?, texto: (T) -> String, alElegir: (T) -> Unit,
                    modifier: Modifier = Modifier) {
    var abierto by remember { mutableStateOf(false) }
    Box(modifier.fillMaxWidth()) {
        Column(
            Modifier.fillMaxWidth().background(Colores.PANEL2, RoundedCornerShape(8.dp)).clickable { abierto = true }
                .padding(horizontal = 12.dp, vertical = 8.dp)
        ) {
            if (etiqueta.isNotEmpty()) Text(etiqueta, color = Colores.MUTED, fontSize = 11.sp)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(elegida?.let(texto) ?: "—", Modifier.weight(1f), color = Colores.TEXTO, maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
                Icon(Iconos.expandir, null, tint = Colores.MUTED)
            }
        }
        DropdownMenu(abierto, { abierto = false }, containerColor = Colores.PANEL2) {
            for (o in opciones) {
                DropdownMenuItem(text = { Text(texto(o), color = if (o == elegida) Colores.DORADO else Colores.TEXTO) },
                    onClick = { abierto = false; alElegir(o) })
            }
        }
    }
}

@Composable
fun Interruptor(texto: String, valor: Boolean, alCambiar: (Boolean) -> Unit, detalle: String? = null) {
    Row(Modifier.fillMaxWidth().clickable { alCambiar(!valor) }.padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(texto, color = Colores.TEXTO)
            if (detalle != null) Tenue(detalle)
        }
        Switch(valor, alCambiar, colors = SwitchDefaults.colors(checkedThumbColor = Colores.SOBRE_DORADO,
            checkedTrackColor = Colores.DORADO))
    }
}

@Composable
fun CampoNumero(texto: String, valor: Int, alCambiar: (Int) -> Unit, modifier: Modifier = Modifier) {
    var t by remember(valor) { mutableStateOf(valor.toString()) }
    OutlinedTextField(t, { nuevo ->
        t = nuevo.filter { it.isDigit() }.take(4)
        t.toIntOrNull()?.let(alCambiar)
    }, modifier, label = { Text(texto) }, singleLine = true)
}

/** Fila de cifras: "CUENTA / Sincronizada / captura hace 3 h". */
@Composable
fun Cifra(titulo: String, valor: String, detalle: String, modifier: Modifier = Modifier) {
    Tarjeta(modifier) {
        Text(titulo.uppercase(), color = Colores.MUTED, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
        Text(valor, color = Colores.TEXTO, fontSize = 20.sp, fontWeight = FontWeight.SemiBold, maxLines = 1,
            overflow = TextOverflow.Ellipsis)
        Tenue(detalle, maxLineas = 2)
    }
}

@Composable
fun Separacion() = Box(Modifier.size(1.dp, 10.dp))

@Composable
fun FilaIcono(icono: androidx.compose.ui.graphics.vector.ImageVector, texto: String, color: Color = Colores.TEXTO) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(icono, null, Modifier.size(18.dp), tint = color)
        Text(texto, color = color)
    }
}

@Composable
fun Espacio(ancho: Int = 8) = Box(Modifier.width(ancho.dp))
