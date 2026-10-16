import asyncio
import aiohttp
import sqlite3
import secrets
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram import BaseMiddleware

# Add BOT_TOKEN in your hosting panel environment variables.
BOT_TOKEN = os.getenv("BOT_TOKEN").strip()
ADMIN_IDS = [7673683792]  # Telegram numeric IDs of trusted admins
if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN в переменных окружения хостинга")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class CommandCleanupMiddleware(BaseMiddleware):
    """Remove slash-commands after processing; menu navigation edits one message."""
    async def __call__(self, handler, event, data):
        result = await handler(event, data)
        if isinstance(event, types.Message) and event.text and event.text.startswith("/"):
            try:
                await event.delete()
            except Exception:
                pass
        return result


dp.message.outer_middleware(CommandCleanupMiddleware())

DEFAULT_COMMENT = "@DuDRovEGift залетай в нашу банду"
GIFT_PRICE = 75
current_price = GIFT_PRICE
GIFT_CATALOG = [
    {"key": "santa_bear", "emoji": "🧸🎅", "name": "Мишка в шапке", "id": "5956217000635139069"},
    {"key": "tree", "emoji": "🎄", "name": "Новогодняя ёлка", "id": "5922558454332916696"},
    {"key": "heart_bear", "emoji": "🧸❤️", "name": "Мишка с сердцем", "id": "5800655655995968830"},
    {"key": "love", "emoji": "💝", "name": "LOVE", "id": "5801108895304779062"},
    {"key": "pink_bear", "emoji": "🧸🌸", "name": "Розовый мишка", "id": "5866352046986232958"},
    {"key": "green_bear", "emoji": "🧸🍀", "name": "Мишка в зелёном", "id": "5893356958802511476"},
    {"key": "clown_bear", "emoji": "🤡🧸", "name": "Мишка с шариком", "id": "5935895822435615975"},
    {"key": "bunny_bear", "emoji": "🐰🧸", "name": "Мишка-зайчик", "id": "5969796561943660080"},
    {"key": "football_bear", "emoji": "🧸⚽", "name": "Мишка с мячом", "id": "59742106329777745012"},
]

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
            total_donated INTEGER DEFAULT 0,
            join_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value INTEGER
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
            comment TEXT,
            purchase_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            donation_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("price", 75)')
    conn.commit()
    conn.close()

init_db()

def load_price():
    global current_price
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = "price"')
    result = cursor.fetchone()
    conn.close()
    if result:
        current_price = result[0]

def save_price(price):
    global current_price
    current_price = price
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE settings SET value = ? WHERE key = "price"', (price,))
    conn.commit()
    conn.close()

# Catalog pricing is fixed at GIFT_PRICE for every item.

def add_user(user_id, username, first_name):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, ?)',
                   (user_id, username, first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_user_stats(user_id, stars):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET stars_spent = stars_spent + ?, gifts_received = gifts_received + 1 WHERE user_id = ?', (stars, user_id))
    conn.commit()
    conn.close()

def add_donation(user_id, amount):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO donations (user_id, amount) VALUES (?, ?)', (user_id, amount))
    cursor.execute('UPDATE users SET total_donated = total_donated + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_top_donors(limit=10):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, total_donated FROM users WHERE total_donated > 0 ORDER BY total_donated DESC LIMIT ?', (limit,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_user_stats(user_id):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT stars_spent, gifts_received, gift_balance, total_donated, join_date FROM users WHERE user_id = ?', (user_id,))
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
    cursor.execute('SELECT SUM(total_donated) FROM users')
    total_donated = cursor.fetchone()[0] or 0
    conn.close()
    return total_users, total_stars, total_gifts, total_donated

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

def create_check(gifts_count: int, created_by: int, hours_valid: int = 24) -> str:
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    code = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(hours=hours_valid)
    cursor.execute('INSERT INTO checks (code, gifts_count, created_by, expires_at) VALUES (?, ?, ?, ?)', 
                   (code, gifts_count, created_by, expires_at))
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
    
    cursor.execute('UPDATE checks SET is_activated = 1, activated_by = ?, activated_at = CURRENT_TIMESTAMP WHERE code = ?', (user_id, code))
    cursor.execute('UPDATE users SET gift_balance = gift_balance + ? WHERE user_id = ?', (gifts_count, user_id))
    conn.commit()
    conn.close()
    return True, gifts_count, f"Активирован! Получено {gifts_count} подарков"

async def send_gift_via_api(user_id: int, gift_id: str, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendGift"
    payload = {"user_id": user_id, "gift_id": gift_id, "text": text, "pay_for_upgrade": False}
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

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 КАТАЛОГ ПОДАРКОВ", callback_data="buy")],
        [InlineKeyboardButton(text="👤 МОЙ ПРОФИЛЬ", callback_data="profile")],
        [InlineKeyboardButton(text="💝 ПОДДЕРЖАТЬ", callback_data="donate_menu")],
        [InlineKeyboardButton(text="🏆 ТОП ДОНАТЕРОВ", callback_data="top_donors")],
        [InlineKeyboardButton(text="⚡ АКТИВИРОВАТЬ ЧЕК", callback_data="activate_menu")],
        [InlineKeyboardButton(text="💰 БАЛАНС БОТА", callback_data="bot_balance")]
    ])

def get_gift_keyboard():
    rows = []
    for gift in GIFT_CATALOG:
        rows.append([InlineKeyboardButton(
            text=f"{gift['emoji']} {gift['name']} — {GIFT_PRICE} ⭐",
            callback_data=f"gift_{gift['key']}"
        )])
    rows.append([InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def find_gift(key):
    return next((gift for gift in GIFT_CATALOG if gift["key"] == key), None)


def get_donate_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 10 STARS", callback_data="donate_10")],
        [InlineKeyboardButton(text="⭐ 25 STARS", callback_data="donate_25")],
        [InlineKeyboardButton(text="⭐ 50 STARS", callback_data="donate_50")],
        [InlineKeyboardButton(text="⭐ 100 STARS", callback_data="donate_100")],
        [InlineKeyboardButton(text="⭐ 250 STARS", callback_data="donate_250")],
        [InlineKeyboardButton(text="⭐ 500 STARS", callback_data="donate_500")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_to_main")]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика и баланс", callback_data="stats")],
        [InlineKeyboardButton(text="🎫 Создать чек", callback_data="create_check_menu"), InlineKeyboardButton(text="⚡ Проверить чек", callback_data="checks_info")],
        [InlineKeyboardButton(text="💰 Цена каталога: 75 ⭐", callback_data="set_price_menu")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton(text="🔎 Найти пользователя", callback_data="find_user")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
    ])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    text = (
        "🎁 <b>GIFT STORE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Подарки Telegram за Stars\n\n"
        f"✨ В каталоге: {len(GIFT_CATALOG)} подарков\n"
        f"💎 Цена каждого: <b>{GIFT_PRICE} ⭐</b>\n\n"
        "Выберите действие в меню ниже. Навигация работает через одну панель, "
        "поэтому чат не будет засоряться сообщениями."
    )
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    text = "🧸 **ГЛАВНОЕ МЕНЮ**\n\nВыберите действие:"
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data == "buy")
async def buy_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎁 <b>КАТАЛОГ ПОДАРКОВ</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"Выберите подарок. Каждый стоит <b>{GIFT_PRICE} ⭐</b>.",
        reply_markup=get_gift_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("gift_"))
async def gift_choice_callback(callback: types.CallbackQuery):
    gift = find_gift(callback.data.removeprefix("gift_"))
    if not gift:
        await callback.answer("Подарок не найден", show_alert=True)
        return
    user = callback.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    await bot.send_invoice(
        chat_id=user.id,
        title=f"{gift['emoji']} {gift['name']}",
        description=f"Подарок Telegram. Стоимость {GIFT_PRICE} Stars.",
        payload=f"gift_{gift['key']}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=gift["name"], amount=GIFT_PRICE)],
        start_parameter=f"gift_{gift['key']}"
    )
    await callback.answer("Счёт отправлен в личный чат")


@dp.callback_query(F.data == "donate_menu")
async def donate_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💝 **ПОДДЕРЖАТЬ ПРОЕКТ**\n\n"
        "Выберите сумму доната:\n\n"
        "⭐ 10+ Stars — благодарность\n"
        "⭐ 50+ Stars — именная запись\n"
        "⭐ 100+ Stars — VIP статус\n\n"
        "Все донаты идут на развитие бота!",
        reply_markup=get_donate_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("donate_"))
async def donate_callback(callback: types.CallbackQuery):
    amount = int(callback.data.replace("donate_", ""))
    user = callback.from_user
    
    add_user(user.id, user.username or "", user.first_name or "")
    
    prices = [LabeledPrice(label="💝 Донат", amount=amount)]
    
    await bot.send_invoice(
        chat_id=user.id,
        title="💝 Поддержка",
        description=f"Спасибо за поддержку! {amount} Stars",
        payload=f"donate_{amount}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="donate_purchase"
    )
    await callback.answer()

@dp.callback_query(F.data == "top_donors")
async def top_donors_callback(callback: types.CallbackQuery):
    donors = get_top_donors(10)
    
    if not donors:
        text = "🏆 **ТОП ДОНАТЕРОВ**\n\nПока никого нет. Будьте первым! 💝"
    else:
        text = "🏆 **ТОП ДОНАТЕРОВ**\n\n"
        for i, (user_id, username, first_name, total) in enumerate(donors, 1):
            name = f"@{username}" if username else first_name
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {name} — {total} ⭐\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💝 ТОЖЕ ПОДДЕРЖАТЬ", callback_data="donate_menu")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: types.CallbackQuery):
    user = callback.from_user
    stats = get_user_stats(user.id)
    
    if stats:
        stars_spent, gifts_received, gift_balance, total_donated, join_date = stats
        text = (
            f"👤 **ВАШ ПРОФИЛЬ**\n\n"
            f"📛 **Имя:** {user.first_name}\n"
            f"🔖 **Username:** @{user.username or 'Нет'}\n"
            f"📅 **В боте с:** {join_date[:10]}\n\n"
            f"⭐ **Потрачено Stars:** {stars_spent}\n"
            f"🎁 **Куплено подарков:** {gifts_received}\n"
            f"📦 **Баланс подарков:** {gift_balance}\n"
            f"💝 **Всего донатов:** {total_donated} ⭐"
        )
    else:
        text = "❌ Данные не найдены"
    
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data == "bot_balance")
async def bot_balance_callback(callback: types.CallbackQuery):
    balance = await get_bot_stars_balance()
    await callback.message.edit_text(
        f"💰 **БАЛАНС БОТА:** {balance} Stars\n\n"
        f"💡 Эти Stars используются для отправки подарков.",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@dp.callback_query(F.data == "activate_menu")
async def activate_menu_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⚡ **АКТИВАЦИЯ ЧЕКА**\n\n"
        "Введите код чека командой:\n"
        "`/activate КОД`\n\n"
        "Пример: `/activate abc123`",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@dp.message(Command("activate"))
async def activate_cmd(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Используйте: `/activate КОД`", parse_mode=ParseMode.MARKDOWN)
        return
    
    code = args[1]
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    success, count, msg = activate_check(code, user.id)
    
    if success:
        await message.answer(f"✅ {msg}\n💰 Баланс: {get_gift_balance(user.id)}")
    else:
        await message.answer(f"❌ {msg}")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ ДОСТУП ЗАПРЕЩЁН!")
        return
    
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(
        "👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n━━━━━━━━━━━━━━━━━━\n"
        "Управление магазином, чеками и пользователями.",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "set_price_menu")
async def set_price_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"💰 <b>ЦЕНА КАТАЛОГА</b>\n\n"
        f"Все подарки из изображения стоят фиксированно <b>{GIFT_PRICE} ⭐</b>.\n"
        f"Чтобы изменить цену, поменяйте GIFT_PRICE в файле main.py и перезапустите бота.",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@dp.message(Command("set_price"))
async def set_price_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ ДОСТУП ЗАПРЕЩЁН!")
        return
    
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /set_price <число>")
            return
        new_price = int(args[1])
        if new_price < 1:
            await message.answer("❌ Цена должна быть больше 0!")
            return
        await message.answer("ℹ️ Цена подарков фиксирована на 75 ⭐. Измените GIFT_PRICE в main.py, если хотите другую цену.")
    except ValueError:
        await message.answer("❌ Введите число!")

@dp.callback_query(F.data == "stats")
async def stats_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    total_users, total_stars, total_gifts, total_donated = get_total_stats()
    bot_balance = await get_bot_stars_balance()
    
    text = (
        f"📊 **СТАТИСТИКА БОТА**\n\n"
        f"👥 **Пользователей:** {total_users}\n"
        f"⭐ **Потрачено Stars:** {total_stars}\n"
        f"🎁 **Куплено подарков:** {total_gifts}\n"
        f"💝 **Собрано донатов:** {total_donated} ⭐\n"
        f"🤖 **Баланс бота:** {bot_balance} Stars\n"
        f"💰 **Цена каждого подарка:** {GIFT_PRICE} Stars"
    )
    
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data == "create_check_menu")
async def create_check_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎫 **СОЗДАНИЕ ЧЕКА**\n\n"
        "Введите количество подарков командой:\n"
        "`/create_check <число>`\n\n"
        "Пример: `/create_check 5`",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

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
    if not 1 <= count <= 10000:
        await message.answer("❌ Количество должно быть от 1 до 10000.")
        return
    code = create_check(count, message.from_user.id)
    
    text = (
        f"✅ **ЧЕК СОЗДАН!**\n\n"
        f"🎁 **Подарков:** {count}\n"
        f"🔑 **Код:** `{code}`\n"
        f"⏰ **Действителен:** 24 часа\n\n"
        f"📝 **Активация:** /activate {code}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ АКТИВИРОВАТЬ", callback_data=f"activate_now_{code}")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.callback_query(F.data.startswith("activate_now_"))
async def activate_now_callback(callback: types.CallbackQuery):
    code = callback.data.replace("activate_now_", "")
    user = callback.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    success, count, msg = activate_check(code, user.id)
    
    if success:
        await callback.answer(f"✅ Получено {count} подарков!", show_alert=True)
        await callback.message.edit_text(
            f"✅ **ЧЕК АКТИВИРОВАН!**\n\n"
            f"🎁 Получено подарков: {count}\n"
            f"👤 Пользователь: @{user.username or user.first_name}\n"
            f"💰 Баланс: {get_gift_balance(user.id)}"
        )
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)

@dp.callback_query(F.data == "checks_info")
async def checks_info_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    conn = sqlite3.connect('gift_bot.db')
    rows = conn.execute(
        'SELECT code, gifts_count, is_activated, expires_at FROM checks ORDER BY created_at DESC LIMIT 10'
    ).fetchall()
    conn.close()
    if not rows:
        text = "🎫 <b>ЧЕКИ</b>\nПока чеков нет."
    else:
        lines = ["🎫 <b>ПОСЛЕДНИЕ 10 ЧЕКОВ</b>"]
        for code, count, activated, expires in rows:
            status = "✅ активирован" if activated else "🟢 активен"
            lines.append(f"• <code>{code}</code> — {count} подарков · {status} · до {expires}")
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()


@dp.callback_query(F.data == "broadcast")
async def broadcast_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 **РАССЫЛКА**\n\n"
        "Введите текст рассылки командой:\n"
        "`/broadcast <текст>`\n\n"
        "Пример: `/broadcast Всем привет!`",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

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

@dp.callback_query(F.data == "find_user")
async def find_user_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 **ПОИСК ПОЛЬЗОВАТЕЛЯ**\n\n"
        "Введите ID пользователя командой:\n"
        "`/user <id>`\n\n"
        "Пример: `/user 123456789`",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

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
            stars_spent, gifts_received, gift_balance, total_donated, join_date = stats
            text = (
                f"👤 **ПОЛЬЗОВАТЕЛЬ**\n\n"
                f"🆔 **ID:** `{user_id}`\n"
                f"📅 **В боте с:** {join_date[:10]}\n"
                f"⭐ **Потрачено Stars:** {stars_spent}\n"
                f"🎁 **Подарков получено:** {gifts_received}\n"
                f"📦 **Баланс подарков:** {gift_balance}\n"
                f"💝 **Донатов:** {total_donated} ⭐"
            )
        else:
            text = "❌ Пользователь не найден"
        
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    except:
        await message.answer("❌ Ошибка! ID должен быть числом")

@dp.message(F.text)
async def handle_check_in_chat(message: types.Message):
    text = message.text
    bot_username = (await bot.get_me()).username
    
    if text.startswith(f"@{bot_username}"):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            gifts_count = int(parts[1])
            
            if gifts_count <= 0 or gifts_count > 100:
                await message.reply("❌ Количество подарков от 1 до 100")
                return
            
            code = create_check(gifts_count, message.from_user.id)
            
            check_text = (
                f"✨ **ЧЕК НА {gifts_count} ПОДАРКОВ** ✨\n\n"
                f"🔑 **Код:** `{code}`\n"
                f"⏰ **Действует:** 24 часа"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡ АКТИВИРОВАТЬ", callback_data=f"activate_now_{code}")]
            ])
            
            await message.reply(check_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    user = message.from_user
    payload = message.successful_payment.invoice_payload
    stars_spent = message.successful_payment.total_amount
    
    if payload.startswith("donate"):
        amount = int(payload.split("_")[1])
        add_user(user.id, user.username or "", user.first_name or "")
        add_donation(user.id, amount)
        
        if amount >= 100:
            await message.answer(
                f"💝 **СПАСИБО ЗА ЩЕДРЫЙ ДОНАТ!**\n\n"
                f"Вы пожертвовали {amount} Stars!\n"
                f"Вы получаете VIP статус!\n\n"
                f"🏆 Вы в ТОПе донатеров!",
                reply_markup=get_main_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.answer(
                f"💝 **СПАСИБО ЗА ПОДДЕРЖКУ!**\n\n"
                f"Вы пожертвовали {amount} Stars!",
                reply_markup=get_main_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"💝 Донат: @{user.username or user.first_name} | {amount} ⭐")
    
    else:
        gift_key = payload.removeprefix("gift_") if payload.startswith("gift_") else GIFT_CATALOG[0]["key"]
        gift = find_gift(gift_key)
        if not gift:
            await message.answer("❌ Не удалось определить подарок. Напишите администратору.")
            return
        comment = DEFAULT_COMMENT
        success, response = await send_gift_via_api(user.id, gift["id"], comment)
        add_user(user.id, user.username or "", user.first_name or "")
        if success:
            update_user_stats(user.id, stars_spent)
            conn = sqlite3.connect('gift_bot.db')
            conn.execute('INSERT INTO purchases (user_id, stars, gift_id, comment) VALUES (?, ?, ?, ?)',
                         (user.id, stars_spent, gift["id"], comment))
            conn.commit()
            conn.close()
            await message.answer(
                f"✅ <b>ПОДАРОК ОТПРАВЛЕН</b>\n\n{gift['emoji']} <b>{gift['name']}</b>\n"
                f"⭐ Оплачено: {stars_spent} Stars\n💬 Комментарий: {comment}",
                reply_markup=get_main_keyboard(), parse_mode=ParseMode.HTML
            )
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, f"🛍 Покупка: {user.id} | {gift['name']} | {stars_spent} ⭐")
                except Exception:
                    pass
        else:
            error = response.get('description', 'Неизвестная ошибка')
            add_gift_balance(user.id, 1)
            await message.answer(
                f"⚠️ Оплата прошла, но Telegram не отправил подарок автоматически.\n"
                f"{gift['emoji']} {gift['name']} сохранён в балансе; свяжитесь с администратором.\n"
                f"Код ошибки: {error}", reply_markup=get_main_keyboard()
            )
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, f"⚠️ Не удалось отправить {gift['name']}. Пользователь {user.id}; {error}")
                except Exception:
                    pass

async def main():
    balance = await get_bot_stars_balance()
    print("🚀 БОТ ЗАПУЩЕН!")
    print(f"💰 Баланс бота: {balance} Stars")
    print(f"🎁 Подарков в каталоге: {len(GIFT_CATALOG)}")
    print(f"💰 Цена каждого: {GIFT_PRICE} Stars")
    print(f"💬 Комментарий: {DEFAULT_COMMENT}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
