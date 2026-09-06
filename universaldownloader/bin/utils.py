import json
import os
import re
import sys
import time

import emoji
import requests
from unidecode import unidecode
from yt_dlp.utils import DownloadCancelled

def resource_path(relative_path):
    """ Holt den absoluten Pfad zur Resource – funktioniert bei dev UND in der EXE """
    try:
        # PyInstaller Temp-Ordner (_MEIPASS) wenn bundled
        base_path = sys._MEIPASS
    except AttributeError:
        # Normaler Python-Modus (Entwicklung)
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


settings_path = resource_path(r".\bin\settings.json")


def load_settings():
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception(f"Fehler: settings.json nicht gefunden unter: {settings_path}")
    except json.JSONDecodeError:
        raise Exception("Fehler: settings.json ist ungültiges JSON")


def write_to_json(key: str, value):
    settings[key] = value
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)


settings = load_settings()
bad_chars = settings.get("bad_chars", [])


def remove_emoji(text: str) -> str:
    return ''.join(c for c in text if not emoji.is_emoji(c))


def rename_title(title: str, artist: str | None = None, channel_name: str | None = None):
    title = unidecode(remove_emoji(title.lower()))

    for char in bad_chars:
        title = title.replace(char.lower(), " ")

    if not artist:
        if channel_name and "topic" in channel_name.lower():
            artist = channel_name.rsplit(" - Topic", 1)[0].strip()
        elif " - " in title:
            artist, title = title.rsplit(" - ", 1)
        elif "-" in title:
            artist, title = title.rsplit("-", 1)
        elif "|" in title:
            artist, title = title.split("|", 1)
        elif " | " in title:
            artist, title = title.split(" | ", 1)
        elif channel_name:
            artist = channel_name
        else:
            artist = "Unbekannt"

    if "-" in title:
        title = title.replace("-", "")

    artist = unidecode(remove_emoji(artist or ""))

    title = " ".join(title.split()).title().strip()
    artist = " ".join(artist.split()).title().strip()

    return title, artist


# Schutz vor Livestreams/HLS-Fehleinschätzungen: yt-dlp schätzt die Gesamtgröße bei
# fragmentierten Formaten aus der bisherigen Fragmentgröße hoch - bei Livestreams (oder
# falsch eingeschätzten Formaten) kann das auf mehrere GiB für ein einzelnes "Video" laufen.
# Der Hook bricht sauber ab (statt stunden-/GiB-lang weiterzuladen), download_entry fängt das
# als normalen Fehler ab und überspringt den Track.
def _abort_if_too_large(max_bytes):
    def hook(status):
        if status.get("status") != "downloading":
            return
        size = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
        if size > max_bytes:
            raise DownloadCancelled(
                f"Datei zu groß ({size / 1024**3:.1f} GiB, vermutlich Livestream) - übersprungen."
            )
    return hook


_MAX_AUDIO_BYTES = 3 * 1024 * 1024 * 1024    # 3 GiB - deckt auch lange DJ-Sets/Mixes ab
_MAX_VIDEO_BYTES = 30 * 1024 * 1024 * 1024   # 30 GiB - deckt auch lange Mixe/Videos in hoher Auflösung ab

# Ohne JS-Runtime kann yt-dlp YouTubes Signatur-/PO-Token-Herausforderung nicht lösen und
# weicht auf ungewöhnliche Player-Clients aus, die YouTube mit "Sign in to confirm you're
# not a bot" blockt - auch ohne dass Cookies nötig wären. Mit gebündeltem Deno behoben.
_JS_RUNTIMES = {"deno": {"path": resource_path("deno.exe")}}


def ydl_opts_video(path: str):
    return {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": path + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": resource_path("ffmpeg.exe"),
        "progress_hooks": [_abort_if_too_large(_MAX_VIDEO_BYTES)],
        "js_runtimes": _JS_RUNTIMES,
    }


def ydl_opts_audio(path: str):
    return {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "EmbedThumbnail", "already_have_thumbnail": False},
        ],
        "writethumbnail": True,
        "outtmpl": path + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": resource_path("ffmpeg.exe"),
        "progress_hooks": [_abort_if_too_large(_MAX_AUDIO_BYTES)],
        "js_runtimes": _JS_RUNTIMES,
    }


def ydl_opts_extract(extract_flat=True):
    return {
        "quiet": True,
        "extract_flat": "in_playlist" if extract_flat else False,
        "skip_download": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "js_runtimes": _JS_RUNTIMES,
    }


def verify_metadata(title: str, artist: str):
    return title, artist, False


def update_main_path(main_path: str):
    if not main_path:
        print("MainPath not exist")
        # os.path.dirname(__file__) zeigt in der gebauten exe auf den temporären
        # _MEIPASS-Entpackungsordner, der beim Beenden gelöscht wird - Downloads würden
        # dort verschwinden. Deshalb ein pfadunabhängiger Default im Nutzerprofil.
        path = os.path.join(os.path.expanduser("~"), "Downloads", "UniversalDownloader",
                            time.strftime("%d.%m.%Y"))
    else:
        print("main_path exist")
        # Check if main_path ends with a datecode pattern (dd.mm.yyyy)
        datecode_pattern = r'(\d{2}\.\d{2}\.\d{4})$'
        match = re.search(datecode_pattern, main_path)
        if match:
            # Replace old datecode with current date
            old_date = match.group(1)
            current_date = time.strftime("%d.%m.%Y")
            path = main_path.replace(old_date, current_date)
        else:
            path = os.sep.join([main_path, time.strftime("%d.%m.%Y")])
    return os.path.normpath(path)


def center_window(root, w, h):
    root.update_idletasks()

    # Bildschirmgröße (logisch, nach Skalierung)
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()

    # Mitte berechnen
    x = (ws - w) // 2
    y = (hs - h) // 2

    root.geometry(f'{w}x{h}+{x}+{y}')

    # WICHTIG: Nochmal update_idletasks(), damit Tkinter die Position "akzeptiert"
    root.update_idletasks()


def _build_entry(yt_id="", url="", title="", artist="", playlist="", album="", track_number=1, force_audio=False):
    """
    force_audio: True, wenn die Quelle nur Audio liefert (Spotify/Soundcloud)
    """
    return {
        "id": yt_id,
        "url": url,
        "title": title,
        "artist": artist or "Unbekannt",
        "playlist": playlist,
        "album": album,
        "track_number": track_number,
        "force_audio": force_audio
    }



