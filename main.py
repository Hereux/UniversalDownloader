import asyncio
import os
import queue
from datetime import datetime

from mpmath.ctx_mp_python import return_mpc

import yt_music_search
import eyed3
import spotipy
import yt_dlp

from bin import utils
import tkinter as tk
from tkinter import Tk, Label, Entry, StringVar


class Downloader:
    def __init__(self, loop, settings, path):
        super().__init__()
        self.loop = loop
        self.path = path
        self.settings = settings
        self.spotipy = spotipy.Spotify(
            auth_manager=spotipy.SpotifyOAuth(
                client_id=self.settings["spotipy_id"],
                client_secret=self.settings["spotipy_secret"],
                redirect_uri="http://127.0.0.1:8888/callback"
            )
        )

    @staticmethod
    def url_identify(orig_url: str, download_video: bool = True):
        download_data = {
            "type": "",
            "download_url": "",
            "download_video": download_video,
        }

        # YouTube Video mit Index
        if orig_url.__contains__("watch?") and orig_url.__contains__("&list="):
            print("URL wurde als YouTube Video mit Index erkannt.")
            download_data["type"] = "yt_video"
            download_data["download_url"] = orig_url.split("&list=")[0]
            pass

        # YouTube Playlist
        elif orig_url.__contains__("playlist?list=") or orig_url.__contains__("list="):
            print("URL wurde als YouTube Playlist erkannt.")
            download_data["type"] = "yt_playlist"
            download_data["download_url"] = orig_url
            pass

        # YouTube Video
        elif orig_url.__contains__("watch?v="):
            print("URL wurde als YouTube Video erkannt.")
            download_data["type"] = "yt_video"
            download_data["download_url"] = orig_url
            pass

        # Spotify Playlist
        elif orig_url.__contains__("spotify.com/") and orig_url.__contains__("playlist/"):
            print("URL wurde als Spotify Playlist erkannt.")
            download_data["type"] = "spot_playlist"
            download_data["download_url"] = orig_url
            pass

        elif orig_url.__contains__("spotify.com/") and orig_url.__contains__("album/"):
            print("URL wurde als Spotify Album erkannt.")
            download_data["type"] = "spot_album"
            download_data["download_url"] = orig_url
            pass

        # Spotify Song
        elif orig_url.__contains__("spotify.com/"):
            print("URL wurde als Spotify Song erkannt.")
            download_data["type"] = "spot_song"
            download_data["download_url"] = orig_url
            pass

        # Keine gültige URL
        else:
            print("URL wurde nicht erkannt, suche auf YouTube.")
            download_data["type"] = "yt_search"
            download_data["search_title"] = orig_url

        return download_data

    def extract_data(self, download_data: dict):
        playlist_title = "/"

        # Sucht auf YouTube nach dem Lied. Falls Download_video True ist, wird nach einem Song gesucht.
        if download_data["type"] == "yt_search":
            ytsearch_info = yt_music_search.YoutubeSearch(download_data["search_title"], 1,
                                                          yt_music=download_data["download_video"]).to_dict()

            if len(ytsearch_info) <= 0:
                print("Video existiert nicht: " + download_data["search_title"])
                return None

            url_suffix = ytsearch_info[0]["url_suffix"]

            # Wenn das Suchergebnis eine Playlist/Mix ist, wird nur das Video genommen.
            if "&list=" in url_suffix:
                url_suffix = url_suffix.split("&list=")[0]
            url = "https://youtube.com" + url_suffix
            download_data["download_url"] = url
            download_data["type"] = "yt_video"
            print("Video wurde auf YouTube gesucht.")

        else:
            url = download_data["download_url"]

        # Informationen auslesen
        with yt_dlp.YoutubeDL({"extract_flat": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        if download_data["type"] == "yt_playlist":
            download_data["playlist_title"] = info["title"]
            download_data["entries"] = info["entries"]
            return download_data

        title = info["title"]
        renamed_title = utils.rename_title(title)
        path_title = f"{renamed_title[1]} - {renamed_title[0]}"

        if download_data.get("playlist_title", None):
            playlist_title = "/" + download_data["playlist_title"] + "/"

        path = self.settings["main_path"] + playlist_title + path_title

        download_data["title"] = renamed_title[0]
        download_data["artist"] = renamed_title[1]
        download_data["video_path"] = path
        download_data["duration"] = info["duration"]
        download_data["channel"] = info["uploader"]
        download_data["date"] = info["upload_date"]

        print(download_data)
        return download_data

    def download_yt_video(self, download_data: dict):

        date: str = download_data["date"]
        year, month, day = None, None, None

        if len(date) >= 4:
            year = int(date[:4])
        if len(date) >= 6:
            month = int(date[4:6])
        if len(date) == 8:
            day = int(date[6:8])

        path_ = download_data["video_path"]

        if download_data["download_video"]:
            if os.path.isfile(path_ + ".mp4"):
                print("Video existiert bereits: " + download_data["title"])
                print("Überspringe Download.")
                return

            ydl = yt_dlp.YoutubeDL(utils.ydl_opts_video(path_))
            ydl.download(download_data["download_url"])
        else:
            if os.path.isfile(path_ + ".mp3"):
                print("Video existiert bereits: " + download_data["title"])
                print("Überspringe Download.")
                return

            ydl = yt_dlp.YoutubeDL(utils.ydl_opts_audio(path_))
            ydl.download(download_data["download_url"])

            song = eyed3.load(path_ + ".mp3")
            if not song:
                print("Fehler: Video konnte nicht geladen werden!")
                return
            song.tag.title = download_data["title"]
            song.tag.artist = download_data["artist"]
            song.tag.recording_date = eyed3.core.Date(year, month, day)
            song.tag.save()


class Main:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.settings = utils.load_settings()
        self.path = f"../Downloads/{datetime.now().strftime('%d.%m.%Y')}"

        self.loop = loop
        self.spotipy_id = self.settings["spotipy_id"]
        self.spotipy_secret = self.settings["spotipy_secret"]
        self.root = Tk()
        self.paste_url = StringVar()
        self.download_queue = queue.Queue()
        self.running = True

        utils.write_to_json("path", self.path)

        self.downloader = Downloader(self.loop, self.settings, self.path)

    async def window_loop(self):
        self.root.geometry('600x200')
        self.root.title('Youtube Video Downloader')

        Label_1 = Label(self.root, text="YouTube-Link hier einfügen", font=("bold", 20))
        Label_1.place(x=150, y=20)

        Label_2 = Label(self.root, text="Entwickelt von Hereux.", width=105, font=("bold", 9))
        Label_2.place(x=140, y=150)

        pastelink = Entry(self.root, width=60, textvariable=self.paste_url)
        pastelink.place(x=140, y=80)

        tk.Button(self.root, text="Video herunterladen", width=20, bg="green", fg="white",
                  command=self.video_press).place(x=40, y=110)
        tk.Button(self.root, text="Download abbrechen", width=20, bg="green", fg="white",
                  command=self.cancel_press).place(x=400, y=110)

        tk.Button(self.root, text="Downloader schließen", width=20, bg='green', fg="white",
                  command=self.exit).place(x=220, y=110)

        while self.running:
            self.root.update_idletasks()
            self.root.update()
            await asyncio.sleep(0.01)

        self.root.destroy()
        return

    async def downloader_loop(self):
        while self.running:
            try:
                url = self.download_queue.get(block=True, timeout=-1)
                print("Got new URL from Queue:", url)
                self.downloader.download_video(url, download_video=False)  # get from queue? button?
            except queue.Empty:
                await asyncio.sleep(0.1)
        return

    def video_press(self):
        print("urL:", self.paste_url.get())
        self.download_queue.put(self.paste_url.get())
        return

    def cancel_press(self):

        return

    def exit(self):
        self.running = False


if __name__ == "__main__":
    downloader = Downloader(asyncio.new_event_loop(), utils.load_settings(),
                            f"../Downloads/{datetime.now().strftime('%d.%m.%Y')}")
    orig_url = "https://open.spotify.com/intl-de/track/1YqVbH2fw8mz6JaPQiSUnl?si=33d09d40a6d7427a"
    download_data = downloader.url_identify(orig_url, False)
    print(download_data)

    if download_data["type"] == "yt_video":
        download_data = downloader.extract_data(download_data)
        downloader.download_yt_video(download_data)

    elif download_data["type"] == "yt_playlist":
        download_data = downloader.extract_data(download_data)
        entry_download_data = download_data.copy()
        entry_download_data["type"] = "yt_video"

        for entry in download_data["entries"]:
            entry_download_data["download_url"] = entry["url"]
            entry_download_data = downloader.extract_data(entry_download_data)
            downloader.download_yt_video(entry_download_data)

    elif download_data["type"] == "spot_song":
        pass

if __name__ == "__mdain__":
    loop = asyncio.new_event_loop()
    main = Main(loop)
    loop.create_task(main.window_loop())
    loop.create_task(main.downloader_loop())
    loop.run_forever()
    loop.close()
