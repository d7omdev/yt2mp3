import yt_dlp
import os
import requests
from tqdm import tqdm
import eyed3
from typing import Any, Dict
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Set the base download location
base_download_location = '/home/d7om/Music/YT'

class MyLogger:
    def debug(self, _msg: str) -> None:
        pass

    def warning(self, _msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        print(Fore.RED + msg)

def my_hook(d: Dict[str, Any]) -> None:
    global pbar
    if 'status' not in d:
        return
    
    if d['status'] == 'downloading':
        if 'downloaded_bytes' in d and isinstance(pbar, tqdm):
            try:
                pbar.update(d['downloaded_bytes'] - pbar.n)
            except Exception as e:
                print(Fore.RED + f"Error updating progress bar: {e}")
    elif d['status'] == 'finished':
        if isinstance(pbar, tqdm):
            pbar.close()
        print(Fore.GREEN + 'Done downloading, now converting ...')

def add_metadata_and_thumbnail(file_path: str, artist: str, album: str, title: str, thumbnail_url: str) -> None:
    if not os.path.exists(file_path):
        print(Fore.RED + f"File not found: {file_path}")
        return

    audiofile = eyed3.load(file_path)
    if audiofile is not None and audiofile.tag is not None:
        audiofile.tag.artist = artist
        audiofile.tag.album = album
        audiofile.tag.title = title

        # Download and embed thumbnail
        try:
            response = requests.get(thumbnail_url)
            response.raise_for_status()
            image_data = response.content
            
            # Determine image type
            if thumbnail_url.lower().endswith('.png'):
                mime_type = 'image/png'
            else:
                mime_type = 'image/jpeg'  # Default to JPEG
            
            audiofile.tag.images.set(3, image_data, mime_type, u"Cover")
            print(Fore.GREEN + "Thumbnail embedded successfully.")
        except requests.RequestException as e:
            print(Fore.RED + f"Error downloading thumbnail: {e}")
        
        audiofile.tag.save()
    else:
        print(Fore.RED + f"Failed to load file or tag is None: {file_path}")

def download_audio_from_youtube() -> None:
    global pbar
    while True:
        video_url = input(Fore.CYAN + "Enter video or playlist link (or press Enter to exit): ")
        if not video_url:
            break

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'logger': MyLogger(),
            'progress_hooks': [my_hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(video_url, download=False)
                if info_dict is not None:
                    if 'entries' in info_dict:  # It's a playlist
                        playlist_title = info_dict.get('title', 'Unknown Playlist')
                        for entry in info_dict['entries']:
                            download_track(entry, playlist_title)
                    else:  # It's a single video
                        download_track(info_dict)
                else:
                    print(Fore.RED + "Error: info_dict is None")
        except yt_dlp.DownloadError as e:
            print(Fore.RED + f"Error downloading video: {e}")
        except Exception as e:
            print(Fore.RED + f"An unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()

def download_track(info_dict: Dict[str, Any], playlist_title: str = "") -> None:
    global pbar
    artist = info_dict.get('uploader', 'Unknown Artist')
    album = info_dict.get('album', 'Unknown Album')
    title = info_dict.get('title', 'Unknown Title')
    thumbnail_url = info_dict.get('thumbnail')

    download_location = os.path.join(base_download_location, artist)
    if playlist_title:
        download_location = os.path.join(download_location, playlist_title)
    if not os.path.exists(download_location):
        os.makedirs(download_location)

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'logger': MyLogger(),
        'progress_hooks': [my_hook],
        'outtmpl': os.path.join(download_location, '%(title)s.%(ext)s')
    }

    file_size = info_dict.get('filesize')
    if file_size is None:
        file_size = info_dict.get('filesize_approx', 0)

    pbar = tqdm(total=file_size, unit='B', unit_scale=True, desc=title)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([info_dict['webpage_url']])

        downloaded_file = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')

        if thumbnail_url:
            add_metadata_and_thumbnail(downloaded_file, artist, album, title, thumbnail_url)
        else:
            print(Fore.YELLOW + "No thumbnail URL found for this video.")
            add_metadata_and_thumbnail(downloaded_file, artist, album, title, "")

        print(Fore.GREEN + f"Successfully downloaded and processed: {downloaded_file}")

if __name__ == "__main__":
    download_audio_from_youtube()
