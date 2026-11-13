"""
Construye lo que se publica en cada Release de GitHub. PyInstaller no compila para otro sistema: cada paquete se
genera en su sistema (el de Linux, en Linux, en WSL o en GitHub Actions: .github/workflows/linux.yml).

  Windows:
    dist/AFK-Community/                  la carpeta portable
    dist/AFK-Community-portable.zip      esa carpeta comprimida
    dist/AFK-Community-setup.exe         el instalador (si Inno Setup 6 está instalado)
        .venv\\Scripts\\python herramientas\\construir_exe.py  [--sin-zip] [--sin-instalador]

  Linux:
    dist/AFK-Community/                  la carpeta portable
    dist/AFK-Community-linux.tar.gz      esa carpeta comprimida (tar conserva el permiso de ejecución)
        python3 herramientas/construir_exe.py  [--sin-zip]

  Opciones para revisar que no se filtren datos tuyos (busca en la carpeta portable tus correos, ids de cuenta
  y nombres de personajes, sacados de tus cuentas):
    --cuentas <ruta>          dónde están tus cuentas, si no es datos_usuario/cuentas (p. ej. compilando en WSL:
                              /mnt/c/.../datos_usuario/cuentas)
    --sin-revision-personal   no buscar datos tuyos (en GitHub Actions: el código sale de git y no hay cuentas)

Los nombres no llevan la versión para que el enlace .../releases/latest/download/<archivo> del README
apunte siempre a la última. La versión va dentro del instalador y en el título del Release.

Carpeta portable (lo único que ve el usuario):
  AFK-Community.exe   el lanzador (en Linux: AFK-Community)
  app/                Python y librerías (PyInstaller) + el código en .py (se actualiza desde GitHub)
                      + los datos del usuario, que se crean al usarla
  README.md
NO lleva datos personales (cuentas, sesión, credenciales, descargas). La app se conecta por HTTP: no lleva navegador.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOMBRE = "AFK-Community"
WINDOWS = sys.platform == "win32"
EJECUTABLE = f"{NOMBRE}.exe" if WINDOWS else NOMBRE
DIST = RAIZ / "dist"
SALIDA = DIST / NOMBRE
CONTENIDO = "app"                     # carpeta junto al ejecutable con todo lo demás
APP = SALIDA / CONTENIDO
ZIP = DIST / f"{NOMBRE}-portable.zip"
TAR = DIST / f"{NOMBRE}-linux.tar.gz"
SETUP = DIST / f"{NOMBRE}-setup.exe"
CODIGO = ["aplicacion", "navegador", "idiomas", "recursos", "docs"]   # docs: imágenes del README
ARCHIVOS = ["main.py", "lanzador.py", "version.py", "requirements.txt"]
# Lo único que puede quedar arriba, junto al ejecutable
PERMITIDOS_ARRIBA = {EJECUTABLE, CONTENIDO, "README.md"}
# Lo que la app crea al usarse (la prueba del .exe puede crear alguno): se borra antes de empaquetar
DATOS_DE_USO = ["datos_usuario", "cuentas", "datos", "assets", "guias", "respaldos", "perfil_esperian", "preferencias.json",
                "config_credenciales.json", "game_accounts.json", "sources_guardados.json", "actualizacion.json",
                "api.txt", "prueba_exe.txt"]


def version():
    return re.search(r'VERSION\s*=\s*"([^"]+)"', (RAIZ / "version.py").read_text(encoding="utf-8")).group(1)


def icono():
    """Ícono del .exe a partir de una imagen del juego ya descargada (si existe)."""
    from PIL import Image
    destino = RAIZ / "build" / "icono.ico"
    destino.parent.mkdir(parents=True, exist_ok=True)
    for candidato in (RAIZ / "assets" / "game-ui" / "hero-screen" / "collection-1.webp",
                      RAIZ / "recursos" / "capturas" / "Cofre 3.png"):
        if candidato.exists():
            Image.open(candidato).convert("RGBA").save(destino, sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                                                                        (128, 128), (256, 256)])
            return destino
    return None


def limpiar_dist():
    """Borra la carpeta y los paquetes anteriores (también los de nombre con versión, de antes de la 1.2.0)."""
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    viejos = DIST.glob(f"{NOMBRE}-*portable.zip"), DIST.glob(f"{NOMBRE}-*setup.exe")
    if not WINDOWS:   # en Linux se rehace solo el .tar.gz: lo de Windows que haya en dist/ se deja
        viejos = (DIST.glob(f"{NOMBRE}-linux.tar.gz"),)
    for viejo in [p for grupo in viejos for p in grupo]:
        viejo.unlink()


def pyinstaller():
    llavero = ["--collect-submodules", "win32ctypes"] if WINDOWS else \
        ["--collect-submodules", "secretstorage", "--collect-submodules", "jeepney"]   # Secret Service (Linux)
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
            "--name", NOMBRE, "--distpath", str(DIST), "--workpath", str(RAIZ / "build"),
            "--specpath", str(RAIZ / "build"), "--contents-directory", CONTENIDO,
            # el código de la app NO va dentro del ejecutable: se carga desde los .py de app/
            "--exclude-module", "aplicacion", "--exclude-module", "navegador", "--exclude-module", "idiomas",
            "--collect-submodules", "keyring", *llavero,
            "--collect-submodules", "openpyxl", "--hidden-import", "PIL._tkinter_finder",
            str(RAIZ / "lanzador.py")]
    ico = icono() if WINDOWS else None   # en Linux el ícono lo pone el escritorio, no el ejecutable
    if ico:
        args[3:3] = ["--icon", str(ico)]
    print("PyInstaller…")
    subprocess.run(args, check=True, cwd=str(RAIZ))
    return {p.name for p in APP.iterdir()}   # lo que trae el runtime de Python


def archivos_del_codigo():
    """
    Los archivos de CODIGO que van en la app: lo que git sube (o subiría), nunca lo del .gitignore
    (p. ej. las Guías, que siguen en desarrollo y solo existen en tu PC).
    """
    r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", *CODIGO],
                       cwd=str(RAIZ), capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"⚠ No se pudo listar el código con git: {r.stderr.strip()}")
    return [RAIZ / p for p in r.stdout.splitlines() if (RAIZ / p).is_file()]


def copiar_codigo():
    print("Copiando el código…")
    for origen in archivos_del_codigo():
        destino = APP / origen.relative_to(RAIZ)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
    for archivo in ARCHIVOS:
        shutil.copy2(RAIZ / archivo, APP / archivo)
    # El README va arriba, junto al .exe: sus imágenes están en app/docs/
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    (SALIDA / "README.md").write_text(re.sub(r'(src|href)="docs/', rf'\1="{CONTENIDO}/docs/', texto), encoding="utf-8")


def limpiar_datos():
    """Borra lo que la app pudo crear al probarla (cuentas, preferencias...)."""
    for nombre in DATOS_DE_USO:
        for ruta in (APP / nombre, SALIDA / nombre):
            if ruta.is_dir():
                shutil.rmtree(ruta)
            elif ruta.exists():
                ruta.unlink()
    for carpeta in CODIGO:
        for cache in (APP / carpeta).rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
    shutil.rmtree(APP / "__pycache__", ignore_errors=True)


def _opcion(nombre):
    """Valor de una opción '--nombre valor' de la línea de comandos (o None)."""
    if nombre in sys.argv and sys.argv.index(nombre) + 1 < len(sys.argv):
        return sys.argv[sys.argv.index(nombre) + 1]
    return None


def _marcas_personales():
    """Textos que delatan datos tuyos: ids de cuenta, correos y nombres de personajes de tus cuentas (en este PC)."""
    marcas = set()
    if "--sin-revision-personal" in sys.argv:
        print("  (sin revisión de datos personales: --sin-revision-personal)")
        return marcas
    cuentas = Path(_opcion("--cuentas") or RAIZ / "datos_usuario" / "cuentas")
    if not cuentas.is_dir():
        sys.exit(f"⚠ No encuentro tus cuentas en {cuentas}: no se puede revisar que no se filtren datos tuyos. "
                 "Indica dónde están con --cuentas <ruta>.")
    for cuenta in cuentas.glob("*"):
        if cuenta.is_dir() and not cuenta.name.startswith("_") and len(cuenta.name) > 12:
            marcas.add(cuenta.name)
        ficha = cuenta / "account.json"
        try:
            datos = json.loads(ficha.read_text(encoding="utf-8")) if ficha.exists() else {}
        except (OSError, json.JSONDecodeError):
            datos = {}
        texto = json.dumps(datos, ensure_ascii=False)
        marcas.update(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", texto))
    for ficha in cuentas.glob("*/*/*.json"):
        if ficha.stem == ficha.parent.name:
            try:
                nombre = (json.loads(ficha.read_text(encoding="utf-8")) or {}).get("name")
            except (OSError, json.JSONDecodeError, AttributeError):
                nombre = None
            if nombre and len(nombre) >= 4:
                marcas.add(nombre)
    return marcas


def verificar_sin_datos(runtime):
    """Falla si en la carpeta portable hay algo que no sea la app (o algún dato tuyo dentro de los archivos)."""
    sobrantes = [p.name for p in SALIDA.iterdir() if p.name not in PERMITIDOS_ARRIBA]
    sobrantes += [f"{CONTENIDO}/{p.name}" for p in APP.iterdir() if p.name not in runtime | {*CODIGO, *ARCHIVOS}]
    marcas = _marcas_personales()
    revisar = [SALIDA / "README.md", *(APP / a for a in ARCHIVOS)]
    for carpeta in CODIGO:
        revisar += [r for r in (APP / carpeta).rglob("*") if r.suffix.lower() in (".py", ".json", ".txt", ".md")]
    encontrados = []
    for ruta in revisar:
        texto = ruta.read_text(encoding="utf-8", errors="ignore")
        if any(m in texto for m in marcas):
            encontrados.append(f"{ruta.relative_to(SALIDA)} (contiene un dato de tus cuentas)")
    print(f"Revisando que no haya datos personales… ({len(marcas)} marcas buscadas)")
    if sobrantes or encontrados:
        for s in sorted(sobrantes):
            print("  ✗ sobra:", s)
        for e in encontrados:
            print("  ✗", e)
        return False
    print("  ✓ solo la app: ningún dato tuyo")
    return True


def prueba():
    print(f"Probando {EJECUTABLE} (carga de la app y llavero del sistema)…")
    resultado = APP / "prueba_exe.txt"
    resultado.unlink(missing_ok=True)
    subprocess.run([str(SALIDA / EJECUTABLE)], env={**os.environ, "AFK_PRUEBA": "1"}, timeout=180)
    texto = resultado.read_text(encoding="utf-8") if resultado.exists() else "sin resultado"
    resultado.unlink(missing_ok=True)
    print("  →", texto)
    return texto.startswith("ok")


def comprimir():
    if not WINDOWS:   # .tar.gz: conserva el permiso de ejecución y los enlaces que deja PyInstaller
        print(f"Comprimiendo {TAR.name}…")
        with tarfile.open(TAR, "w:gz", compresslevel=6) as t:
            t.add(SALIDA, arcname=NOMBRE)
        return TAR
    print(f"Comprimiendo {ZIP.name}…")
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for ruta in SALIDA.rglob("*"):
            if ruta.is_file():
                z.write(ruta, Path(NOMBRE) / ruta.relative_to(SALIDA))
    return ZIP


def iscc():
    """Compilador de Inno Setup (ISCC.exe), si está instalado."""
    candidatos = [os.environ.get("ISCC"), shutil.which("iscc"),
                  Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
                  Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
                  Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe"]
    for c in candidatos:
        if c and Path(c).is_file():
            return Path(c)
    return None


def instalador():
    """AFK-Community-setup.exe con Inno Setup (herramientas/instalador.iss)."""
    compilador = iscc()
    if not compilador:
        print("⚠ Inno Setup no está instalado: no se genera el instalador (winget install JRSoftware.InnoSetup).")
        return None
    print("Generando el instalador (Inno Setup)…")
    args = [str(compilador), "/Q", f"/DAppVersion={version()}", f"/DSourceDir={SALIDA}", f"/DOutputDir={DIST}",
            f"/DOutputName={SETUP.stem}"]
    ico = RAIZ / "build" / "icono.ico"
    if ico.exists():
        args.append(f"/DIconFile={ico}")
    args.append(str(RAIZ / "herramientas" / "instalador.iss"))
    subprocess.run(args, check=True, cwd=str(RAIZ))
    return SETUP


if __name__ == "__main__":
    print(f"{NOMBRE} {version()}")
    limpiar_dist()
    runtime = pyinstaller()
    copiar_codigo()
    ok = prueba()
    limpiar_datos()
    if not verificar_sin_datos(runtime):
        sys.exit("⚠ La carpeta portable tiene algo que no es de la app: no se empaqueta.")
    if "--sin-zip" not in sys.argv:
        z = comprimir()
        print(f"✓ Listo: {SALIDA}  ·  {z.name} ({z.stat().st_size / 1e6:.0f} MB)")
    if ok and WINDOWS and "--sin-instalador" not in sys.argv:
        setup = instalador()
        if setup and setup.exists():
            print(f"✓ Instalador: {setup.name} ({setup.stat().st_size / 1e6:.0f} MB)")
    if not ok:
        sys.exit(f"⚠ La prueba de {EJECUTABLE} falló: revisa el mensaje de arriba.")
