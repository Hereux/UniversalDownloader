# Universal Downloader

Ein Windows-Desktop-Tool zum Herunterladen von Musik und Videos von YouTube, Spotify (via YouTube-Suche) und SoundCloud – als portable, installationsfreie `.exe`.

Entwickelt von Hereux.

## Features

- **Quellen**: YouTube (Video/Playlist/Suche), Spotify (Track/Album/Playlist), SoundCloud
- **Audio oder Video**: mp3-Extraktion mit eingebettetem Thumbnail, oder mp4 in bester verfügbarer Qualität
- **Metadaten-Korrektur**: gleicht Titel/Künstler parallel gegen Deezer ab (optional zusätzlich MusicBrainz als langsamerer, genauerer Fallback), damit uneinheitlich benannte YouTube-Titel korrekt getaggt werden
- **Parallele Downloads**: einstellbare Anzahl gleichzeitiger Downloads
- **Übersicht übersprungener Titel**: nicht verfügbare, zu große (Livestream-Verdacht) oder fehlgeschlagene Downloads werden am Ende gesammelt angezeigt statt nur kurz im Statustext aufzublitzen
- **Einstellungen**: Downloadpfad, Standard-Audio/Video, Metadaten-Korrektur, parallele Downloads, Spotify API-Zugangsdaten – alles über ein Menü in der App

## Nutzung (fertige exe)

1. `YT Music Search.exe` aus den [Releases](../../releases) bzw. `dist/` starten – keine Installation nötig.
2. Für Spotify-Links: einmalig unter **Einstellungen → Spotify API** eine eigene Client ID/Secret eintragen (kostenlos über das [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), als Redirect-URI `http://127.0.0.1:8888/callback` eintragen). Ohne das funktionieren YouTube- und SoundCloud-Links weiterhin normal.
3. Link einfügen, Download starten.

**Nicht unterstützt**: Spotify-eigene algorithmische/redaktionelle Playlists (Discover Weekly, Release Radar, offizielle Spotify-Playlists) – das ist eine Einschränkung der Spotify-API seit November 2024 und betrifft alle Drittanbieter-Apps, nicht nur dieses Tool.

## Aus dem Quellcode bauen

Voraussetzung: Python 3.14, eine virtuelle Umgebung mit den Paketen aus `requirements.txt` sowie `pyinstaller`.

```bash
pip install -r requirements.txt pyinstaller
pyinstaller "YT Music Search.spec"
```

Der Build läuft komplett automatisch: `ffmpeg.exe` und `deno.exe` (JS-Runtime für yt-dlp, gegen YouTubes Bot-Checks) werden mitgebündelt, und `settings.public.json` (ohne persönliche Zugangsdaten/Pfad) wird automatisch als `bin/settings.json` in die exe gestaged – die eigene lokale `bin/settings.json` mit echten Zugangsdaten bleibt dabei unangetastet und wird nie mit committet oder gebündelt (siehe `.gitignore`).

Fertige exe liegt danach in `dist/`.

## Projektstruktur

```
universaldownloader/
├── main.py              # GUI (ttkbootstrap)
├── download.py          # Download-Logik (Downloader-Thread)
├── settings_menu.py     # Einstellungsdialog
├── ffmpeg.exe           # gebündelt für Audio-Konvertierung
├── deno.exe             # gebündelt als JS-Runtime für yt-dlp
└── bin/
    ├── utils.py             # Helper, yt-dlp-Optionen, Settings-I/O
    ├── musicbrainz.py       # Deezer/MusicBrainz-Metadatenabgleich
    ├── settings.json        # lokale Konfiguration (nicht getrackt)
    └── settings.public.json # Vorlage ohne Zugangsdaten für Builds
```

## Bekannte Einschränkungen

- Spotify-Playlists, die Spotify selbst gehören (algorithmisch/redaktionell), können wegen einer API-Einschränkung nicht importiert werden.
- Höhere Werte bei "Gleichzeitige Downloads" erhöhen das Risiko von Ratelimits/Abbrüchen bei YouTube.
