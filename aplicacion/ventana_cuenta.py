
import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import asyncio
import threading
from navegador.scraper import configurar_cuenta, obtener_game_accounts, guardar_game_accounts
from navegador.sitio import SERVICIO_KEYRING
import keyring
from idiomas import tr

class VentanaCuenta:
    def __init__(self, parent, perfil_path):

        self.parent = parent
        self.perfil_path = Path(perfil_path)

        self.config_file = (
            self.perfil_path.parent
            / "config_credenciales.json"
        )

        self.top = tk.Toplevel(parent)
        self.top.title(tr("Acceso al sitio"))
        self.top.geometry("900x700")
        self.top.resizable(True, True)
        self.top.grab_set()

        # Credenciales
        self.correo_var = tk.StringVar(value="")
        self.password_var = tk.StringVar(value="")

        # Servidor seleccionado
        self.servidor_var = tk.StringVar(value="")

        # Cuentas disponibles
        self.cuentas_guardadas = []
        self.personajes_guardados = []

        # Cargar credenciales
        self.cargar_credenciales_guardadas()

        # Crear interfaz
        self.crear_interfaz()

        # Cargar cuentas previamente descargadas
        self.cargar_cuentas_locales()

    def cargar_credenciales_guardadas(self):
        """Lee el correo del JSON y la contraseña del Administrador de credenciales de Windows."""
        if not self.config_file.exists():
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return

        correo = data.get("correo", "")
        self.correo_var.set(correo)
        if not correo:
            return

        # Migración: si quedó una contraseña en texto plano, moverla al keyring
        password_plano = data.pop("password", None)
        if password_plano:
            try:
                keyring.set_password(SERVICIO_KEYRING, correo, password_plano)
                self._escribir_config(data)
            except Exception as e:
                print(f"No se pudo migrar la contraseña al keyring: {e}")
            self.password_var.set(password_plano)
            return

        try:
            self.password_var.set(keyring.get_password(SERVICIO_KEYRING, correo) or "")
        except Exception as e:
            print(f"No se pudo leer la contraseña del keyring: {e}")

    def _escribir_config(self, data):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def crear_interfaz(self):

        # ============================================
        # 1. CREDENCIALES
        # ============================================

        frame_credenciales = ttk.LabelFrame(
            self.top,
            text=tr("Credenciales")
        )

        frame_credenciales.pack(
            fill="x",
            padx=15,
            pady=10
        )

        ttk.Label(
            frame_credenciales,
            text=tr("Correo:")
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=10,
            pady=5
        )

        ttk.Entry(
            frame_credenciales,
            textvariable=self.correo_var,
            width=45
        ).grid(
            row=0,
            column=1,
            padx=10,
            pady=5
        )

        ttk.Label(
            frame_credenciales,
            text=tr("Contraseña:")
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=10,
            pady=5
        )

        ttk.Entry(
            frame_credenciales,
            textvariable=self.password_var,
            width=45,
            show="*"
        ).grid(
            row=1,
            column=1,
            padx=10,
            pady=5
        )

        # Referencia guardada para deshabilitar si es necesario
        self.btn_guardar = ttk.Button(
            frame_credenciales,
            text=tr("Guardar credenciales"),
            command=self.guardar_datos
        )
        self.btn_guardar.grid(
            row=2,
            column=0,
            columnspan=2,
            pady=10
        )

        # ============================================
        # 2. ACTUALIZACIÓN
        # ============================================

        self.btn_actualizar = ttk.Button(
            self.top,
            text=tr("Actualizar / Descargar cuentas"),
            command=self.ejecutar_descarga_cuentas
        )

        self.btn_actualizar.pack(pady=10)

        # ============================================
        # 3. LISTA DE CUENTAS
        # ============================================

        frame_cuentas = ttk.LabelFrame(
            self.top,
            text=tr("Cuentas disponibles")
        )

        frame_cuentas.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=10
        )

        # Crear tabla unificada
        self.tabla_cuentas = ttk.Treeview(
            frame_cuentas,
            columns=("account_id", "servidor", "nombre", "Nivel","estado"),
            show="headings",
            selectmode="browse"
        )

        columnas = {
            "account_id": ("Account ID", 260),
            "servidor": ("Servidor", 100),
            "nombre": ("Nombre", 180),
            "Nivel": ("Nivel", 130),
            "estado": ("Estado", 110)
        }

        for columna, (titulo, ancho) in columnas.items():
            self.tabla_cuentas.heading(
                columna,
                text=tr(titulo)
            )
            self.tabla_cuentas.column(
                columna,
                width=ancho,
                anchor="center" if columna != "account_id" else "w"
            )

        self.tabla_cuentas.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        self.tabla_cuentas.bind(
            "<<TreeviewSelect>>",
            self.al_seleccionar_cuenta
        )

        # ============================================
        # 4. CAMBIAR SERVIDOR
        # ============================================

        frame_servidor = ttk.LabelFrame(
            self.top,
            text=tr("Servidor de la cuenta")
        )

        frame_servidor.pack(
            fill="x",
            padx=15,
            pady=10
        )

        ttk.Label(
            frame_servidor,
            text=tr("Servidor:")
        ).pack(
            side="left",
            padx=10,
            pady=10
        )

        self.combo_servidores = ttk.Combobox(
            frame_servidor,
            textvariable=self.servidor_var,
            state="readonly",
            width=20
        )

        self.combo_servidores.pack(
            side="left",
            padx=10
        )

        self.btn_cambiar_servidor = ttk.Button(
            frame_servidor,
            text=tr("Cambiar servidor"),
            command=self.cambiar_servidor,
            state="disabled"
        )

        self.btn_cambiar_servidor.pack(
            side="left",
            padx=10
        )



    def ejecutar_descarga_cuentas(self):
        def tarea_en_hilo():
            try:
                print("⏳ Iniciando actualización de cuentas...")
                datos = obtener_game_accounts(self.perfil_path)
                if not datos:
                    raise RuntimeError(tr("No se obtuvieron datos de la API."))

                directorio_base = self.perfil_path.parent
                accounts = guardar_game_accounts(datos, directorio_base)

                ruta_general = directorio_base / "game_accounts.json"
                with open(ruta_general, "w", encoding="utf-8") as f:
                    json.dump(datos, f, ensure_ascii=False, indent=4)
                print(f"📥 JSON general guardado: {ruta_general}")

            except Exception as e:
                mensaje = str(e)
                print(f"❌ Error al actualizar las cuentas: {mensaje}")
                self.top.after(0, lambda: self._descarga_fallida(mensaje))
                return

            self.top.after(0, lambda: self._descarga_completada(accounts))

        self.btn_actualizar.config(state="disabled")
        threading.Thread(target=tarea_en_hilo, daemon=True).start()

    def _descarga_completada(self, accounts):
        """Se ejecuta en el hilo de Tk tras descargar las cuentas."""
        self.btn_actualizar.config(state="normal")
        self.cuentas_guardadas = accounts
        self.personajes_guardados = [
            {
                "account_id": cuenta.get("id"),
                "selected_server": cuenta.get("selected_server"),
                "uid": personaje.get("uid"),
                "svr_id": personaje.get("svr_id"),
                "name": personaje.get("name", "Sin nombre"),
                "level": personaje.get("level", "N/A"),
                "datos": personaje,
            }
            for cuenta in accounts
            for personaje in cuenta.get("roles", [])
        ]
        self.actualizar_tabla_cuentas()

        print("\n" + "=" * 50)
        print("✅ ACTUALIZACIÓN COMPLETADA")
        print(f"Cuentas: {len(accounts)}")
        print(f"Personajes: {len(self.personajes_guardados)}")
        print(f"Directorio: {self.perfil_path.parent / 'cuentas'}")
        print("=" * 50)

    def _descarga_fallida(self, mensaje):
        self.btn_actualizar.config(state="normal")
        messagebox.showerror(tr("Error"), tr('No se pudieron actualizar las cuentas:\n{0}', mensaje), parent=self.top)

    def cargar_cuentas_locales(self):
        directorio_cuentas = self.perfil_path.parent / "cuentas"
        self.cuentas_guardadas = []

        if not directorio_cuentas.exists():
            self.actualizar_tabla_cuentas()
            return

        for carpeta_cuenta in directorio_cuentas.iterdir():
            if not carpeta_cuenta.is_dir():
                continue

            archivo_cuenta = carpeta_cuenta / "account.json"
            if not archivo_cuenta.exists():
                continue

            try:
                with open(archivo_cuenta, "r", encoding="utf-8") as f:
                    cuenta = json.load(f)

                roles = []
                for carpeta_servidor in carpeta_cuenta.iterdir():
                    if not carpeta_servidor.is_dir():
                        continue

                    archivo_personaje = carpeta_servidor / f"{carpeta_servidor.name}.json"
                    if archivo_personaje.exists():
                        with open(archivo_personaje, "r", encoding="utf-8") as f:
                            personaje = json.load(f)
                        roles.append(personaje)

                cuenta["roles"] = roles
                self.cuentas_guardadas.append(cuenta)

            except Exception as e:
                print(f"Error cargando cuenta {carpeta_cuenta.name}: {e}")

        self.actualizar_tabla_cuentas()

    def actualizar_tabla_cuentas(self):
            for item in self.tabla_cuentas.get_children():
                self.tabla_cuentas.delete(item)

            for cuenta in self.cuentas_guardadas:
                account_id = cuenta.get("id")
                if account_id is None:
                    continue

                roles = cuenta.get("roles", [])
                servidor_local = cuenta.get("servidor_local")
                if servidor_local is None:
                    servidor_local = cuenta.get("selected_server")

                roles_ordenados = sorted(
                    roles,
                    key=lambda rol: (
                        0, int(str(rol.get("svr_id")))
                    ) if str(rol.get("svr_id", "")).isdigit()
                    else (1, str(rol.get("svr_id", "")))
                )

                for personaje in roles_ordenados:
                    servidor = personaje.get("svr_id")
                    if servidor is None:
                        continue

                    nombre = personaje.get("name", "Sin nombre")
                    nivel = str(personaje.get("level", "N/A")) # <--- Obtenemos el nivel
                    
                    seleccionado = (str(servidor) == str(servidor_local))
                    estado = "✓ Activo" if seleccionado else ""
                    
                    item_id = f"{account_id}|{servidor}"

                    # Insertamos los valores incluyendo el nivel en la 4ta columna
                    self.tabla_cuentas.insert(
                        "",
                        "end",
                        iid=item_id,
                        values=(str(account_id), str(servidor), nombre, nivel, estado)
                    )

            self.servidor_var.set("")
            self.combo_servidores["values"] = []
            self.btn_cambiar_servidor.config(state="disabled")
            if hasattr(self, 'btn_seleccionar_estado'):
                self.btn_seleccionar_estado.config(state="disabled")

    def al_seleccionar_cuenta(self, event=None):
        seleccion = self.tabla_cuentas.selection()
        if not seleccion:
            return

        item_id = seleccion[0]
        valores = self.tabla_cuentas.item(item_id, "values")
        account_id = str(valores[0])
        servidor_fila = str(valores[1])

        cuenta = next(
            (c for c in self.cuentas_guardadas if str(c.get("id")) == account_id),
            None
        )

        if cuenta is None:
            return

        servidores = sorted(
            {
                str(rol["svr_id"])
                for rol in cuenta.get("roles", [])
                if rol.get("svr_id") is not None
            },
            key=lambda s: ((0, int(s)) if s.isdigit() else (1, s))
        )

        self.combo_servidores["values"] = servidores
        self.servidor_var.set(servidor_fila)
        
        # Habilitamos los botones de acción al seleccionar una fila
        self.btn_cambiar_servidor.config(state="normal")
        if hasattr(self, 'btn_seleccionar_estado'):
            self.btn_seleccionar_estado.config(state="normal")


    
    def cambiar_servidor(self):
        seleccion = self.tabla_cuentas.selection()
        if not seleccion:
            messagebox.showwarning(tr("Atención"), tr("Selecciona una cuenta."), parent=self.top)
            return

        item_id = seleccion[0]
        valores = self.tabla_cuentas.item(item_id, "values")
        account_id = str(valores[0])
        nuevo_servidor = self.servidor_var.get()

        if not nuevo_servidor:
            messagebox.showwarning(tr("Atención"), tr("Selecciona un servidor."), parent=self.top)
            return

        cuenta = next(
            (c for c in self.cuentas_guardadas if str(c.get("id")) == account_id),
            None
        )

        if cuenta is None:
            return

        servidores_disponibles = {
            str(rol["svr_id"])
            for rol in cuenta.get("roles", [])
            if rol.get("svr_id") is not None
        }

        if nuevo_servidor not in servidores_disponibles:
            messagebox.showerror(tr("Error"), tr("El servidor no pertenece a esta cuenta."), parent=self.top)
            return

        servidor_original = next(
            rol["svr_id"]
            for rol in cuenta["roles"]
            if str(rol["svr_id"]) == nuevo_servidor
        )

        archivo_cuenta = self.perfil_path.parent / "cuentas" / account_id / "account.json"

        try:
            with open(archivo_cuenta, "r", encoding="utf-8") as f:
                datos = json.load(f)

            datos["servidor_local"] = servidor_original

            with open(archivo_cuenta, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=4)

            cuenta["servidor_local"] = servidor_original
            self.actualizar_tabla_cuentas()

            nuevo_item_id = f"{account_id}|{nuevo_servidor}"
            if self.tabla_cuentas.exists(nuevo_item_id):
                self.tabla_cuentas.selection_set(nuevo_item_id)
                self.tabla_cuentas.focus(nuevo_item_id)
                self.tabla_cuentas.see(nuevo_item_id)

            messagebox.showinfo(tr("Servidor actualizado"), tr('Servidor local seleccionado: {0}', nuevo_servidor), parent=self.top)

        except Exception as e:
            messagebox.showerror(tr("Error"), tr('No se pudo guardar el servidor:\n{0}', e), parent=self.top)

    def guardar_datos(self):
        correo = self.correo_var.get().strip()
        password = self.password_var.get()

        if not correo or not password:
            messagebox.showwarning(tr("Atención"), tr("Por favor completa ambos campos."), parent=self.top)
            return

        try:
            # La contraseña va al Administrador de credenciales de Windows;
            # en el JSON solo se guarda el correo.
            keyring.set_password(SERVICIO_KEYRING, correo, password)
            self._escribir_config({"correo": correo})
        except Exception as e:
            messagebox.showerror(tr("Error"), tr('No se pudieron guardar las credenciales:\n{0}', e), parent=self.top)
            return

        self.btn_guardar.config(state="disabled")
        messagebox.showinfo(tr("Procesando"), tr("Iniciando sesión en esperianarchive.com..."), parent=self.top)

        def tarea_en_hilo():
            try:
                asyncio.run(configurar_cuenta(
                    perfil_path=self.perfil_path,
                    correo=correo,
                    password=password
                ))
            except Exception as e:
                mensaje = str(e)
                self.top.after(0, lambda: self._login_fallido(mensaje))
                return
            self.top.after(0, self._login_correcto)

        threading.Thread(target=tarea_en_hilo, daemon=True).start()

    def _login_correcto(self):
        messagebox.showinfo(tr("Éxito"), tr("¡Sesión iniciada correctamente! Tus credenciales quedaron guardadas."), parent=self.top)
        self.top.destroy()

    def _login_fallido(self, mensaje):
        messagebox.showerror(tr("Error"), tr('Ocurrió un error al iniciar sesión:\n{0}', mensaje), parent=self.top)
        self.btn_guardar.config(state="normal")
