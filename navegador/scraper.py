import asyncio
import time
import re
from pathlib import Path
from playwright.async_api import async_playwright
from .utils import load, save
from .parser import unpack_sources
from tkinter import messagebox
import json

BASE = "https://esperianarchive.com"

# librerias/scraper.py
async def configurar_cuenta(perfil_path, correo="", password=""):
    profile = Path(perfil_path).resolve()
    browser = None  # Inicializamos en None por seguridad
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile), 
                headless=True, 
                viewport={'width': 1440, 'height': 900}
            )
            
            page = browser.pages[0] if browser.pages else await browser.new_page()
            await page.goto(BASE + '/login', wait_until='domcontentloaded', timeout=90000)

            if correo and password:
                print("Ingresando credenciales automáticamente...")
                await page.click('input[name="email"]')
                await page.fill('input[name="email"]', correo)
                await page.click('input[type="password"]')
                await page.fill('input[type="password"]', password)
                
                # Hacemos clic en el botón Sign in
                await page.click('button.button:has-text("Sign in")')
                
                # Damos un breve momento para que la página procese y revise el aviso
                await page.wait_for_timeout(2500)
                
                # Verificamos si apareció el aviso de error en la pantalla
                error_locator = page.locator('div.notice.error')
                if await error_locator.is_visible():
                    texto_error = await error_locator.inner_text()
                    # Esto saltará al bloque finally (cerrando el navegador) y mostrará el error en la app
                    raise Exception(f"Credenciales incorrectas: {texto_error}")
                
                # Si no hay error, esperamos a que cambie la URL indicando éxito
                await page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
                print("¡Inicio de sesión completado y sesión guardada en el perfil!")
                messagebox.showinfo("Éxito", "¡Proceso completado correctamente!")
            else:
                input("\nPresiona ENTER cuando hayas iniciado sesión manualmente... ")

        finally:
            # Solo intentamos cerrar si el navegador llegó a abrirse
            if browser:
                await browser.close()

async def descargar_runs(perfil_path, limite=0, espera=0.35):
    profile = Path(perfil_path).resolve()
    runs, errors = [], []
    
    async with async_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile), 
            headless=True, # Puede ir en True para que corra en segundo plano
            viewport={'width': 1440, 'height': 900}
        )
        try:
            page = browser.pages[0] if browser.pages else await browser.new_page()
            
            # 1. Creamos un "escucha" (listener) para interceptar la respuesta de la red 
            # cuando la página cargue el archivo inicial automáticamente
            archivo_inicial_data = None
            
            async def interceptar_respuesta(response):
                nonlocal archivo_inicial_data
                # Ajusta esta ruta o patrón según el nombre del archivo o endpoint que se descarga al inicio
                if "/api/nc-sim/sources" in response.url and response.status == 200:
                    try:
                        archivo_inicial_data = await response.json()
                    except:
                        pass

            page.on("response", interceptar_respuesta)

            # 2. Navegamos a la página
            await page.goto(BASE + '/nc-simulator', wait_until='networkidle', timeout=90000)

            # Si el archivo se descarga físicamente a la computadora, también podemos usar el evento 'download'
            # Pero si entra por red (JSON), el listener de arriba lo atrapa al instante.

            if not archivo_inicial_data:
                raise Exception("No se pudo capturar el archivo inicial de la página.")

            sources = unpack_sources(archivo_inicial_data)
            if limite: 
                sources = sources[:limite]

            # 3. Función auxiliar para hacer peticiones posteriores usando la sesión
            async def fetch(url):
                return await page.evaluate("""async (url) => {
                    const r = await fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}});
                    let body; try { body = await r.json(); } catch (e) { body = {error: 'No JSON'}; }
                    return {status: r.status, body};
                }""", url)

            # 4. Bucle para descargar los detalles usando los IDs del archivo capturado
            for i, s in enumerate(sources, 1):
                rid = str(s.get('id') or '')
                try:
                    result = await fetch('/api/nc-sim/source?kind=own&id=' + rid)
                    detail = result['body']
                    runs.append({**s, 'detalle': detail})
                    await asyncio.sleep(max(espera, 0))
                except Exception as e:
                    errors.append({'run_id': rid, 'error': str(e)})

            return runs, errors

        finally:
            if browser:
                await browser.close()


async def obtener_sources_iniciales(perfil_path):
    profile = Path(perfil_path).resolve()
    browser = None

    async with async_playwright() as p:
        try:
            # ¡AQUÍ FALTABA EL AWAIT!
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=True,
                viewport={'width': 1440, 'height': 900}
            )
            
            page = browser.pages[0] if browser.pages else await browser.new_page()
            
            # Navegamos al simulador para establecer las cookies
            await page.goto(BASE + '/nc-simulator', wait_until='domcontentloaded', timeout=90000)

            # Hacemos el fetch con la sesión activa
            resultado = await page.evaluate("""async () => {
                const r = await fetch('/api/nc-sim/sources', {
                    credentials: 'same-origin',
                    headers: {'Accept': 'application/json'}
                });
                if (!r.ok) {
                    throw new Error(`Error en la API: ${r.status}`);
                }
                return await r.json();
            }""")

            return unpack_sources(resultado)

        except Exception as e:
            raise Exception(f"No se pudieron obtener los sources iniciales: {str(e)}")
            
        finally:
            if browser:
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
            "La API devolvió una estructura inesperada."
        )

    accounts = resultado.get("accounts", [])

    if not isinstance(accounts, list):
        raise ValueError(
            "El campo 'accounts' no contiene una lista."
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