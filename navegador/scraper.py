import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright
from .parser import unpack_sources
from .rutas import cargar_mapa_personajes, ruta_detalle, todos_los_detalles
from .visuales import Visuales, extraer_tablas, ruta_tablas
from idiomas import tr

BASE = "https://esperianarchive.com"
VIEWPORT = {"width": 1440, "height": 900}
REQUEST_TIMEOUT = 90_000


async def _open_browser(playwright, profile_path):
    return await playwright.chromium.launch_persistent_context(
        user_data_dir=str(Path(profile_path).resolve()),
        headless=True,
        viewport=VIEWPORT,
    )


FETCH_TIMEOUT_MS = 30_000


def _sin_progreso(_mensaje):
    pass


async def _fetch_json(page, url, timeout_ms=FETCH_TIMEOUT_MS, x_page=None):
    """Hace fetch dentro de la página (usa la sesión del perfil). Corta a los timeout_ms."""
    return await page.evaluate(
        """async ([url, timeoutMs, xPage]) => {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), timeoutMs);
            try {
                const response = await fetch(url, {
                    credentials: 'same-origin',
                    headers: xPage ? {'Accept': 'application/json', 'x-page': xPage}
                                   : {'Accept': 'application/json'},
                    signal: controller.signal
                });
                let body;
                try {
                    body = await response.json();
                } catch (error) {
                    body = {error: 'No JSON'};
                }
                return {status: response.status, body};
            } catch (error) {
                const timeout = error.name === 'AbortError';
                return {status: 0, body: {error: timeout ? 'Tiempo de espera agotado' : String(error)}};
            } finally {
                clearTimeout(timer);
            }
        }""",
        [url, timeout_ms, x_page],
    )


async def _abrir_sesion_simulador(p, perfil_path, progreso):
    """Abre el navegador, entra al simulador y verifica que la sesión siga iniciada."""
    progreso(tr("Abriendo navegador (Chromium)..."))
    try:
        browser = await _open_browser(p, perfil_path)
    except Exception as error:
        raise RuntimeError(
            tr('No se pudo abrir el navegador. ¿Hay otra descarga en curso usando el mismo perfil? Detalle: {0}', error)
        ) from error

    try:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        progreso(tr("Conectando a esperianarchive.com..."))
        await page.goto(BASE + '/nc-simulator', wait_until='domcontentloaded', timeout=REQUEST_TIMEOUT)
        progreso(tr("Página cargada. Verificando sesión..."))

        if "/login" in page.url:
            raise RuntimeError(tr("La sesión no está iniciada. Usa 'Acceso al sitio' para iniciar sesión."))

        me = await _fetch_json(page, '/api/auth/me')
        if me['status'] in (401, 403):
            raise RuntimeError(tr("La sesión expiró. Usa 'Acceso al sitio' para iniciar sesión de nuevo."))
        if me['status'] == 0:
            raise RuntimeError(tr('No hay conexión con el servidor: {0}', me['body'].get('error')))
    except BaseException:
        await browser.close()
        raise

    progreso(tr("Sesión verificada ✓"))
    return browser, page

async def configurar_cuenta(perfil_path, correo="", password=""):
    browser = None

    async with async_playwright() as p:
        try:
            browser = await _open_browser(p, perfil_path)
            page = browser.pages[0] if browser.pages else await browser.new_page()
            await page.goto(BASE + '/login', wait_until='domcontentloaded', timeout=REQUEST_TIMEOUT)

            if correo and password:
                print("Ingresando credenciales automáticamente...")
                await page.fill('input[name="email"]', correo)
                await page.fill('input[type="password"]', password)
                await page.click('button.button:has-text("Sign in")')
                await page.wait_for_timeout(2500)

                error_locator = page.locator('div.notice.error')
                if await error_locator.is_visible():
                    texto_error = await error_locator.inner_text()
                    raise Exception(f"Credenciales incorrectas: {texto_error}")

                await page.wait_for_url(
                    lambda url: "/login" not in url,
                    timeout=20_000,
                )
                print("¡Inicio de sesión completado y sesión guardada en el perfil!")
            else:
                input("\nPresiona ENTER cuando hayas iniciado sesión manualmente... ")

        finally:
            if browser:
                await browser.close()

async def obtener_sources_iniciales(perfil_path, progreso=_sin_progreso):
    """Descarga la lista resumida de runs (poca información)."""
    browser = None

    async with async_playwright() as p:
        try:
            browser, page = await _abrir_sesion_simulador(p, perfil_path, progreso)
            progreso(tr("Descargando lista de runs (/api/nc-sim/sources)..."))
            response = await _fetch_json(page, '/api/nc-sim/sources', timeout_ms=REQUEST_TIMEOUT)
            if response['status'] == 0 or response['status'] >= 400:
                detalle = response['body'].get('error', '') if isinstance(response['body'], dict) else ''
                raise RuntimeError(f"Error en la API: {response['status']} {detalle}".strip())
            todas = unpack_sources(response['body'])
            # La API entrega todas las runs juntas; se descartan de inmediato las ajenas.
            sources = [run for run in todas if run.get("mine") is True]
            progreso(tr('Lista recibida: {0} runs tuyas (se descartaron {1} ajenas).', len(sources), len(todas) - len(sources)))
            return sources

        except Exception as error:
            raise RuntimeError(tr('No se pudieron obtener los sources iniciales: {0}', error)) from error
        finally:
            if browser:
                progreso(tr("Cerrando navegador..."))
                await browser.close()


def detalles_pendientes(base_dir, sources):
    """
    Runs propias (mine: true) cuyo detalle aún no existe en cuentas/<cuenta>/<servidor>/detalles/.
    Retorna (pendientes, ya_descargadas) con pendientes = [(run, ruta_destino), ...].
    """
    mapa = cargar_mapa_personajes(base_dir)
    pendientes, ya = [], 0
    for run in sources:
        if run.get("mine") is not True or not run.get("id"):
            continue  # nunca se descarga nada que no sea propio
        destino = ruta_detalle(base_dir, mapa, run)
        if destino.exists():
            ya += 1
        else:
            pendientes.append((run, destino))
    return pendientes, ya


def _guardar_json_atomico(destino, datos):
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".tmp")
    # JSON compacto: cada detalle pesa ~2 MB con sangría
    temporal.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporal.replace(destino)  # escritura atómica: no quedan archivos a medias


async def descargar_detalles_faltantes(
    perfil_path,
    sources,
    base_dir,
    progreso=_sin_progreso,
    avance=None,
    cancelar=None,
    espera=0.35,
):
    """
    Descarga el detalle completo (harta información) de las runs propias que faltan
    y lo guarda en cuentas/<cuenta>/<servidor>/detalles/<id>.json.

    progreso(str): mensajes de estado.
    avance(hechas, total): para la barra de progreso.
    cancelar: threading.Event; si se activa, se detiene tras la run actual.

    Retorna (descargadas, errores) donde errores es una lista de (id, mensaje).
    """
    pendientes, ya = detalles_pendientes(base_dir, sources)
    total = len(pendientes)
    descargadas, errores = 0, []

    if not pendientes:
        progreso(tr("No hay detalles pendientes: ya tienes todos."))
        return descargadas, errores

    progreso(tr('{0} detalles ya descargados. Faltan {1}.', ya, total))
    if avance:
        avance(0, total)

    browser = None
    async with async_playwright() as p:
        try:
            browser, page = await _abrir_sesion_simulador(p, perfil_path, progreso)

            for i, (run, destino) in enumerate(pendientes, 1):
                if cancelar is not None and cancelar.is_set():
                    progreso(tr("Descarga cancelada por el usuario."))
                    break

                rid = str(run["id"])
                carpeta_rel = destino.parent.parent.relative_to(Path(base_dir) / "cuentas")
                progreso(f"[{i}/{total}] {rid}  →  {carpeta_rel.as_posix()}")
                respuesta = await _fetch_json(page, f'/api/nc-sim/source?kind=own&id={rid}')
                status = respuesta['status']
                body = respuesta['body']

                if status == 200 and isinstance(body, dict) and 'error' not in body:
                    _guardar_json_atomico(destino, body)
                    descargadas += 1
                else:
                    detalle = body.get('error', '') if isinstance(body, dict) else ''
                    mensaje = f"HTTP {status} {detalle}".strip()
                    errores.append((rid, mensaje))
                    progreso(tr('   ⚠ Error en {0}: {1}', rid, mensaje))
                    if status in (401, 403):
                        progreso(tr("La sesión expiró; se detiene la descarga."))
                        break

                if avance:
                    avance(i, total)
                await asyncio.sleep(max(espera, 0))

            return descargadas, errores

        finally:
            if browser:
                progreso(tr("Cerrando navegador..."))
                await browser.close()


# ============================================
# ASSETS (imágenes de héroes, mascotas, etc.)
# ============================================

EXTENSIONES_ASSET = (".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg")

# Vuelca los exports de un módulo JS del sitio (tablas estáticas) a datos JSON
_JS_VOLCAR_MODULO = """async (url) => {
  const m = await import(url);
  const vistos = new WeakSet();
  const limpiar = (v, d) => {
    if (d > 8 || typeof v === 'function') return null;
    if (v && typeof v === 'object') {
      if (vistos.has(v)) return null;
      vistos.add(v);
      if (Array.isArray(v)) return v.map(x => limpiar(x, d + 1));
      const o = {};
      for (const k of Object.keys(v)) o[k] = limpiar(v[k], d + 1);
      return o;
    }
    return v;
  };
  const out = {};
  for (const k of Object.keys(m)) out[k] = limpiar(m[k], 0);
  return out;
}"""


# Busca en el módulo principal del sitio la tabla de recomendaciones de colecciones
# (filas con collectionTid + requirements). No depende del nombre minificado del export.
_JS_RECOMENDACIONES = """async () => {
  const url = performance.getEntriesByType('resource').map(e => e.name).find(n => /\\/index-[^/]+\\.js/.test(n));
  if (!url) return [];
  const m = await import(url);
  for (const k of Object.keys(m)) {
    const v = m[k];
    if (Array.isArray(v) && v.length && v[0] && typeof v[0] === 'object'
        && 'collectionTid' in v[0] && 'requirements' in v[0]) {
      return JSON.parse(JSON.stringify(v));
    }
  }
  return [];
}"""


async def actualizar_tablas_sitio(page, base_dir, progreso=_sin_progreso):
    """
    Guarda en NC/assets/tablas_sitio.json las tablas estáticas del sitio (nombres e imágenes de
    jefes, equipo, afijos, colecciones, estrellas...). Son datos del juego, no runs de nadie.
    """
    progreso(tr("Leyendo tablas del sitio (jefes, equipo, afijos, colecciones)..."))
    url = await page.evaluate(
        "() => performance.getEntriesByType('resource').map(e => e.name)"
        ".find(n => /\\/GameVisuals-[^/]+\\.js/.test(n)) || null"
    )
    if not url:
        raise RuntimeError(tr("No se encontró el módulo GameVisuals en la página."))
    tablas = extraer_tablas(await page.evaluate(_JS_VOLCAR_MODULO, url))
    if not tablas.get("jefes") or not tablas.get("equipo"):
        raise RuntimeError(tr("El módulo GameVisuals cambió de formato."))

    # Guía de colecciones (planilla comunitaria "Collections Checklist" que usa el sitio)
    try:
        tablas["recomendaciones_colecciones"] = await page.evaluate(_JS_RECOMENDACIONES) or []
    except Exception as error:
        progreso(tr('   ⚠ No se pudo leer la guía de colecciones: {0}', (str(error).splitlines() or [''])[0]))
        tablas["recomendaciones_colecciones"] = []
    destino = ruta_tablas(base_dir)
    destino.parent.mkdir(parents=True, exist_ok=True)
    nuevo = json.dumps(tablas, ensure_ascii=False, indent=1)
    if not destino.exists() or destino.read_text(encoding="utf-8") != nuevo:
        destino.write_text(nuevo, encoding="utf-8")
    progreso(tr('Tablas del sitio: {0} jefes, {1} piezas de equipo, {2} afijos, {3} colecciones, {4} recomendaciones de la guía.', len(tablas['jefes']), len(tablas['equipo']), len(tablas['afijos']), len(tablas['colecciones']), len(tablas.get('recomendaciones_colecciones') or [])))


def _recolectar_urls(obj, encontradas):
    if isinstance(obj, dict):
        for valor in obj.values():
            _recolectar_urls(valor, encontradas)
    elif isinstance(obj, list):
        for valor in obj:
            _recolectar_urls(valor, encontradas)
    elif isinstance(obj, str):
        url = obj.split("?", 1)[0]
        if url.startswith(BASE):
            url = url[len(BASE):]
        if url.startswith("/") and not url.startswith("//") and url.lower().endswith(EXTENSIONES_ASSET):
            encontradas.add(url)


ARCHIVO_CACHE_URLS = "urls_por_detalle.json"


def _urls_de_detalles(base_dir):
    """
    Todas las URLs de imágenes que usan tus detalles: las que vienen en el JSON (héroes, mascotas)
    y las que el sitio arma con sus tablas (jefes, equipo, afijos, colecciones, estrellas, SI...).
    Se cachea por archivo para no releer ~0,1 s por detalle cada vez.
    """
    vis = Visuales(base_dir)
    carpeta = Path(base_dir) / "assets"
    archivo_cache = carpeta / ARCHIVO_CACHE_URLS
    firma_tablas = str(ruta_tablas(base_dir).stat().st_mtime) if ruta_tablas(base_dir).exists() else ""

    cache = {}
    if archivo_cache.exists():
        try:
            cache = json.loads(archivo_cache.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cache = {}
    if cache.get("_tablas") != firma_tablas:
        cache = {"_tablas": firma_tablas}

    urls, cambiado, vistos = set(vis.urls_fijas()) if vis.disponible else set(), False, set()
    for archivo in todos_los_detalles(base_dir):
        clave = archivo.relative_to(Path(base_dir)).as_posix()
        vistos.add(clave)
        mtime = archivo.stat().st_mtime
        entrada = cache.get(clave)
        if not entrada or entrada.get("mtime") != mtime:
            try:
                detalle = json.loads(archivo.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            propias = set()
            _recolectar_urls(detalle.get("rounds") or [], propias)  # solo lo usado en tus rondas
            if vis.disponible:
                for ronda in detalle.get("rounds") or []:
                    propias.update(vis.urls_de_ronda(ronda))
            entrada = {"mtime": mtime, "urls": sorted(propias)}
            cache[clave] = entrada
            cambiado = True
        urls.update(entrada["urls"])

    for clave in [c for c in cache if c != "_tablas" and c not in vistos]:
        del cache[clave]
        cambiado = True
    if cambiado:
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo_cache.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return urls


def assets_pendientes(base_dir):
    """
    URLs de imágenes usadas por tus detalles descargados que aún no están en NC/assets/.
    Retorna (pendientes, total_referenciadas) con pendientes = [(url, ruta_destino), ...].
    """
    urls = _urls_de_detalles(base_dir)
    carpeta = Path(base_dir) / "assets"
    pendientes = []
    for url in sorted(urls):
        destino = carpeta.joinpath(*url.lstrip("/").split("/"))
        if not destino.exists():
            pendientes.append((url, destino))
    return pendientes, len(urls)


async def descargar_assets(
    perfil_path,
    base_dir,
    progreso=_sin_progreso,
    avance=None,
    cancelar=None,
    espera=0.05,
):
    """
    Descarga a NC/assets/<misma ruta que en la web> las imágenes usadas en tus detalles.
    Solo baja las que no tienes. Retorna (descargadas, errores).
    """
    descargadas, errores = 0, []
    if not todos_los_detalles(base_dir):
        progreso(tr("No hay detalles descargados todavía: descarga primero los detalles."))
        return descargadas, errores

    browser = None
    async with async_playwright() as p:
        try:
            browser, page = await _abrir_sesion_simulador(p, perfil_path, progreso)

            try:
                await actualizar_tablas_sitio(page, base_dir, progreso)
            except Exception as error:
                progreso(tr('   ⚠ No se pudieron actualizar las tablas del sitio: {0}', str(error).splitlines()[0]))

            progreso(tr("Buscando imágenes usadas en tus runs..."))
            pendientes, total_refs = assets_pendientes(base_dir)
            total = len(pendientes)
            if not pendientes:
                progreso(tr('Ya tienes las {0} imágenes.', total_refs))
                return descargadas, errores

            progreso(tr('{0} imágenes usadas en tus runs; faltan {1}.', total_refs, total))
            if avance:
                avance(0, total)

            for i, (url, destino) in enumerate(pendientes, 1):
                if cancelar is not None and cancelar.is_set():
                    progreso(tr("Descarga cancelada por el usuario."))
                    break

                progreso(f"[{i}/{total}] {url}")
                error_final = None
                for intento in (1, 2):
                    try:
                        # browser.request comparte las cookies de la sesión
                        respuesta = await browser.request.get(BASE + url, timeout=FETCH_TIMEOUT_MS * intento)
                        if respuesta.ok:
                            destino.parent.mkdir(parents=True, exist_ok=True)
                            temporal = destino.with_name(destino.name + ".tmp")
                            temporal.write_bytes(await respuesta.body())
                            temporal.replace(destino)
                            descargadas += 1
                            error_final = None
                        else:
                            error_final = f"HTTP {respuesta.status}"
                        break
                    except Exception as error:
                        # Solo la primera línea: el resto del log de Playwright incluye la cookie de sesión
                        error_final = (str(error).splitlines() or ["Error desconocido"])[0]
                        if intento == 1:
                            progreso(tr("   ↻ Tardó demasiado, reintentando..."))

                if error_final:
                    errores.append((url, error_final))
                    progreso(f"   ⚠ {error_final}")

                if avance:
                    avance(i, total)
                await asyncio.sleep(max(espera, 0))

            return descargadas, errores

        finally:
            if browser:
                progreso(tr("Cerrando navegador..."))
                await browser.close()


# ============================================
# FETCH: pedir al sitio que vuelva a leer los datos desde el juego
# ============================================

ESTADOS_EN_CURSO = {"FETCHING", "QUEUED", "PENDING", "RUNNING", "WAITING"}
ARCHIVO_ULTIMO_FETCH = "ultimo_fetch.json"
INTERVALO_FETCH_S = 4          # el sitio consulta cada 4 s
TIEMPO_MAX_FETCH_S = 15 * 60


async def _cuentas_api(page):
    # Sin la cabecera x-page el sitio responde 409 ("This page is out of date")
    respuesta = await _fetch_json(page, "/api/game-accounts", x_page="/game-accounts")
    if respuesta["status"] != 200 or not isinstance(respuesta["body"], dict):
        raise RuntimeError(tr('No se pudo leer /api/game-accounts (HTTP {0}).', respuesta['status']))
    return respuesta["body"].get("accounts") or []


def _cuenta_con_servidor(cuentas, account_id, server_id):
    """La cuenta indicada; si ya no existe en el sitio, la que tenga ese servidor."""
    for c in cuentas:
        if str(c.get("id")) == str(account_id):
            return c
    for c in cuentas:
        if any(str(r.get("svr_id")) == str(server_id) for r in c.get("roles") or []):
            return c
    return None


def resumen_fetch(cuenta):
    """Lo relevante del report de un fetch: estado, fecha y sección Nightmare Corridor."""
    report = cuenta.get("report") or {}
    nc = (report.get("sections") or {}).get("NC") or {}
    return {
        "estado": cuenta.get("status"),
        "error": cuenta.get("error"),
        "fetchedAt": cuenta.get("fetchedAt"),
        "servidor": report.get("serverId") or cuenta.get("selectedServer"),
        "nc_estado": nc.get("status"),
        "nc_temporada": nc.get("season"),
        "nc_disponibles": nc.get("available"),
        "nc_traidas": nc.get("fetched"),
        "nc_fallos": nc.get("failures") or [],
        "runs_importadas": report.get("importedRuns"),
        "limitaciones": report.get("limitations") or [],
    }


async def hacer_fetch_servidor(perfil_path, base_dir, account_id, server_id,
                               progreso=_sin_progreso, cancelar=None):
    """
    Igual que el botón "Fetch" del sitio: POST /api/game-accounts/<id>/fetch {serverId} y luego
    consulta /api/game-accounts cada 4 s hasta que el estado deje de ser FETCHING.
    Guarda las cuentas actualizadas en cuentas/ y devuelve resumen_fetch(cuenta).
    """
    browser = None
    async with async_playwright() as p:
        try:
            browser, page = await _abrir_sesion_simulador(p, perfil_path, progreso)

            cuentas = await _cuentas_api(page)
            cuenta = _cuenta_con_servidor(cuentas, account_id, server_id)
            if cuenta is None:
                raise RuntimeError(tr('El sitio no tiene ninguna cuenta con el servidor {0}.', server_id))
            account_id = str(cuenta["id"])
            anterior = cuenta.get("fetchedAt")
            progreso(tr('Último fetch registrado: {0}', anterior or 'nunca'))

            if str(cuenta.get("status")).upper() not in ESTADOS_EN_CURSO:
                progreso(tr('Solicitando fetch del servidor {0}...', server_id))
                respuesta = await page.evaluate(
                    """async ([url, cuerpo]) => {
                        const r = await fetch(url, {
                            method: 'POST', credentials: 'same-origin',
                            headers: {'Content-Type': 'application/json', 'Accept': 'application/json',
                                      'x-page': '/game-accounts'},
                            body: JSON.stringify(cuerpo)
                        });
                        let body = null;
                        try { body = await r.json(); } catch (e) {}
                        return {status: r.status, body};
                    }""",
                    [f"/api/game-accounts/{account_id}/fetch", {"serverId": int(server_id)}],
                )
                if respuesta["status"] not in (200, 202):
                    detalle = respuesta["body"].get("error") if isinstance(respuesta["body"], dict) else ""
                    raise RuntimeError(f"El sitio rechazó el fetch (HTTP {respuesta['status']}) {detalle or ''}".strip())
                progreso(tr('El sitio aceptó el fetch: {0}.', (respuesta['body'] or {}).get('status', 'en curso')))
            else:
                progreso(tr("Ya había un fetch en curso; esperando a que termine..."))

            inicio = asyncio.get_running_loop().time()
            while True:
                if cancelar is not None and cancelar.is_set():
                    progreso(tr("Dejé de esperar (el fetch sigue en el sitio y terminará solo)."))
                    break
                await asyncio.sleep(INTERVALO_FETCH_S)
                transcurrido = int(asyncio.get_running_loop().time() - inicio)
                cuentas = await _cuentas_api(page)
                cuenta = _cuenta_con_servidor(cuentas, account_id, server_id) or cuenta
                estado = str(cuenta.get("status") or "").upper()
                cola = cuenta.get("queue")
                extra = f" · en cola: {cola}" if cola not in (None, "", 0) else ""
                progreso(tr('   [{0:02d}:{1:02d}] estado: {2}{3}', transcurrido // 60, transcurrido % 60, estado, extra))
                if estado not in ESTADOS_EN_CURSO:
                    break
                if transcurrido > TIEMPO_MAX_FETCH_S:
                    raise RuntimeError(tr("El fetch tarda demasiado (más de 15 min). Revisa el sitio más tarde."))

            # Guardar las cuentas actualizadas (sin el report completo, que es enorme)
            livianas = [{k: v for k, v in c.items() if k != "report"} for c in cuentas]
            guardar_game_accounts({"accounts": livianas}, base_dir)

            resumen = resumen_fetch(cuenta)
            resumen["anterior"] = anterior
            resumen["account_id"] = account_id
            if str(resumen.get("servidor")) == str(server_id) and resumen.get("fetchedAt") != anterior:
                carpeta = Path(base_dir) / "cuentas" / account_id / str(server_id)
                carpeta.mkdir(parents=True, exist_ok=True)
                (carpeta / ARCHIVO_ULTIMO_FETCH).write_text(
                    json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
            return resumen
        finally:
            if browser:
                progreso(tr("Cerrando navegador..."))
                await browser.close()


async def obtener_game_accounts(page):
    """
    Obtiene las cuentas de juego desde Esperian Archive.

    Parámetros
    ----------
    page : playwright.async_api.Page
        Página de Playwright con la sesión iniciada.

    Retorna
    -------
    dict
        Respuesta JSON de la API, incluyendo las cuentas
        y sus respectivos personajes.

    No guarda archivos.
    """

    print("⏳ Obteniendo cuentas de juego...")

    # ============================================
    # 1. CONSULTAR API
    # ============================================

    resultado = await page.evaluate(
        """
        async () => {

            const respuesta = await fetch(
                '/api/game-accounts',
                {
                    method: 'GET',
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json',
                        'x-page': '/game-accounts'
                    }
                }
            );

            if (!respuesta.ok) {
                throw new Error(
                    `Error HTTP ${respuesta.status}: ${respuesta.statusText}`
                );
            }

            return await respuesta.json();
        }
        """
    )

    # ============================================
    # 2. VALIDAR RESPUESTA
    # ============================================

    if not isinstance(resultado, dict):
        raise ValueError(
            tr("La API devolvió una estructura inesperada.")
        )

    accounts = resultado.get("accounts", [])

    if not isinstance(accounts, list):
        raise ValueError(
            tr("El campo 'accounts' no contiene una lista.")
        )

    # ============================================
    # 3. MOSTRAR RESUMEN
    # ============================================

    print(f"✅ Cuentas obtenidas: {len(accounts)}")

    total_personajes = 0

    for cuenta in accounts:

        account_id = cuenta.get("id", "N/A")
        selected_server = cuenta.get("selected_server", "N/A")

        roles = cuenta.get("roles", [])

        print(
            f"\n📁 Cuenta: {account_id}"
            f"\n   Servidor seleccionado: {selected_server}"
        )

        for personaje in roles:

            uid = personaje.get("uid", "N/A")
            nombre = personaje.get("name", "Sin nombre")
            servidor = personaje.get("svr_id", "N/A")
            nivel = personaje.get("level", "N/A")

            print(
                f"   ├─ {nombre}"
                f" | UID: {uid}"
                f" | Servidor: {servidor}"
                f" | Nivel: {nivel}"
            )

            total_personajes += 1

    print(
        f"\n✅ Total: {len(accounts)} cuentas, "
        f"{total_personajes} personajes."
    )

    # ============================================
    # 4. DEVOLVER DATOS
    # ============================================

    return resultado


def guardar_game_accounts(datos, directorio_base):

    directorio_base = Path(directorio_base)
    directorio_cuentas = directorio_base / "cuentas"

    directorio_cuentas.mkdir(
        parents=True,
        exist_ok=True
    )

    accounts = (
        datos
        if isinstance(datos, list)
        else datos.get("accounts", [])
    )

    for cuenta in accounts:

        account_id = str(cuenta.get("id", ""))

        if not account_id:
            continue

        # ============================================
        # 1. CARPETA DE CUENTA
        # ============================================

        carpeta_cuenta = (
            directorio_cuentas / account_id
        )

        carpeta_cuenta.mkdir(
            parents=True,
            exist_ok=True
        )

        # ============================================
        # 2. INFORMACIÓN GENERAL DE LA CUENTA
        # ============================================

        datos_cuenta = {
            clave: valor
            for clave, valor in cuenta.items()
            if clave != "roles"
        }

        archivo_cuenta = (
            carpeta_cuenta / "account.json"
        )

        # Conservar el servidor elegido localmente (no viene de la API)
        if archivo_cuenta.exists():
            try:
                with open(archivo_cuenta, "r", encoding="utf-8") as f:
                    anterior = json.load(f)
                if "servidor_local" in anterior:
                    datos_cuenta["servidor_local"] = anterior["servidor_local"]
                    cuenta["servidor_local"] = anterior["servidor_local"]
            except (OSError, json.JSONDecodeError):
                pass

        with open(
            archivo_cuenta,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                datos_cuenta,
                f,
                ensure_ascii=False,
                indent=4
            )

        # ============================================
        # 3. PERSONAJES
        # ============================================

        for personaje in cuenta.get("roles", []):

            servidor = personaje.get("svr_id")

            if servidor is None:
                continue

            servidor = str(servidor)

            carpeta_servidor = (
                carpeta_cuenta / servidor
            )

            carpeta_servidor.mkdir(
                parents=True,
                exist_ok=True
            )

            # ========================================
            # 4. JSON DEL PERSONAJE
            # ========================================

            archivo_personaje = (
                carpeta_servidor / f"{servidor}.json"
            )

            with open(
                archivo_personaje,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    personaje,
                    f,
                    ensure_ascii=False,
                    indent=4
                )

            print(
                f"Personaje guardado: "
                f"{archivo_personaje}"
            )

    return accounts