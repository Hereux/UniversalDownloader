import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.constants import *
from tkinter import filedialog

import os

from bin.utils import write_to_json, center_window
from universaldownloader.bin.utils import update_main_path


class SettingsDialog(ttk.Toplevel):
    """Modaler Einstellungsdialog"""

    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.parent = parent
        self.settings = settings.copy()  # Arbeitskopie
        self.path_var = ttk.StringVar()
        self.only_audio_default_var = ttk.BooleanVar()
        self.spotify_id_var = ttk.StringVar()
        self.spotify_secret_var = ttk.StringVar()
        self.verify_metadata_var = ttk.BooleanVar()
        self.verify_metadata_deep_var = ttk.BooleanVar()
        self.parallel_downloads_var = ttk.IntVar()

        self.title("Einstellungen")
        self.resizable(False, False)
        self.attributes('-alpha', 0.0)  # komplett durchsichtig
        center_window(self, 650, 650)

        self.after(200, lambda: self.switch_focus())

        self._create_widgets()
        self._load_current_values()


    def switch_focus(self):
        self.attributes('-alpha', 1.0)
        self.grab_set()
        self.focus_set()

    def _create_widgets(self):

        container = ttk.Frame(self, padding=(30,15))
        container.pack(fill=BOTH, expand=True)

        # ── Download-Ordner ───────────────────────────────────────
        ttk.Label(container, text="Speicherort", font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(0, 8))

        path_frame = ttk.Frame(container)
        path_frame.pack(fill=X, pady=(0, 25), padx=(20,5))

        ttk.Entry(path_frame, textvariable=self.path_var).pack(
            side="left", fill=X, expand=True, padx=(0, 12))

        ttk.Button(path_frame, text="Durchsuchen...", command=self._choose_directory,
                   bootstyle="info-outline", width=12).pack(side="left")


        # ── Standardmäßig nur Audio ───────────────────────────────
        ttk.Label(container, text="Standard-Einstellungen", font=("Helvetica", 13, "bold")).pack(anchor="w",
                                                                                                 pady=(5, 8))

        ttk.Checkbutton(
            container,
            text="Nur Audio standardmäßig aktivieren",
            variable=self.only_audio_default_var,
            bootstyle="round-toggle"
        ).pack(anchor="w", pady=6, padx=40)

        parallel_frame = ttk.Frame(container)
        parallel_frame.pack(anchor="w", pady=(10, 0), padx=40, fill=X)

        ttk.Label(parallel_frame, text="Gleichzeitige Downloads:", font=("Helvetica", 11)) \
            .pack(side="left", padx=(0, 10))
        ttk.Spinbox(
            parallel_frame, from_=1, to=10, width=5,
            textvariable=self.parallel_downloads_var
        ).pack(side="left")

        ttk.Label(
            container,
            text="Höhere Werte laden schneller, erhöhen aber das Risiko von Abbrüchen",
            font=("Helvetica", 9), bootstyle="light"
        ).pack(anchor="w", pady=(4, 0), padx=40)

        # ── Spotify API ───────────────────────────────────────────
        ttk.Label(
            container,
            text="Spotify API",
            font=("Helvetica", 13, "bold")
        ).pack(anchor="w", pady=(20, 8))

        spotify_frame = ttk.Frame(container)
        spotify_frame.pack(fill=X, padx=40, pady=(0, 10))

        ttk.Label(spotify_frame, text="Client ID:", font=("Helvetica", 11)).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(spotify_frame,textvariable=self.spotify_id_var,width=50).grid(row=0, column=1, sticky="ew",
                                                                                pady=4, padx=(10, 0))

        ttk.Label(spotify_frame, text="Client Secret:", font=("Helvetica", 11)).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry( spotify_frame, textvariable=self.spotify_secret_var, show="•", width=50).grid(row=1, column=1,
                                                                                                 sticky="ew", pady=4,
                                                                                                 padx=(10, 0))

        spotify_frame.columnconfigure(1, weight=1)

        # ── Metadaten-Korrektur ────────────────────────────────────
        ttk.Label(
            container,
            text="Metadaten-Korrektur (nur Audio-Downloads)",
            font=("Helvetica", 13, "bold")
        ).pack(anchor="w", pady=(20, 8))

        ttk.Checkbutton(
            container,
            text="Titel/Künstler automatisch korrigieren",
            variable=self.verify_metadata_var,
            bootstyle="round-toggle",
            command=self._update_verify_deep_state
        ).pack(anchor="w", pady=6, padx=40)

        self.verify_metadata_deep_check = ttk.Checkbutton(
            container,
            text="MusicBrainz als letzte Instanz nutzen (ca. 30s pro Track)",
            variable=self.verify_metadata_deep_var,
            bootstyle="round-toggle"
        )
        self.verify_metadata_deep_check.pack(anchor="w", pady=6, padx=40)

        # ── Buttons unten ─────────────────────────────────────────
        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=(20, 15))

        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy,
                   bootstyle="secondary", width=12).pack(side="left", padx=15)

        ttk.Button(btn_frame, text="Speichern", command=self._save_settings,
                   bootstyle="success", width=12).pack(side="left", padx=15)

    def _load_current_values(self):
        """Aktuelle Werte in die Felder laden"""

        self.path_var.set(self.settings.get("main_path", ""))
        self.only_audio_default_var.set(self.settings.get("only_audio", True))
        self.parallel_downloads_var.set(self.settings.get("parallel_downloads", 3))
        self.spotify_id_var.set(self.settings.get("spotify_id", ""))
        self.spotify_secret_var.set(self.settings.get("spotify_secret", ""))
        self.verify_metadata_var.set(self.settings.get("verify_metadata", True))
        self.verify_metadata_deep_var.set(self.settings.get("verify_metadata_deep", False))
        self._update_verify_deep_state()

    def _update_verify_deep_state(self):
        state = "normal" if self.verify_metadata_var.get() else "disabled"
        self.verify_metadata_deep_check.configure(state=state)

    def _choose_directory(self):
        directory = filedialog.askdirectory(
            initialdir=self.path_var.get() or os.path.expanduser("~"),
            title="Download-Ordner auswählen"
        )
        if directory:
            self.path_var.set(directory)

    def _save_settings(self):
        """Änderungen übernehmen und speichern"""
        new_settings = {
            "main_path": update_main_path(self.path_var.get().strip()),
            "only_audio": self.only_audio_default_var.get(),
            "parallel_downloads": max(1, min(10, self.parallel_downloads_var.get())),
            "spotify_id": self.spotify_id_var.get().strip(),
            "spotify_secret": self.spotify_secret_var.get().strip(),
            "verify_metadata": self.verify_metadata_var.get(),
            "verify_metadata_deep": self.verify_metadata_deep_var.get()
            # Hier ggf. weitere Felder hinzufügen
        }

        # Validierung (minimal)
        if not new_settings["main_path"]:
            Messagebox.show_error(
                title="Fehler",
                message="Bitte gib einen existierenden Donwload-Ordner an!",
                parent=self
            )
            return


        # In JSON schreiben
        for key, value in new_settings.items():
            write_to_json(key, value)

        # Settings im Hauptprogramm aktualisieren
        self.parent.settings.update(new_settings)

        # Downloader informieren (falls nötig)
        self.parent.downloader.settings.update(new_settings)

        # Dialog schließen
        self.destroy()
        #self.parent.root.deiconify()
        # Optional: kurze Bestätigung
        Messagebox.show_info(
            title="Gespeichert",
            message="Einstellungen wurden gespeichert.",
            parent=self.parent.root
        )