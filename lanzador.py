"""
Punto de entrada del ejecutable portable (AFK-Community.exe en Windows, AFK-Community en Linux).

Carpeta portable:
    AFK-Community.exe   este lanzador (en Linux, AFK-Community)
    app/                Python y librerías (PyInstaller), el código en .py (aplicacion/, navegador/, idiomas/...)
                        y los datos del usuario (cuentas/, preferencias.json...)
    README.md
El código queda en .py y se carga desde app/, para que la actualización automática desde GitHub pueda
reemplazarlo. La app se conecta al sitio por HTTP: no necesita navegador.

También sirve sin compilar:  python lanzador.py
"""
import importlib
import os
import sys
from pathlib import Path

CONGELADO = getattr(sys, "frozen", False)
if CONGELADO:
    _JUNTO_AL_EXE = Path(sys.executable).resolve().parent
    # app/ (desde la 1.2.0); las portables anteriores tenían todo suelto junto al .exe
    BASE = _JUNTO_AL_EXE / "app" if (_JUNTO_AL_EXE / "app" / "aplicacion").is_dir() else _JUNTO_AL_EXE
else:
    BASE = Path(__file__).resolve().parent

if CONGELADO:
    # Las librerías que usa el código de la app tienen que quedar dentro del .exe: se importan aquí para que
    # PyInstaller las detecte (el código de la app se carga desde los .py, no desde el .exe).
    import argparse, ast, asyncio, base64, bisect, calendar, collections, concurrent.futures, contextlib, copy  # noqa
    import csv, dataclasses, datetime, decimal, difflib, email, enum, fnmatch, functools, glob, gzip, hashlib  # noqa
    import heapq, hmac, html, http.client, http.cookiejar, http.cookies, inspect, io, itertools, json, locale  # noqa
    import logging, math, mimetypes, operator, pathlib, pickle, platform, pprint, queue, random, re, secrets  # noqa
    import shlex, shutil, signal, socket, ssl, statistics, string, struct, subprocess, tempfile, textwrap  # noqa
    import threading, time, traceback, typing, unicodedata, urllib.error, urllib.parse, urllib.request, uuid  # noqa
    import webbrowser, xml.etree.ElementTree, zipfile, zlib  # noqa
    import tkinter, tkinter.ttk, tkinter.messagebox, tkinter.filedialog, tkinter.simpledialog, tkinter.font  # noqa
    import PIL.Image, PIL.ImageTk, PIL.ImageDraw, PIL.ImageFont, PIL.ImageOps, PIL.ImageFilter  # noqa
    import PIL.ImageEnhance, PIL.ImageChops, PIL.ImageStat, PIL.ImageGrab  # noqa
    import keyring  # noqa
    if sys.platform == "win32":
        import keyring.backends.Windows, win32ctypes.pywin32.win32cred, win32ctypes.core  # noqa
    else:   # Linux: el llavero del escritorio (GNOME Keyring / KWallet) por Secret Service
        try:
            import keyring.backends.SecretService, secretstorage, jeepney  # noqa
        except ImportError:
            pass
    import openpyxl  # noqa

# El código de la app se busca primero en app/ (o junto al .exe)
sys.path.insert(0, str(BASE))
os.chdir(BASE)


def _prueba():
    """AFK_PRUEBA=1: comprueba que el ejecutable carga la app y el llavero del sistema, y termina."""
    salida = BASE / "prueba_exe.txt"
    try:
        import keyring
        kr = keyring.get_keyring()
        llavero = type(kr).__name__
        if sys.platform == "win32":
            if not type(kr).__module__.startswith("keyring.backends.Windows"):
                raise RuntimeError(f"llavero de Windows no disponible ({llavero})")
            kr.get_password("AFK-Community-prueba", "nadie")   # lectura real (devuelve None)
        else:
            # en Linux el llavero depende del escritorio: solo lo usa el inicio de sesión del sitio (en desarrollo)
            # y el token de GitHub, así que si falta la app igual funciona
            try:
                kr.get_password("AFK-Community-prueba", "nadie")
            except Exception as error:  # noqa: BLE001
                llavero += f" (sin acceso: {error.__class__.__name__})"
        for modulo in ("aplicacion.ventana_principal", "navegador.sitio", "navegador.scraper", "navegador.cuenta",
                       "navegador.fractura", "navegador.actualizador", "navegador.importar",
                       "navegador.roster", "navegador.bloqueos", "aplicacion.optimizador_ajustes",
                       "aplicacion.seccion_progreso", "aplicacion.seccion_amigos"):
            importlib.import_module(modulo)
        salida.write_text(f"ok · llavero {llavero}", encoding="utf-8")
    except Exception as error:  # noqa: BLE001
        salida.write_text(f"error {error.__class__.__name__}: {error}", encoding="utf-8")


def principal():
    if os.environ.get("AFK_PRUEBA") == "1":
        _prueba()
        return
    ventana = importlib.import_module("aplicacion.ventana_principal")
    ventana.iniciar_aplicacion()


if __name__ == "__main__":
    principal()
