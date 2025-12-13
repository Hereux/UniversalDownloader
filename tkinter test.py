import json
import tkinter as tk
import tkinter.font as tkFont
from tkinter import NW

import utils
from ctypes import windll

from PIL import ImageTk, Image

windll.shcore.SetProcessDpiAwareness(1)


class App:

    def __init__(self, root: tk.Tk):
        # setting title
        self.video_download = None
        self.read_settings()

        root.title("YouTube/Spotify Downloader")
        # setting window size
        self.window_width = 800
        self.window_height = 400

        alignstr = '%dx%d+%d+%d' % (self.window_width, self.window_height, self.get_center_pos(self.window_width),
                                    self.get_center_pos(self.window_height))
        root.geometry(alignstr)
        root.resizable(width=False, height=False)
        root.configure(background="#4d4c4c")

        # Titel Label
        title_label = tk.Label(root)
        ft = tkFont.Font(family='Inter', size=25, weight="bold")
        title_label["font"] = ft
        title_label["fg"] = "#f5c6e5"
        title_label["bg"] = "#4d4c4c"
        title_label["justify"] = "center"
        title_label["text"] = "YouTube / Spotify Downloader"
        title_label.place(x=self.get_center_pos(800), y=30, width=800, height=70)
        self.title_label = title_label

        # Entwickelt von Label
        developed_label = tk.Label(root)
        ft = tkFont.Font(family='Inter', size=10, weight="bold")
        developed_label["font"] = ft
        developed_label["fg"] = "#c55b26"
        developed_label["bg"] = "#4d4c4c"
        developed_label["justify"] = "center"
        developed_label["text"] = "Entwickelt von Hereux."
        developed_label.place(x=600, y=360)

        canvas = tk.Canvas(root, bg="black", width=700, height=400)
        canvas.pack()

        background = tk.PhotoImage(file="empty.png")
        canvas.create_image(350, 200, image=background)

        character = tk.PhotoImage(file="yt_logo.png")
        canvas.create_image(30, 30, image=character)

        # Link Eingabe Feld
        link_entry = tk.Entry(root)
        ft = tkFont.Font(family='Inter', size=13)
        link_entry["font"] = ft
        link_entry["bg"] = "#4d4c4c"
        link_entry["fg"] = "#e77840"
        link_entry["justify"] = "center"
        link_entry["text"] = "Link oder Name des Videos eingeben: "
        print(self.get_center_pos(350))
        link_entry.place(x=self.get_center_pos(450), y=self.get_center_pos(height=-30), width=450, height=30)
        self.link_entry = link_entry

        # Download Button
        download_button = tk.Button(root)
        ft = tkFont.Font(family='Inter', size=12)
        download_button["font"] = ft
        download_button["bg"] = "#a72a3f"
        download_button["fg"] = "#dad2d8"
        download_button["activebackground"] = "#cb2a45"
        download_button["activeforeground"] = "#4d4c4c"
        download_button["justify"] = "center"
        download_button["text"] = "Downloade es!"
        download_button.place(x=self.get_center_pos(width=170), y=self.get_center_pos(height=-150), width=170,
                              height=40)
        download_button["command"] = self.on_download_button
        self.download_button = download_button

        # Checkbox für Video Download
        video_checkbox = tk.Checkbutton(root)
        ft = tkFont.Font(family='Inter', size=13)
        video_checkbox["font"] = ft
        video_checkbox["fg"] = "#c55b26"
        video_checkbox["bg"] = "#4d4c4c"
        video_checkbox["activebackground"] = "#4d4c4c"
        video_checkbox["activeforeground"] = "#c55b26"
        video_checkbox["justify"] = "center"
        video_checkbox["text"] = "Video herunterladen"
        video_checkbox.place(x=self.get_center_pos(750), y=self.get_center_pos(height=-150), width=220, height=40)
        video_checkbox["command"] = self.on_checkbox_click
        if self.video_download:
            video_checkbox.select()
        else:
            video_checkbox.deselect()
        self.video_checkbox = video_checkbox

    def on_download_button(self):
        url = self.link_entry.get()
        if not url:
            return
        print("Download")

    def get_center_pos(self, width=None, height=None):
        if width:
            return (self.window_width - width) / 2
        elif height:
            return (self.window_height - height) / 2
        else:
            return None

    def on_checkbox_click(self):
        print("command")
        self.read_settings()
        utils.write_to_json("video_download", not self.video_download)

    def read_settings(self):
        settings = json.load(open("settings.json", "r"))
        self.video_download: bool = settings["video_download"]


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
