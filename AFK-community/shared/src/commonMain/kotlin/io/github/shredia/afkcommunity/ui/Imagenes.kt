package io.github.shredia.afkcommunity.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.shredia.afkcommunity.datos.Almacen
import io.github.shredia.afkcommunity.datos.unir
import io.github.shredia.afkcommunity.recursos.Res
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.jetbrains.compose.resources.ExperimentalResourceApi
import org.jetbrains.compose.resources.decodeToImageBitmap

/*
 * Imágenes del juego: las rutas de los datos ("/game-ui/...", "/api/catalogue/media/...") se buscan
 *   1. en assets/ de la carpeta de datos (lo que haya descargado el usuario), y
 *   2. en las que vienen con la app (files/assets/, copiadas de recursos/assets de la app Python).
 */
object CacheImagenes {
    private const val MAXIMO = 400
    private val cache = LinkedHashMap<String, ImageBitmap?>(64, 0.75f)
    private val mutex = Mutex()
    var almacen: Almacen? = null

    fun yaCargada(url: String): ImageBitmap? = cache[url]

    @OptIn(ExperimentalResourceApi::class)
    suspend fun cargar(url: String): ImageBitmap? {
        mutex.withLock { if (url in cache) return cache[url] }
        val relativa = url.substringBefore('?').trimStart('/')
        val imagen = withContext(Dispatchers.Default) {
            val bytes = runCatching { almacen?.leerBytes(unir("assets", relativa)) }.getOrNull()
                ?: runCatching { Res.readBytes("files/assets/$relativa") }.getOrNull()
            bytes?.let { runCatching { it.decodeToImageBitmap() }.getOrNull() }
        }
        mutex.withLock {
            cache[url] = imagen
            if (cache.size > MAXIMO) cache.remove(cache.keys.first())
        }
        return imagen
    }
}

/** Una imagen del juego, o un recuadro con las iniciales de [alternativo] si no está. */
@Composable
fun ImagenJuego(url: String?, tamano: Dp, modifier: Modifier = Modifier, alternativo: String? = null,
                redondeo: Dp = 6.dp) {
    val imagen by produceState(url?.let { CacheImagenes.yaCargada(it) }, url) {
        value = url?.takeIf { it.isNotEmpty() }?.let { CacheImagenes.cargar(it) }
    }
    val forma = RoundedCornerShape(redondeo)
    val img = imagen
    if (img != null) {
        Image(img, alternativo, modifier.size(tamano).clip(forma), contentScale = ContentScale.Crop)
    } else {
        Box(modifier.size(tamano).clip(forma).background(Colores.PANEL2), contentAlignment = Alignment.Center) {
            if (!alternativo.isNullOrEmpty()) {
                Text(iniciales(alternativo), color = Colores.MUTED, fontWeight = FontWeight.Bold,
                    fontSize = (tamano.value / 3).coerceIn(9f, 18f).sp)
            }
        }
    }
}

private fun iniciales(texto: String): String =
    texto.split(" ", "-").filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }
