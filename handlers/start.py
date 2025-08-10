from aiogram import Router, F
from aiogram.types import Message
from services.dp import conn_bot

router = Router()

@router.message(F.text == "/start")
async def start_handler(message: Message):
    cur_bot = conn_bot.cursor()
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    user_id = message.from_user.id

    cur_bot.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    existing_user = cur_bot.fetchone()

    if existing_user:
        await message.answer(f'Hi, {full_name}! Welcome! 😎')
    else:
        cur_bot.execute(
            "INSERT INTO users (user_id, first_name, last_name, chat_id) VALUES (?, ?, ?, ?)",
            (user_id, first_name, last_name, message.chat.id)
        )
        conn_bot.commit()
        await message.answer(
            f'I am a bot that can download videos from TikTok, Instagram, and YouTube.\n\n'
            f'Send a link to the video you want to download😊'
        )
