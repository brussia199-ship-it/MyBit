import asyncio
import aiohttp
import sqlite3
import secrets
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8105002960:AAGF4uFOi8uTRHIhjwLn1ifhtTbZqp26DPk"
ADMIN_IDS = [7673683792]
GIFT_ID = "5170233102089322756"
DEFAULT_PRICE = 8

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
current_price = DEFAULT_PRICE

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
            gift_balance INTEGER DEFAULT 0,
            join_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            stars INTEGER,
            gift_id TEXT,
            purchase_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ========== ФУНКЦИИ БАЗЫ ДАННЫХ ==========
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
    cursor.execute('SELECT stars_spent, gifts_received, gift_balance, join_date FROM users WHERE user_id = ?', (user_id,))
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

def add_gift_balance(user_id, count):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET gift_balance = gift_balance + ? WHERE user_id = ?', (count, user_id))
    conn.commit()
    conn.close()

def get_gift_balance(user_id):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT gift_balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def use_gift_balance(user_id):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT gift_balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0] > 0:
        cursor.execute('UPDATE users SET gift_balance = gift_balance - 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# ========== ФУНКЦИИ ЧЕКОВ ==========
def create_check(gifts_count: int, created_by: int, hours_valid: int = 24) -> str:
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    
    code = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(hours=hours_valid)
    
    cursor.execute('''
        INSERT INTO checks (code, gifts_count, created_by, expires_at)
        VALUES (?, ?, ?, ?)
    ''', (code, gifts_count, created_by, expires_at))
    conn.commit()
    conn.close()
    
    return code

def activate_check(code: str, user_id: int):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT gifts_count, is_activated, expires_at FROM checks WHERE code = ?', (code,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False, 0, "Чек не найден"
    
    gifts_count, is_activated, expires_at = result
    expires_at_dt = datetime.fromisoformat(expires_at)
    
    if is_activated:
        conn.close()
        return False, 0, "Чек уже активирован"
    
    if expires_at_dt < datetime.now():
        conn.close()
        return False, 0, "Чек просрочен"
    
    cursor.execute('''
        UPDATE checks 
        SET is_activated = 1, activated_by = ?, activated_at = CURRENT_TIMESTAMP
        WHERE code = ?
    ''', (user_id, code))
    
    add_gift_balance(user_id, gifts_count)
    conn.commit()
    conn.close()
    
    return True, gifts_count, "Чек активирован"

def get_check_info(code: str):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM checks WHERE code = ?', (code,))
    result = cursor.fetchone()
    conn.close()
    return result

# ========== ОТПРАВКА ПОДАРКА ЧЕРЕЗ API ==========
async def send_gift_via_api(user_id: int, gift_id: str, text: str = "Telegram моя жизнь"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendGift"
    payload = {
        "user_id": user_id,
        "gift_id": gift_id,
        "text": text,
        "pay_for_upgrade": False
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
            return result.get("ok", False), result

async def get_bot_stars_balance():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getStarBalance"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            result = await resp.json()
            if result.get("ok"):
                return result.get("result", {}).get("total_stars", 0)
            return 0

# ========== КОМАНДЫ ПОЛЬЗОВАТЕЛЯ ==========
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    balance = get_gift_balance(user.id)
    bot_balance = await get_bot_stars_balance()
    
    text = (
        f"🎁 **Бот подарков Telegram Stars**\n\n"
        f"🐻 **Подарок:** Мишка\n"
        f"📝 **Подпись:** Telegram моя жизнь\n"
        f"⭐ **Цена:** {current_price} Stars\n"
        f"💰 **Баланс бота:** {bot_balance} Stars\n"
        f"📦 **Ваши подарки:** {balance}\n\n"
        f"📌 **Команды:**\n"
        f"/buy - Купить подарок\n"
        f"/profile - Мой профиль\n"
        f"/balance - Баланс подарков\n"
        f"/activate - Активировать чек\n"
        f"/ping - Проверить бота"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 КУПИТЬ ПОДАРОК", callback_data="buy")],
        [InlineKeyboardButton(text="👤 МОЙ ПРОФИЛЬ", callback_data="profile")],
        [InlineKeyboardButton(text="⚡ АКТИВИРОВАТЬ ЧЕК", callback_data="activate")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    bot_balance = await get_bot_stars_balance()
    
    if bot_balance < current_price:
        await message.answer(
            f"⚠️ У бота недостаточно Stars для отправки подарка.\n"
            f"Требуется: {current_price}, доступно: {bot_balance}\n"
            f"Попробуйте позже.",
            parse_mode=ParseMode.MARKDOWN
        )
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"⚠️ НЕХВАТКА STARS! Баланс: {bot_balance}, цена: {current_price}")
        return
    
    prices = [LabeledPrice(label="🐻 Подарок Мишка", amount=current_price)]
    
    await bot.send_invoice(
        chat_id=user.id,
        title="🐻 Подарок Мишка",
        description=f"Подарок за {current_price} Stars с подписью 'Telegram моя жизнь'",
        payload="gift_purchase",
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
        stars_spent, gifts_received, gift_balance, join_date = stats
        text = (
            f"👤 **ПРОФИЛЬ**\n\n"
            f"👤 **Имя:** {user.first_name}\n"
            f"🔖 **Username:** @{user.username or 'Нет'}\n"
            f"📅 **В боте с:** {join_date[:10]}\n\n"
            f"⭐ **Потрачено Stars:** {stars_spent}\n"
            f"🎁 **Получено подарков:** {gifts_received}\n"
            f"📦 **Баланс подарков:** {gift_balance}\n"
        )
    else:
        text = "❌ Данные не найдены"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 КУПИТЬ", callback_data="buy")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("balance"))
async def balance_cmd(message: types.Message):
    user = message.from_user
    balance = get_gift_balance(user.id)
    await message.answer(f"📦 **Ваш баланс подарков:** {balance}", parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("activate"))
async def activate_cmd(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Используйте: `/activate КОД_ЧЕКА`", parse_mode=ParseMode.MARKDOWN)
        return
    
    code = args[1]
    user = message.from_user
    
    success, count, msg = activate_check(code, user.id)
    
    if success:
        await message.answer(
            f"✅ {msg}!\n"
            f"🎁 Получено подарков: {count}\n"
            f"💰 Баланс: {get_gift_balance(user.id)}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await message.answer(f"❌ {msg}", parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("ping"))
async def ping_cmd(message: types.Message):
    balance = await get_bot_stars_balance()
    await message.answer(f"🏓 **PONG!**\n💰 Баланс бота: {balance} Stars", parse_mode=ParseMode.MARKDOWN)

# ========== АДМИН КОМАНДЫ ==========
@dp.message(Command("set_price"))
async def set_price_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ ДОСТУП ЗАПРЕЩЁН!")
        return
    
    global current_price
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /set_price 15")
            return
        current_price = int(args[1])
        await message.answer(f"✅ Цена установлена: {current_price} Stars")
    except ValueError:
        await message.answer("❌ Введите число!")

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ ДОСТУП ЗАПРЕЩЁН!")
        return
    
    total_users, total_stars, total_gifts = get_total_stats()
    bot_balance = await get_bot_stars_balance()
    
    text = (
        f"📊 **СТАТИСТИКА БОТА**\n\n"
        f"👥 **Пользователей:** {total_users}\n"
        f"⭐ **Потрачено Stars:** {total_stars}\n"
        f"🎁 **Куплено подарков:** {total_gifts}\n"
        f"💰 **Текущая цена:** {current_price} Stars\n"
        f"🤖 **Баланс бота:** {bot_balance} Stars\n"
    )
    
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("create_check"))
async def create_check_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ ДОСТУП ЗАПРЕЩЁН!")
        return
    
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("❌ Используйте: /create_check <количество>")
        return
    
    count = int(args[1])
    code = create_check(count, message.from_user.id)
    
    text = (
        f"✅ **Чек создан!**\n\n"
        f"🎁 **Подарков:** {count}\n"
        f"🔑 **Код:** `{code}`\n"
        f"⏰ **Действителен:** 24 часа\n\n"
        f"📝 **Активация:** /activate {code}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ АКТИВИРОВАТЬ", callback_data=f"activate_{code}")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("broadcast"))
async def broadcast_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ ДОСТУП ЗАПРЕЩЁН!")
        return
    
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.answer("❌ Используйте: /broadcast Текст")
        return
    
    users = get_all_users()
    success = 0
    fail = 0
    
    status_msg = await message.answer(f"📨 Рассылка для {len(users)} пользователей...")
    
    for user_id, username, first_name in users:
        try:
            await bot.send_message(user_id, f"📢 {broadcast_text}", parse_mode=ParseMode.MARKDOWN)
            success += 1
        except:
            fail += 1
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n✅ Успешно: {success}\n❌ Ошибок: {fail}")

@dp.message(Command("user"))
async def user_info_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ ДОСТУП ЗАПРЕЩЁН!")
        return
    
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /user <user_id>")
            return
        
        user_id = int(args[1])
        stats = get_user_stats(user_id)
        
        if stats:
            stars_spent, gifts_received, gift_balance, join_date = stats
            text = (
                f"👤 **ПОЛЬЗОВАТЕЛЬ**\n\n"
                f"🆔 **ID:** `{user_id}`\n"
                f"📅 **В боте с:** {join_date[:10]}\n"
                f"⭐ **Потрачено Stars:** {stars_spent}\n"
                f"🎁 **Подарков получено:** {gifts_received}\n"
                f"📦 **Баланс подарков:** {gift_balance}\n"
            )
        else:
            text = "❌ Пользователь не найден"
        
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    except:
        await message.answer("❌ Ошибка! ID должен быть числом")

# ========== ЧЕКИ В ЧАТЕ (КАК У @SEND) ==========
@dp.message(F.text)
async def handle_check_mention(message: types.Message):
    text = message.text
    bot_username = (await bot.get_me()).username
    
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
                [InlineKeyboardButton(text="⚡ АКТИВИРОВАТЬ ЧЕК", callback_data=f"activate_{code}")]
            ])
            
            await message.reply(check_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

# ========== ПЛАТЕЖИ ==========
@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    bot_balance = await get_bot_stars_balance()
    if bot_balance < current_price:
        await query.answer(ok=False, error_message="У бота нет Stars. Попробуйте позже.")
        return
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    user = message.from_user
    stars_spent = message.successful_payment.total_amount
    
    success, response = await send_gift_via_api(user.id, GIFT_ID, "Telegram моя жизнь")
    
    if success:
        add_user(user.id, user.username or "", user.first_name or "")
        update_user_stats(user.id, stars_spent)
        
        await message.answer(
            f"✅ **ПОДАРОК ОТПРАВЛЕН!** 🎉\n\n"
            f"🐻 Мишка с подписью **'Telegram моя жизнь'** уже в вашем профиле!\n"
            f"⭐ Потрачено: {stars_spent} Stars\n\n"
            f"📱 **Как посмотреть подарок?**\n"
            f"→ Настройки Telegram\n"
            f"→ Подарки\n"
            f"→ Ваши подарки",
            parse_mode=ParseMode.MARKDOWN
        )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"💰 **НОВАЯ ПОКУПКА!**\n\n"
                f"👤 @{user.username or user.first_name} (ID: {user.id})\n"
                f"⭐ Потрачено Stars: {stars_spent}\n"
                f"🎁 Подарок отправлен!"
            )
    else:
        error = response.get('description', 'Unknown error')
        await message.answer(
            f"❌ **ОШИБКА:** {error}\n"
            f"⚠️ Администратор уведомлён.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"⚠️ **ОШИБКА sendGift**\n\n"
                f"Пользователь: {user.id} (@{user.username})\n"
                f"Stars: {stars_spent}\n"
                f"Ошибка: {error}"
            )

# ========== КНОПКИ ==========
@dp.callback_query(F.data == "buy")
async def buy_callback(callback: types.CallbackQuery):
    await callback.answer("🛒 Оформляем покупку...")
    await buy_cmd(callback.message)

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: types.CallbackQuery):
    await callback.answer("👤 Загружаем профиль...")
    await profile_cmd(callback.message)

@dp.callback_query(F.data == "activate")
async def activate_callback_menu(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("📝 Введите код чека: /activate КОД")

@dp.callback_query(F.data.startswith("activate_"))
async def activate_check_callback(callback: types.CallbackQuery):
    code = callback.data.replace("activate_", "")
    user = callback.from_user
    
    success, count, msg = activate_check(code, user.id)
    
    if success:
        await callback.answer(f"✅ Получено {count} подарков!", show_alert=True)
        await callback.message.edit_text(
            f"✅ **Чек активирован!**\n\n"
            f"🎁 Получено подарков: {count}\n"
            f"👤 Пользователь: @{user.username or user.first_name}\n"
            f"💰 Баланс подарков: {get_gift_balance(user.id)}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)

# ========== ЗАПУСК ==========
async def main():
    balance = await get_bot_stars_balance()
    print("🚀 БОТ ЗАПУЩЕН!")
    print(f"💰 Баланс бота: {balance} Stars")
    print(f"🎁 Цена подарка: {current_price} Stars")
    print(f"🐻 ID подарка: {GIFT_ID}")
    
    if balance < current_price:
        print("⚠️ ВНИМАНИЕ! У бота НЕ ХВАТАЕТ Stars для отправки подарков!")
        print("   Пополните баланс через @BotFather → Payments → Stars → Deposit")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
