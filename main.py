import asyncio
import os
from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import logging

load_dotenv()

bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()
BOT_TOKEN = os.getenv('BOT_TOKEN')
admin_id = os.getenv('ADMIN_ID')

async def main():
    import handlers
    dp.include_router(handlers.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
