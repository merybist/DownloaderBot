import os
import uuid
from aiogram import Bot, Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from dotenv import load_dotenv
import logging
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
import requests
import time
import asyncio
from aiogram.types.input_file import FSInputFile


from main import BOT_TOKEN, admin_id
load_dotenv()

router = Router()

# Тимчасове сховище даних (краще використовувати FSM або базу даних)
callback_store = {}


@router.callback_query(F.data.startswith("convert_mp3_youtube"))
async def convert_to_mp3_youtube(callback: CallbackQuery):
    parts = callback.data.split("|")
    unique_id = parts[1]
    url = callback_store.get(unique_id)

    if not url:
        await callback.answer("Помилка: посилання не знайдено")
        return

    await callback.message.answer("⏳ Конвертую у MP3...")
    filename, title, error = get_audio_stream(url)

    if error:
        await callback.message.answer(error)
        return

    try:
        with open(filename, "rb") as audio:
            await callback.message.answer_audio(
                audio,
                caption="🔗 Завантажуй аудіо тут 👉 @MeryLoadBot"
            )
    except Exception as e:
        await callback.message.answer(f"❌ Помилка: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


@router.message(F.text.regexp(r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([\w-]+)"))
async def handle_youtube_url(message: Message):
    url = message.text.strip()
    unique_id = str(uuid.uuid4())
    callback_store[unique_id] = url

    await message.answer("⏳ Завантажую YouTube...")
    video_path, error = get_youtube_video(url)

    if error:
        await message.answer(error)
        return

    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🎵 Завантажити у MP3",
                callback_data=f"convert_mp3_youtube|{unique_id}"
            )]
        ])

        video_file = FSInputFile(video_path)
        await message.answer_video(
            video_file,
            caption="🔗 Завантажуй відео тут 👉 @MeryLoadBot",
            reply_markup=keyboard
        )
    except Exception as e:
        error_message = f"❌ Помилка: {e}"
        await message.answer(error_message)

        if "No such file or directory" in str(e):
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Вирішення проблеми",
                    callback_data=f"retry_download_{unique_id}"
                )]
            ])
            await message.answer("Спробуйте вирішити проблему:", reply_markup=markup)
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

def custom_oauth_verifier(verification_url, user_code):
    send_message_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": admin_id,
        "text": f"<b>OAuth Verification</b>\n\nOpen this URL in your browser:\n{verification_url}\n\nEnter this code:\n<code>{user_code}</code>",
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

def get_youtube_video(url: str):
    try:
        filename = f"{uuid.uuid4()}.mp4"
        ydl_opts = {
            'quiet': True,
            'outtmpl': filename,
            'format': 'best[ext=mp4]',
            'no_warnings': True,
            'noplaylist': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return filename, None
    except Exception as e:
        logging.error(f"Error downloading YouTube video: {e}")
        return None, f"❌ Помилка при завантаженні: {e}"



def get_video_stream(yt: dict) -> dict | None:
    formats = yt.get("formats", [])
    vs = [f for f in formats
          if f.get("vcodec") != "none"
          and f.get("acodec") != "none"
          and f.get("ext") == "mp4"]
    vs.sort(key=lambda x: int(x.get("height", 0)), reverse=True)
    best = vs[0] if vs else None
    if best:
        best["webpage_url"] = yt["webpage_url"]
    return best


def get_audio_stream(url: str):
    try:
        filename = f"{uuid.uuid4()}.mp3"
        ydl_opts = {
            'quiet': True,
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'outtmpl': filename,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url)
            title = info.get("title", "audio")
        return filename, title, None
    except Exception as e:
        logging.error(f"Error downloading MP3: {e}")
        return None, None, f"❌ Помилка при конвертації: {e}"