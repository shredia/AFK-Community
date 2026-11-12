"""
Lee DATOS (no código) de un módulo JavaScript minificado del sitio, sin ejecutarlo.

Reconoce declaraciones de la forma  nombre=<literal>  donde el literal es un objeto, un arreglo o
JSON.parse(`...`), con strings, números, true/false (!0/!1), null, void 0 y referencias a otras variables
ya leídas. Lo que no sea un literal (funciones, llamadas, operaciones) se ignora.

    variables = leer_variables(texto_js)   ->  {"C": {...}, "ie": {...}, ...}
"""
import json
import re

_INICIO = re.compile(r"(?:(?<=[\s,;{(])|^)([A-Za-z_$][\w$]*)=(?=[{\[]|JSON\.parse\(|`|\"|'|-?\d|!\d)")
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_NUM = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)")


class NoEsLiteral(Exception):
    pass


class _Lector:
    def __init__(self, texto, variables):
        self.t = texto
        self.v = variables

    def espacios(self, i):
        t = self.t
        while i < len(t) and t[i] in " \t\r\n":
            i += 1
        return i

    def valor(self, i):
        i = self.espacios(i)
        t = self.t
        if i >= len(t):
            raise NoEsLiteral
        c = t[i]
        if c == "{":
            return self.objeto(i)
        if c == "[":
            return self.arreglo(i)
        if c in "\"'":
            return self.cadena(i)
        if c == "`":
            return self.plantilla(i)
        if t.startswith("JSON.parse(", i):
            texto, j = self.valor(i + len("JSON.parse("))
            j = self.espacios(j)
            if j >= len(t) or t[j] != ")" or not isinstance(texto, str):
                raise NoEsLiteral
            try:
                return json.loads(texto), j + 1
            except json.JSONDecodeError:
                raise NoEsLiteral
        if t.startswith("!0", i):
            return True, i + 2
        if t.startswith("!1", i):
            return False, i + 2
        if t.startswith("void 0", i):
            return None, i + 6
        m = _NUM.match(t, i)
        if m and (c.isdigit() or c in "-."):
            texto = m.group(0)
            numero = int(texto, 16) if texto.lower().startswith(("0x", "-0x")) else float(texto)
            return (int(numero) if isinstance(numero, float) and numero.is_integer() and "." not in texto
                    and "e" not in texto.lower() else numero), m.end()
        m = _IDENT.match(t, i)
        if m:
            nombre = m.group(0)
            fin = self.espacios(m.end())
            # una llamada, acceso o operación no es un literal
            if fin < len(t) and (t[fin] in "(.[?+*/%<>=&|" or (t[fin] == "-" and t[fin + 1:fin + 2] != ">")):
                raise NoEsLiteral
            if nombre == "true":
                return True, m.end()
            if nombre == "false":
                return False, m.end()
            if nombre == "null" or nombre == "undefined":
                return None, m.end()
            if nombre in self.v:
                return self.v[nombre], m.end()
            raise NoEsLiteral
        raise NoEsLiteral

    def cadena(self, i):
        t, comilla = self.t, self.t[i]
        j, partes = i + 1, []
        while j < len(t):
            c = t[j]
            if c == "\\":
                partes.append(self._escape(j))
                j += self._largo_escape(j)
                continue
            if c == comilla:
                return "".join(partes), j + 1
            partes.append(c)
            j += 1
        raise NoEsLiteral

    def plantilla(self, i):
        t = self.t
        j, partes = i + 1, []
        while j < len(t):
            c = t[j]
            if c == "\\":
                partes.append(self._escape(j))
                j += self._largo_escape(j)
                continue
            if c == "$" and t.startswith("${", j):
                raise NoEsLiteral    # plantilla con expresiones: no es un dato fijo
            if c == "`":
                return "".join(partes), j + 1
            partes.append(c)
            j += 1
        raise NoEsLiteral

    def _escape(self, j):
        c = self.t[j + 1]
        simples = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
        if c in simples:
            return simples[c]
        if c == "u":
            if self.t[j + 2] == "{":
                fin = self.t.index("}", j + 3)
                return chr(int(self.t[j + 3:fin], 16))
            return chr(int(self.t[j + 2:j + 6], 16))
        if c == "x":
            return chr(int(self.t[j + 2:j + 4], 16))
        if c == "\n":
            return ""
        return c

    def _largo_escape(self, j):
        c = self.t[j + 1]
        if c == "u":
            return (self.t.index("}", j + 3) - j + 1) if self.t[j + 2] == "{" else 6
        if c == "x":
            return 4
        return 2

    def clave(self, i):
        i = self.espacios(i)
        t = self.t
        if t[i] in "\"'":
            return self.cadena(i)
        if t[i] == "[":
            raise NoEsLiteral    # clave calculada
        m = _NUM.match(t, i)
        if m and t[i].isdigit():
            texto = m.group(0)
            return (str(int(float(texto))) if float(texto).is_integer() else texto), m.end()
        m = _IDENT.match(t, i)
        if m:
            return m.group(0), m.end()
        raise NoEsLiteral

    def objeto(self, i):
        t, salida = self.t, {}
        j = self.espacios(i + 1)
        while True:
            if t[j] == "}":
                return salida, j + 1
            if t.startswith("...", j):
                extra, j = self.valor(j + 3)
                if isinstance(extra, dict):
                    salida.update(extra)
            else:
                k, j = self.clave(j)
                j = self.espacios(j)
                if t[j] == ":":
                    salida[k], j = self.valor(j + 1)
                elif t[j] in ",}":            # forma abreviada {a,b}
                    if k not in self.v:
                        raise NoEsLiteral
                    salida[k] = self.v[k]
                else:
                    raise NoEsLiteral
            j = self.espacios(j)
            if t[j] == ",":
                j = self.espacios(j + 1)
            elif t[j] != "}":
                raise NoEsLiteral

    def arreglo(self, i):
        t, salida = self.t, []
        j = self.espacios(i + 1)
        while True:
            if t[j] == "]":
                return salida, j + 1
            if t.startswith("...", j):
                extra, j = self.valor(j + 3)
                if not isinstance(extra, list):
                    raise NoEsLiteral
                salida.extend(extra)
            elif t[j] == ",":       # hueco [a,,b]
                salida.append(None)
                j = self.espacios(j + 1)
                continue
            else:
                v, j = self.valor(j)
                salida.append(v)
            j = self.espacios(j)
            if t[j] == ",":
                j = self.espacios(j + 1)
            elif t[j] != "]":
                raise NoEsLiteral


def leer_variables(texto):
    """{nombre: valor} de todas las asignaciones nombre=<literal> del módulo (en orden de aparición)."""
    variables = {}
    lector = _Lector(texto, variables)
    for m in _INICIO.finditer(texto):
        try:
            valor, fin = lector.valor(m.end())
        except (NoEsLiteral, IndexError, ValueError):
            continue
        # tiene que terminar la expresión: , ; } ) o fin de línea (no "a=b.c" ni "a=[...].map(...)")
        sig = lector.espacios(fin)
        if sig < len(texto) and texto[sig] not in ",;})\n":
            continue
        variables[m.group(1)] = valor
    return variables
