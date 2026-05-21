import asyncio
import sqlite3
import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    LabeledPrice, Message, PreCheckoutQuery, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, FSInputFile
)
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8105002960:AAGF4uFOi8uTRHIhjwLn1ifhtTbZqp26DPk"  # Замените на ваш токен
ADMIN_IDS = [7673683792]  # Замените на ваш Telegram ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ===
def init_db():
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    
    # Пользователи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            total_stars_spent INTEGER DEFAULT 0,
            total_gifts_bought INTEGER DEFAULT 0,
            gift_balance INTEGER DEFAULT 0,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Чеки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checks (
            code TEXT PRIMARY KEY,
            gifts_count INTEGER,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            is_activated INTEGER DEFAULT 0,
            activated_by INTEGER DEFAULT NULL,
            activated_at TIMESTAMP DEFAULT NULL
        )
    ''')
    
    # История покупок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            stars_spent INTEGER,
            gifts_received INTEGER,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Глобальные настройки
gift_price_stars = 10  # цена по умолчанию

# === РАБОТА С БАЗОЙ ===
def get_user(user_id: int):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user_if_not_exists(user_id: int, username: str = "", first_name: str = ""):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

def update_user_stars(user_id: int, stars_spent: int, gifts_received: int = 1):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET total_stars_spent = total_stars_spent + ?,
            total_gifts_bought = total_gifts_bought + ?,
            gift_balance = gift_balance + ?
        WHERE user_id = ?
    ''', (stars_spent, gifts_received, gifts_received, user_id))
    conn.commit()
    conn.close()

def add_gift_balance(user_id: int, count: int):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET gift_balance = gift_balance + ? WHERE user_id = ?', (count, user_id))
    conn.commit()
    conn.close()

def use_gift(user_id: int) -> bool:
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT gift_balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()
    if balance and balance[0] > 0:
        cursor.execute('UPDATE users SET gift_balance = gift_balance - 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def create_check(gifts_count: int, created_by: int, hours_valid: int = 24) -> str:
    code = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(hours=hours_valid)
    
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO checks (code, gifts_count, created_by, expires_at)
        VALUES (?, ?, ?, ?)
    ''', (code, gifts_count, created_by, expires_at))
    conn.commit()
    conn.close()
    return code

def activate_check(code: str, user_id: int) -> tuple[bool, int]:
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT gifts_count, is_activated, expires_at FROM checks WHERE code = ?
    ''', (code,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False, 0
    
    gifts_count, is_activated, expires_at = result
    expires_at_dt = datetime.fromisoformat(expires_at)
    
    if is_activated or expires_at_dt < datetime.now():
        conn.close()
        return False, 0
    
    cursor.execute('''
        UPDATE checks 
        SET is_activated = 1, activated_by = ?, activated_at = CURRENT_TIMESTAMP
        WHERE code = ?
    ''', (user_id, code))
    
    add_gift_balance(user_id, gifts_count)
    conn.commit()
    conn.close()
    return True, gifts_count

def get_stats():
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT SUM(total_stars_spent) FROM users')
    total_stars = cursor.fetchone()[0] or 0
    cursor.execute('SELECT SUM(total_gifts_bought) FROM users')
    total_gifts = cursor.fetchone()[0] or 0
    conn.close()
    return total_users, total_stars, total_gifts

# === КОМАНДЫ ПОЛЬЗОВАТЕЛЯ ===
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user = message.from_user
    create_user_if_not_exists(user.id, user.username or "", user.first_name)
    
    text = (
        "🎁 **Бот подарков Telegram Stars** 🎁\n\n"
        "Здесь вы можете купить эксклюзивные подарки за Telegram Stars!\n\n"
        "**Доступные команды:**\n"
        "• `/buy` - Купить подарок\n"
        "• `/profile` - Мой профиль\n"
        "• `/ping` - Проверить работу бота\n\n"
        f"💰 **Текущая цена:** {gift_price_stars} Stars за подарок"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Купить подарок", callback_data="buy")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")]
    ])
    
    await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

@dp.message(Command("buy"))
async def buy_cmd(message: Message):
    user = message.from_user
    create_user_if_not_exists(user.id, user.username or "", user.first_name)
    
    if gift_price_stars <= 0:
        await message.answer("⚠️ Цена подарка ещё не установлена администратором.")
        return
    
    prices = [LabeledPrice(label="Подарок", amount=gift_price_stars)]
    
    await bot.send_invoice(
        chat_id=user.id,
        title="✨ Подарок за Telegram Stars ✨",
        description=f"Приобретите эксклюзивный подарок всего за {gift_price_stars} Stars!\n\nПодарок будет добавлен в ваш профиль.",
        payload="gift_purchase",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="gift"
    )

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    user = message.from_user
    create_user_if_not_exists(user.id, user.username or "", user.first_name)
    
    user_data = get_user(user.id)
    if user_data:
        _, username, first_name, total_stars, total_gifts, gift_balance, join_date = user_data
        
        text = (
            f"👤 **Ваш профиль**\n\n"
            f"**Имя:** {first_name}\n"
            f"**Username:** @{username if username else 'Нет'}\n"
            f"**В боте с:** {join_date[:10]}\n\n"
            f"⭐ **Всего потрачено Stars:** {total_stars}\n"
            f"🎁 **Куплено подарков:** {total_gifts}\n"
            f"📦 **Доступно подарков:** {gift_balance}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Купить ещё", callback_data="buy")]
        ])
        
        await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

@dp.message(Command("ping"))
async def ping_cmd(message: Message):
    await message.answer("🏓 **Pong!** Бот работает отлично!", parse_mode=ParseMode.MARKDOWN)

# === АДМИНИСТРАТОРСКИЕ КОМАНДЫ ===
@dp.message(Command("set_price"))
async def set_price_cmd(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    
    args = command.args
    if not args or not args.isdigit():
        await message.answer("❌ Используйте: `/set_price <количество звезд>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    global gift_price_stars
    gift_price_stars = int(args)
    await message.answer(f"✅ Цена подарка установлена: {gift_price_stars} Telegram Stars")

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав.")
        return
    
    total_users, total_stars, total_gifts = get_stats()
    
    text = (
        f"📊 **Статистика бота**\n\n"
        f"👥 **Всего пользователей:** {total_users}\n"
        f"⭐ **Потрачено Stars:** {total_stars}\n"
        f"🎁 **Куплено подарков:** {total_gifts}\n"
        f"💰 **Текущая цена:** {gift_price_stars} Stars\n"
    )
    
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("user"))
async def user_info_cmd(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав.")
        return
    
    args = command.args
    if not args or not args.isdigit():
        await message.answer("❌ Используйте: `/user <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    user_id = int(args)
    user_data = get_user(user_id)
    
    if not user_data:
        await message.answer(f"❌ Пользователь с ID {user_id} не найден.")
        return
    
    _, username, first_name, total_stars, total_gifts, gift_balance, join_date = user_data
    
    text = (
        f"👤 **Профиль пользователя**\n\n"
        f"**ID:** {user_id}\n"
        f"**Имя:** {first_name}\n"
        f"**Username:** @{username if username else 'Нет'}\n"
        f"**В боте с:** {join_date[:10]}\n\n"
        f"⭐ **Потрачено Stars:** {total_stars}\n"
        f"🎁 **Куплено подарков:** {total_gifts}\n"
        f"📦 **Баланс подарков:** {gift_balance}\n"
    )
    
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("broadcast"))
async def broadcast_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав.")
        return
    
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("❌ Используйте: `/broadcast <текст сообщения>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    
    success = 0
    fail = 0
    
    await message.answer(f"📨 Начинаю рассылку для {len(users)} пользователей...")
    
    for user in users:
        try:
            await bot.send_message(user[0], f"📢 **Рассылка от администратора**\n\n{text}", parse_mode=ParseMode.MARKDOWN)
            success += 1
        except:
            fail += 1
        await asyncio.sleep(0.05)  # чтобы не спамить
    
    await message.answer(f"✅ Рассылка завершена!\nУспешно: {success}\nОшибок: {fail}")

@dp.message(Command("create_check"))
async def create_check_cmd(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав.")
        return
    
    args = command.args
    if not args or not args.isdigit() or int(args) <= 0:
        await message.answer("❌ Используйте: `/create_check <количество подарков>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    gifts_count = int(args)
    code = create_check(gifts_count, message.from_user.id)
    
    text = (
        f"✅ **Чек создан!**\n\n"
        f"🎁 **Подарков:** {gifts_count}\n"
        f"🔑 **Код чека:** `{code}`\n"
        f"⏰ **Действителен:** 24 часа\n\n"
        f"Пользователь может активировать его в боте через меню."
    )
    
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

# === ОБРАБОТЧИКИ ПЛАТЕЖЕЙ ===
@dp.pre_checkout_query()
async def pre_checkout_query_handler(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    user = message.from_user
    stars_spent = message.successful_payment.total_amount
    
    create_user_if_not_exists(user.id, user.username or "", user.first_name)
    update_user_stars(user.id, stars_spent, 1)
    
    gift_message = (
        f"🎉 **Поздравляем!** 🎉\n\n"
        f"Вы успешно приобрели подарок за {stars_spent} Stars!\n"
        f"Подарок уже добавлен в ваш профиль.\n\n"
        f"🔍 Посмотреть подарок можно в команде `/profile`"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Посмотреть профиль", callback_data="profile")]
    ])
    
    await message.answer(gift_message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    
    # Уведомление админу
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"💰 **Новая покупка!**\n\n"
            f"👤 Пользователь: @{user.username or user.first_name} (ID: {user.id})\n"
            f"⭐ Потрачено Stars: {stars_spent}\n"
            f"🎁 Получен подарок"
        )

# === ОБРАБОТЧИКИ КНОПОК ===
@dp.callback_query(F.data == "buy")
async def buy_callback(callback: CallbackQuery):
    await callback.answer()
    await buy_cmd(callback.message)

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    await callback.answer()
    await profile_cmd(callback.message)

# === ОБРАБОТЧИК ЧЕКОВ (КАК У @SEND) ===
@dp.message(F.text)
async def handle_check_mention(message: Message):
    text = message.text
    bot_username = (await bot.get_me()).username
    
    # Формат: @bot_username количество
    if text.startswith(f"@{bot_username}"):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            gifts_count = int(parts[1])
            
            if gifts_count <= 0 or gifts_count > 100:
                await message.reply("❌ Количество подарков должно быть от 1 до 100.")
                return
            
            code = create_check(gifts_count, message.from_user.id)
            
            check_text = (
                f"✨ **Чек на {gifts_count} подарков** ✨\n\n"
                f"🎁 **Подарки:** {gifts_count}\n"
                f"🔑 **Код:** `{code}`\n"
                f"⏰ **Действителен:** 24 часа\n"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡ Активировать чек", callback_data=f"activate_{code}")]
            ])
            
            await message.reply(check_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("activate_"))
async def activate_check_callback(callback: CallbackQuery):
    code = callback.data.replace("activate_", "")
    user_id = callback.from_user.id
    
    success, gifts_count = activate_check(code, user_id)
    
    if success:
        await callback.answer(f"✅ Чек активирован! Получено {gifts_count} подарков!", show_alert=True)
        
        text = (
            f"🎉 **Чек активирован!** 🎉\n\n"
            f"Вы получили {gifts_count} подарков!\n"
            f"Теперь у вас есть {gifts_count} подарков в балансе.\n\n"
            f"Используйте `/profile` чтобы увидеть свой профиль."
        )
        
        await callback.message.edit_text(
            f"✅ **Чек активирован пользователем @{callback.from_user.username or callback.from_user.first_name}**\n\n"
            f"🎁 Получено подарков: {gifts_count}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await callback.message.answer(text, parse_mode=ParseMode.MARKDOWN)
    else:
        await callback.answer("❌ Чек недействителен или уже использован!", show_alert=True)

# === ЗАПУСК БОТА ===
async def main():
    print("🤖 Бот подарков запущен!")
    print(f"👤 Администраторы: {ADMIN_IDS}")
    print(f"💰 Текущая цена: {gift_price_stars} Stars")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
