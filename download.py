import os
import queue
import threading
import time

import eyed3
import ttkbootstrap as tb
import yt_dlp
from sclib import SoundcloudAPI, Track, Playlist
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

import yt_music_search
from bin.utils import rename_title, ydl_opts_extract, ydl_opts_audio, ydl_opts_video, verify_metadata


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

        self.current = 0
        self.total = 0

        self.sc_api = SoundcloudAPI(client_id=settings["soundcloud_id"])

        self.spotify = Spotify(auth_manager=SpotifyOAuth(
            client_id=settings["spotipy_id"],
            client_secret=settings["spotipy_secret"],
            redirect_uri="http://127.0.0.1:8888/callback",
            scope="playlist-read-private"
        ))

        self.start()

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
            self._update_progress()

            try:
                entries = self.identify_url(url)
                self.total = len(entries)
                self._update_progress()
            except RuntimeError as e:
                self.status_var.set(str(e))
                continue
            except Exception as e:
                self.status_var.set(f"Unbekannter Fehler: {e}")
                continue

            for entry in entries:
                if not self.running:
                    break
                self._wait_if_paused()
                self.status_var.set(f'Lade "{entry["title"]}" herunter...')
                self.download_entry(entry)
                self.current += 1
                self._update_progress()

            self.status_var.set(f"Download abgeschlossen.")

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

    def identify_url(self, url: str):
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
            params = dict(param.split("=", 1) for param in url.split("?")[1].split("&") if "=" in param)
            list_id = params.get("list")
            if list_id:
                playlist_url = f"https://www.youtube.com/playlist?list={list_id}"
                return self._handle_youtube_playlist(playlist_url)
            return self._handle_youtube_playlist(url)

        if "watch?v=" in url or "youtu.be/" in url:
            return [self._handle_youtube_video(url)]

        if "https://" in url:
            import urllib.request
            urllib.request.urlretrieve(url, 'video_name.mp4')
            return None
        return [self._handle_youtube_search(url)]

    def _handle_soundcloud(self, url):
        try:
            result = self.sc_api.resolve(url)
        except Exception:
            raise RuntimeError("Ungültige Soundcloud-URL")

        if isinstance(result, Track):
            title, artist = rename_title(result.title, result.artist)
            return [self._build_entry(url=url, title=title, artist=artist, force_audio=True)]

        if isinstance(result, Playlist):
            playlist_name = rename_title(result.title)[0]
            return [self._build_entry(url=t.permalink_url,
                                      title=rename_title(t.title, t.artist)[0],
                                      artist=rename_title(t.title, t.artist)[1],
                                      playlist=playlist_name,
                                      track_number=i + 1,
                                      force_audio=True)
                    for i, t in enumerate(result.tracks)]
        raise RuntimeError("Soundcloud-URL ist kein Track oder Playlist")

    def _handle_spotify_playlist(self, url):
        data = self.spotify.playlist(url)
        name = rename_title(data["name"])[0]
        return [self._handle_spotify_track(t["track"]["external_urls"]["spotify"], name)
                for t in data["tracks"]["items"] if t["track"]]

    def _handle_spotify_album(self, url):
        data = self.spotify.album(url)
        name = rename_title(data["name"])[0]
        return [self._handle_spotify_track(t["external_urls"]["spotify"], name) for t in data["tracks"]["items"]]

    def _handle_spotify_track(self, url, playlist_name=""):
        track = self.spotify.track(url)
        title, artist = rename_title(track["name"], track["artists"][0]["name"])
        yt_id = self._search_youtube(f"{artist} - {title}")
        return self._build_entry(yt_id=yt_id,
                                 title=title,
                                 artist=artist,
                                 playlist=playlist_name,
                                 track_number=track.get("track_number", 1),
                                 force_audio=True)  # Spotify hat immer nur Audio

    def _handle_youtube_playlist(self, url):
        with yt_dlp.YoutubeDL(ydl_opts_extract()) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise RuntimeError("Playlist ist leer. (YouTube Auto-Mix wird nicht unterstützt)")

        playlist_name = rename_title(info.get("title", "Playlist"))[0]
        entries = []
        for idx, e in enumerate(info.get("entries", []), 1):
            if not e:
                continue
            channel = e.get("channel") if self.only_audio else None
            title, artist = rename_title(e["title"], channel_name=channel)
            entries.append(self._build_entry(yt_id=e["id"], title=title, artist=artist,
                                             playlist=playlist_name, track_number=idx))
        return entries

    def _handle_youtube_video(self, url):
        with yt_dlp.YoutubeDL(ydl_opts_extract()) as ydl:
            info = ydl.extract_info(url, download=False)
        channel = info.get("channel") if self.only_audio else None
        title, artist = rename_title(info["title"], channel_name=channel)
        if self.only_audio:
            title, artist, _ = verify_metadata(title, artist)
        return self._build_entry(yt_id=info["id"], title=title, artist=artist)

    def _handle_youtube_search(self, query):
        yt_id = self._search_youtube(query)
        return self._handle_youtube_video(f"https://www.youtube.com/watch?v={yt_id}")

    def _search_youtube(self, term: str) -> str:
        results = yt_music_search.YoutubeSearch(term, max_results=1, yt_music=True).to_dict()
        if not results:
            raise RuntimeError(f"Kein Ergebnis für: {term}")
        return results[0]["id"]

    def _build_entry(self, yt_id="", url="", title="", artist="", playlist="", track_number=1, force_audio=False):
        """
        force_audio: True, wenn die Quelle nur Audio liefert (Spotify/Soundcloud)
        """
        return {
            "id": yt_id,
            "url": url,
            "title": title,
            "artist": artist or "Unbekannt",
            "playlist": playlist,
            "track_number": track_number,
            "force_audio": force_audio
        }

    def download_entry(self, entry: dict):
        base = self.settings["main_path"]
        if entry["playlist"]:
            base = os.path.join(base, entry["playlist"])
        os.makedirs(base, exist_ok=True)

        save_path = os.path.join(base, f"{entry['artist']} - {entry['title']}")
        extension = ".mp3" if (self.only_audio or entry.get("force_audio", False)) else ".mp4"
        final_file = save_path + extension

        if os.path.exists(final_file):
            self.status_var.set(f'"{entry["title"]}" bereits vorhanden.')
            time.sleep(0.8)
            return

        # Verwende Audio-Optionen, wenn global only_audio oder force_audio für diese Quelle gesetzt ist
        use_audio = self.only_audio or entry.get("force_audio", False)
        opts = ydl_opts_audio(save_path) if use_audio else ydl_opts_video(save_path)
        source = entry["id"] or entry["url"]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([source])

            # Metadaten nur bei Audio setzen
            if use_audio:
                try:
                    audio = eyed3.load(final_file)
                    if audio and audio.tag:
                        audio.tag.title = entry["title"]
                        audio.tag.artist = entry["artist"]
                        audio.tag.track_num = entry["track_number"]
                        audio.tag.save()
                except Exception:
                    pass

        except Exception as e:
            print(f"Download-Fehler: {e}")
            self.status_var.set(f"Fehler bei {entry['title']}")
