import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import asyncio

# ТОКЕН ВАШЕГО БОТА (получите у @BotFather)
BOT_TOKEN = "8859884837:AAEDXq0qQ4fjPeDGpOiq3DmoQ3S5-kjHLMI"

# Указанный стикер
STICKER_ID = "CAACAgIAAxkBAAERQgFqDvOwwCpQ5GFosmZyw8z3tWbbtgAC0ZkAAo3w6EoJjVpoEIXgQzsE"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Сначала отправляем стикер
    await bot.send_sticker(message.chat.id, STICKER_ID)
    await message.answer(
        "👋 Отправь мне любой стикер, фото, сообщение или перешли мне сообщение из канала/группы — "
        "и я скажу его ID.\n\n"
        "🤖 Узнать ID бота: отправь команду /my_id (покажу твой ID и ID бота)\n"
        "📢 Узнать ID канала: перешли любое сообщение из канала в этот чат"
    )

@dp.message(Command("my_id"))
async def show_my_id(message: Message):
    user_id = message.from_user.id
    bot_id = (await bot.get_me()).id
    await message.answer(
        f"🆔 Твой ID: `{user_id}`\n"
        f"🤖 ID бота: `{bot_id}`",
        parse_mode="Markdown"
    )

@dp.message()
async def show_ids(message: Message):
    # ID пользователя (отправителя)
    user_id = message.from_user.id
    user_info = f"👤 ID пользователя: `{user_id}`\n"

    # ID чата (канала, группы, ЛС)
    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_info = f"📱 ID чата (`{chat_type}`): `{chat_id}`\n"

    sticker_id = None
    sticker_info = ""

    # Если сообщение — стикер
    if message.sticker:
        sticker_id = message.sticker.file_id
        sticker_info = f"🏷️ ID стикера: `{sticker_id}`\n"
        # Дополнительно: уникальный ID набора стикеров
        if message.sticker.set_name:
            sticker_info += f"📦 Набор стикеров: `{message.sticker.set_name}`\n"

    # Если переслано из канала (или супергруппы)
    forward_from_chat = message.forward_from_chat
    if forward_from_chat:
        channel_id = forward_from_chat.id
        channel_name = forward_from_chat.title or "канал"
        channel_info = f"📢 ID канала `{channel_name}`: `{channel_id}`\n"
        await message.answer(
            f"{user_info}{chat_info}{channel_info}" + (sticker_info if sticker_id else ""),
            parse_mode="Markdown"
        )
        return

    # Если просто стикер
    if sticker_id:
        await message.answer(
            f"{user_info}{chat_info}{sticker_info}",
            parse_mode="Markdown"
        )
    else:
        # Любое другое сообщение — показываем ID пользователя и чата
        await message.answer(
            f"{user_info}{chat_info}",
            parse_mode="Markdown"
        )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
