# aplicacion/tema.py
"""Tema visual común de la app: oscuro tipo juego (azul noche + dorado)."""
import tkinter as tk
from tkinter import ttk

# ---------------- Paleta ----------------
FONDO = "#0f1624"        # fondo de ventanas
PANEL = "#172133"        # paneles / tarjetas
PANEL2 = "#1e2b42"       # paneles elevados, filas alternas
BORDE = "#2c3c58"
TEXTO = "#e9e4d6"        # texto principal (marfil)
MUTED = "#8f9bb3"        # texto secundario
DORADO = "#e3b45a"       # acento principal
DORADO_OSCURO = "#a87a2a"
OK = "#79d48a"
WARN = "#f2b84b"
ERR = "#ff7b7b"
INFO = "#78b6ff"
SELECCION = "#3a4f78"

FUENTE = ("Segoe UI", 10)
FUENTE_NEGRITA = ("Segoe UI", 10, "bold")
FUENTE_TITULO = ("Segoe UI Semibold", 18)
FUENTE_SUBTITULO = ("Segoe UI", 11)
FUENTE_MONO = ("Consolas", 10)

_aplicado = set()


def aplicar(root):
    """Aplica el tema a la ventana raíz (afecta a todas las ventanas de la app)."""
    root.configure(background=FONDO)

    # Widgets "clásicos" de tk (Label, Text, Listbox, Canvas, Toplevel...)
    for patron, valor in (
        ("*Background", FONDO), ("*background", FONDO),
        ("*Foreground", TEXTO), ("*foreground", TEXTO),
        ("*Toplevel.background", FONDO),
        ("*Label.background", FONDO), ("*Label.foreground", TEXTO),
        ("*Text.background", PANEL), ("*Text.foreground", TEXTO), ("*Text.insertBackground", DORADO),
        ("*Text.selectBackground", SELECCION), ("*Text.relief", "flat"), ("*Text.borderWidth", 0),
        ("*Listbox.background", PANEL), ("*Listbox.foreground", TEXTO),
        ("*Listbox.selectBackground", SELECCION), ("*Listbox.selectForeground", DORADO),
        ("*Listbox.relief", "flat"), ("*Listbox.borderWidth", 0), ("*Listbox.highlightThickness", 0),
        ("*Canvas.background", FONDO), ("*Canvas.highlightThickness", 0),
        ("*Entry.background", PANEL2), ("*Entry.foreground", TEXTO),
        ("*TCombobox*Listbox.background", PANEL2), ("*TCombobox*Listbox.foreground", TEXTO),
        ("*TCombobox*Listbox.selectBackground", SELECCION), ("*TCombobox*Listbox.selectForeground", DORADO),
    ):
        root.option_add(patron, valor)

    from tkinter import font as tkfont
    for nombre in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        try:
            tkfont.nametofont(nombre).configure(family="Segoe UI", size=10)
        except tk.TclError:
            pass
    estilo = ttk.Style(root)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    estilo.configure(".", background=FONDO, foreground=TEXTO, fieldbackground=PANEL2, bordercolor=BORDE,
                     darkcolor=PANEL, lightcolor=PANEL2, troughcolor=PANEL, focuscolor=DORADO,
                     selectbackground=SELECCION, selectforeground=DORADO, insertcolor=DORADO, font=FUENTE)
    estilo.configure("TFrame", background=FONDO)
    estilo.configure("Panel.TFrame", background=PANEL)
    estilo.configure("TLabel", background=FONDO, foreground=TEXTO)
    estilo.configure("Panel.TLabel", background=PANEL, foreground=TEXTO)
    estilo.configure("Muted.TLabel", background=FONDO, foreground=MUTED)
    estilo.configure("Titulo.TLabel", background=FONDO, foreground=DORADO, font=FUENTE_TITULO)

    estilo.configure("TLabelframe", background=FONDO, bordercolor=BORDE, relief="solid", borderwidth=1)
    estilo.configure("TLabelframe.Label", background=FONDO, foreground=DORADO, font=FUENTE_NEGRITA)

    # Botones
    estilo.configure("TButton", background=PANEL2, foreground=TEXTO, bordercolor=BORDE, focusthickness=0,
                     padding=(10, 5), relief="flat")
    estilo.map("TButton",
               background=[("disabled", PANEL), ("pressed", SELECCION), ("active", "#2a3a58")],
               foreground=[("disabled", "#5d6a82"), ("active", DORADO)],
               bordercolor=[("active", DORADO_OSCURO)])
    estilo.configure("Acento.TButton", background=DORADO_OSCURO, foreground="#1a1206", font=FUENTE_NEGRITA)
    estilo.map("Acento.TButton",
               background=[("disabled", PANEL), ("pressed", DORADO_OSCURO), ("active", DORADO)],
               foreground=[("disabled", "#5d6a82"), ("active", "#1a1206")])

    # Botones de alternancia (p. ej. Planilla / Datos)
    estilo.configure("Toolbutton", background=PANEL, foreground=MUTED, padding=(10, 5), relief="flat",
                     bordercolor=BORDE)
    estilo.map("Toolbutton", background=[("selected", DORADO_OSCURO), ("active", "#2a3a58")],
               foreground=[("selected", "#1a1206"), ("active", DORADO)])

    # Entradas
    for clase in ("TEntry", "TCombobox", "TSpinbox"):
        estilo.configure(clase, fieldbackground=PANEL2, foreground=TEXTO, background=PANEL2,
                         bordercolor=BORDE, arrowcolor=DORADO, insertcolor=DORADO, padding=3)
        estilo.map(clase, fieldbackground=[("readonly", PANEL2), ("disabled", PANEL)],
                   foreground=[("disabled", "#5d6a82")], bordercolor=[("focus", DORADO_OSCURO)])
    estilo.configure("TCheckbutton", background=FONDO, foreground=TEXTO, indicatorbackground=PANEL2,
                     indicatorforeground=DORADO)
    estilo.map("TCheckbutton", background=[("active", FONDO)], foreground=[("active", DORADO)],
               indicatorbackground=[("selected", DORADO_OSCURO)])

    # Pestañas
    estilo.configure("TNotebook", background=FONDO, bordercolor=BORDE, tabmargins=(2, 4, 2, 0))
    estilo.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(14, 6), bordercolor=BORDE)
    estilo.map("TNotebook.Tab", background=[("selected", PANEL2), ("active", "#22314c")],
               foreground=[("selected", DORADO), ("active", TEXTO)])

    # Tablas
    estilo.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXTO, bordercolor=BORDE,
                     rowheight=24)
    estilo.map("Treeview", background=[("selected", SELECCION)], foreground=[("selected", DORADO)])
    estilo.configure("Treeview.Heading", background=PANEL2, foreground=DORADO, bordercolor=BORDE,
                     font=FUENTE_NEGRITA, relief="flat", padding=(6, 4))
    estilo.map("Treeview.Heading", background=[("active", "#2a3a58")])
    estilo.configure("Cuenta.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXTO)

    # Otros
    estilo.configure("TScrollbar", background=PANEL2, troughcolor=FONDO, bordercolor=FONDO, arrowcolor=MUTED,
                     gripcount=0, relief="flat")
    estilo.map("TScrollbar", background=[("active", "#2f4264")])
    estilo.configure("TPanedwindow", background=FONDO)
    estilo.configure("Sash", sashthickness=6, background=BORDE)
    estilo.configure("TSeparator", background=BORDE)
    estilo.configure("Horizontal.TProgressbar", background=DORADO, troughcolor=PANEL, bordercolor=BORDE,
                     lightcolor=DORADO, darkcolor=DORADO_OSCURO)

    # Tarjetas del menú principal
    estilo.configure("Tarjeta.TFrame", background=PANEL, bordercolor=BORDE, relief="solid", borderwidth=1)
    estilo.configure("Tarjeta.TLabel", background=PANEL, foreground=TEXTO)
    estilo.configure("TarjetaTitulo.TLabel", background=PANEL, foreground=DORADO, font=("Segoe UI Semibold", 12))
    estilo.configure("TarjetaTexto.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
    estilo.configure("TarjetaPaso.TLabel", background=PANEL, foreground="#1a1206", font=("Segoe UI", 9, "bold"))
    _aplicado.add(str(root))


def estilo_texto(widget):
    """Colores para tk.Text creados antes de aplicar el tema."""
    widget.configure(background=PANEL, foreground=TEXTO, insertbackground=DORADO, relief="flat",
                     selectbackground=SELECCION, highlightthickness=0, padx=6, pady=4)
