"""
Actualización automática desde GitHub (shredia/AFK-Community).

  - Solo se actualiza con VERSIONES PUBLICADAS: etiquetas vX.Y.Z (tags) del repositorio.
  - Repositorio público: no hace falta nada. Si fuera privado, se usa un token de solo lectura guardado
    en el llavero de Windows (nunca en un archivo).
  - Se reemplaza solo el código. Tus datos (datos_usuario/: cuentas, assets, credenciales, preferencias...)
    no se tocan.
  - Antes de reemplazar, se guarda una copia del código actual en datos_usuario/respaldos/<versión>/.
  - Si la carpeta es tu copia de desarrollo (tiene .git), no se sobrescribe: ahí se usa git pull.

Publicar una versión (desde la carpeta de desarrollo):
    python -m navegador.actualizador publicar 1.2.0
  (actualiza version.py, hace commit, crea la etiqueta v1.2.0 y la sube a GitHub)
"""
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = "shredia/AFK-Community"
API = f"https://api.github.com/repos/{REPO}"
SERVICIO_TOKEN = "AFK-Community-GitHub"
SERVICIO_TOKEN_ANTIGUO = "NC-GitHub"   # nombre anterior del repositorio
USUARIO_TOKEN = "token"
AGENTE = "nc-actualizador"
ARCHIVO_ESTADO = "actualizacion.json"
HORAS_ENTRE_REVISIONES = 12

# Lo que nunca se sobrescribe ni se borra (datos del usuario)
PROTEGIDOS = {"datos_usuario",
              # ubicación antigua de los datos (hasta la 1.2.0)
              "cuentas", "perfil_esperian", "assets", "guias", "datos", "respaldos", ".venv", "node_modules",
              ".git", "config_credenciales.json", "game_accounts.json", "sources_guardados.json",
              "preferencias.json", ARCHIVO_ESTADO, "api.txt",
              # versión portable (.exe): runtime de Python y navegador empaquetados
              "_internal", "navegadores", "AFK-Community.exe", "dist", "build", "herramientas"}

RAIZ = Path(__file__).resolve().parent.parent
# True dentro del .exe portable (PyInstaller): no hay pip ni main.py que ejecutar con Python
CONGELADO = getattr(sys, "frozen", False)


class ErrorActualizacion(Exception):
    pass


# ---------------- versión ----------------

def version_local():
    try:
        texto = (RAIZ / "version.py").read_text(encoding="utf-8")
        return re.search(r'VERSION\s*=\s*"([^"]+)"', texto).group(1)
    except (OSError, AttributeError):
        return "0.0.0"


def _tupla(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) + (0,) * (3 - len(re.findall(r"\d+", str(v))[:3]))


def es_mas_nueva(remota, local):
    return _tupla(remota) > _tupla(local)


def es_copia_desarrollo():
    return (RAIZ / ".git").exists()


# ---------------- token ----------------

def leer_token():
    try:
        import keyring
        return (keyring.get_password(SERVICIO_TOKEN, USUARIO_TOKEN)
                or keyring.get_password(SERVICIO_TOKEN_ANTIGUO, USUARIO_TOKEN))
    except Exception:
        return None


def guardar_token(token):
    import keyring
    if token:
        keyring.set_password(SERVICIO_TOKEN, USUARIO_TOKEN, token.strip())
    else:
        try:
            keyring.delete_password(SERVICIO_TOKEN, USUARIO_TOKEN)
        except Exception:
            pass


# ---------------- GitHub ----------------

def _pedir(url, token, binario=False, timeout=20):
    cabeceras = {"User-Agent": AGENTE, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:   # solo hace falta si el repositorio es privado
        cabeceras["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=cabeceras)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            datos = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ErrorActualizacion("GitHub rechazó el token (revisa que tenga acceso de lectura a shredia/AFK-Community).")
        if e.code == 403:
            raise ErrorActualizacion("GitHub limitó las consultas por ahora; inténtalo más tarde.")
        if e.code == 404:
            raise ErrorActualizacion("No se encontró el repositorio shredia/AFK-Community (si es privado, agrega un token).")
        raise ErrorActualizacion(f"GitHub respondió {e.code}.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErrorActualizacion(f"Sin conexión con GitHub ({e.__class__.__name__}).")
    return datos if binario else json.loads(datos.decode("utf-8"))


def ultima_version(token=None):
    """{'version', 'tag', 'notas'} de la etiqueta vX.Y.Z más alta (o None si no hay ninguna)."""
    token = token or leer_token()
    etiquetas = _pedir(f"{API}/tags?per_page=100", token)
    versiones = [t["name"] for t in etiquetas if re.fullmatch(r"v?\d+(\.\d+){0,2}", t.get("name", ""))]
    if not versiones:
        return None
    tag = max(versiones, key=_tupla)
    notas = ""
    try:  # si además hay un "release" con notas, se muestran
        notas = (_pedir(f"{API}/releases/tags/{tag}", token) or {}).get("body") or ""
    except ErrorActualizacion:
        pass
    return {"version": tag.lstrip("v"), "tag": tag, "notas": notas}


def revisar(base_dir, forzar=False):
    """Revisa si hay versión nueva (como mucho cada 12 h salvo forzar). Devuelve la info o None."""
    archivo = Path(base_dir) / ARCHIVO_ESTADO
    try:
        estado = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        estado = {}
    if not forzar and time.time() - estado.get("revisado", 0) < HORAS_ENTRE_REVISIONES * 3600:
        info = estado.get("ultima")
    else:
        info = ultima_version()
        estado.update({"revisado": time.time(), "ultima": info})
        archivo.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    if info and es_mas_nueva(info["version"], version_local()):
        return info
    return None


# ---------------- aplicar ----------------

def _protegido(relativa):
    primera = relativa.parts[0] if relativa.parts else ""
    return primera in PROTEGIDOS or relativa.name == "__pycache__" or "__pycache__" in relativa.parts


def aplicar(info, progreso=print):
    """Descarga la versión, respalda el código actual y lo reemplaza. Devuelve True si cambió requirements.txt."""
    if es_copia_desarrollo():
        raise ErrorActualizacion("Esta carpeta es tu copia de desarrollo (tiene .git): actualízala con git pull.")
    token = leer_token()
    progreso(f"Descargando {info['tag']}…")
    datos = _pedir(f"{API}/zipball/{info['tag']}", token, binario=True, timeout=120)
    zf = zipfile.ZipFile(io.BytesIO(datos))
    nombres = [n for n in zf.namelist() if not n.endswith("/")]
    prefijo = nombres[0].split("/")[0] + "/"
    archivos = {}
    for n in nombres:
        rel = Path(n[len(prefijo):])
        if rel.parts and not _protegido(rel):
            archivos[rel] = zf.read(n)
    if not any(r.as_posix() == "main.py" for r in archivos):
        raise ErrorActualizacion("El paquete descargado no parece la aplicación (falta main.py).")

    # respaldo del código actual
    respaldo = RAIZ / "datos_usuario" / "respaldos" / f"v{version_local()}_{time.strftime('%Y%m%d_%H%M%S')}"
    progreso(f"Respaldando el código actual en {respaldo.relative_to(RAIZ)}…")
    for rel in archivos:
        actual = RAIZ / rel
        if actual.is_file():
            destino = respaldo / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(actual, destino)
    req_antes = (RAIZ / "requirements.txt").read_bytes() if (RAIZ / "requirements.txt").exists() else b""

    progreso(f"Instalando {len(archivos)} archivos…")
    for rel, contenido in archivos.items():
        destino = RAIZ / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + ".nuevo")
        tmp.write_bytes(contenido)
        tmp.replace(destino)

    cambio_req = archivos.get(Path("requirements.txt"), req_antes) != req_antes
    if cambio_req and CONGELADO:
        progreso("⚠ Esta versión usa librerías nuevas: descarga e instala también el instalador (o el .zip portable) más reciente.")
    elif cambio_req:
        progreso("Instalando librerías nuevas (requirements.txt)…")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            ultima = ((r.stderr or "").strip().splitlines() or ["pip terminó con error"])[-1]
            progreso("⚠ No se pudieron instalar algunas librerías: " + ultima)
    progreso(f"✓ Actualizada a la versión {info['version']}. Reinicia la aplicación.")
    return cambio_req


def reiniciar():
    """Vuelve a abrir la aplicación en un proceso nuevo (el .exe portable o main.py)."""
    if CONGELADO:
        subprocess.Popen([sys.executable], cwd=str(RAIZ))
    else:
        subprocess.Popen([sys.executable, str(RAIZ / "main.py")], cwd=str(RAIZ))


# ---------------- publicar (copia de desarrollo) ----------------

def publicar(version):
    """Sube una versión: version.py + commit + etiqueta vX.Y.Z + push."""
    if not es_copia_desarrollo():
        raise SystemExit("Solo se publica desde la carpeta de desarrollo (con .git).")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("La versión debe ser X.Y.Z, por ejemplo 1.2.0")
    if not es_mas_nueva(version, version_local()):
        raise SystemExit(f"La versión {version} no es mayor que la actual ({version_local()}).")
    (RAIZ / "version.py").write_text(f'"""Versión de la aplicación (la usa el actualizador)."""\nVERSION = "{version}"\n',
                                     encoding="utf-8")

    def git(*args):
        r = subprocess.run(["git", *args], cwd=str(RAIZ), capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"git {' '.join(args)} falló:\n{r.stderr.strip()}")
        return r.stdout.strip()
    git("add", "-A")
    git("commit", "-m", f"Versión {version}")
    git("tag", f"v{version}")
    git("push")
    git("push", "origin", f"v{version}")
    print(f"✓ Publicada la versión {version}. Las aplicaciones instaladas la verán al revisar actualizaciones.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "publicar":
        publicar(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "revisar":
        print("Local:", version_local(), "· última publicada:", ultima_version())
    else:
        print("Uso: python -m navegador.actualizador publicar X.Y.Z  |  revisar")
