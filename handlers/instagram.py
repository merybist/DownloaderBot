import os
import re
import uuid
import asyncio
import httpx
import aiohttp

from dotenv import load_dotenv
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.types.input_file import FSInputFile
from moviepy import VideoFileClip
from main import bot


load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")

DOWNLOADS_FOLDER = "services/downloads"
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

router = Router()
callback_store = {}


async def download_reel(reel_url: str) -> str:
    shortcode_match = re.search(r"(reel|p)/([a-zA-Z0-9_-]+)", reel_url)
    if not shortcode_match:
        raise Exception("❌ Не вдалося витягнути shortcode з URL")

    shortcode = shortcode_match.group(2)

    api_url = "https://instagram-scrapper-posts-reels-stories-downloader.p.rapidapi.com/reel_by_shortcode"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    params = {"shortcode": shortcode}

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers, params=params) as response:
            data = await response.json()
            print("API response:", data)  # Для логів

            # Check if we got a valid response
            if not data:
                raise Exception("❌ Відповідь API порожня")

            # Get the best quality video URL
            video_versions = data.get("video_versions", [])
            if not video_versions:
                raise Exception("❌ Відео не знайдено у відповіді API")

            # Select the highest resolution video
            video_url = max(video_versions, key=lambda x: x.get("width", 0))["url"]

            filename = f"{uuid.uuid4()}.mp4"
            file_path = os.path.join(DOWNLOADS_FOLDER, filename)

            async with session.get(video_url) as media_resp:
                if media_resp.status == 200:
                    with open(file_path, "wb") as f:
                        f.write(await media_resp.read())
                    return file_path
                else:
                    raise Exception(f"❌ Не вдалося завантажити файл: HTTP {media_resp.status}")

def convert_video_to_mp3(video_path: str) -> tuple[str | None, str | None]:

    try:
        output_path = video_path.replace(".mp4", ".mp3")
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(output_path)
        clip.close()
        return output_path, None
    except Exception as e:
        return None, str(e)

#https://www.instagram.com/reel/DL8T0dioRJm/?igsh=MXdhbXlnanJjMHd1Zw==
@router.message(F.text.regexp(r"(https?://)?(www\.)?(instagram\.com/reel/)([a-zA-Z0-9_-]+)"))
async def handle_instagram_reel(message: Message):
    url = message.text.strip()
    bot_username = (await bot.get_me()).username
    await message.answer("⏳ Download Instagram...")

    loop = asyncio.get_running_loop()
    try:
        video_path = await loop.run_in_executor(None, lambda: asyncio.run(download_reel(url)))
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
        return

    unique_id = str(uuid.uuid4())
    callback_store[unique_id] = url

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Download in MP3", callback_data=f"convert_mp3|{unique_id}")]
    ])

    video_file = FSInputFile(video_path)
    await message.answer_video(
        video_file,
        caption=f"🔗 Download audio here 👉 @{bot_username}",
        reply_markup=keyboard
    )

    # Очищення відео після відправлення (можна робити пізніше)
    if os.path.exists(video_path):
        os.remove(video_path)


@router.callback_query(F.data.startswith("convert_mp3|"))
async def convert_to_mp3_instagram(callback: CallbackQuery):
    parts = callback.data.split("|")
    bot_username = (await bot.get_me()).username
    unique_id = parts[1]
    url = callback_store.get(unique_id)

    if not url:
        await callback.message.answer("❌ Error is not active.")
        return

    await callback.message.answer("⏳ Convert in MP3...")

    loop = asyncio.get_running_loop()
    try:
        video_path = await loop.run_in_executor(None, lambda: asyncio.run(download_reel(url)))
    except Exception as e:
        await callback.message.answer(f"❌ Error: {e}")
        return

    mp3_path, error = await loop.run_in_executor(None, convert_video_to_mp3, video_path)

    if error:
        await callback.message.answer(f"❌ Error: {error}")
        return

    audio_file = FSInputFile(mp3_path)
    try:
        await callback.message.answer_audio(
            audio_file,
            caption=f"🔗 Download audio here 👉 @{bot_username}",
        )
    except Exception as e:
        await callback.message.answer(f"❌ Помилка надсилання: {e}")
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
