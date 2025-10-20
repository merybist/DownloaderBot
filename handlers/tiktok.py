import os
import uuid
import requests
import random
import string
import asyncio
import subprocess
from moviepy import VideoFileClip

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, InputMediaPhoto
)
from aiogram.types.input_file import FSInputFile
from yt_dlp import YoutubeDL

from main import bot, logging

# -------- CONFIG --------
DOWNLOADS_FOLDER = "services/downloads"
router = Router()
callback_store = {}  
callback_store_sizes = {}  

# -------- UTILS --------
def ensure_downloads_folder_exists(folder: str = DOWNLOADS_FOLDER):
    if not os.path.exists(folder):
        os.makedirs(folder)

def sanitize_filename(filename: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in filename)

async def generate_random_string(length: int = 8) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# -------- MP3 CONVERSION --------
async def get_audio_stream(url: str) -> tuple[str | None, str | None, str | None]:
    try:
        ensure_downloads_folder_exists()
        temp_video = f"{uuid.uuid4()}.mp4"
        output_mp3 = temp_video.replace(".mp4", ".mp3")

        ydl_opts = {
            "quiet": True,
            "format": "mp4",
            "outtmpl": temp_video,
            "noplaylist": True
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio")

        subprocess.run(
            ["ffmpeg", "-i", temp_video, "-vn", "-ab", "192k", "-ar", "44100", "-y", output_mp3],
            check=True
        )
        os.remove(temp_video)
        return output_mp3, title, None
    except Exception as e:
        logging.error(f"Error converting to MP3: {e}")
        return None, None, f"❌ Conversion failed: {e}"

# -------- TIKTOK DOWNLOADER CLASS ---------
class DownloaderTikTok:
    def __init__(self, output_dir: str, filename: str):
        self.output_dir = output_dir
        self.filename = filename

    async def download_video(self, url_or_id: str) -> bool:
        return await asyncio.to_thread(self._download_video_sync, url_or_id)

    def _download_video_sync(self, url_or_id: str) -> bool:
        try:
            video_id = url_or_id
            if url_or_id.startswith("http"):
                video_id = url_or_id.split("/")[-1].split("?")[0]

            download_url = f"https://tikwm.com/video/media/play/{video_id}.mp4"
            response = requests.get(download_url, allow_redirects=True, timeout=20)
            response.raise_for_status()

            os.makedirs(os.path.dirname(self.filename) or ".", exist_ok=True)
            with open(self.filename, "wb") as f:
                f.write(response.content)
            return True
        except Exception as e:
            logging.error(f"Error downloading TikTok video {url_or_id}: {e}")
            return False

    async def get_video_size(self, path: str) -> tuple[int, int]:
        return await asyncio.to_thread(self._get_size_sync, path)

    def _get_size_sync(self, path: str) -> tuple[int, int]:
        with VideoFileClip(path) as clip:
            return clip.size

# -------- TIKTOK DOWNLOAD LOGIC --------
async def download_tiktok(url: str) -> tuple[str | list[str] | None, str | None, str | None]:
    try:
        ensure_downloads_folder_exists()
        api_url = f"https://tikwm.com/api/?url={url}"

        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("data"):
            return None, None, "⚠️ Could not fetch TikTok video from API."

        post_data = data["data"]

        if "images" in post_data and post_data["images"]:
            image_urls = post_data["images"]
            image_folder = os.path.join(DOWNLOADS_FOLDER, str(uuid.uuid4()))
            os.makedirs(image_folder, exist_ok=True)
            image_paths = []
            for idx, img_url in enumerate(image_urls):
                try:
                    img_data = requests.get(img_url, timeout=15).content
                    img_path = os.path.join(image_folder, f"slide_{idx + 1}.jpg")
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    image_paths.append(img_path)
                except Exception as e:
                    logging.warning(f"Failed to download image {img_url}: {e}")
            return image_paths, "photo", None

        video_id = post_data.get("id") or url.split("/")[-1].split("?")[0]
        filename_prefix = f"{await generate_random_string()}_video.mp4"
        output_path = os.path.join(DOWNLOADS_FOLDER, sanitize_filename(filename_prefix))

        downloader = DownloaderTikTok(DOWNLOADS_FOLDER, output_path)
        success = await downloader.download_video(video_id)
        if not success or not os.path.exists(output_path):
            return None, None, "⚠️ Failed to download TikTok video."

        try:
            width, height = await downloader.get_video_size(output_path)
        except Exception as e:
            logging.warning(f"Cannot get video size: {e}")
            width, height = None, None

        callback_store_sizes[output_path] = (width, height)
        return output_path, "video", None

    except Exception as e:
        logging.exception("Error downloading TikTok")
        return None, None, f"❌ Error downloading TikTok: {e}"

# -------- MESSAGE HANDLER --------
@router.message(F.text.regexp(r"(https?://)?(www\.)?(tiktok\.com/.+|vm\.tiktok\.com/.+|vt\.tiktok\.com/.+)"))
async def handle_tiktok(message: Message):
    url = message.text.strip()
    bot_username = (await bot.get_me()).username
    await message.answer("⏳ Downloading TikTok...")

    result, content_type, error = await download_tiktok(url)
    if error:
        await message.answer(error)
        return

    try:
        if content_type == "photo":
            media_group = [InputMediaPhoto(media=FSInputFile(p)) for p in result]
            await message.answer_media_group(media_group)
            await message.answer(f"📸 Download photos here 👉 @{bot_username}")

            for path in result:
                if os.path.exists(path):
                    os.remove(path)
            try:
                os.rmdir(os.path.dirname(result[0]))
            except Exception:
                pass

        else:
            unique_id = str(uuid.uuid4())
            callback_store[unique_id] = url
            width_height = callback_store_sizes.get(result, (None, None))
            width, height = width_height

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🎵 Download in MP3",
                    callback_data=f"convert_mp3_tiktok|{unique_id}"
                )
            ]])

            video_file = FSInputFile(result)
            await message.answer_video(
                video_file,
                caption=f"🔗 Download video here 👉 @{bot_username}",
                reply_markup=keyboard,
                **({"width": width, "height": height} if width and height else {})
            )

            if os.path.exists(result):
                os.remove(result)

    except Exception as e:
        await message.answer(f"❌ Error: {e}")

# -------- CALLBACK HANDLER FOR MP3 --------
@router.callback_query(F.data.startswith("convert_mp3_tiktok"))
async def convert_to_mp3(callback: CallbackQuery):
    bot_username = (await bot.get_me()).username
    parts = callback.data.split("|")
    unique_id = parts[1]
    url = callback_store.get(unique_id)

    if not url:
        await callback.message.answer("❌ URL not found")
        return

    await callback.message.answer("⏳ Converting to MP3...")
    filename, title, error = await get_audio_stream(url)
    if error:
        await callback.message.answer(error)
        return

    try:
        audio_file = FSInputFile(filename)
        await callback.message.answer_audio(
            audio_file,
            caption=f"🔗 Download audio here 👉 @{bot_username}"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Error: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)
