import yt_dlp
import os
import requests
from tqdm import tqdm
import eyed3
from typing import Any, Dict
from colorama import Fore, init
import argparse
import json

# Initialize colorama
init(autoreset=True)

CONFIG_FILE = 'config.json'

def load_config() -> Dict[str, Any]:
    """Load configuration from a file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to a file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_valid_download_location() -> str:
    """Prompt the user to enter a valid download location."""
    while True:
        base_download_location = input(Fore.WHITE + "Enter the base download location: ")
        if os.path.isdir(base_download_location):
            return base_download_location
        else:
            print(Fore.RED + "Invalid download location. Please enter a valid directory path.")

# Argument parser setup
parser = argparse.ArgumentParser(description="Download audio from YouTube.")
parser.add_argument('-f', '--folder', type=str, help='Set the base download location.')
args = parser.parse_args()

# Load existing configuration
config = load_config()

# Set the base download location
if args.folder:
    if os.path.isdir(args.folder):
        base_download_location = args.folder
        config['base_download_location'] = base_download_location
        save_config(config)
    else:
        print(Fore.RED + "Invalid download location provided with -f argument.")
        base_download_location = get_valid_download_location()
        config['base_download_location'] = base_download_location
        save_config(config)
elif 'base_download_location' not in config:
    base_download_location = get_valid_download_location()
    config['base_download_location'] = base_download_location
    save_config(config)
else:
    base_download_location = config['base_download_location']

print(Fore.GREEN + f"Using download location: {base_download_location}")
print(Fore.LIGHTBLACK_EX + "To change the download location, run the script with the -f argument.")

class Logger:
    """Custom logger for yt-dlp."""
    def debug(self, _msg: str) -> None:
        pass

    def warning(self, _msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        # Skip private video messages and show them only if needed
        if 'Private video' in msg or 'Sign in if you\'ve been granted access' in msg:
            pass
        else:
            print(Fore.RED + msg)


def download_progress_hook(d: Dict[str, Any]) -> None:
    """Progress hook to display download progress using tqdm."""
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
        print(Fore.GREEN + '󱁩 Download completed.')
        print(Fore.YELLOW + ' Converting ...')


def embed_metadata_and_thumbnail(file_path: str, artist: str, album: str, title: str, thumbnail_url: str) -> None:
    """Embeds metadata and a thumbnail into the downloaded mp3 file."""
    if not os.path.exists(file_path):
        print(Fore.RED + f"File not found: {file_path}")
        return

    audiofile = eyed3.load(file_path)
    if audiofile and audiofile.tag:
        audiofile.tag.artist = artist
        audiofile.tag.album = album
        audiofile.tag.title = title

        # Download and embed thumbnail
        try:
            response = requests.get(thumbnail_url)
            response.raise_for_status()
            image_data = response.content

            mime_type = 'image/png' if thumbnail_url.lower().endswith('.png') else 'image/jpeg'
            audiofile.tag.images.set(3, image_data, mime_type, u"Cover")
        except requests.RequestException as e:
            print(Fore.RED + f"Error downloading thumbnail: {e}")

        audiofile.tag.save()
    else:
        print(Fore.RED + f"Failed to load file or tag is None: {file_path}")


def download_audio(info_dict: Dict[str, Any], playlist_title: str = "") -> None:
    """Downloads audio and embeds metadata for a single track."""
    global pbar
    artist = info_dict.get('uploader', 'Unknown Artist').replace('/', '')
    album = info_dict.get('album', 'Unknown Album').replace('/', '').replace(':', '_')
    title = info_dict.get('title', 'Unknown Title').replace('/', '')
    thumbnail_url = info_dict.get('thumbnail')

    # Create the download directory
    download_location = os.path.join(base_download_location, artist)
    if playlist_title:
        download_location = os.path.join(download_location, playlist_title)
        album = playlist_title
    os.makedirs(download_location, exist_ok=True)

    # Set yt-dlp options
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'logger': Logger(),
        'progress_hooks': [download_progress_hook],
        'outtmpl': os.path.join(download_location, '%(title)s.%(ext)s')
    }

    # Handle file size estimation
    file_size = info_dict.get('filesize') or info_dict.get('filesize_approx', 0)
    pbar = tqdm(total=file_size, unit='B', unit_scale=True, desc=title, colour='white')

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([info_dict['webpage_url']])
        downloaded_file = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')

        if thumbnail_url:
            embed_metadata_and_thumbnail(downloaded_file, artist, album, title, thumbnail_url)
        else:
            print(Fore.YELLOW + "No thumbnail URL found for this video.")
            embed_metadata_and_thumbnail(downloaded_file, artist, album, title, "")

        print(Fore.GREEN + f"󱣫 Successfully downloaded : {downloaded_file}")


def process_url(video_url: str) -> None:
    """Processes a given URL, determining if it's a playlist or single video, and downloads accordingly."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'logger': Logger(),
        'quiet': True,
        'ignoreerrors': True,
        'progress_hooks': [download_progress_hook],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            if info_dict is not None:
                
                # Check if the URL is a playlist or a single video
                if 'entries' in info_dict:
                    playlist_title = info_dict.get('title', 'Unknown Playlist')
                    print(Fore.CYAN + f"Downloading playlist: {playlist_title}")
                    skipped_videos = 0
                    for entry in info_dict['entries']:
                        if entry is None:
                            skipped_videos += 1
                            continue
                        download_audio(entry, playlist_title)
                    if skipped_videos > 0:
                        print(Fore.YELLOW + f"Skipped {skipped_videos} private or unavailable videos.")
                else:
                    print(Fore.CYAN + f"Downloading video: {info_dict.get('title', 'Unknown Title')}")
                    download_audio(info_dict)
            else:
                print(Fore.RED + "Error: Failed to retrieve video information")
    except yt_dlp.DownloadError as e:
        print(Fore.RED + f"Error downloading video: {e}")
    except Exception as e:
        print(Fore.RED + f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()


def main() -> None:
    """Main function to prompt user input and download audio from YouTube."""
    try:
        while True:
            video_url = input("\nEnter video or playlist link: ")
            if not video_url:
                print(Fore.GREEN + "\nGoodbye 👋")
                break
            process_url(video_url)
    except KeyboardInterrupt:
        print(Fore.GREEN + "\nGoodbye 👋")

if __name__ == "__main__":
    main()
