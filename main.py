import os
import time
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.utility import enable_high_dpi_awareness
from bin.utils import load_settings, write_to_json, center_window
import download

enable_high_dpi_awareness()


class Main:
    def __init__(self):
        self.settings = load_settings()
        path = os.path.join(os.path.dirname(__file__), "Downloads", time.strftime("%d.%m.%Y"))
        write_to_json("main_path", path)

        self.root = tb.Window(themename="darkly")
        self.root.title("Universal Downloader")

        self.root.withdraw()

        # Größe und Eigenschaften setzen
        self.root.geometry("850x500")
        self.root.resizable(False, False)
        self.root.attributes('-alpha', 0.0)  # komplett durchsichtig
        center_window(self)

        self.root.after(300, lambda: self.root.attributes('-alpha', 1.0))
        self.root.deiconify()

        self.url_var = tb.StringVar()
        self.only_audio_var = tb.BooleanVar(value=self.settings.get("only_audio", True))

        self.downloader = download.Downloader(self.settings)
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
        self.root.iconbitmap("bin/icon.ico")

        start_frame = tb.Frame(self.root, padding=20)
        start_frame.pack(fill=BOTH, expand=True)

        image = tb.PhotoImage(file="bin/logo.png")
        image = image.subsample(4)
        logo_label = tb.Label(start_frame, image=image, bootstyle="primary")
        logo_label.image = image
        logo_label.pack(anchor="center", pady=(0, 20), expand=True)

        developer_label = tb.Label(start_frame, text="Entwickelt von Hereux.", font=("Helvetica", 16, "italic"),
                                   bootstyle="secondary")
        developer_label.pack(anchor="center", pady=(0, 10), expand=True)

        main_frame = tb.Frame(self.root, padding=20)
        main_frame.pack_forget()

        self.root.after(3000, lambda: start_frame.pack_forget())
        self.root.after(3000, lambda: main_frame.pack(fill=BOTH, expand=True))

        # Header
        header_label = tb.Label(main_frame, text="Universal Downloader", font=("Helvetica", 20, "bold"))
        header_label.pack(pady=(0, 30))

        # URL-Eingabe
        self.url_entry = tb.Entry(main_frame, textvariable=self.url_var, font=("Helvetica", 14), width=70)
        self.url_entry.pack(pady=(0, 15), padx=30)

        # Audio-Only-Switch
        audio_only_switch = tb.Checkbutton(main_frame, text="Nur Audio herunterladen", variable=self.only_audio_var,
                                           bootstyle="success-round-toggle")
        audio_only_switch.pack(anchor="w", pady=(5, 15), padx=30)

        # Buttons
        button_frame = tb.Frame(main_frame)
        button_frame.pack(pady=(20, 20))

        tb.Button(button_frame, text="Download starten", command=self.start_download, bootstyle="success", width=20) \
            .pack(side="left", padx=20)
        tb.Button(button_frame, text="Pause / Fortsetzen", command=self.toggle_pause, bootstyle="warning", width=20) \
            .pack(side="left", padx=20)
        tb.Button(button_frame, text="Beenden", command=self.shutdown, bootstyle="danger", width=20) \
            .pack(side="left", padx=20)

        # Status-Label
        tb.Label(main_frame, textvariable=self.downloader.status_var,
                 font=("Helvetica", 15, "italic"), bootstyle="info").pack(pady=(10, 15))

        # Progress-Text ( 0 / 1 )
        progress_frame = tb.Frame(main_frame)
        progress_frame.pack(pady=(15, 5), fill=X)

        self.progress_text_label = tb.Label(
            progress_frame,
            textvariable=self.downloader.progress_text,
            font=("Helvetica", 15),
            bootstyle="info"
        )
        self.progress_text_label.pack()

        # Progressbar
        self.progress_bar = tb.Progressbar(main_frame, variable=self.downloader.progress_var,
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

        self.url_entry.bind("<FocusIn>", self._clear_placeholder)
        self.url_entry.bind("<FocusOut>", self._set_placeholder)

        # Progressbar nur zeigen, wenn Playlist (über Status-Var beobachten)
        self.downloader.status_var.trace_add("write", self._visible_progress_text)

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

if __name__ == "__main__":
    Main()
