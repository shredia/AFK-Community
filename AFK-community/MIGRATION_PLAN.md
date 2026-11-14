# Plan de migración: AFK-Community (Python) → Kotlin Multiplatform

> Estado: **Etapa 0 terminada. Etapas 1–4 completas para Android** (ver §12): todas las secciones publicadas de la
> app Python. La web queda para después. Falta: compilar el APK (no hay SDK de Android instalado) y probarlo en un
> teléfono.
> Origen: app Python 1.2.4 en `NC/` (≈15 000 líneas). Destino: este proyecto (`NC/AFK-community/`).

---

## 1. Lo que hay hoy

### 1.1 App Python

| Capa | Archivos | Qué hace | ¿Depende de Tkinter / del SO? |
|---|---|---|---|
| Lógica | `navegador/optimizador.py` (668) | Índice de runs, composiciones, baneos y límites, búsqueda óptima (ramificación y poda) | No |
| | `navegador/importar.py` (934) | Detecta e importa `afk-runs.json`, `afk-inventory.json`, run suelta `afk-NC-*.json` y `.zip`; exporta `.zip`; amigos y simulaciones | `zipfile` |
| | `navegador/cuenta.py` (431) | Cuenta actual (inventario compactado), índice de héroes, uso de cada héroe/colección en NC | No |
| | `navegador/roster.py` (211) | Perfil de roster + correcciones; «¿puedo armar este equipo?» | No |
| | `navegador/bloqueos.py` (109) | Reglas unificadas de baneos y límites (alcance: todo / yo / amigos) | No |
| | `navegador/fractura.py` (406) | Planificador de Fractura temporal: pisos, cofres, tiendas, bolsa | `openpyxl` (importar Excel) |
| | `navegador/visuales.py` (360) | Traduce datos de una run a imágenes (tablas del sitio) | No |
| | `navegador/rutas.py` (163) | Dónde vive cada archivo; migraciones de carpetas | Sistema de archivos |
| | `idiomas/` | `tr("texto en español {0}")` + `es.json` / `en.json` (1 090 frases) | No |
| Red (desactivada) | `navegador/sitio.py`, `scraper.py`, `js_literales.py`, `parser.py` | Login en esperianarchive.com, descargas, lectura de tablas del JS del sitio | `keyring`, HTTP. **`SITIO_EN_DESARROLLO = True`** |
| Red (activa) | `navegador/cdn.py` | Íconos del CDN comunitario (raw.githubusercontent) | HTTP |
| Red (activa) | `navegador/actualizador.py` | Actualización desde GitHub | Específico de la distribución Python |
| Sin publicar | `navegador/reconocer.py` | Reconoce héroes en imágenes (para «Guías · pronto») | Pillow |
| UI | `aplicacion/*.py` (≈8 500) | Tkinter: 12 ventanas/secciones | Tkinter, Pillow |

**Funcionalidades visibles para el usuario** (menú lateral de `ventana_principal.py`):

1. **Inicio**: resumen (cuenta, runs con detalle, amigos), primeros pasos, enlace a Discord.
2. **Optimizador** (`ventana_optimizador.py`, 2 650 líneas, la pieza central):
   - rotación de 6 jefes (manual o «la más reciente»);
   - resultado óptimo sin repetir héroes (ni mascotas, opcional), con límite de tiempo y cancelación;
   - pestañas *Explorar* (buscar equipos), *Resumen*, *Estadísticas*, *Qué me falta*, panel de detalle del equipo (héroes, build, SP);
   - marcar a mano el héroe del Special Power cuando hay varios especiales (`sp_manual.json`).
3. **Configurar optimizador** (`optimizador_ajustes.py`): *Fuentes* (tus servidores + amigos), *Bloqueos* (baneos y límites de build), *Mi roster* (correcciones), *Búsqueda*, *Vista*.
4. **Explorar equipos**: atajo a la pestaña Explorar.
5. **Progreso semanal**: mejor total por semana (gráfico + tabla).
6. **Mi cuenta**: recursos, héroes, colecciones, equipo, mascotas y su uso en NC.
7. **Amigos**: ver, renombrar, borrar y optimizar con las runs de amigos.
8. **Fractura temporal**: pisos, cofres de elección, tiendas de medallas, resumen de la bolsa; importar planilla Excel.
9. **Ajustes**: idioma, actualizaciones, **Importar / exportar**.
10. *Descargar runs* y *Acceso al sitio*: **en desarrollo** (pantalla «en desarrollo»).
11. *Guías*: **pronto** (no publicada).

**Datos**: todo son archivos JSON en `datos_usuario/` (ver §5). Ejemplo real: 295 detalles de runs, de ~800 KB cada uno (~240 MB). El índice compacto del optimizador ocupa 1–13 MB por servidor.

### 1.2 Proyecto Kotlin

Es la plantilla del asistente, sin código propio todavía:

- Kotlin 2.4.21, Compose Multiplatform 1.12.2, AGP 9.1.1, Material 3.
- Módulos `shared` (targets: `jvm`, `js`, `wasmJs`, `android`; sin iOS), `desktopApp`, `webApp`, `androidApp`.
- Paquete `com.example.afk_community`.
- `App.kt` es el «Click me!» de ejemplo.
- **Compila**: `:shared:jvmTest`, `:desktopApp:compileKotlin` y `:webApp:compileKotlinWasmJs` terminan en verde. No hay Java en el PATH; se usó el JDK que trae IntelliJ (`JAVA_HOME=%LOCALAPPDATA%\Programs\IntelliJ IDEA\jbr`). Desde IntelliJ / Android Studio funciona sin configurar nada.

Dos cosas importantes:

- **Vive en el mismo repositorio que la app Python** (`NC/AFK-community/`), por decisión D1. Para que el actualizador Python no la descargue en las instalaciones de los usuarios, `NC/.gitattributes` la marca con `export-ignore`. GitHub arma el zip de cada versión con `git archive`, que respeta esa marca. Lo verifiqué: el zip no lleva ningún archivo de `AFK-community/` y sí trae `main.py`. Esto protege también a las instalaciones con actualizadores antiguos.
- El paquete `com.example…` no se puede publicar en Google Play. Ver D2.

---

## 2. Qué va a `commonMain` y qué no

**Va a `commonMain`, sin cambios por plataforma (~80 % de la lógica):**

- los modelos;
- la lectura y escritura de los JSON;
- `detectar` y la conversión de `afk-runs.json` / `afk-inventory.json`;
- el análisis de dueño de las runs;
- el índice y las composiciones;
- los baneos, límites y bloqueos;
- el optimizador;
- el roster y el «qué me falta»;
- el progreso semanal;
- el cálculo de la Fractura;
- los visuales (qué imagen va con cada cosa);
- los idiomas (`tr()` con los mismos `es.json` / `en.json`);
- toda la UI en Compose.

**Necesita una implementación por plataforma** (`expect`/`actual` o una interfaz con una implementación por plataforma):

| Necesidad | Desktop (JVM) | Android | Web (wasm/js) |
|---|---|---|---|
| Almacenamiento de archivos | `java.io.File` en una carpeta de datos | `context.filesDir` | **OPFS** (Origin Private File System) del navegador |
| Elegir archivo para importar / guardar `.zip` | Diálogo nativo | Selector del sistema (SAF) | `<input type=file>` / descarga |
| Leer y escribir `.zip` | `java.util.zip` | `java.util.zip` | Lector/escritor mínimo + `CompressionStream` del navegador (ver §4) |
| Abrir enlaces (Discord, sitio) | `LocalUriHandler` de Compose (común) | ídem | ídem |
| «Mostrar en la carpeta» | Explorador del SO | — (no aplica) | — (no aplica) |

El código web va en `webMain`, que comparten los targets `js` y `wasmJs` (D4): se escribe una sola vez.

---

## 3. Arquitectura propuesta

Un solo módulo con la lógica y la UI (`shared`), separado por paquetes. Sin inyección de dependencias, sin librería de navegación y sin capas de repositorio/caso de uso: la app Python funciona bien con funciones y archivos, y se mantiene esa forma.

```
shared/src/
  commonMain/kotlin/<paquete>/
    modelo/        data classes @Serializable: Run, Ronda, Heroe, Mascota, Composicion, Opciones,
                   Resultado, Regla (baneo/límite), FichaPersonaje, CuentaActual, EstadoFractura...
    datos/         Almacen (interfaz), Rutas (misma estructura de carpetas que Python),
                   Json (lectura tolerante), Importar, Exportar, Indice
    logica/        Optimizador, Composiciones, Bloqueos, Roster, Progreso, Fractura, Visuales, Cuenta
    idiomas/       tr(), N_() y carga de es.json / en.json (copiados de idiomas/)
    ui/            Tema (oscuro con dorado, como tema.py), App (menú lateral + sección), una carpeta
                   por pantalla: inicio/, optimizador/, cuenta/, amigos/, progreso/, fractura/, ajustes/
  commonMain/composeResources/
    files/         tablas_sitio.json, fractura_temporal_base.json
                   (files/idiomas/ NO se copia: Gradle incluye al compilar los NC/idiomas/*.json de la app Python)
    drawable/      imágenes incluidas (las de recursos/assets) e íconos de la UI como vectores XML
                   (Material Symbols, en lugar de los emojis de la app Python: D3)
  jvmMain/ androidMain/ webMain/
    Almacen, selector de archivos, zip            (lo único específico de cada plataforma)
  commonTest/      pruebas unitarias de la lógica
  jvmTest/         pruebas de equivalencia contra resultados de Python (leen archivos de casos)
```

Criterios:

- **Mismos nombres que en Python**, en español: `optimizar`, `candidatosPorJefe`, `construirComposiciones`… Así cada función Kotlin se compara fácilmente con su original.
- **Estado de la UI**: clases de estado simples con `mutableStateOf` y corrutinas. Se usa `ViewModel` (ya incluido en la plantilla) solo en pantallas con trabajo largo, como el optimizador y la importación.
- **Navegación**: un `enum Seccion` y un `when`, igual que el menú de Python. En pantallas angostas (Android, móvil web), el menú pasa a un cajón lateral.
- **JSON con forma variable**: la ficha de un héroe trae decenas de campos que la lógica no usa, pero la UI sí muestra (grabados, muebles, equipo…). Por eso:
  - los modelos tipan solo lo que usa la lógica;
  - el resto se conserva como `JsonObject` (`Heroe.crudo`) para mostrarlo.

  Esto evita modelar 300 campos y mantiene los archivos idénticos al reescribirlos.
- **Estructura del proyecto Kotlin**: no se cambia, salvo el nombre del paquete (D2).
- **Íconos**: cada emoji de la UI Python (📥 📤 👤 👥 ★ ⌕ ↗ ⚙ 📂 💬…) pasa a su equivalente de Material Symbols, como vector XML en `composeResources/drawable`. Se usa con `painterResource`. No hace falta ninguna dependencia: la librería `material-icons-extended` ya no se publica para Compose Multiplatform. Se ve igual en las cuatro plataformas y no pesa.

---

## 4. Dependencias

| Dependencia | Para qué | ¿Imprescindible? |
|---|---|---|
| `kotlinx-serialization-json` (+ plugin) | Leer y escribir todos los JSON | Sí |
| `kotlinx-coroutines-core` | Trabajo en segundo plano y cancelación del optimizador (ya viene de forma transitiva; se declara explícita) | Sí |
| `kotlinx-datetime` | Fechas: semanas del progreso, «próximo viernes», «hace 3 h», `playedAt` | Sí |
| **FileKit** (`filekit-dialogs-compose`) | Elegir y guardar archivos en Desktop, Android y Web con una sola API | Recomendada. Alternativa: ~150 líneas propias por plataforma |
| Ktor client | Solo cuando se migre la conexión al sitio o la descarga de íconos del CDN (§7) | Más adelante |

**No se agregan:**
- inyección de dependencias (Koin);
- librería de navegación;
- base de datos (SQLDelight / Room): los archivos JSON bastan y mantienen el formato;
- Coil: las imágenes se decodifican con `decodeToImageBitmap()` de Compose;
- librería de íconos: son vectores XML en los recursos (D3);
- librería de Excel: la importación de planillas no se migra (D5);
- librería de gráficos: el progreso semanal se dibuja con `Canvas`;
- Firebase / Supabase.

**Zip en la web**: sin dependencias. Un `.zip` es un índice simple, y el navegador trae `CompressionStream` / `DecompressionStream("deflate-raw")`. Si resulta frágil, la alternativa es JSZip vía npm.

---

## 5. Almacenamiento local

**Regla: mismos archivos y mismo formato que Python.**

```
<datos>/preferencias.json
<datos>/cuentas/<cuenta>/<servidor>/<servidor>.json        ficha del personaje
                                    runs.json, detalles/<id>.json, cuenta_actual.json
                                    optimizador_indice.json, bloqueos.json, sp_manual.json,
                                    perfil_roster.json, fractura_temporal.json
<datos>/cuentas/_amigos/<nombre>/...
```

Interfaz común:

```kotlin
interface Almacen {
    suspend fun leerTexto(ruta: String): String?
    suspend fun escribirTexto(ruta: String, texto: String)   // atómica: archivo temporal + renombrar
    suspend fun leerBytes(ruta: String): ByteArray?
    suspend fun escribirBytes(ruta: String, bytes: ByteArray)
    suspend fun listar(carpeta: String): List<String>
    suspend fun borrar(ruta: String)                         // archivo o carpeta
}
```

| Plataforma | Dónde | Notas |
|---|---|---|
| Desktop | Carpeta de datos propia (`%APPDATA%/AFK-Community`, `~/.local/share/AFK-Community`). En desarrollo se cambia con una variable de entorno para usar una copia de prueba (p. ej. `NC_pruebas/datos_usuario`) | Como el formato es el mismo, una carpeta `datos_usuario` de Python se puede copiar tal cual |
| Android | `context.filesDir` | Privado de la app; el respaldo es el `.zip` de exportar |
| Web | OPFS (`navigator.storage.getDirectory()`), con `navigator.storage.persist()` para que el navegador no lo borre | Cabe sin problema (cuota de GB). Es local al navegador: el `.zip` de exportar es el respaldo |

Ventajas:
- La importación y exportación `.zip` es compatible entre la app Python y la Kotlin, en ambos sentidos.
- Las pruebas de equivalencia pueden usar datos reales.
- No hay migraciones de formato.

---

## 6. Conexión con la API de Esperian Archive

Situación actual:
- En Python, la conexión está **desactivada** (`SITIO_EN_DESARROLLO = True`).
- Los datos entran por los archivos que el usuario descarga del sitio (`afk-runs.json`, `afk-inventory.json`, `afk-NC-*.json`).
- Las tablas del sitio (`tablas_sitio.json`) ya vienen incluidas en la app.

Estrategia:

1. **No migrar la conexión ahora.** La app Kotlin funcionará igual que la Python publicada: con importación de archivos.
2. Cuando se active (después de completar la migración y con tu aprobación), se haría así:
   - `Sesion` con Ktor: `POST /api/auth/login`, cookie en memoria y cabecera `X-Page`;
   - `js_literales` portado a Kotlin común (es solo un analizador de texto).
   - **Solo en Desktop y Android.**
3. **Web: no es posible sin un servidor intermedio**, y las restricciones excluyen servicios externos. Lo verifiqué: las imágenes de `esperianarchive.com` se sirven **sin cabecera CORS**, así que un navegador no puede leerlas desde otro dominio. Su API tiene casi seguro la misma restricción. En la web solo se usará la importación de archivos.
4. **CDN de íconos** (`raw.githubusercontent.com`): sí permite CORS (`Access-Control-Allow-Origin: *`, verificado). Funcionará en todas las plataformas cuando haga falta.
5. **Contraseña del sitio**: Python usa el llavero del sistema. Desktop y Android lo resolverían por separado (Android Keystore; en Desktop, pedirla en cada sesión o usar el llavero del SO). Se decide cuando toque.

---

## 7. Lo que NO se migra (por ahora)

| Qué | Por qué |
|---|---|
| Actualizador (`actualizador.py`) | Es propio de la distribución Python. La web siempre está al día; Desktop y Android se actualizan con su instalador o tienda |
| Descargar runs / Acceso al sitio | Desactivado en Python (§6) |
| Guías y `reconocer.py` | No publicado («pronto») |
| `herramientas/` (construir `.exe`, instalador) | Compose Desktop empaqueta con `packageDistributionForCurrentOS` |
| Importar planilla Excel de Fractura (`importar_excel`, `openpyxl`) | Descartado (D5). Se migra toda la lógica de la Fractura: datos base incluidos, cálculo, cofres, tiendas, bolsa y vínculos |

La app Python sigue intacta y publicada mientras dura la migración.

---

## 8. Orden de migración

Cada etapa termina compilando en Desktop y Web, con pruebas en verde. **Se avanza solo después de tu revisión.**

### Etapa 0: Preparación
- Cambiar el paquete `com.example.afk_community` por el de D2: carpetas de `src`, `namespace`, `applicationId` y `mainClass`.
- Agregar serialization y datetime.
- Interfaz `Almacen` + implementación JVM.
- `tr()` con los JSON de idiomas.
- **Arnés de equivalencia**: un script Python que vive en este proyecto (`herramientas_migracion/generar_casos.py`):
  - importa los módulos de `../navegador` sin modificarlos;
  - procesa una carpeta de datos de prueba;
  - guarda las entradas y los resultados esperados (composiciones, candidatos por jefe, resultado del optimizador, análisis de runs…).
  
  Las pruebas `jvmTest` comparan Kotlin contra esos resultados. Los casos usan una copia de prueba de los datos y quedan fuera de git (son datos personales).

### Etapa 1: Modelos
Data classes de §3, con pruebas de ida y vuelta: leer → escribir → leer da lo mismo, y los archivos siguen siendo legibles por Python.

### Etapa 2: Archivos JSON
- `rutas`;
- leer `runs.json` / `detalles` / `optimizador_indice.json` (`cargar_indice`);
- `detectar` (las 4 formas de archivo);
- `convertir_heroe` / `convertir_mascota`;
- `importar_runs`, `importar_inventario`, `analizar_runs`;
- amigos y simulaciones;
- después, `.zip` (exportar e importar copia y de amigo).

### Etapa 3: Algoritmos (en este orden)
1. `construir_composiciones`, `deducir_golden`, SP manual.
2. Baneos, límites y `bloqueos` (alcance yo / amigos).
3. `candidatos_por_jefe` y `optimizar`. Mismo recorrido, misma poda y mismo desempate. Ver §9.3.
4. `roster` (evaluar equipo, filtrar por roster).
5. `cuenta` (índice de héroes, uso en NC) y `visuales`.
6. Progreso semanal (`semanas_de`).
7. `fractura.calcular`.

### Etapa 4: Interfaz (Compose), de lo básico a lo complejo
1. Esqueleto: tema, menú lateral, idioma.
2. Importar / exportar: sin esto no hay datos.
3. Mi cuenta.
4. Optimizador: resultado y tarjetas de equipo, luego detalle, luego Explorar / Resumen / Estadísticas / Qué me falta.
5. Configurar optimizador (5 pestañas) y rotación.
6. Amigos.
7. Progreso semanal.
8. Fractura temporal.
9. Inicio y Ajustes.

### Etapa 5: Compatibilidad Desktop + Web
- Almacenamiento OPFS y selector de archivos en la web.
- Optimizador cooperativo (§9.1).
- Fuentes y emojis en la web (§9.2).
- Rendimiento con índices de 13 MB.

### Etapa 6: Android
- Almacenamiento y selector.
- Diseño para pantalla angosta (menú en cajón, tarjetas en una columna).

### Etapa 7: PWA (§10)

---

## 9. Incompatibilidades y riesgos

1. **La web tiene un solo hilo.** El optimizador puede buscar hasta 60 s, y en la web congelaría la página.
   - **Solución**: la búsqueda pasa a ser una función `suspend` que cede el control cada 2 048 nodos. Python ya revisa el tiempo justo en ese punto, así que el recorrido y el resultado no cambian.
   - En Desktop y Android corre en `Dispatchers.Default`.
2. **Fuentes en la web.** Compose Web dibuja en un canvas y no usa las fuentes del sistema.
   - Los emojis se reemplazan por íconos (D3).
   - Hay que comprobar que la fuente por defecto tenga las tildes y la «ñ». Si no, se incluye una fuente latina liviana (~100–300 KB).
3. **Equivalencia con empates.** Cuando dos equipos tienen el mismo tiempo, Python se queda con el primero que encuentra. Ese orden depende del orden de las runs en el índice (orden de inserción del diccionario).
   - Kotlin usará `LinkedHashMap` y ordenamiento estable, igual que Python.
   - Las pruebas exigen el **mismo total óptimo**, y la **misma selección** cuando no hay empates.
4. **JSON flexibles.** Python acepta números como texto (`"123"`), campos ausentes o `null`. Kotlin necesita lectura tolerante: `ignoreUnknownKeys`, `coerceInputValues` y conversiones como `_entero` de Python.
5. **Tamaño de los datos.** Leer 295 detalles de 800 KB solo ocurre al reconstruir el índice, igual que en Python. Lo normal es leer `optimizador_indice.json`. En la web hay que medir el tiempo de leer un JSON de 13 MB.
6. **Web sin acceso al sitio** (§6).
7. **Zip en la web** (§4).
8. **Imágenes.** `recursos/assets` pesa 7,5 MB: se incluye en la app (en la web aumenta la primera descarga; el service worker la guarda en caché). Las imágenes que Python descarga del sitio no se pueden descargar en la web (CORS).
9. **Mismo repositorio que la app Python** (D1). Resuelto con `export-ignore` (§1.2).
   - Si la carpeta cambia de nombre, hay que actualizar `NC/.gitattributes`.
   - Los commits que solo tocan `AFK-community/` no cambian nada para quien usa la app Python, porque el actualizador solo instala versiones etiquetadas y esta carpeta no viaja en ellas.

### Decisiones tomadas

| | Decisión | Consecuencia |
|---|---|---|
| **D1** | Un solo repositorio y una sola carpeta para todo | El proyecto Kotlin sigue en `NC/AFK-community/`. `NC/.gitattributes` lo excluye del zip del actualizador (verificado) y fija LF en `gradlew` |
| **D2** | Nombre del paquete: **`io.github.shredia.afkcommunity`** | Aplicado en la Etapa 0 |
| **D3** | Emojis → íconos | Material Symbols como vectores XML en los recursos, sin dependencias |
| **D4** | Se mantienen `js` y `wasmJs` | El código web va en `webMain`, compartido por los dos |
| **D5** | Sin importación de Excel | Se migra toda la lógica de la Fractura, pero no `importar_excel` |

**Por qué `io.github.shredia.afkcommunity`:**
- Los paquetes se nombran con un dominio al revés que controlas. `shredia.github.io` es tuyo por ser dueño de la cuenta `shredia`, sin comprar dominio. Es la convención que acepta Maven Central y que se usa en Google Play.
- `afkcommunity` va todo junto porque los guiones no son válidos en paquetes. Los guiones bajos sí lo son, pero la guía de estilo de Kotlin los desaconseja.
- El mismo valor sirve de `applicationId` en Android y de identificador del instalador de escritorio. **No se puede cambiar después de publicar en Google Play.**
- Si algún día compras un dominio propio (p. ej. `afkcommunity.app`), el paquete sería `app.afkcommunity`. Conviene decidirlo antes de publicar en Android, no antes de empezar.

---

## 10. Convertir la web en PWA

Se hace al final, cuando la web ya funciona. Solo hacen falta archivos estáticos, sin servicios externos:

1. `webApp/src/webMain/resources/manifest.webmanifest`: nombre, íconos (192 y 512 px), `display: standalone`, colores del tema oscuro.
2. `sw.js` (service worker), con dos estrategias:
   - **cache-first** para el «cascarón»: `index.html`, `.wasm`, `.js`, `composeResources/`;
   - **red primero** para `index.html`, para recibir versiones nuevas.
   
   Usa un nombre de caché con la versión, para que se limpie al publicar.
3. Registrar el service worker en `index.html`.
4. Pedir `navigator.storage.persist()` al iniciar.
5. Publicar en un hosting estático con HTTPS (p. ej. GitHub Pages; solo sirve archivos).

Como todos los datos son locales (OPFS), la app instalada funciona sin conexión. El respaldo y el paso entre dispositivos se hacen con el `.zip` de exportar, igual que hoy entre PCs.

---

## 11. Pruebas

- **`commonTest`**: pruebas unitarias de cada función portada, con casos pequeños escritos a mano:
  - baneos por alcance y copia;
  - límites `max = -1`;
  - `deducir_golden` con 0, 1 o 2 especiales;
  - poda del optimizador;
  - `detectar` con las 4 formas de archivo.
  
  Corren en JVM y en la web (`:shared:allTests`).
- **`jvmTest`**: equivalencia con Python sobre datos reales (Etapa 0).
- **Cada etapa** termina con `./gradlew :shared:allTests :desktopApp:run` y `:webApp:wasmJsBrowserDevelopmentRun`, y con Android desde la Etapa 6.

---

## 12. Registro de avance

### Etapa 0: Preparación (terminada)

**Qué se hizo:**
- **Paquete** `io.github.shredia.afkcommunity` en todos los módulos (`namespace`, `applicationId`, `mainClass`). La clase de recursos es `io.github.shredia.afkcommunity.recursos.Res`. El instalador de escritorio se llama `AFK-Community`.
- **Dependencias** (en `libs.versions.toml`): `kotlinx-serialization-json` 1.13.0 (con su plugin), `kotlinx-datetime` 0.8.0, `kotlinx-coroutines-core` 1.11.0, y `kotlinx-coroutines-test` para las pruebas.
- **Idiomas** (`idiomas/`): `tr()`, `N_()`, `Idiomas.usar()`, `cambiarIdioma()` e `idiomasDisponibles()`.
  - Los archivos son **los mismos** `NC/idiomas/*.json` de la app Python. La tarea Gradle `juntarRecursos` los incluye al compilar y genera `files/idiomas/indice.txt`. Hay una sola fuente de traducciones; la herramienta `python -m idiomas actualizar` conserva en `en.json` las frases que no usa el código Python.
  - `formatear()` reproduce el `str.format` de Python que usan las frases: `{0}`, `{}`, `{0:.3f}`, `{1:+.3f}`, `{0:7.3f}`, `{0:02d}`, `{0:<20}`, `{{ }}`. Esto incluye el redondeo exacto de Python, por ejemplo `format(2.675, '.2f') = '2.67'` y los empates al par.
  - JVM y Android usan `BigDecimal`; la web usa los dígitos exactos de `toFixed(x, 100)`.
- **Almacenamiento** (`datos/Almacen`): la interfaz común y `AlmacenArchivos` para escritorio.
  - Carpeta: `%APPDATA%/AFK-Community`, o la variable `AFK_DATOS` para usar una copia de prueba.
  - Escritura atómica igual a la de Python (`.tmp` y luego reemplazar).
  - `modificado()` da exactamente el `st_mtime` de Python. Verificado con 264 detalles: los 264 coinciden con los guardados en `optimizador_indice.json`, así que el índice de la app Python se reutiliza sin reconstruirlo.
- **Arnés de equivalencia**: `herramientas_migracion/generar_casos.py`.
  - Usa los módulos Python sin modificarlos y trabaja sobre una copia.
  - Genera `casos_prueba/<cuenta>_<servidor>/` con `entrada/` y `esperado/` (índice, composiciones y 10 variantes del optimizador, con y sin bloqueos).
  - Con tus datos generó 2 casos (282 MB): el servidor 1111 con «Óptimo global» en las 10 variantes, y el 1192 con casos «Sin solución».
  - `casos_prueba/` está en `.gitignore`.
- **Pruebas**: 13 pruebas de formato, idiomas y almacenamiento.
  - Las de formato e idiomas corren en JVM, Wasm y JS.
  - Las de almacenamiento y archivos de idioma corren en la JVM.
  - Todas pasan. También compilan `desktopApp` y `webApp` (wasm y js).

**Cómo correr las pruebas** (desde `AFK-community/`):
```
JAVA_HOME=%LOCALAPPDATA%\Programs\IntelliJ IDEA\jbr                 (o el JDK que tengas)
CHROME_BIN=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe   (para las pruebas web)
gradlew :shared:jvmTest :shared:wasmJsTest :shared:jsTest
```
**Regenerar los casos** (desde `AFK-community/`, después de cambiar la app Python o los datos):
```
..\.venv\Scripts\python herramientas_migracion\generar_casos.py ..\datos_usuario\cuentas
```

**Diferencias con Python encontradas** (aceptadas, documentadas en el código):
- **Solo en el target `js`**: JavaScript no distingue `3` de `3.0`. Un decimal sin parte fraccionaria pasado a `tr("{0}")` se escribe `3`, no `3.0`. En JVM, Android y Wasm es igual que Python.

### Primera versión Android (Etapas 1–4, sin web)

Por pedido: agregar las funciones de la app Python, enfocado en Android; la web se ignora por ahora (abre la app
con un almacén en memoria, sin importar nada).

**Decisiones que cambian el plan:**
- **JSON genérico en lugar de data classes** (cambia §3 y la Etapa 1). Los datos se manejan como en Python:
  `JsonObject` con lectores tolerantes (`datos/Js.kt`: `o()`, `a()`, `verdad()`, `py()`, `entero()`… reproducen
  `x or {}`, `bool()`, `str()`, `int()` de Python). Así cada función Kotlin se compara línea a línea con su
  original y los archivos quedan idénticos. Solo `Composicion`, `Opciones` y `Resultado` son clases.
- **Archivos grandes por trozos** (`datos/TrozoJson.kt`). afk-runs.json y afk-inventory.json pesan ~75 MB: el árbol
  completo de kotlinx no cabe en la memoria de un teléfono (en la JVM de pruebas, con 512 MB, fallaba). Se recorre
  el texto y se parsea cada run por separado; del inventario se descarta el bloque `source` (19 MB, solo se usa el
  servidor). La importación real corre con 512 MB.
- **Íconos en código** (`ui/Iconos.kt`) en lugar de XML en los recursos (D3): los mismos trazados de Material
  Symbols, sin dependencias y sin generar accesores.
- **Imágenes del juego incluidas**: `recursos/assets` (7,2 MB) se copia a `files/assets/` al compilar
  (`juntarRecursos`). Se buscan primero en `assets/` de la carpeta de datos.
- `minSdk` sigue en 24: Android usa su propio almacén con `java.io` (`androidApp/PlataformaAndroid.kt`), sin
  `java.nio.file`. `largeHeap` activado por el índice del optimizador.

**Qué hay** (paquete `io.github.shredia.afkcommunity`):
- `logica/`: `Optimizador` (índice, composiciones, SP manual, baneos, límites, búsqueda cooperativa que cede cada
  2 048 nodos), `Bloqueos`, `Visuales`, `Cuenta` (compactar inventario, índice de héroes, uso en NC), `Importar`
  (detectar, plantillas, convertir héroe/mascota, runs, inventario, amigos, simulaciones, copias .zip, runs de la app).
- `ui/`: tema oscuro con dorado, menú en cajón lateral y pantallas Inicio, Optimizador (rotación, opciones, fuentes
  «tú / amigo / todos los amigos / tú + amigos», resultado, alternativas por jefe, detalle con «No usar» y SP manual),
  Explorar equipos, Configurar optimizador (bloqueos: activar / borrar), Mi cuenta (héroes, colecciones, mascotas,
  recursos), Amigos (renombrar, borrar, optimizar con sus runs), Importar / exportar y Ajustes (idioma).
- Plataformas: `androidApp` (selector del sistema, `filesDir`, botón atrás → Inicio) y `desktopApp` (ventana del
  tamaño de un teléfono, para probar sin emulador).

**Pruebas** (jvmTest, todas en verde):
- `EquivalenciaOptimizadorTest`: con los casos de `casos_prueba/`, el índice, las 1 584 composiciones y las 10
  variantes del optimizador dan lo mismo que Python (total, equipos elegidos, candidatos y desempates). El índice
  armado desde cero da las mismas runs.
- Importación real (`ImportarRealTest`, con `AFK_IMPORTAR_ORIGEN` / `AFK_IMPORTAR_DESTINO`): importando
  afk-inventory.json + afk-runs.json en carpetas vacías, Kotlin y Python escriben los **mismos 302 archivos** (solo
  cambia la hora de importación).
- `CopiaZipTest`: exportar → restaurar, importar como amigo sin duplicar, rutas peligrosas rechazadas, y el .zip
  real exportado por la app Python (297 runs como amigo).
- En la app de escritorio, con esos datos: óptimo global 2m 12.393 s, igual que Python.

**Falta (de esta parte):** ver «Segunda parte» abajo.

### Segunda parte: lo que faltaba de la app Python

- **Progreso semanal** (`logica/Progreso.kt`, `ui/pantallas/Progreso.kt`): `semanas_de`, gráfico en `Canvas` (mejor run y
  suma de mejores) y lista con «última vez con estos jefes». `sum()` de Python 3.12+ usa suma compensada (Neumaier):
  se reproduce con `sumaPy`, si no 117.847 sale 117.84700000000001.
- **Fractura temporal** (`logica/Fractura.kt`, `ui/pantallas/Fractura.kt`): `calcular`, vínculos con la bolsa,
  inventario, próximo viernes; pestañas Resumen por recurso, Cofres de elección (ahora / planeado con topes, gastados),
  Tiendas de medallas (compradas / planeadas con máximos), Recompensas por piso; vincular un recurso con la bolsa;
  reiniciar compras / nueva temporada. Cabecera plegable para pantallas angostas. Íconos: bolsa, recortes de
  `recursos/capturas` (incluidos en `files/assets/capturas`) y el CDN incluido. Sin importación de Excel (D5).
- **Perfil de roster** (`logica/Roster.kt`): `cargar_perfil`, correcciones (`perfil_roster.json`), `evaluar_equipo`,
  `filtrar_por_roster`. `anotarEstrellas` (★ de cada colección) como `_anotar_estrellas` de Python.
- **Optimizador**: pestañas ★ Resumen (tu equipo vs. los demás por jefe), 🎯 Qué me falta (equipos más rápidos y qué
  te falta, «lo que más te acerca») y 📊 Estadísticas (daño, curación, defensa, energía, vida por héroe). Fuentes
  «Todos los demás» y «Tu selección» (`seleccion_fuentes`), filtro de roster para equipos de otros
  (`equipos_otros_roster`).
- **Configurar optimizador**: Bloqueos (lista + nueva regla: baneos y límites de héroe / colección / mascota, por jefe
  y «aplica a»), Mi roster (correcciones), Fuentes (Tu selección), Búsqueda (modo de roster).
- **Traducciones**: 123 frases nuevas de la app Kotlin agregadas a `NC/idiomas/en.json` (la herramienta
  `python -m idiomas actualizar` las conserva aunque el código Python no las use).

**Pruebas nuevas**: `EquivalenciaExtraTest` contra `herramientas_migracion/generar_casos_extra.py` (progreso semanal,
Fractura con el avance y la bolsa reales, perfil de roster y 1 770 evaluaciones «¿puedes armarlo?»): todo igual a
Python. En total 23 pruebas JVM en verde.

**Falta:**
- **Compilar el APK**: no hay SDK de Android en este PC (Android Studio está instalado, pero su asistente inicial no
  descargó el SDK). El código de `androidApp` no se ha compilado todavía.
- Probar en un teléfono real (tamaños de letra, teclado, selector de archivos, rendimiento con índices grandes).
- Fuera del alcance de la app Python publicada: conexión al sitio, Guías, Vista (tamaño de retratos).
