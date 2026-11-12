"""
Construye la versión portable:  dist/AFK-Community/AFK-Community.exe  (+ un .zip para compartir).

    .venv\\Scripts\\python herramientas\\construir_exe.py

La carpeta resultante NO lleva datos personales (cuentas, sesión, credenciales, descargas): se crean al usarla.
Contenido:
  AFK-Community.exe        Python + librerías (PyInstaller)
  _internal/               runtime de Python
  aplicacion/ navegador/ idiomas/ recursos/ version.py ...   el código, en .py (se actualiza desde GitHub)
La app se conecta al sitio por HTTP: no lleva navegador.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOMBRE = "AFK-Community"
DIST = RAIZ / "dist"
SALIDA = DIST / NOMBRE
CODIGO = ["aplicacion", "navegador", "idiomas", "recursos"]
ARCHIVOS = ["main.py", "lanzador.py", "version.py", "requirements.txt"]


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


def pyinstaller():
    ico = icono()
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
            "--name", NOMBRE, "--distpath", str(DIST), "--workpath", str(RAIZ / "build"),
            "--specpath", str(RAIZ / "build"),
            # el código de la app NO va dentro del .exe: se carga desde los .py de al lado
            "--exclude-module", "aplicacion", "--exclude-module", "navegador", "--exclude-module", "idiomas",
            "--collect-submodules", "keyring", "--collect-submodules", "win32ctypes",
            "--collect-submodules", "openpyxl", "--hidden-import", "PIL._tkinter_finder",
            str(RAIZ / "lanzador.py")]
    if ico:
        args[3:3] = ["--icon", str(ico)]
    print("PyInstaller…")
    subprocess.run(args, check=True, cwd=str(RAIZ))


def copiar_codigo():
    print("Copiando el código…")
    for carpeta in CODIGO:
        shutil.copytree(RAIZ / carpeta, SALIDA / carpeta, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for archivo in ARCHIVOS:
        shutil.copy2(RAIZ / archivo, SALIDA / archivo)


def leeme():
    (SALIDA / "LEEME.txt").write_text(
        f"{NOMBRE} {version()} — versión portable\n\n"
        "• Abre AFK-Community.exe. No hace falta instalar nada.\n"
        "• Tus datos (cuentas, sesión, imágenes, guías) se guardan dentro de esta carpeta.\n"
        "  Para llevarte la app a otro PC, copia la carpeta completa.\n"
        "• La contraseña de Esperian se guarda en el Administrador de credenciales de Windows\n"
        "  (no viaja con la carpeta): en otro PC vuelve a escribirla en «Acceso al sitio».\n"
        "• Actualizaciones: la app avisa sola cuando hay una versión nueva en GitHub\n"
        "  (botón ⟳ abajo a la derecha).\n", encoding="utf-8")


def prueba():
    print("Probando el .exe (carga de la app y llavero de Windows)…")
    resultado = SALIDA / "prueba_exe.txt"
    resultado.unlink(missing_ok=True)
    subprocess.run([str(SALIDA / f"{NOMBRE}.exe")], env={**os.environ, "AFK_PRUEBA": "1"}, timeout=180)
    texto = resultado.read_text(encoding="utf-8") if resultado.exists() else "sin resultado"
    resultado.unlink(missing_ok=True)
    print("  →", texto)
    return texto.startswith("ok")


def comprimir():
    archivo = DIST / f"{NOMBRE}-v{version()}-portable.zip"
    print(f"Comprimiendo {archivo.name}…")
    with zipfile.ZipFile(archivo, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for ruta in SALIDA.rglob("*"):
            if ruta.is_file():
                z.write(ruta, Path(NOMBRE) / ruta.relative_to(SALIDA))
    return archivo


if __name__ == "__main__":
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    pyinstaller()
    copiar_codigo()
    leeme()
    ok = prueba()
    if "--sin-zip" not in sys.argv:
        z = comprimir()
        print(f"✓ Listo: {SALIDA}  ·  {z.name} ({z.stat().st_size / 1e6:.0f} MB)")
    if not ok:
        sys.exit("⚠ La prueba del .exe falló: revisa el mensaje de arriba.")
