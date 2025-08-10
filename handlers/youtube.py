import os
import uuid
import requests
import time
import logging
import uuid
import random
import string
import re

from aiogram import Bot, Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from dotenv import load_dotenv
from pytubefix import YouTube
from aiogram.types.input_file import FSInputFile
from moviepy import AudioFileClip

from main import bot


from main import BOT_TOKEN, admin_id
load_dotenv()

router = Router()

DOWNLOADS_FOLDER = "services/downloads"

# Тимчасове сховище даних (краще використовувати FSM або базу даних)
callback_store = {}


@router.callback_query(F.data.startswith("convert_mp3_youtube"))
async def convert_to_mp3_youtube(callback: CallbackQuery):
    bot_username = (await bot.get_me()).username
    parts = callback.data.split("|")
    unique_id = parts[1]
    url = callback_store.get(unique_id)

    if not url:
        await callback.answer("Помилка: посилання не знайдено")
        return

    await callback.message.answer("⏳ Конвертую у MP3...")
    filename, title, error = download_mp3(url)

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


@router.message(F.text.regexp(r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([\w-]+)"))
async def handle_youtube_url(message: Message):
    bot_username = (await bot.get_me()).username
    url = message.text.strip()
    unique_id = str(uuid.uuid4())
    callback_store[unique_id] = url

    await message.answer("⏳ Завантажую YouTube...")
    video_path, error = download_video_youtube(url)

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
            caption=f"🔗 Завантажуй аудіо тут 👉 @{bot_username}",
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

def sanitize_filename(filename):
    """
    Видаляє недопустимі символи з назви файлу.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


def ensure_downloads_folder_exists(downloads_folder):
    if not os.path.exists(downloads_folder):
        os.makedirs(downloads_folder)

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_video_stream(yt):
    # Першочергово пробуємо отримати 1080p із прогресивним потоком (відео+аудіо)
    return yt.streams.filter(res="1080p", file_extension='mp4', progressive=True).first() or \
        yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()


def download_video_youtube(url, custom_label="youtube_video"):
    try:
        ensure_downloads_folder_exists(DOWNLOADS_FOLDER)

        yt = YouTube(url)
        video_stream = get_video_stream(yt)
        RES = '1080p'

        for idx, i in enumerate(yt.streams):
            if i.resolution == RES:
                print(idx)
                print(i.resolution)
                break
        print(yt.streams[idx])

        filename_prefix = f"{generate_random_string()}_{custom_label}"
        filename = sanitize_filename(filename_prefix) + ".mp4"
        output_path = os.path.join(DOWNLOADS_FOLDER, filename)

        video_stream.download(output_path=DOWNLOADS_FOLDER, filename=filename)
        return output_path, None

    except Exception as e:
        return None, f"❌ Помилка завантаження відео: {e}"


def download_mp3(url):
    try:
        ensure_downloads_folder_exists(DOWNLOADS_FOLDER)

        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()

        if not audio_stream:
            return None, None, "❌ Не знайдено аудіо для завантаження."

        title = sanitize_filename(yt.title)
        temp_video_path = os.path.join(DOWNLOADS_FOLDER, f"{generate_random_string()}_temp.mp4")
        final_mp3_path = os.path.join(DOWNLOADS_FOLDER, f"{title}.mp3")

        audio_stream.download(output_path=DOWNLOADS_FOLDER, filename=os.path.basename(temp_video_path))

        audioclip = AudioFileClip(temp_video_path)
        audioclip.write_audiofile(final_mp3_path, bitrate="192k")
        audioclip.close()
        os.remove(temp_video_path)

        return final_mp3_path, yt.title, None

    except Exception as e:
        return None, None, f"❌ Помилка завантаження аудіо: {e}"