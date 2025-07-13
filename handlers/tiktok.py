import os
import uuid
import requests
import random
import string
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, InputMediaPhoto
)
from aiogram.types.input_file import FSInputFile
from services.utils import sanitize_filename, ensure_downloads_folder_exists, DOWNLOADS_FOLDER
from main import bot, logging
from yt_dlp import YoutubeDL
import subprocess

DOWNLOADS_FOLDER="services/downloads"

router = Router()
callback_store = {}

async def get_audio_stream(url: str):
    try:
        # Крок 1: Завантажуємо mp4 (muxed)
        filename = f"{uuid.uuid4()}.mp4"
        output_mp3 = filename.replace(".mp4", ".mp3")

        ydl_opts = {
            'quiet': True,
            'format': 'mp4',
            'outtmpl': filename,
            'noplaylist': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio")

        # Крок 2: Конвертація в MP3 через ffmpeg
        subprocess.run([
            "ffmpeg", "-i", filename, "-vn", "-ab", "192k", "-ar", "44100", "-y", output_mp3
        ], check=True)

        os.remove(filename)  # видаляємо mp4
        return output_mp3, title, None

    except Exception as e:
        logging.error(f"Error downloading MP3: {e}")
        return None, None, f"❌ Помилка при конвертації: {e}"

async def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

async def download_tiktok(url, type="tiktok"):
    try:
        ensure_downloads_folder_exists(DOWNLOADS_FOLDER)
        api_url = f"https://tikwm.com/api/?url={url}"

        response = requests.get(api_url)
        data = response.json()

        if not data.get("data"):
            return None, None, "⚠️ Не вдалося отримати відео з API."

        post_data = data["data"]

        # Обробка фото
        if "images" in post_data:
            image_urls = post_data["images"]
            image_folder = os.path.join(DOWNLOADS_FOLDER, str(uuid.uuid4()))
            os.makedirs(image_folder, exist_ok=True)

            image_paths = []
            for idx, img_url in enumerate(image_urls):
                img_data = requests.get(img_url).content
                img_path = os.path.join(image_folder, f"slide_{idx + 1}.jpg")
                with open(img_path, "wb") as f:
                    f.write(img_data)
                image_paths.append(img_path)

            return image_paths, "photo", None

        video_url = post_data.get("play")
        if not video_url:
            return None, None, "⚠️ Не вдалося отримати відео з API."

        label = "video" if type == "video" else "audio"
        filename_prefix = f"{generate_random_string()}_{label}"
        filename = sanitize_filename(filename_prefix)
        output_path = os.path.join(DOWNLOADS_FOLDER, filename)

        video_content = requests.get(video_url).content
        with open(output_path, "wb") as f:
            f.write(video_content)

        return output_path, "video", None

    except Exception as e:
        return None, None, f"❌ Помилка завантаження: {e}"

@router.message(F.text.regexp(r"(https?://)?(www\.)?(tiktok\.com/.+|vm\.tiktok\.com/.+|vt\.tiktok\.com/.+)"))
async def handle_tiktok(message: Message):
    url = message.text.strip()
    await message.answer("⏳ Завантажую TikTok...")

    result, content_type, error = await download_tiktok(url)

    if error:
        await message.answer(error)
        return

    try:
        if content_type == "photo":
            media_group = [
                InputMediaPhoto(media=FSInputFile(path)) for path in result
            ]
            await message.answer_media_group(media_group)
            await message.answer("📸 Завантажуй фото тут 👉 @MeryLoadBot")

            for path in result:
                if os.path.exists(path):
                    os.remove(path)
            os.rmdir(os.path.dirname(result[0]))

        else:
            unique_id = str(uuid.uuid4())
            callback_store[unique_id] = url

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🎵 Завантажити у MP3",
                    callback_data=f"convert_mp3_tiktok|{unique_id}"
                )
            ]])

            video_file = FSInputFile(result)
            await message.answer_video(
                video_file,
                caption="🔗 Завантажуй відео тут 👉 @MeryLoadBot",
                reply_markup=keyboard
            )

            if os.path.exists(result):
                os.remove(result)

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")


@router.callback_query(F.data.startswith("convert_mp3_tiktok"))
async def convert_to_mp3(callback: CallbackQuery):
    bot_username = (await bot.get_me()).username
    parts = callback.data.split("|")
    unique_id = parts[1]
    url = callback_store.get(unique_id)

    if not url:
        await callback.message.answer("❌ Помилка: посилання не знайдено")
        return

    await callback.message.answer("⏳ Конвертую у MP3...")

    filename, title, error = await get_audio_stream(url)
    if error:
        await callback.message.answer(error)
        return

    try:
        audio_file = FSInputFile(filename)
        await callback.message.answer_audio(
            audio_file,
            caption=f"🔗 Завантажуй аудіо тут 👉 @{bot_username}",
        )
    except Exception as e:
        await callback.message.answer(f"❌ Помилка: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)