from tkinter import *
from Download import *

root = Tk()
root.geometry('600x200')
root.title('Youtube Video Downloader')

Label_1 = Label(root, text="YouTube-Link hier einfügen", font=("bold", 20))
Label_1.place(x=150, y=20)

Label_2 = Label(root, text="Entwickelt von Hereux.", width=105, font=("bold", 9))
Label_2.place(x=140, y=150)

button_result = StringVar()

pastelink = Entry(root, width=60, textvariable=button_result)
pastelink.place(x=140, y=80)

settings = json.load(open("settings.json", "r"))
spotipy_id = settings["spotipy_id"]
spotipy_secret = settings["spotipy_secret"]


class YouTubeDownloadScript:
    def __init__(self):
        self.path = f"../Downloads/{datetime.now().strftime('%d.%m.%Y')}"
        write_to_json("path", self.path)

        self.is_playlist = False
        self.is_spotify = False
        self.is_album = False

        # Initialisierung von Spotipy
        self.spotipy = spotipy.Spotify(
            auth_manager=spotipy.SpotifyOAuth(client_id=spotipy_id, client_secret=spotipy_secret)
        )

        # Initialisierung von YoutubeDL
        self.ydl_opts = ydl_opts()
        self.ydl_audio = yt_dlp.YoutubeDL(self.ydl_opts[0])
        self.ydl_video = yt_dlp.YoutubeDL(self.ydl_opts[1])

        if not os.path.exists(path):
            os.makedirs(path)

    def download_video(self, url, download_video: bool = False):
        self.path = f"../Downloads/{datetime.now().strftime('%d.%m.%Y')}"
        write_to_json("path", self.path)

        url = self.url_identify(url)

        if self.is_spotify:  # Spotify (Titel oder Playlist)
            spotify_download(self.spotipy, url, is_album=self.is_album, is_playlist=self.is_playlist)
        elif self.is_playlist:  # YouTube Playlist
            download_playlist(url, download_video=download_video)
        elif url:  # YouTube Video
            print(download_video)
            video_download(url, download_video=download_video)
        else:
            print("Fehler: URL konnte nicht erkannt werden!")
            return

    def url_identify(self, url):
        self.is_playlist = False
        self.is_spotify = False

        # YouTube Playlist mit Index
        if url.__contains__("&index="):
            self.is_playlist = True
            playlist_infos = self.ydl_audio.extract_info(url, download=False)  # Extrahiert Infos über die Playlist
            url = playlist_infos["url"]
            pass

        # YouTube Playlist
        elif url.__contains__("playlist?list="):
            self.is_playlist = True
            pass

        # YouTube Video
        elif url.__contains__("youtube.com/watch?") or url.__contains__("youtu.be/") or \
                url.__contains__("/shorts"):
            liste = self.ydl_audio.extract_info(url, download=False)  # Extrahiert Infos über das Video
            url = liste["fulltitle"]
            pass

        # Spotify Playlist
        elif url.__contains__("spotify.com/") and url.__contains__("playlist/"):
            self.is_spotify = True
            self.is_playlist = True
            pass

        elif url.__contains__("spotify.com/") and url.__contains__("album/"):
            print("Album")
            self.is_spotify = True
            self.is_album = True
            pass

        # Spotify Song
        elif url.__contains__("spotify.com/"):
            self.is_spotify = True
            pass

        # Keine gültige URL
        else:
            print("Fehler: URL konnte nicht erkannt werden!")
            url = None

        if self.is_spotify:
            url = url.split("?")[0]
            if url.__contains__("intl-de"):
                url = url.replace("intl-de/", "")

        return url


yts = YouTubeDownloadScript()

Button(root, text="Video", width=20, bg="green", fg="white",
       command=lambda: yts.download_video(url=button_result.get(), download_video=settings["video_download"])).place(
    x=40, y=110)
Button(root, text="Playlist", width=20, bg="green", fg="white",
       command=lambda: yts.download_video(url=button_result.get(), download_video=settings["video_download"])).place(
    x=400, y=110)

Button(root, text="Video herunterladen", width=20, bg='green', fg="white").place(x=220, y=110)
root.mainloop()
