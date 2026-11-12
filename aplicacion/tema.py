# aplicacion/tema.py
"""Tema visual común de la app: oscuro neutro (grafito azulado) con acento dorado."""
import tkinter as tk
from tkinter import ttk

# ---------------- Paleta ----------------
FONDO = "#0d1118"        # fondo de ventanas / contenido
LATERAL = "#10151e"      # menú lateral
PANEL = "#151b26"        # tarjetas / paneles
PANEL2 = "#1c2433"       # paneles elevados, campos, filas alternas
HOVER = "#232d40"        # fondo al pasar el ratón
BORDE = "#273247"
TEXTO = "#e7e9ef"        # texto principal
MUTED = "#8a93a6"        # texto secundario
TENUE = "#5b6478"        # texto deshabilitado / muy secundario
DORADO = "#e9b949"       # acento principal
DORADO_OSCURO = "#b98a2c"
SOBRE_DORADO = "#1a1306"  # texto sobre botones dorados
OK = "#6fcf8f"
WARN = "#f0b44c"
ERR = "#f27272"
INFO = "#6aa8ff"
SELECCION = "#2a3852"

FAMILIA = "Segoe UI"
FUENTE = (FAMILIA, 10)
FUENTE_PEQUENA = (FAMILIA, 9)
FUENTE_NEGRITA = (FAMILIA, 10, "bold")
FUENTE_TITULO = ("Segoe UI Semibold", 18)
FUENTE_SECCION = ("Segoe UI Semibold", 13)
FUENTE_SUBTITULO = (FAMILIA, 11)
FUENTE_TOTAL = ("Segoe UI Semibold", 20)
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
            tkfont.nametofont(nombre).configure(family=FAMILIA, size=10)
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
    estilo.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=FUENTE_PEQUENA)
    estilo.configure("Muted.TLabel", background=FONDO, foreground=MUTED)
    estilo.configure("Pequeno.TLabel", background=FONDO, foreground=MUTED, font=FUENTE_PEQUENA)
    estilo.configure("Titulo.TLabel", background=FONDO, foreground=TEXTO, font=FUENTE_TITULO)
    estilo.configure("Seccion.TLabel", background=FONDO, foreground=TEXTO, font=FUENTE_SECCION)
    estilo.configure("Total.TLabel", background=FONDO, foreground=DORADO, font=FUENTE_TOTAL)
    estilo.configure("Etiqueta.TLabel", background=FONDO, foreground=MUTED, font=(FAMILIA, 8, "bold"))

    # Recuadros: borde fino y título discreto
    estilo.configure("TLabelframe", background=FONDO, bordercolor=BORDE, relief="solid", borderwidth=1)
    estilo.configure("TLabelframe.Label", background=FONDO, foreground=MUTED, font=(FAMILIA, 9, "bold"))

    # Botones
    estilo.configure("TButton", background=PANEL2, foreground=TEXTO, bordercolor=BORDE, focusthickness=0,
                     padding=(12, 6), relief="flat", lightcolor=PANEL2, darkcolor=PANEL2)
    estilo.map("TButton",
               background=[("disabled", PANEL), ("pressed", SELECCION), ("active", HOVER)],
               foreground=[("disabled", TENUE), ("active", DORADO)],
               bordercolor=[("active", DORADO_OSCURO)],
               lightcolor=[("active", HOVER)], darkcolor=[("active", HOVER)])
    estilo.configure("Acento.TButton", background=DORADO, foreground=SOBRE_DORADO, font=FUENTE_NEGRITA,
                     bordercolor=DORADO, lightcolor=DORADO, darkcolor=DORADO, padding=(16, 7))
    estilo.map("Acento.TButton",
               background=[("disabled", PANEL), ("pressed", DORADO_OSCURO), ("active", "#f3c962")],
               foreground=[("disabled", TENUE), ("active", SOBRE_DORADO)],
               bordercolor=[("disabled", BORDE), ("active", "#f3c962")],
               lightcolor=[("active", "#f3c962")], darkcolor=[("active", "#f3c962")])
    # Botón sin fondo (acciones secundarias, '✕', enlaces)
    estilo.configure("Plano.TButton", background=FONDO, foreground=MUTED, bordercolor=FONDO,
                     lightcolor=FONDO, darkcolor=FONDO, padding=(6, 4))
    estilo.map("Plano.TButton", background=[("active", HOVER)], foreground=[("active", DORADO)],
               bordercolor=[("active", HOVER)], lightcolor=[("active", HOVER)], darkcolor=[("active", HOVER)])

    # Botones de alternancia (p. ej. Planilla / Datos)
    estilo.configure("Toolbutton", background=PANEL, foreground=MUTED, padding=(12, 6), relief="flat",
                     bordercolor=BORDE)
    estilo.map("Toolbutton", background=[("selected", SELECCION), ("active", HOVER)],
               foreground=[("selected", DORADO), ("active", TEXTO)])

    # Menú lateral
    estilo.configure("Lateral.TFrame", background=LATERAL)
    estilo.configure("Lateral.TLabel", background=LATERAL, foreground=TEXTO)
    estilo.configure("LateralMuted.TLabel", background=LATERAL, foreground=MUTED, font=FUENTE_PEQUENA)
    estilo.configure("LateralTitulo.TLabel", background=LATERAL, foreground=DORADO, font=("Segoe UI Semibold", 15))
    estilo.configure("LateralGrupo.TLabel", background=LATERAL, foreground=TENUE, font=(FAMILIA, 8, "bold"))
    estilo.configure("Nav.Toolbutton", background=LATERAL, foreground=MUTED, anchor="w", padding=(16, 8),
                     font=(FAMILIA, 10), bordercolor=LATERAL, lightcolor=LATERAL, darkcolor=LATERAL)
    estilo.map("Nav.Toolbutton",
               background=[("selected", PANEL2), ("active", HOVER)],
               foreground=[("disabled", TENUE), ("selected", DORADO), ("active", TEXTO)],
               bordercolor=[("selected", PANEL2), ("active", HOVER)],
               lightcolor=[("selected", PANEL2), ("active", HOVER)],
               darkcolor=[("selected", PANEL2), ("active", HOVER)])

    # Entradas
    for clase in ("TEntry", "TCombobox", "TSpinbox"):
        estilo.configure(clase, fieldbackground=PANEL2, foreground=TEXTO, background=PANEL2,
                         bordercolor=BORDE, arrowcolor=DORADO, insertcolor=DORADO, padding=4,
                         lightcolor=PANEL2, darkcolor=PANEL2)
        estilo.map(clase, fieldbackground=[("readonly", PANEL2), ("disabled", PANEL)],
                   foreground=[("disabled", TENUE)], bordercolor=[("focus", DORADO_OSCURO)],
                   lightcolor=[("focus", PANEL2)], darkcolor=[("focus", PANEL2)])
    for clase, fondo in (("TCheckbutton", FONDO), ("TRadiobutton", FONDO),
                         ("Panel.TCheckbutton", PANEL), ("Panel.TRadiobutton", PANEL)):
        estilo.configure(clase, background=fondo, foreground=TEXTO, indicatorbackground=PANEL2,
                         indicatorforeground=SOBRE_DORADO, indicatormargin=(0, 0, 6, 0))
        estilo.map(clase, background=[("active", fondo)], foreground=[("disabled", TENUE), ("active", DORADO)],
                   indicatorbackground=[("selected", DORADO), ("active", HOVER)])

    # Pestañas
    estilo.configure("TNotebook", background=FONDO, bordercolor=BORDE, tabmargins=(0, 4, 0, 0))
    estilo.configure("TNotebook.Tab", background=FONDO, foreground=MUTED, padding=(14, 7), bordercolor=BORDE,
                     lightcolor=FONDO)
    estilo.map("TNotebook.Tab", background=[("selected", PANEL), ("active", HOVER)],
               foreground=[("selected", DORADO), ("active", TEXTO)],
               lightcolor=[("selected", DORADO)])

    # Tablas
    estilo.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXTO, bordercolor=BORDE,
                     rowheight=26, lightcolor=PANEL, darkcolor=PANEL)
    estilo.map("Treeview", background=[("selected", SELECCION)], foreground=[("selected", DORADO)])
    estilo.configure("Treeview.Heading", background=PANEL2, foreground=MUTED, bordercolor=BORDE,
                     font=(FAMILIA, 9, "bold"), relief="flat", padding=(6, 5), lightcolor=PANEL2, darkcolor=PANEL2)
    estilo.map("Treeview.Heading", background=[("active", HOVER)], foreground=[("active", DORADO)])
    estilo.configure("Cuenta.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXTO)

    # Otros
    estilo.configure("TScrollbar", background=PANEL2, troughcolor=FONDO, bordercolor=FONDO, arrowcolor=MUTED,
                     gripcount=0, relief="flat", lightcolor=PANEL2, darkcolor=PANEL2)
    estilo.map("TScrollbar", background=[("active", HOVER)])
    estilo.configure("TPanedwindow", background=FONDO)
    estilo.configure("Sash", sashthickness=6, background=BORDE)
    estilo.configure("TSeparator", background=BORDE)
    estilo.configure("Horizontal.TProgressbar", background=DORADO, troughcolor=PANEL, bordercolor=BORDE,
                     lightcolor=DORADO, darkcolor=DORADO_OSCURO)

    # Tarjetas
    estilo.configure("Tarjeta.TFrame", background=PANEL, bordercolor=BORDE, relief="solid", borderwidth=1)
    estilo.configure("Tarjeta.TLabel", background=PANEL, foreground=TEXTO)
    estilo.configure("TarjetaTitulo.TLabel", background=PANEL, foreground=TEXTO, font=("Segoe UI Semibold", 12))
    estilo.configure("TarjetaTexto.TLabel", background=PANEL, foreground=MUTED, font=FUENTE_PEQUENA)
    estilo.configure("TarjetaTiempo.TLabel", background=PANEL, foreground=DORADO, font=("Segoe UI Semibold", 14))
    estilo.configure("TarjetaPaso.TLabel", background=PANEL, foreground=SOBRE_DORADO, font=(FAMILIA, 9, "bold"))
    estilo.configure("Tarjeta.TLabelframe", background=PANEL, bordercolor=BORDE, relief="solid", borderwidth=1)
    estilo.configure("Tarjeta.TLabelframe.Label", background=PANEL, foreground=MUTED, font=(FAMILIA, 9, "bold"))
    estilo.configure("Tarjeta.TCheckbutton", background=PANEL, foreground=TEXTO, indicatorbackground=PANEL2)
    estilo.map("Tarjeta.TCheckbutton", background=[("active", PANEL)], foreground=[("active", DORADO)],
               indicatorbackground=[("selected", DORADO)])
    _aplicado.add(str(root))


def estilo_texto(widget):
    """Colores para tk.Text creados antes de aplicar el tema."""
    widget.configure(background=PANEL, foreground=TEXTO, insertbackground=DORADO, relief="flat",
                     selectbackground=SELECCION, highlightthickness=0, padx=6, pady=4)


class Chip(tk.Frame):
    """Etiqueta redondeada-ish con texto y un '✕' opcional (bloqueos y filtros activos)."""

    def __init__(self, padre, texto, al_quitar=None, al_clic=None, color=TEXTO, fondo=PANEL2):
        super().__init__(padre, background=fondo, highlightthickness=1, highlightbackground=BORDE)
        self._fondo = fondo
        lbl = tk.Label(self, text=texto, background=fondo, foreground=color, font=FUENTE_PEQUENA, padx=8, pady=2)
        lbl.pack(side="left")
        partes = [self, lbl]
        if al_quitar:
            x = tk.Label(self, text="✕", background=fondo, foreground=MUTED, font=FUENTE_PEQUENA, padx=4,
                         cursor="hand2")
            x.pack(side="left")
            x.bind("<Button-1>", lambda e: al_quitar())
            x.bind("<Enter>", lambda e: x.configure(foreground=ERR))
            x.bind("<Leave>", lambda e: x.configure(foreground=MUTED))
        if al_clic:
            for w in partes:
                w.configure(cursor="hand2")
                w.bind("<Button-1>", lambda e: al_clic())
        for w in partes:
            w.bind("<Enter>", lambda e: self._pintar(HOVER), add="+")
            w.bind("<Leave>", lambda e: self._pintar(self._fondo), add="+")

    def _pintar(self, color):
        try:
            self.configure(background=color)
            for w in self.winfo_children():
                w.configure(background=color)
        except tk.TclError:
            pass


def ventana(padre, titulo=None, tamano=None, minimo=None):
    """
    Toplevel normal, o una 'sección' incrustada si `padre` es un AnfitrionSeccion del menú lateral.
    Las ventanas principales (cuenta, runs, optimizador…) la usan en vez de tk.Toplevel.
    """
    if isinstance(padre, AnfitrionSeccion):
        return padre.crear_seccion()
    top = tk.Toplevel(padre)
    if titulo:
        top.title(titulo)
    if tamano:
        top.geometry(tamano)
    if minimo:
        top.minsize(*minimo)
    return top


class AnfitrionSeccion(ttk.Frame):
    """Hueco del contenido principal donde se incrusta una ventana (al cerrarla, avisa al menú)."""

    def __init__(self, padre, al_cerrar=None):
        super().__init__(padre)
        self.al_cerrar = al_cerrar
        self.seccion = None

    def crear_seccion(self):
        self.seccion = Seccion(self)
        self.seccion.pack(fill="both", expand=True)
        self.seccion.bind("<Destroy>", self._destruida, add="+")
        return self.seccion

    def _destruida(self, evento):
        if evento.widget is self.seccion:
            self.seccion = None
            if self.al_cerrar:
                self.after_idle(self.al_cerrar)


class Seccion(ttk.Frame):
    """Frame que acepta las llamadas de Toplevel que usan las ventanas (sin efecto al estar incrustado)."""
    incrustada = True

    def title(self, *a, **k):
        return ""

    def geometry(self, *a, **k):
        return ""

    def minsize(self, *a, **k):
        pass

    def maxsize(self, *a, **k):
        pass

    def resizable(self, *a, **k):
        pass

    def protocol(self, *a, **k):
        pass

    def transient(self, *a, **k):
        pass

    def grab_set(self, *a, **k):
        pass

    def grab_release(self, *a, **k):
        pass

    def lift(self, *a, **k):
        pass

    def focus_force(self, *a, **k):
        pass

    def attributes(self, *a, **k):
        pass

    def state(self, *a, **k):
        return "normal"

    def withdraw(self):
        pass

    def deiconify(self):
        pass

    wm_title = title
    wm_geometry = geometry
