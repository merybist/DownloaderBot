import os
import uuid
import requests
import time
import logging
import random
import string
import re
import asyncio

from aiogram import Bot, Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.types.input_file import FSInputFile
from yt_dlp import YoutubeDL
from moviepy import VideoFileClip, AudioFileClip

from main import bot, BOT_TOKEN, admin_id

router = Router()
DOWNLOADS_FOLDER = "services/downloads"
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

callback_store = {}

# ------------------------- UTILS -------------------------

def custom_oauth_verifier(verification_url, user_code):
    send_message_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": admin_id,
        "text": f"<b>OAuth Verification</b>\n\nOpen this URL:\n{verification_url}\nEnter this code:\n<code>{user_code}</code>",
        "parse_mode": "HTML"
    }
    response = requests.get(send_message_url, params=params)
    if response.status_code == 200:
        logging.info("OAuth message sent successfully.")
    else:
        logging.error(f"OAuth message failed. Status code: {response.status_code}")
    for i in range(30, 0, -5):
        logging.info(f"{i} seconds remaining for verification")
        time.sleep(5)

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def ensure_downloads_folder_exists():
    if not os.path.exists(DOWNLOADS_FOLDER):
        os.makedirs(DOWNLOADS_FOLDER)

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

async def safe_remove(file_path):
    if os.path.exists(file_path):
        await asyncio.to_thread(os.remove, file_path)

async def get_clip_dimensions(file_path: str):
    try:
        return await asyncio.to_thread(lambda: VideoFileClip(file_path).size)
    except Exception as e:
        logging.error(f"Error getting video dimensions: {e}")
        return None, None

async def get_audio_duration(file_path: str):
    try:
        return await asyncio.to_thread(lambda: AudioFileClip(file_path).duration)
    except Exception as e:
        logging.error(f"Error getting audio duration: {e}")
        return 0

# ------------------------- YT_DLP DOWNLOAD -------------------------

async def download_media(url: str, is_audio=False):
    ensure_downloads_folder_exists()
    filename_prefix = generate_random_string()
    outtmpl = os.path.join(DOWNLOADS_FOLDER, f"{filename_prefix}.%(ext)s")

    ydl_opts = {
        "format": "bestvideo+bestaudio/best" if is_audio else "bestvideo+bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "merge_output_format": "mp4",
        "oauth": True,
        "oauth_verifier": custom_oauth_verifier,
    }

    try:
        loop = asyncio.get_running_loop()
        with YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
        ext = info.get("ext") or ("mp3" if is_audio else "mp4")
        downloaded_file = outtmpl.replace("%(ext)s", ext)
        return downloaded_file, info, None
    except Exception as e:
        logging.error(f"YT_DLP download error: {e}")
        return None, None, f"❌ Помилка завантаження: {e}"

# ------------------------- CALLBACKS -------------------------

@router.callback_query(F.data.startswith("convert_mp3_youtube"))
async def convert_to_mp3_youtube(callback: CallbackQuery):
    bot_username = (await bot.get_me()).username
    unique_id = callback.data.split("|")[1]
    url = callback_store.get(unique_id)

    if not url:
        await callback.answer("Error: URL not found")
        return

    await callback.message.answer("⏳ Converting in MP3...")
    mp3_path, info, error = await download_media(url, is_audio=True)

    if error:
        await callback.message.answer(error)
        return

    try:
        await callback.message.answer_audio(FSInputFile(mp3_path), caption=f"🔗 Download audio 👉 @{bot_username}")
    finally:
        await safe_remove(mp3_path)

# ------------------------- MESSAGE HANDLERS -------------------------

@router.message(F.text.regexp(r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([\w-]+)"))
async def handle_youtube_url(message: Message):
    bot_username = (await bot.get_me()).username
    url = message.text.strip()
    unique_id = str(uuid.uuid4())
    callback_store[unique_id] = url

    await message.answer("⏳ Downloading YouTube video...")
    video_path, info, error = await download_media(url, is_audio=False)

    if error:
        await message.answer(error)
        return

    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Download in MP3", callback_data=f"convert_mp3_youtube|{unique_id}")]
        ])
        file_size = os.path.getsize(video_path)
        if file_size > MAX_FILE_SIZE:
            await message.answer("❌ File is so big.")
            await safe_remove(video_path)
            return

        width, height = await get_clip_dimensions(video_path)
        await message.answer_video(
            video=FSInputFile(video_path),
            caption=f"🔗 Download video 👉 @{bot_username}",
            reply_markup=keyboard,
            width=width,
            height=height
        )
    finally:
        await safe_remove(video_path)
