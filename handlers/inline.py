import os
import uuid
from aiogram import Router, Bot
from aiogram.types import InlineQuery, InlineQueryResultCachedVideo
from aiogram.types.input_file import FSInputFile
from handlers.youtube import get_youtube_video
from handlers.tiktok import download_tiktok
from handlers.instagram import download_reel
from main import bot

router = Router()
CHANNEL_ID = os.getenv("CHANNEL_ID")

@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery, bot: Bot):
    bot_username = (await bot.get_me()).username
    url = inline_query.query.strip()
    file_path = None

    # Визначення типу
    try:
        if "youtube.com" in url or "youtu.be" in url:
            file_path, error = get_youtube_video(url)
            if error:
                raise Exception(error)

        elif "tiktok.com" in url or "vm.tiktok.com" in url or "vt.tiktok.com" in url:
            file_path, _, error = await download_tiktok(url, type="video")
            if error:
                raise Exception(error)

        elif "instagram.com/reel/" in url:
            file_path = await download_reel(url)

        else:
            raise Exception("Непідтримуване посилання")

        # Надсилання в канал
        video_message = await bot.send_video(
            chat_id=CHANNEL_ID,
            video=FSInputFile(file_path),
            caption=f"🎬 Запит від @{inline_query.from_user.username or inline_query.from_user.id}"
        )

        file_id = video_message.video.file_id

        await inline_query.answer([
            InlineQueryResultCachedVideo(
                id=str(uuid.uuid4()),
                video_file_id=file_id,
                title="📥 Натисни, щоб відправити відео",
                caption=f"🔗 Завантажуй аудіо тут 👉 @{bot_username}"
            )
        ], cache_time=1)

    except Exception as e:
        print(f"[INLINE ERROR] {e}")
        await inline_query.answer([], switch_pm_text="❌ Не вдалося обробити", switch_pm_parameter="start", cache_time=1)

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
