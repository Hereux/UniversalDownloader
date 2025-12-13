import threading
import time
import ffmpeg
import os


# Import everything needed to edit download_video clips


def thready(folder, subfolder_path):
    global audio_clip
    global video_clip
    for file in os.listdir(subfolder_path):
        if file.endswith(".mp3"):
            audio_clip = subfolder_path + "/" + file
            audio_clip = ffmpeg.input(audio_clip)
        else:
            video_clip = subfolder_path + "/" + file
            video_clip = ffmpeg.input(video_clip)
    teest = ffmpeg.concat(video_clip, audio_clip, v=1, a=1).output(f"{subfolder_path}/{folder}.mp4")
    ffmpeg.run(teest, quiet=True, overwrite_output=True)


def combine_folder(folder_name):
    for folder in os.listdir(f"Downloads/{folder_name}"):
        subfolder_path = f"Downloads/{folder_name}/{folder}"
        '''
        os.remove(subfolder_path + f"/{folder}.mp4")
        '''
        if len(os.listdir(subfolder_path)) >= 2:
            thrd = threading.Thread(target=thready, args=(folder, subfolder_path))

            thrd.start()
            print(thrd.is_alive())


def combine(download_path):
    audio_clip = ffmpeg.input(download_path + ".mp3")
    video_clip = ffmpeg.input(download_path + ".mp4")

    new_file = ffmpeg.concat(video_clip, audio_clip, v=1, a=1).output(download_path + "_combined.mp4")
    ffmpeg.run(new_file, quiet=True, overwrite_output=True)
