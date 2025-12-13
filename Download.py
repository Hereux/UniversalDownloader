import os
import threading
import time
from datetime import datetime

import combine_video_and_audio
import eyed3
import spotipy
import youtube_search
import yt_dlp
from eyed3.core import Date
from utils import *

settings = json.load(open("settings.json", "r"))
path = settings["path"]


def video_download(title: str = None, artist: str = None, url: str = None, download_video: bool = False):
    print(download_video)
    # Sucht auf YouTube nach dem Video
    ytsearch_info = youtube_search.YoutubeSearch(title, max_results=1).to_dict()
    if len(ytsearch_info) <= 0:
        print("Video existiert nicht: " + title)
        return
    duration = ytsearch_info[0]["duration"]
    date = ytsearch_info[0]["publish_time"]
    url_ending = ytsearch_info[0]["url_suffix"]
    title = ytsearch_info[0]["title"]
    renamed = rename_title(title)
    title = renamed[0]

    # Wenn keine URL angegeben wurde, wird die URL aus den Suchergebnissen genommen
    if not url:
        url = f"https://www.youtube.com{url_ending}"

    if not type(date) == int:
        date = int(date.split(" ")[1])
    date = datetime.now().year - date

    if not artist:
        artist = renamed[1]
        artist = rename_title(artist)[0]

    video_opts, audio_opts = ydl_opts(title)
    ydl_audio = yt_dlp.YoutubeDL(audio_opts)

    if title + ".mp3" in os.listdir(path):  # Überprüft ob das Video bereits heruntergeladen wurde
        print(f"{title} | existiert bereits!")
        return

    try:
        ydl_audio.download([url])
    except:
        print(f"{title} | konnte nicht heruntergeladen werden!")
        return

    print(download_video, type(download_video))
    if download_video is True:
        print("Ich bin hier")
        try:
            ydl_video = yt_dlp.YoutubeDL(video_opts)
            ydl_video.download([url])
        except:
            print(f"{title} | konnte nicht heruntergeladen werden!")
            return

    song_path = download_path(title)

    song = eyed3.load(song_path + ".mp3")
    song.tag.title = title
    song.tag.artist = artist
    song.tag.recording_date = Date(date)
    song.tag.save()

    # if os.path.isfile(song_path + ".mp4"):
    #    combine_video_and_audio.combine(song_path)

    print(f"\nDas Video wurde heruntergeladen. \nName: {title} \nLänge: {duration} Minuten \nLink: {url}")


def spotify_download(spotipy: spotipy.Spotify, url, is_album, is_playlist=False):
    if is_album:
        print("Album")
        playlist = spotipy.album(url)
        playlist_name = rename_title(playlist["name"])[0]
        print(playlist_name)
        playlist_path = download_path(playlist_name)
        write_to_json("path", playlist_path)

        for track in playlist["tracks"]["items"]:
            artist = track["artists"][0]["name"]
            title = track["name"]

            print(f"Lade [{artist}: {title}] herunter...")
            video_download(title=f"{artist} {title}", artist=artist)

    elif is_playlist:
        print("Playlist")
        playlist = spotipy.playlist(url)
        playlist_name = rename_title(playlist["name"])[0]
        print(playlist_name)
        playlist_path = download_path(playlist_name)
        write_to_json("path", playlist_path)

        for track in playlist["tracks"]["items"]:
            track = track["track"]
            artist = track["artists"][0]["name"]
            title = track["name"]

            print(f"Lade [{artist}: {title}] herunter...")
            video_download(title=f"{artist} {title}", artist=artist)

    elif not is_playlist:
        track = spotipy.track(url)
        artist = track["artists"][0]["name"]
        title = track["name"]

        print(f"Lade [{artist}: {title}] herunter...")
        video_download(title=f"{artist} {title}", artist=artist)


def download_playlist(user_url, download_video=False):
    threads = []
    count = None
    numb: int = 0
    numb2: int = 0
    video_opts, audio_opts = ydl_opts()

    if ";" in user_url:
        playlist = user_url.rsplit(";", 1)
        playlist_url = playlist[0]
        count = int(playlist[1])
    else:
        playlist_url = user_url

    try:
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            playlist_infos = ydl.extract_info(playlist_url, download=False)
    except:
        print("Playlist konnte nicht gefunden werden!")
        print("Vielleicht ist die Playlist privat?")
        return
    print("Playlist: ", playlist_infos["title"])
    print("Videos in der Playlist: ", len(playlist_infos["entries"]))

    playlist_title = playlist_infos["title"]
    playlist_path = download_path(playlist_title)
    if not os.path.exists(playlist_path):
        os.makedirs(playlist_path)
    write_to_json("path", playlist_path)

    if not count:
        count = int(len(playlist_infos["entries"]))

    for video_info in playlist_infos["entries"]:
        numb += 1
        numb2 += 1
        threads.append(threading.Thread(
            target=video_download, args=(video_info["title"], None, video_info["url"], download_video))
        )
        # Thread wird erstellt und in die Liste hinzugefügt
        time.sleep(0.1)

        if numb == 20 or numb2 == count:
            for thread in threads:
                thread.start()  # Startet alle Threads
            for thread in threads:
                thread.join()  # Wartet bis alle Threads fertig sind
                print(numb2, "/", count)
            threads.clear()
            numb = 0

    print("Playlist wurde heruntergeladen!")

    for x in os.listdir(playlist_path):
        if not x.endswith(".mp3") and not x.endswith(".mp4"):
            print(x)
            os.remove(path + "/" + x)
