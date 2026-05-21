import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from pyrogram import Client

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8105002960:AAGF4uFOi8uTRHIhjwLn1ifhtTbZqp26DPk"        # Токен бота от @BotFather
ADMIN_IDS = [7673683792]                  # Ваш Telegram ID

# Pyrogram (ТОТ ЖЕ БОТ) - он умеет отправлять подарки!
PYRO_BOT_TOKEN = BOT_TOKEN               # Тот же токен

GIFT_ID = "5025876399963955719"          # ID подарка (мишка)
DEFAULT_PRICE = 10                       # Цена по умолчанию в Stars

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pyro_bot = Client("gift_bot", bot_token=PYRO_BOT_TOKEN)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            stars_spent INTEGER DEFAULT 0,
            gifts_received INTEGER DEFAULT 0,
            join_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def add_user(user_id, username, first_name):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, join_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_user_stats(user_id, stars):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET stars_spent = stars_spent + ?, 
            gifts_received = gifts_received + 1
        WHERE user_id = ?
    ''', (stars, user_id))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT stars_spent, gifts_received, join_date FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_total_stats():
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT SUM(stars_spent) FROM users')
    total_stars = cursor.fetchone()[0] or 0
    cursor.execute('SELECT SUM(gifts_received) FROM users')
    total_gifts = cursor.fetchone()[0] or 0
    conn.close()
    return total_users, total_stars, total_gifts

def get_all_users():
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

# ========== ЦЕНА ПОДАРКА ==========
current_price = DEFAULT_PRICE

# ========== ОТПРАВКА ПОДАРКА ОТ БОТА ЧЕРЕЗ PYROGRAM ==========
async def send_gift_from_bot(user_id: int, gift_id: str, text: str = "Telegram моя жизнь"):
    """Отправляет реальный подарок ОТ БОТА!"""
    try:
        await pyro_bot.start()
        result = await pyro_bot.send_gift(
            chat_id=user_id,
            gift_id=gift_id,
            text=text
        )
        await pyro_bot.stop()
        return True, result
    except Exception as e:
        print(f"Ошибка отправки подарка: {e}")
        return False, str(e)

# ========== КОМАНДЫ ПОЛЬЗОВАТЕЛЯ ==========
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    text = (
        "🎁 **Бот подарков Telegram Stars** 🎁\n\n"
        "Я отправляю **реальные подарки** прямо в профиль!\n\n"
        f"🐻 **Подарок:** Мишка\n"
        f"📝 **Подпись:** Telegram моя жизнь\n"
        f"⭐ **Цена:** {current_price} Stars\n\n"
        "📌 **Команды:**\n"
        "/buy - Купить подарок\n"
        "/profile - Мой профиль\n"
        "/ping - Проверить бота"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Купить подарок", callback_data="buy")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    prices = [LabeledPrice(label="Подарок Мишка", amount=current_price)]
    
    await bot.send_invoice(
        chat_id=user.id,
        title="🐻 Подарок Мишка",
        description=f"Подарок за {current_price} Stars с подписью 'Telegram моя жизнь'",
        payload=f"gift_{GIFT_ID}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="gift_purchase"
    )

@dp.message(Command("profile"))
async def profile_cmd(message: types.Message):
    user = message.from_user
    stats = get_user_stats(user.id)
    
    if stats:
        stars_spent, gifts_received, join_date = stats
        text = (
            f"👤 **Ваш профиль**\n\n"
            f"**Имя:** {user.first_name}\n"
            f"**Username:** @{user.username or 'Нет'}\n"
            f"**В боте с:** {join_date[:10]}\n\n"
            f"⭐ **Потрачено Stars:** {stars_spent}\n"
            f"🎁 **Получено подарков:** {gifts_received}\n"
        )
    else:
        text = "❌ Данные не найдены"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Купить ещё", callback_data="buy")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("ping"))
async def ping_cmd(message: types.Message):
    await message.answer("🏓 **Pong!** Бот работает отлично!", parse_mode=ParseMode.MARKDOWN)

# ========== АДМИН КОМАНДЫ ==========
@dp.message(Command("set_price"))
async def set_price_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав!")
        return
    
    global current_price
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /set_price <количество Stars>")
            return
        current_price = int(args[1])
        await message.answer(f"✅ Цена подарка установлена: {current_price} Stars")
    except ValueError:
        await message.answer("❌ Введите число")

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав!")
        return
    
    total_users, total_stars, total_gifts = get_total_stats()
    
    text = (
        f"📊 **Статистика бота**\n\n"
        f"👥 **Всего пользователей:** {total_users}\n"
        f"⭐ **Потрачено Stars:** {total_stars}\n"
        f"🎁 **Отправлено подарков:** {total_gifts}\n"
        f"💰 **Текущая цена:** {current_price} Stars\n"
    )
    
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("broadcast"))
async def broadcast_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав!")
        return
    
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.answer("❌ Используйте: /broadcast <текст>")
        return
    
    users = get_all_users()
    success = 0
    fail = 0
    
    status_msg = await message.answer(f"📨 Начинаю рассылку для {len(users)} пользователей...")
    
    for user_id, username, first_name in users:
        try:
            await bot.send_message(
                user_id,
                f"📢 **Рассылка от администратора**\n\n{broadcast_text}",
                parse_mode=ParseMode.MARKDOWN
            )
            success += 1
        except:
            fail += 1
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\nУспешно: {success}\nОшибок: {fail}")

@dp.message(Command("user"))
async def user_info_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав!")
        return
    
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /user <user_id>")
            return
        
        user_id = int(args[1])
        stats = get_user_stats(user_id)
        
        if stats:
            stars_spent, gifts_received, join_date = stats
            text = (
                f"👤 **Информация о пользователе**\n\n"
                f"**ID:** `{user_id}`\n"
                f"**В боте с:** {join_date[:10]}\n"
                f"⭐ **Потрачено Stars:** {stars_spent}\n"
                f"🎁 **Получено подарков:** {gifts_received}\n"
            )
        else:
            text = "❌ Пользователь не найден"
        
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    except:
        await message.answer("❌ Ошибка ввода")

# ========== ПЛАТЕЖИ ==========
@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    user = message.from_user
    stars_spent = message.successful_payment.total_amount
    
    # Отправляем статус "печатает"
    await bot.send_chat_action(user.id, "typing")
    
    # ОТПРАВЛЯЕМ РЕАЛЬНЫЙ ПОДАРОК ОТ БОТА!
    success, result = await send_gift_from_bot(user.id, GIFT_ID, "Telegram моя жизнь")
    
    if success:
        # Сохраняем в БД
        add_user(user.id, user.username or "", user.first_name or "")
        update_user_stats(user.id, stars_spent)
        
        await message.answer(
            f"✅ **Подарок отправлен!** 🎉\n\n"
            f"🐻 Мишка с подписью **'Telegram моя жизнь'** уже в вашем профиле!\n"
            f"⭐ Потрачено: {stars_spent} Stars\n\n"
            f"📱 **Как посмотреть подарок?**\n"
            f"→ Настройки Telegram\n"
            f"→ Подарки\n"
            f"→ Ваши подарки",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Уведомление админу
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"💰 **Новая покупка!**\n\n"
                f"👤 Пользователь: @{user.username or user.first_name} (ID: {user.id})\n"
                f"⭐ Потрачено Stars: {stars_spent}\n"
                f"🎁 Подарок: Мишка отправлен ОТ БОТА!\n"
                f"✅ Статус: Успешно"
            )
    else:
        await message.answer(
            f"❌ **Ошибка при отправке подарка!**\n\n"
            f"Администратор уже уведомлён. Ваши Stars будут возвращены в течение 24 часов.\n"
            f"Ошибка: `{result}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"⚠️ **КРИТИЧЕСКАЯ ОШИБКА!**\n\n"
                f"Пользователь: {user.id} (@{user.username})\n"
                f"Потрачено Stars: {stars_spent}\n"
                f"Ошибка: {result}\n\n"
                f"❗ Нужно вернуть Stars вручную!"
            )

# ========== КНОПКИ ==========
@dp.callback_query(F.data == "buy")
async def buy_callback(callback: types.CallbackQuery):
    await callback.answer()
    await buy_cmd(callback.message)

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: types.CallbackQuery):
    await callback.answer()
    await profile_cmd(callback.message)

# ========== ЗАПУСК ==========
async def main():
    print("🚀 Бот подарков запущен!")
    print(f"🤖 Бот отправляет РЕАЛЬНЫЕ подарки ОТ СЕБЯ!")
    print(f"💰 Текущая цена: {DEFAULT_PRICE} Stars")
    print(f"🐻 ID подарка: {GIFT_ID}")
    
    # Запускаем aiogram бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
