"""
Punto de entrada del .exe portable (AFK-Community.exe).

El .exe solo trae Python y las librerías. El código de la app (aplicacion/, navegador/, idiomas/) queda en
archivos .py al lado del .exe y se carga desde ahí, para que la actualización automática desde GitHub pueda
reemplazarlo. La app se conecta al sitio por HTTP: no necesita navegador.

También sirve sin compilar:  python lanzador.py
"""
import importlib
import os
import sys
from pathlib import Path

CONGELADO = getattr(sys, "frozen", False)
BASE = Path(sys.executable).resolve().parent if CONGELADO else Path(__file__).resolve().parent

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
    import keyring, keyring.backends.Windows, win32ctypes.pywin32.win32cred, win32ctypes.core  # noqa
    import openpyxl  # noqa

# El código de la app se busca primero junto al .exe
sys.path.insert(0, str(BASE))
os.chdir(BASE)


def _prueba():
    """AFK_PRUEBA=1: comprueba que el .exe carga la app y puede usar el llavero de Windows, y termina."""
    salida = BASE / "prueba_exe.txt"
    try:
        import keyring
        kr = keyring.get_keyring()
        if not type(kr).__module__.startswith("keyring.backends.Windows"):
            raise RuntimeError(f"llavero de Windows no disponible ({type(kr).__name__})")
        kr.get_password("AFK-Community-prueba", "nadie")   # lectura real (devuelve None)
        for modulo in ("aplicacion.ventana_principal", "navegador.sitio", "navegador.scraper", "navegador.cuenta",
                       "navegador.fractura", "navegador.actualizador"):
            importlib.import_module(modulo)
        salida.write_text(f"ok · llavero {type(kr).__name__}", encoding="utf-8")
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
