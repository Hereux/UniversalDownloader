import os
import queue
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import eyed3
import ttkbootstrap as tb
import yt_dlp
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from yt_dlp.utils import DownloadCancelled

import yt_music_search
from bin.utils import rename_title, ydl_opts_extract, ydl_opts_audio, ydl_opts_video, verify_metadata
from universaldownloader.bin import musicbrainz
from universaldownloader.bin.utils import _build_entry


class SpotifyCredentialsMissing(RuntimeError):
    pass

# TODO: Spotify Playlisten defekt

class Downloader(threading.Thread):
    def __init__(self, settings: dict):
        super().__init__(daemon=True)
        self.settings = settings
        self.queue = queue.Queue()
        self.running = True
        self.paused = False
        self.only_audio = True

        self.status_var = tb.StringVar(value="Bereit")
        self.progress_var = tb.IntVar(value=0)
        self.progress_text = tb.StringVar(value="0 / 0")
        self.skipped_var = tb.StringVar(value="")
        self.spotify_error_var = tb.StringVar(value="")

        self.current = 0
        self.total = 0
        self.skipped: list[str] = []

        # Wird erst bei Bedarf angelegt (siehe _get_spotify) - ohne konfigurierte
        # Zugangsdaten soll die App für YouTube/SoundCloud trotzdem normal starten.
        self._spotify = None

        self._FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
        self._RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)', re.I)

        self.start()

    def _get_spotify(self) -> Spotify:
        if self._spotify is None:
            client_id = self.settings.get("spotify_id")
            client_secret = self.settings.get("spotify_secret")
            if not client_id or not client_secret:
                raise SpotifyCredentialsMissing("Spotify-Zugangsdaten fehlen.")
            self._spotify = Spotify(auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri="http://127.0.0.1:8888/callback",
                scope="playlist-read-private"
            ))
        return self._spotify

    def run(self):
        while self.running:
            try:
                url = self.queue.get(timeout=0.5)
            except queue.Empty:
                if self.total > 0:
                    self.current = self.total = 0
                    self._update_progress()
                continue

            self.status_var.set("Bereite Download vor...")
            self.current = self.total = 0
            self.skipped = []
            self._update_progress()

            try:
                entries = self.identify_url(url)
                self.total = len(entries)
                self._update_progress()

                valid_entries: list[dict] = [entry for entry in entries if entry is not None]

                if not valid_entries:
                    self.total = 0
                    self._update_progress()
                    continue

            except SpotifyCredentialsMissing:
                self.status_var.set("Spotify-Zugangsdaten fehlen.")
                self.spotify_error_var.set("missing")
                continue
            except SpotifyException as e:
                if e.http_status == 404:
                    self.status_var.set("Spotify-Playlists/Mixes werden nicht unterstützt.")
                else:
                    self.status_var.set(f"Spotify-Fehler: {e}")
                continue
            except RuntimeError as e:
                self.status_var.set(str(e))
                continue
            except Exception as e:
                self.status_var.set(f"Unbekannter Fehler: {e}")
                print(e)
                continue

            if self.settings.get("verify_metadata", True):
                self._verify_entries(valid_entries)

            self._download_entries(valid_entries)

            self.status_var.set(f"Download abgeschlossen.")

            if self.skipped:
                self.skipped_var.set("\n".join(self.skipped))
                self.skipped = []

    def _download_entries(self, entries: list[dict]):
        progress_lock = threading.Lock()

        def worker(entry):
            if not self.running:
                return
            self._wait_if_paused()
            # Entzerrt die Startzeitpunkte etwas, statt alle Downloads im exakt selben
            # Moment loszuschicken.
            time.sleep(random.uniform(0.2, 1.0))
            self.status_var.set(f'Lade "{entry["title"]}" herunter...')
            self.download_entry(entry)
            with progress_lock:
                self.current += 1
                self._update_progress()

        max_workers = max(1, int(self.settings.get("parallel_downloads", 3)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(worker, entries))

    def _verify_entries(self, entries: list[dict]):
        """Prüft Titel/Künstler aller Einträge parallel (Deezer ist schnell genug dafür),
        statt es seriell während des Downloads pro Track zu tun."""
        allow_musicbrainz = self.settings.get("verify_metadata_deep", False)

        def verify(entry):
            if not (self.only_audio or entry.get("force_audio")):
                return
            try:
                match = musicbrainz.similarity_check(
                    entry["artist"], entry["title"], min_score=85, min_similarity=0.75,
                    allow_musicbrainz=allow_musicbrainz
                )
            except Exception as e:
                # Ein einzelner fehlgeschlagener Lookup darf nie die ganze Playlist/den
                # Downloader-Thread abschießen.
                print(f"Metadaten-Prüfung fehlgeschlagen für {entry.get('title')}: {e}")
                return
            if match and match.status != "unknown":
                entry["artist"] = match.artist
                entry["title"] = match.title

        self.status_var.set(f"Prüfe Metadaten für {len(entries)} Titel...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(verify, entries))

    def _wait_if_paused(self):
        while self.paused and self.running:
            time.sleep(0.2)

    def _update_progress(self):
        if self.total > 0:
            percent = int((self.current / self.total) * 100)
            self.progress_var.set(percent)
            self.progress_text.set(f"{self.current} / {self.total}")
        else:
            self.progress_var.set(0)
            self.progress_text.set("0 / 0")

    def sanitize(self, name, replacement=""):
        name = self._FORBIDDEN.sub(replacement, name)
        name = name.rstrip(". ")  # Windows verbietet Punkt/Leerzeichen am Ende
        if self._RESERVED.match(name):
            name = "_" + name
        return name or "unbenannt"

    def identify_url(self, url: str) -> list[dict | None] | list[dict]:
        url = url.replace("intl-de/", "").strip()

        if "soundcloud.com" in url:
            return self._handle_soundcloud(url)
        if "spotify.com/playlist/" in url:
            return self._handle_spotify_playlist(url)
        if "spotify.com/album/" in url:
            return self._handle_spotify_album(url)
        if "spotify.com/track/" in url:
            return [self._handle_spotify_track(url)]
        if "youtube.com/playlist" in url or "youtube.com/watch" in url and "list=" in url:
            # Extrahiere den list= Parameter sicher
            params = dict(param.split("=", 1) for param in url.split("?")[1].split("&") if "=" in param)\
                if "?" in url else {}
            list_id = params.get("list")

            if list_id:
                playlist_url = f"https://www.youtube.com/playlist?list={list_id}"
                return self._handle_youtube_playlist(playlist_url)
            return self._handle_youtube_playlist(url)


        # Youtube Video, direkter Download
        if "watch?v=" in url or "youtu.be/" in url:

            # YouTube Automix, Rechtsklick in Video
            if "list=" in url:
                url = url.split("?list=")[0]

            return [self._handle_youtube_video(url)]

        # Falls es kein Link ist, suche
        return [self._handle_youtube_search(url)]

    def _handle_soundcloud(self, url) -> list[dict]:

        with yt_dlp.YoutubeDL(ydl_opts_extract(True)) as ydl:
            data_flat = ydl.extract_info(url, download=False)

        if data_flat.get("playlist_count", None):
            print("Playlist")

            if data_flat.get("playlist_count") >= 20:
                self.status_var.set("Die Datenextraktion von großen Playlists kann mehrere Minuten dauern.")

            with yt_dlp.YoutubeDL(ydl_opts_extract(False)) as ydl:
                data = ydl.extract_info(url, download=False)

        else:
            data = data_flat

        if data.get("entries", []):
            entries = []

            playlist_name = rename_title(data.get("album") or "")[0]  # Playlist und Album identisch

            entries_list = data.get("entries")
            for track_id, playlist_entry in enumerate(entries_list if isinstance(entries_list, list) else [], 1):
                album_raw = playlist_entry.get("album")
                album = rename_title(album_raw)[0] if album_raw else None

                title_raw = playlist_entry.get("track") or playlist_entry.get("title")
                artist_raw = playlist_entry.get("artist") or playlist_entry.get("uploader")

                title, artist = rename_title(title_raw or "", artist_raw or "")
                entry = _build_entry(
                    title=title,
                    artist=artist,
                    album=album,
                    url=playlist_entry.get("url") or "",
                    playlist=playlist_name,
                    track_number=track_id,
                    force_audio=True
                )

                entries.append(entry)
                continue
            print(entries)
            return entries

        elif data.get("title"):
            print("Video")

            title, artist = rename_title(data.get("title") or "", data.get("artist") or data.get("uploader") or "")

            entry = _build_entry(
                url=data.get("url") or "",
                title=title,
                artist=artist,
                force_audio=True
            )
            return [entry]

        raise Exception("Unbekannter Soundcloud-Link.")

    def _handle_spotify_playlist(self, url) -> list[dict]:
        spotify = self._get_spotify()
        data = spotify.playlist(url)
        name = rename_title(data.get("name") or "")[0]

        tracks = data["tracks"]
        items = tracks["items"]
        while tracks["next"]:
            tracks = spotify.next(tracks)
            items.extend(tracks["items"])

        def process_track(item_with_index):
            idx, t = item_with_index
            if not t["track"]:
                return None
            try:
                return self._handle_spotify_track(
                    t["track"]["external_urls"]["spotify"], name, track_number=idx
                )
            except Exception as e:
                print(f"Error processing Spotify track {idx}: {e}")
                return None

        self.status_var.set(f"Suche YouTube-Links für {len(items)} Tracks...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            entries = list(executor.map(process_track, enumerate(items, 1)))

        return [e for e in entries if e is not None]

    def _handle_spotify_album(self, url) -> list[dict]:
        data = self._get_spotify().album(url)
        name = rename_title(data.get("name") or "")[0]

        def process_track(t):
            try:
                return self._handle_spotify_track(t["external_urls"]["spotify"], name)
            except Exception as e:
                print(f"Error processing Spotify album track: {e}")
                return None

        self.status_var.set(f"Suche YouTube-Links für {len(data['tracks']['items'])} Tracks...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            entries = list(executor.map(process_track, data["tracks"]["items"]))

        return [e for e in entries if e is not None]

    def _handle_spotify_track(self, url, playlist_name="", track_number: int=None) -> dict | None:
        track = self._get_spotify().track(url)
        title, artist = rename_title(track.get("name") or "", track.get("artists", [{}])[0].get("name") or "")

        duration = track.get("duration_ms") // 1000

        try:
            yt_id = self._search_youtube(f"{artist} - {title}", duration=duration)
        except RuntimeError as e:
            self.status_var.set(str(e))
            return None

        return _build_entry(yt_id=yt_id,
                            title=title,
                            artist=artist,
                            playlist=playlist_name,
                            track_number=track_number,
                            force_audio=True)  # Spotify hat immer nur Audio


    def _handle_youtube_playlist(self, url) -> list[dict]:
        with yt_dlp.YoutubeDL(ydl_opts_extract()) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise RuntimeError("Playlist ist leer. (YouTube Auto-Mix wird nicht unterstützt)")

        playlist_name = rename_title(info.get("title") or "Playlist")[0]
        entries = []
        entries_list = info.get("entries")
        for idx, e in enumerate(entries_list if isinstance(entries_list, list) else [], 1):
            if not e:
                self.skipped.append(f"Position {idx} in \"{playlist_name}\": nicht verfügbar")
                continue
            raw_title = e.get("title") or ""
            if raw_title in ("[Private video]", "[Deleted video]") or e.get("availability") in (
                    "private", "needs_auth", "premium_only", "subscriber_only"):
                self.skipped.append(f"Position {idx} in \"{playlist_name}\": nicht verfügbar ({raw_title or 'unbekannt'})")
                continue
            channel = e.get("channel") if self.only_audio else None
            title, artist = rename_title(e.get("title") or "", channel_name=channel)
            entries.append(_build_entry(yt_id=e.get("id") or "", title=title, artist=artist,
                                        playlist=playlist_name, track_number=idx))
        return entries

    def _handle_youtube_video(self, url) -> dict:
        with yt_dlp.YoutubeDL(ydl_opts_extract()) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise RuntimeError("Konnte Video-Infos nicht laden.")
        channel = info.get("channel") if self.only_audio else None
        title, artist = rename_title(info.get("title") or "", channel_name=channel)
        if self.only_audio:
            title, artist, _ = verify_metadata(title, artist)
        return _build_entry(yt_id=info.get("id") or "", title=title, artist=artist)

    def _handle_youtube_search(self, query) -> dict:
        yt_id = self._search_youtube(query)
        return self._handle_youtube_video(f"https://www.youtube.com/watch?v={yt_id}")

    @staticmethod
    def _search_youtube(term: str, duration: int=None) -> str:

        results = yt_music_search.YoutubeSearch(term, max_results=1, yt_music=True, duration=duration).to_dict()

        if not results:
            raise RuntimeError(f"Kein Ergebnis für: {term}")
        return results[0]["id"]

    def download_entry(self, entry: dict):
        base_path = str(self.settings.get("main_path", ""))

        if entry["playlist"]:
            base_path = os.path.join(base_path, str(entry["playlist"]))
        os.makedirs(base_path, exist_ok=True)

        artist = entry.get("artist", "Unknown")
        title = entry.get("title", "Unknown")
        album = entry.get("album", "Unknown")
        track_number = entry.get("track_number", None)
        source = entry["id"] or entry["url"]  # If not ID then URL
        force_audio = entry.get("force_audio", False)
        is_audio = self.only_audio or force_audio

        save_path = os.path.join(str(base_path), f"{str(self.sanitize(artist))} - {str(self.sanitize(title))}")
        extension = ".mp3" if is_audio else ".mp4"
        final_file = save_path + extension

        if os.path.exists(final_file):
            self.status_var.set(f'"{title}" bereits vorhanden.')
            time.sleep(0.4)
            return

        # Verwende Audio-Optionen, wenn global only_audio oder force_audio für diese Quelle gesetzt ist
        opts = ydl_opts_audio(str(save_path)) if is_audio else ydl_opts_video(str(save_path))

        try:
            stime = time.time()
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([source])
            print(time.time() - stime)
        except DownloadCancelled as e:
            # Kein Retry: Livestream/Größenüberschreitung bleibt beim zweiten Versuch identisch.
            self.status_var.set(f'"{title}" übersprungen (zu groß/Livestream).')
            self.skipped.append(f"{title}: {e}")
            return
        except Exception as e:
            print(f"Download-Fehler: {e}")
            self.status_var.set(f"Fehler bei {title}. Wiederholen..")
            time.sleep(3)

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([source])

            except DownloadCancelled as e:
                self.status_var.set(f'"{title}" übersprungen (zu groß/Livestream).')
                self.skipped.append(f"{title}: {e}")
                return
            except Exception as e:
                print(f"Download-Fehler: {e}")
                self.status_var.set(f"Fehler bei {title}")
                self.skipped.append(f"{title}: Download fehlgeschlagen")
                return

        # Metadaten nur bei Audiodateien setzen
        if is_audio:

            try:
                audio = eyed3.load(final_file)
                if audio and audio.tag:
                    audio.tag.title = title
                    audio.tag.artist = artist
                    audio.tag.album = album
                    audio.tag.track_num = track_number
                    audio.tag.save()
            except Exception:
                print("Fehler beim Setzen der Metadaten.")


