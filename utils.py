import json

import emoji
from unidecode import unidecode


def load_settings():
    return json.load(open("settings.json", "r"))


settings = load_settings()
bad_chars = settings["bad_chars"]


def text_has_emoji(text):
    for character in text:
        if emoji.is_emoji(character):
            text = text.replace(character, "")
    return text


def rename_title(title: str):
    artist = "Unbekannt"
    title = title.lower()  # Konvertiert den Titel in Kleinbuchstaben
    title = text_has_emoji(title)  # Entfernt Emojis aus dem Titel
    title = unidecode(title)  # Entfernt Sonderzeichen aus dem Titel

    if " - " in title:
        newtitle = title.rsplit(" - ", maxsplit=1)
        artist = newtitle[0]
        title = newtitle[1]
    elif "-" in title:
        newtitle = title.rsplit("-", maxsplit=1)
        artist = newtitle[0]
        title = newtitle[1]

    for char in bad_chars:
        if char in title:
            title = title.replace(char, "")
        continue

    if title.__contains__("  "):
        title = title.replace("  ", " ")
    if title.startswith(" "):
        title = "".join(title.split(maxsplit=0))
    if title.endswith(" "):
        title = "".join(title.rsplit(maxsplit=0))
    title = title.title()
    artist = artist.title()
    return title, artist


def ydl_opts(title: str = "None"):
    path = download_path(title)
    print(path)
    ydl_opts1 = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",  # Audio und download_video kombiniert
        "quiet": True,
        "extract_flat": True,
        "noprogress": True,
        "ignoreerrors": True,
        "no_warnings": True,
        "outtmpl": path + ".%(ext)s"

    }
    ydl_opts2 = {
        "format": "bestaudio/best",
        "writethumbnail": True,
        "quiet": True,
        "extract_flat": True,
        "ingore_errors": True,
        "skip_unavailable_fragments": True,
        "no_warnings": True,
        "noprogress": True,
        "outtmpl": download_path(title),
        "postprocessors": [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
            {'key': 'FFmpegMetadata', 'add_metadata': 'True'},
            {'key': 'EmbedThumbnail', 'already_have_thumbnail': False, }
        ]
    }

    return ydl_opts1, ydl_opts2


def download_path(file_name: str):
    load_settings()
    path = settings["path"]
    return path + "/" + file_name


def write_to_json(setting, value):
    json.load(open("settings.json", "r"))
    settings[setting] = value

    with open("settings.json", "w") as write:
        json.dump(settings, write, indent=4)
