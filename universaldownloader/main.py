import os
import sys
import webbrowser

from universaldownloader.bin.utils import update_main_path

if __name__ == "__main__":
    # Ordner der main.py zum Suchpfad hinzufügen
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.utils import enable_high_dpi_awareness
from ttkbootstrap.dialogs import Messagebox
from settings_menu import SettingsDialog
from bin.utils import load_settings, write_to_json, center_window, resource_path
from download import Downloader

enable_high_dpi_awareness()


class SpotifyInfoDialog(ttk.Toplevel):
    """Hinweis auf fehlende Spotify-Zugangsdaten mit klickbarem Link und kopierbarer Redirect-URI."""

    DASHBOARD_URL = "https://developer.spotify.com/dashboard"
    REDIRECT_URI = "http://127.0.0.1:8888/callback"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Spotify-Zugangsdaten fehlen")
        self.resizable(False, False)
        center_window(self, 480, 360)
        self.after(100, self._focus)

        container = ttk.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttk.Label(
            container,
            text="Für Spotify-Links werden eine Client ID und ein Client Secret benötigt.\n"
                "Kostenlos erstellen unter:",
            wraplength=440, justify="left"
        ).pack(anchor="w", pady=(0, 6))

        link = ttk.Label(
            container, text=self.DASHBOARD_URL, bootstyle="info",
            cursor="hand2", font=("Helvetica", 10, "underline")
        )
        link.pack(anchor="w", pady=(0, 18))
        link.bind("<Button-1>", lambda e: webbrowser.open(self.DASHBOARD_URL))

        ttk.Label(container, text="Redirect-URI (dort in der App-Einstellung eintragen):") \
            .pack(anchor="w", pady=(0, 4))

        uri_frame = ttk.Frame(container)
        uri_frame.pack(fill=X, pady=(0, 18))

        uri_entry = ttk.Entry(uri_frame)
        uri_entry.insert(0, self.REDIRECT_URI)
        uri_entry.configure(state="readonly")
        uri_entry.pack(side="left", fill=X, expand=True, padx=(0, 8))

        ttk.Button(
            uri_frame, text="Kopieren", bootstyle="secondary-outline", width=10,    # TODO: Kopieren Knopf Farbe druck invertieren
            command=lambda: self._copy_to_clipboard(self.REDIRECT_URI)
        ).pack(side="left")

        ttk.Label(
            container,
            text="Client ID/Secret danach unter Einstellungen → Spotify API eintragen.",
            wraplength=440, justify="left"
        ).pack(anchor="w", pady=(0, 18))

        ttk.Button(container, text="OK", command=self.destroy, bootstyle="success", width=10).pack()

    def _focus(self):
        self.grab_set()
        self.focus_set()

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)


class Main:
    def __init__(self):
        self.settings = load_settings()
        path = update_main_path(self.settings.get("main_path"))
        self.settings["main_path"] = path
        write_to_json("main_path", path)

        self.root = ttk.Window(themename="darkly")
        self.root.title("Universal Downloader")

        self.root.withdraw()

        # Größe und Eigenschaften setzen
        self.root.resizable(False, False)
        self.root.attributes('-alpha', 0.0)  # komplett durchsichtig
        center_window(self.root, 850, 500)

        # noinspection PyArgumentList
        self.root.after(300, lambda: self.root.attributes('-alpha', 1.0))
        self.root.deiconify()

        self.url_var = ttk.StringVar()
        self.only_audio_var = ttk.BooleanVar(value=self.settings.get("only_audio", True))

        self.downloader = Downloader(self.settings)
        self.downloader.only_audio = self.only_audio_var.get()
        self.only_audio_var.trace_add("write", self.update_only_audio)

        self._build_ui()
        self._set_placeholder()

        self.root.mainloop()

    def update_only_audio(self, *args):
        only_audio = self.only_audio_var.get()
        self.downloader.only_audio = only_audio
        write_to_json("only_audio", only_audio)

    def _build_ui(self):
        self.root.iconbitmap(default=resource_path("bin/icon.ico"))

        start_frame = ttk.Frame(self.root, padding=20)
        start_frame.pack(fill=BOTH, expand=True)

        image = ttk.PhotoImage(file=resource_path("bin/logo.png"))
        image = image.subsample(4)
        logo_label = ttk.Label(start_frame, image=image, bootstyle="primary")
        logo_label.image = image
        logo_label.pack(anchor="center", pady=(0, 20), expand=True)

        developer_label = ttk.Label(start_frame, text="Entwickelt von Hereux.", font=("Helvetica", 16, "italic"),
                                    bootstyle="secondary")
        developer_label.pack(anchor="center", pady=(0, 10), expand=True)

        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack_forget()

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(pady=(0, 20), fill='x')

        # noinspection PyArgumentList
        self.root.after(2000, lambda: start_frame.pack_forget())
        # noinspection PyArgumentList
        self.root.after(2000, lambda: main_frame.pack(fill=BOTH, expand=True))

        # Settings-Button
        self.settings_button = ttk.Button(
            header_frame,
            text='\u2699',
            bootstyle="secondary",
            width=3
        )
        self.settings_button.pack(side="right", padx=15, pady=5)
        self.settings_button.bind("<Button-1>", lambda e: self.open_settings())

        # Header
        header_label = ttk.Label(
            header_frame,
            text="Universal Downloader",
            font=("Helvetica", 20, "bold"),
            anchor="center"  # wichtig!
        )
        header_label.pack(side="left", fill="x", padx=(75, 0), expand=True)

        # URL-Eingabe
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, font=("Helvetica", 14), width=70)
        self.url_entry.pack(pady=(15, 15), padx=30)

        # Audio-Only-Switch
        audio_only_switch = ttk.Checkbutton(main_frame, text="Nur Audio herunterladen", variable=self.only_audio_var,
                                            bootstyle="success-round-toggle")
        audio_only_switch.pack(anchor="w", pady=(5, 15), padx=30)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=30)

        ttk.Button(button_frame, text="Download starten", command=self.start_download, bootstyle="success", width=20) \
            .pack(side="left", padx=20)
        ttk.Button(button_frame, text="Pause / Fortsetzen", command=self.toggle_pause, bootstyle="warning", width=20) \
            .pack(side="left", padx=20)
        ttk.Button(button_frame, text="Beenden", command=self.shutdown, bootstyle="danger", width=20) \
            .pack(side="left", padx=20)

        # Status-Label
        ttk.Label(main_frame, textvariable=self.downloader.status_var,
                  font=("Helvetica", 15, "italic"), bootstyle="info", wraplength=700).pack(pady=(10, 15))

        # Progress-Text ( 0 / 1 )
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(pady=(15, 5), fill=X)

        self.progress_text_label = ttk.Label(
            progress_frame,
            textvariable=self.downloader.progress_text,
            font=("Helvetica", 15),
            bootstyle="info"
        )
        self.progress_text_label.pack()

        # Progressbar
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.downloader.progress_var,
                                            bootstyle="success-striped", maximum=100)
        self.progress_bar.pack(pady=0, padx=30, fill=X)

        # self.progress_bar.pack_forget()

        # Defocus
        def defocus(event):
            if self.root.focus_get() == self.url_entry:
                self.root.focus_set()

        main_frame.bind("<Button-1>", defocus)
        for child in main_frame.winfo_children():
            child.bind("<Button-1>", defocus, add="+")

        self.root.bind("<Escape>", lambda e: self.shutdown())
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.url_entry.bind("<FocusIn>", self._clear_placeholder)
        self.url_entry.bind("<FocusOut>", self._set_placeholder)

        # Progressbar nur zeigen, wenn Playlist (über Status-Var beobachten)
        self.downloader.status_var.trace_add("write", self._visible_progress_text)

        # Übersicht übersprungener Titel nach Abschluss eines Downloads
        self.downloader.skipped_var.trace_add("write", self._show_skipped_summary)

        # Hinweis, wenn ein Spotify-Link ohne konfigurierte Zugangsdaten kommt
        self.downloader.spotify_error_var.trace_add("write", self._show_spotify_credentials_missing)

    def open_settings(self):
        SettingsDialog(self, self.settings)

    def _show_spotify_credentials_missing(self, *args):
        SpotifyInfoDialog(self.root)

    def _show_skipped_summary(self, *args):
        text = self.downloader.skipped_var.get()
        if not text:
            return
        Messagebox.show_warning(
            title="Übersprungene Titel",
            message=f"Folgende Titel wurden übersprungen:\n\n{text}",
            parent=self.root
        )

    def _visible_progress_text(self, *args):
        if self.downloader.total == 0:
            # self.progress_bar.pack_forget()
            self.progress_text_label.pack_forget()
            pass
        else:
            # self.progress_bar.pack(pady=(15, 5), fill=X, padx=30)
            self.progress_text_label.pack()

    def _set_placeholder(self, event=None):
        if not self.url_var.get().strip():
            self.url_var.set("URL eingeben:")
            self.url_entry.configure(foreground="gray")

    def _clear_placeholder(self, event=None):
        if self.url_var.get() == "URL eingeben:":
            self.url_var.set("")
            self.url_entry.configure(foreground="white")

    def start_download(self):
        url = self.url_var.get().strip()
        if url and url != "URL eingeben:":
            self.downloader.queue.put(url)
            self._set_placeholder()
        else:
            self.downloader.status_var.set("Bitte eine gültige URL eingeben!")

    def toggle_pause(self):
        self.downloader.paused = not self.downloader.paused
        status = "Pausiert" if self.downloader.paused else "Fortgesetzt"
        self.downloader.status_var.set(status)
        self.progress_bar.configure(bootstyle="warning-striped" if self.downloader.paused else "success-striped")

    def shutdown(self):
        self.downloader.running = False
        self.root.destroy()
        # ThreadPoolExecutor-Worker (Downloads/Metadaten-Verifikation) sind keine Daemon-Threads
        # und würden den Prozess sonst im Hintergrund weiterlaufen lassen, bis alle offenen
        # Downloads fertig sind. Harter Exit erzwingt das sofortige Prozessende.
        os._exit(0)


Main()
