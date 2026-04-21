import asyncio
import aiohttp
import random
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils.markdown import text
import string
from datetime import datetime
from aiohttp_socks import ProxyConnector

API_TOKEN = '8325557607:AAE1CVGBGNgCMLCey9Xs2Ebu-9yOUjAcx3Y'

PROXY_LIST = [
    # 'socks5://логин:пароль@ip:порт',
    # 'socks5://логин:пароль@ip:порт',
]

# ... (остальные настройки COMPLAINT_TEMPLATES, USER_AGENTS и ReportManager остаются без изменений)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Для aiogram v2.x используем декоратор с lambda
@dp.message_handler(commands=['start'])
async def cmd_start(message: Message):
    welcome_text = """
    🤖 Бот для отправки жалоб активирован
    
    Команды:
    /report <username> - начать отправку жалоб
    /status - проверить статус
    
    Пример: /report username123
    """
    await message.reply(welcome_text)

@dp.message_handler(commands=['report'])
async def cmd_report(message: Message):
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply("Укажи юз.. Пример: /report username123")
        return
    
    target = args[1].strip().replace('@', '')
    
    status_msg = await message.reply(f"🚀 Запускаю атаку на @{target}\nОтправляю 50 жалоб...")
    
    user_sessions[message.from_user.id] = {
        'target': target,
        'start_time': datetime.now(),
        'status': 'in_progress'
    }
    
    success, failed = await report_manager.flood_reports(target, count=50)
    
    user_sessions[message.from_user.id]['status'] = 'completed'
    user_sessions[message.from_user.id]['success'] = success
    user_sessions[message.from_user.id]['failed'] = failed
    
    result_text = f"""
    📊 Результаты атаки на @{target}
    
    ✅ Успешно: {success}
    ❌ Неуспешно: {failed}
    📈 Процент успеха: {(success/(success+failed))*100:.1f}%
    
    Готово.
    """
    
    await status_msg.edit_text(result_text)

@dp.message_handler(commands=['status'])
async def cmd_status(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        await message.reply("Нет активных сессий.")
        return
    
    session = user_sessions[user_id]
    
    if session['status'] == 'in_progress':
        status = "🔄 В процессе..."
    else:
        status = f"✅ Завершено: {session['success']} успешно, {session['failed']} провалено"
    
    status_text = f"""
    📈 Текущий статус
    
    Цель: @{session['target']}
    Статус: {status}
    Начато: {session['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    await message.reply(status_text)

@dp.message_handler()
async def handle_message(message: Message):
    await message.reply("Используй /report <username>")

async def main():
    await dp.start_polling()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен. Нажми Ctrl + C для остановки.")
    asyncio.run(main())
