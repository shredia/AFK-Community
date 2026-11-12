"""
Conexión con esperianarchive.com por HTTP (sin navegador).

  - Login:   POST /api/auth/login {email, password} -> cookie de sesión (solo en memoria, mientras la app está abierta).
  - API:     las mismas peticiones que hace la página, con la cabecera X-Page (sin ella el sitio responde 409).
  - Si la sesión vence (401), vuelve a entrar sola con tu correo y la contraseña del llavero de Windows.
  - Tablas del sitio (jefes, equipo, afijos, colecciones...): se descarga el módulo GameVisuals-*.js y se leen
    sus datos con js_literales (no se ejecuta JavaScript).

La contraseña nunca se guarda en archivos: se lee del Administrador de credenciales de Windows.
"""
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path

from idiomas import tr

BASE = "https://esperianarchive.com"
SERVICIO_KEYRING = "EsperianArchive-NC"
ARCHIVO_CONFIG = "config_credenciales.json"
AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/131.0 Safari/537.36")
TIMEOUT = 90


class ErrorSitio(RuntimeError):
    def __init__(self, mensaje, status=0):
        super().__init__(mensaje)
        self.status = status


# ============================================================
# Credenciales
# ============================================================

def leer_credenciales(base_dir):
    """(correo, contraseña) guardados por 'Acceso al sitio' (config_credenciales.json + llavero)."""
    try:
        correo = json.loads((Path(base_dir) / ARCHIVO_CONFIG).read_text(encoding="utf-8")).get("correo") or ""
    except (OSError, json.JSONDecodeError):
        correo = ""
    password = ""
    if correo:
        try:
            import keyring
            password = keyring.get_password(SERVICIO_KEYRING, correo) or ""
        except Exception:
            password = ""
    return correo, password


# ============================================================
# Sesión
# ============================================================

class Sesion:
    """Cliente del sitio con cookies propias. Una por aplicación (ver sesion())."""

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.usuario = None
        self._candado = threading.Lock()

    # ---- bajo nivel
    def _pedir(self, metodo, ruta, cuerpo=None, x_page="/", timeout=TIMEOUT, binario=False):
        url = ruta if ruta.startswith("http") else BASE + ruta
        cabeceras = {"User-Agent": AGENTE, "Accept": "application/json" if not binario else "*/*",
                     "X-Page": x_page, "Origin": BASE, "Referer": BASE + x_page}
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode("utf-8")
            cabeceras["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)
        try:
            with self.opener.open(req, timeout=timeout) as r:
                contenido, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            contenido, status = e.read(), e.code
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            razon = getattr(e, "reason", e)
            return {"status": 0, "body": {"error": tr("Sin conexión con el sitio ({0}).", razon)}}
        if binario:
            return {"status": status, "body": contenido}
        try:
            cuerpo_resp = json.loads(contenido.decode("utf-8")) if contenido else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            cuerpo_resp = {"error": "No JSON"}
        return {"status": status, "body": cuerpo_resp}

    # ---- login
    def entrar(self, correo=None, password=None):
        """Inicia sesión. Sin argumentos usa las credenciales guardadas."""
        if not correo or not password:
            correo, password = leer_credenciales(self.base_dir)
        if not correo or not password:
            raise ErrorSitio(tr("Faltan tus credenciales: usa 'Acceso al sitio' para guardarlas."), 401)
        r = self._pedir("POST", "/api/auth/login", {"email": correo, "password": password}, x_page="/login")
        if r["status"] == 200 and isinstance(r["body"], dict):
            self.usuario = r["body"].get("user")
            return self.usuario
        if r["status"] == 0:
            raise ErrorSitio(r["body"]["error"], 0)
        detalle = (r["body"] or {}).get("error") if isinstance(r["body"], dict) else ""
        raise ErrorSitio(tr("No se pudo iniciar sesión: {0}", detalle or f"HTTP {r['status']}"), r["status"])

    def verificar(self, progreso=lambda m: None):
        """Comprueba la sesión (/api/auth/me); si no hay, entra con las credenciales guardadas."""
        with self._candado:
            r = self._pedir("GET", "/api/auth/me")
            if r["status"] == 200 and isinstance(r["body"], dict) and r["body"].get("user"):
                self.usuario = r["body"]["user"]
                return self.usuario
            if r["status"] == 0:
                raise ErrorSitio(r["body"]["error"], 0)
            progreso(tr("Iniciando sesión en esperianarchive.com..."))
            return self.entrar()

    # ---- API
    def json(self, ruta, x_page="/", timeout=TIMEOUT, metodo="GET", cuerpo=None):
        """{'status', 'body'} como lo devolvía el fetch del navegador. Reintenta una vez si la sesión venció."""
        r = self._pedir(metodo, ruta, cuerpo, x_page=x_page, timeout=timeout)
        if r["status"] == 401:
            self.entrar()
            r = self._pedir(metodo, ruta, cuerpo, x_page=x_page, timeout=timeout)
        return r

    def bytes(self, ruta, timeout=60):
        r = self._pedir("GET", ruta, x_page="/", timeout=timeout, binario=True)
        if r["status"] == 401:
            self.entrar()
            r = self._pedir("GET", ruta, x_page="/", timeout=timeout, binario=True)
        return r

    def texto_publico(self, ruta, timeout=60):
        r = self._pedir("GET", ruta, x_page="/", timeout=timeout, binario=True)
        if r["status"] != 200:
            raise ErrorSitio(tr("No se pudo leer {0} (HTTP {1}).", ruta, r["status"]), r["status"])
        return r["body"].decode("utf-8")

    def descargar(self, ruta, destino):
        """Guarda un archivo del sitio (imagen) en destino. Devuelve None o el texto del error."""
        r = self.bytes(ruta)
        if r["status"] != 200:
            return f"HTTP {r['status']}" if r["status"] else (r["body"] or b"").decode("utf-8", "ignore")[:80]
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(destino.name + ".tmp")
        temporal.write_bytes(r["body"])
        temporal.replace(destino)
        return None


_SESIONES = {}


def sesion(base_dir):
    """La sesión de la aplicación (se reutiliza entre ventanas mientras la app está abierta)."""
    clave = str(Path(base_dir).resolve())
    if clave not in _SESIONES:
        _SESIONES[clave] = Sesion(base_dir)
    return _SESIONES[clave]


def abrir_sesion(base_dir, progreso=lambda m: None):
    """Sesión verificada (entra sola si hace falta). Lanza ErrorSitio con un mensaje claro si no se puede."""
    s = sesion(base_dir)
    progreso(tr("Conectando a esperianarchive.com..."))
    s.verificar(progreso)
    progreso(tr("Sesión verificada ✓"))
    return s


# ============================================================
# Tablas del sitio (módulos JavaScript públicos, sin ejecutarlos)
# ============================================================

def modulos_del_sitio(s):
    """(texto de index-*.js, texto de GameVisuals-*.js) de la versión actual del sitio."""
    html = s.texto_publico("/nc-simulator")
    m = re.search(r'/assets/index-[\w-]+\.js', html)
    if not m:
        raise ErrorSitio(tr("No se encontró el módulo principal del sitio."))
    index = s.texto_publico(m.group(0))
    m = re.search(r'assets/GameVisuals-[\w-]+\.js', index)
    if not m:
        raise ErrorSitio(tr("No se encontró el módulo GameVisuals en la página."))
    return index, s.texto_publico("/" + m.group(0))


def recomendaciones_colecciones(index_js):
    """
    Guía de colecciones del sitio (la que muestra en Catálogo → Guides): dos listas de filas que el sitio
    convierte con sus funciones G1 e IS. Aquí se hace lo mismo en Python.
    """
    from .js_literales import leer_variables, _Lector
    m = re.search(r'=\[\.\.\.([\w$]+)\.map\(\(\w,\w\)=>([\w$]+)\(\w,"(\w+)",\w\)\),'
                  r'\.\.\.([\w$]+)\.map\(\(\w,\w\)=>\2\(\w,"(\w+)",\w\)\)\]', index_js)
    if not m:
        return []
    variables = leer_variables(index_js)
    listas = [(variables.get(m.group(1)) or [], m.group(3)), (variables.get(m.group(4)) or [], m.group(5))]
    # extras fijos dentro de la función (p. ej. heroModes para "Basic" fila 3)
    extras = {}
    inicio = index_js.find(f"function {m.group(2)}(")
    cuerpo = index_js[inicio:inicio + 3000] if inicio >= 0 else ""
    for e in re.finditer(r'\w==="(\w+)"&&\w===(\d+)\?(?=\{)', cuerpo):
        try:
            valor, _ = _Lector(cuerpo, variables).objeto(e.end())
            extras[(e.group(1), int(e.group(2)))] = valor
        except Exception:
            continue

    def requisitos(texto):
        salida = []
        for parte in str(texto).split(", "):
            r = re.match(r"^(.+?)(?: \((\d+)(?:-(\d+))?\))?$", parte)
            if not r:
                continue
            minimo = None if r.group(2) is None else int(r.group(2))
            salida.append({"stat": r.group(1), "min": minimo,
                           "max": None if r.group(2) is None else int(r.group(3) or r.group(2))})
        return salida

    salida = []
    for filas, grupo in listas:
        for u, fila in enumerate(filas):
            fila = list(fila) + [None] * (8 - len(fila))
            o, f, d, m_, y, g, x, s_ = fila[:8]
            rec = {"id": f"{grupo.lower()}-{u + 1}", "group": grupo, "collectionTid": o, "skillBonus": f,
                   "modes": str(d or "").split(" "), "primary": m_, "requirements": requisitos(m_),
                   "secondary": y, "heroTids": g, "notes": x}
            if s_ is not None:
                rec["audience"] = s_
            rec.update(extras.get((grupo, u)) or {})
            salida.append(rec)
    return salida
