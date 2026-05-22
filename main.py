import asyncio
import aiohttp
import sqlite3
import secrets
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

BOT_TOKEN = "8105002960:AAGF4uFOi8uTRHIhjwLn1ifhtTbZqp26DPk"
ADMIN_IDS = [7673683792]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

GIFTS = {
    "bear": {"id": "5956217000635139069", "name": "🧸 Плюшевый мишка", "emoji": "🧸"},
    "heart": {"id": "5170145012310081615", "name": "💝 Сердце с лентой", "emoji": "💝"}
}

current_price = 15

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
            gift_name TEXT,
            comment TEXT,
            purchase_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            message TEXT,
            donation_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("price", 15)')
    
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

load_price()

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

def update_donation_stats(user_id, amount):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET total_donated = total_donated + ?
        WHERE user_id = ?
    ''', (amount, user_id))
    conn.commit()
    conn.close()

def add_donation(user_id, amount, message=""):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO donations (user_id, amount, message)
        VALUES (?, ?, ?)
    ''', (user_id, amount, message))
    conn.commit()
    conn.close()
    update_donation_stats(user_id, amount)

def add_purchase(user_id, stars, gift_id, gift_name, comment=""):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO purchases (user_id, stars, gift_id, gift_name, comment)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, stars, gift_id, gift_name, comment))
    conn.commit()
    conn.close()

def get_top_donors(limit=10):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, first_name, total_donated 
        FROM users 
        WHERE total_donated > 0 
        ORDER BY total_donated DESC 
        LIMIT ?
    ''', (limit,))
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
        return False, 0, "❌ Чек не найден"
    
    gifts_count, is_activated, expires_at = result
    expires_at_dt = datetime.fromisoformat(expires_at)
    
    if is_activated:
        conn.close()
        return False, 0, "❌ Чек уже активирован"
    
    if expires_at_dt < datetime.now():
        conn.close()
        return False, 0, "❌ Чек просрочен"
    
    cursor.execute('''
        UPDATE checks 
        SET is_activated = 1, activated_by = ?, activated_at = CURRENT_TIMESTAMP
        WHERE code = ?
    ''', (user_id, code))
    
    add_gift_balance(user_id, gifts_count)
    conn.commit()
    conn.close()
    return True, gifts_count, f"✅ Активирован! Получено {gifts_count} подарков"

async def send_gift_via_api(user_id: int, gift_id: str, text: str = None, bot_username: str = None):
    if text is None:
        text = f"Подарок от @{bot_username}" if bot_username else "Подарок"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendGift"
    payload = {
        "user_id": user_id,
        "gift_id": gift_id,
        "text": text,
        "pay_for_upgrade": True
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

def get_gifts_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧸 ПЛЮШЕВЫЙ МИШКА", callback_data="gift_bear")],
        [InlineKeyboardButton(text="💝 СЕРДЦЕ С ЛЕНТОЙ", callback_data="gift_heart")],
        [InlineKeyboardButton(text="💝 ПОДДЕРЖАТЬ", callback_data="donate_menu")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_to_main")]
    ])

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 ◈ КУПИТЬ ПОДАРОК", callback_data="gifts_menu")],
        [InlineKeyboardButton(text="👤 ◈ МОЙ ПРОФИЛЬ", callback_data="profile")],
        [InlineKeyboardButton(text="📦 ◈ МОИ ПОДАРКИ", callback_data="balance")],
        [InlineKeyboardButton(text="💝 ◈ ПОДДЕРЖАТЬ", callback_data="donate_menu")],
        [InlineKeyboardButton(text="🏆 ◈ ТОП ДОНАТЕРОВ", callback_data="top_donors")],
        [InlineKeyboardButton(text="⚡ ◈ АКТИВИРОВАТЬ ЧЕК", callback_data="activate_menu")],
        [InlineKeyboardButton(text="💰 ◈ БАЛАНС БОТА", callback_data="bot_balance")]
    ])

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
        [InlineKeyboardButton(text="💰 УСТАНОВИТЬ ЦЕНУ", callback_data="set_price_menu")],
        [InlineKeyboardButton(text="📊 СТАТИСТИКА", callback_data="stats")],
        [InlineKeyboardButton(text="🎫 СОЗДАТЬ ЧЕК", callback_data="create_check_menu")],
        [InlineKeyboardButton(text="📢 РАССЫЛКА", callback_data="broadcast")],
        [InlineKeyboardButton(text="🔍 НАЙТИ ПОЛЬЗОВАТЕЛЯ", callback_data="find_user")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_to_main")]
    ])

def get_comment_keyboard(gift_key: str, gift_name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 ДОБАВИТЬ КОММЕНТАРИЙ (+3⭐)", callback_data=f"comment_{gift_key}")],
        [InlineKeyboardButton(text="⏩ БЕЗ КОММЕНТАРИЯ", callback_data=f"no_comment_{gift_key}")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="gifts_menu")]
    ])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    text = (
        "✨ **ПОДАРКИ ЗА TELEGRAM STARS** ✨\n\n"
        "Добро пожаловать в магазин реальных подарков для профиля Telegram!\n\n"
        f"🎁 **Доступные подарки:**\n"
        f"  🧸 Плюшевый мишка — {current_price}⭐\n"
        f"  💝 Сердце с лентой — {current_price}⭐\n\n"
        f"💬 **Комментарий к подарку:**\n"
        f"   • Без комментария: @{user.username or user.first_name}\n"
        f"   • С комментарием: +3 Stars\n\n"
        "🎁 **Выберите подарок в меню ниже**"
    )
    
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    user = callback.from_user
    text = "✨ **ГЛАВНОЕ МЕНЮ**\n\nВыберите действие:"
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data == "gifts_menu")
async def gifts_menu(callback: types.CallbackQuery):
    text = (
        "🎁 **ВЫБЕРИТЕ ПОДАРОК**\n\n"
        f"🧸 Плюшевый мишка — {current_price}⭐\n"
        f"💝 Сердце с лентой — {current_price}⭐\n\n"
        f"💬 Комментарий: +3 Stars"
    )
    
    await callback.message.edit_text(text, reply_markup=get_gifts_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data.startswith("gift_"))
async def select_gift(callback: types.CallbackQuery):
    gift_key = callback.data.replace("gift_", "")
    gift = GIFTS.get(gift_key)
    
    if not gift:
        await callback.answer("Подарок не найден")
        return
    
    text = (
        f"{gift['emoji']} **{gift['name']}**\n\n"
        f"💰 **Цена:** {current_price} Stars\n"
        f"💬 **Комментарий:**\n"
        f"   • Без комментария — @{callback.from_user.username or callback.from_user.first_name}\n"
        f"   • С комментарием — +3 Stars ({current_price + 3} Stars)\n\n"
        f"Выберите вариант:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_comment_keyboard(gift_key, gift['name']), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data.startswith("comment_"))
async def with_comment(callback: types.CallbackQuery):
    gift_key = callback.data.replace("comment_", "")
    gift = GIFTS.get(gift_key)
    user = callback.from_user
    
    if not gift:
        await callback.answer("Подарок не найден")
        return
    
    await callback.message.edit_text(
        f"📝 **ВВЕДИТЕ КОММЕНТАРИЙ**\n\n"
        f"Подарок: {gift['emoji']} {gift['name']}\n"
        f"💰 Цена с комментарием: {current_price + 3} Stars\n\n"
        f"Отправьте текстовое сообщение — это будет подпись к подарку.\n"
        f"Максимум 100 символов."
    )
    
    async with dp.fsm.storage:
        await dp.fsm.storage.set_state(user.id, "waiting_comment")
        await dp.fsm.storage.set_data(user.id, {"gift_key": gift_key})
    
    await callback.answer()

@dp.callback_query(F.data.startswith("no_comment_"))
async def without_comment(callback: types.CallbackQuery):
    gift_key = callback.data.replace("no_comment_", "")
    gift = GIFTS.get(gift_key)
    user = callback.from_user
    
    if not gift:
        await callback.answer("Подарок не найден")
        return
    
    comment = f"Подарок от @{user.username or user.first_name}"
    
    prices = [LabeledPrice(label=f"{gift['emoji']} {gift['name']}", amount=current_price)]
    
    await bot.send_invoice(
        chat_id=user.id,
        title=f"{gift['emoji']} {gift['name']}",
        description=f"Подарок без комментария. Подпись: {comment}",
        payload=f"gift_{gift_key}_no_comment",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="gift_purchase"
    )
    await callback.answer()

@dp.message()
async def handle_comment_input(message: types.Message):
    user = message.from_user
    
    async with dp.fsm.storage:
        state = await dp.fsm.storage.get_state(user.id)
        
        if state == "waiting_comment":
            comment = message.text[:100]
            data = await dp.fsm.storage.get_data(user.id)
            gift_key = data.get("gift_key")
            gift = GIFTS.get(gift_key)
            
            await dp.fsm.storage.set_state(user.id, None)
            
            if gift:
                prices = [LabeledPrice(label=f"{gift['emoji']} {gift['name']} + комментарий", amount=current_price + 3)]
                
                await bot.send_invoice(
                    chat_id=user.id,
                    title=f"{gift['emoji']} {gift['name']}",
                    description=f"Подарок с комментарием: {comment}",
                    payload=f"gift_{gift_key}_comment_{comment}",
                    provider_token="",
                    currency="XTR",
                    prices=prices,
                    start_parameter="gift_purchase"
                )

@dp.callback_query(F.data == "donate_menu")
async def donate_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💝 **ПОДДЕРЖАТЬ ПРОЕКТ**\n\n"
        "Выберите сумму доната:\n\n"
        "⭐ 1 Star = поддержка\n"
        "⭐ 10+ Stars = благодарность\n"
        "⭐ 50+ Stars = именная запись\n"
        "⭐ 100+ Stars = VIP статус\n\n"
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
        description=f"Спасибо за поддержку! {amount} Stars помогут развитию.",
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
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."
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
            f"📦 **Доступно подарков:** {gift_balance}\n"
            f"💝 **Всего донатов:** {total_donated} ⭐"
        )
    else:
        text = "❌ Данные не найдены"
    
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def balance_callback(callback: types.CallbackQuery):
    user = callback.from_user
    balance = get_gift_balance(user.id)
    await callback.message.edit_text(
        f"📦 **ВАШ БАЛАНС ПОДАРКОВ:** {balance}\n\n"
        f"Используйте подарки через команду `/send_gift @username`\n\n"
        f"💡 Подарки можно дарить друзьям!",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@dp.callback_query(F.data == "bot_balance")
async def bot_balance_callback(callback: types.CallbackQuery):
    balance = await get_bot_stars_balance()
    await callback.message.edit_text(
        f"💰 **БАЛАНС БОТА:** {balance} Stars\n\n"
        f"💡 Эти Stars используются для отправки подарков.\n"
        f"💝 Вы можете пополнить баланс бота через донат!",
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
        await message.answer("❌ Используйте: `/activate КОД_ЧЕКА`", parse_mode=ParseMode.MARKDOWN)
        return
    
    code = args[1]
    user = message.from_user
    
    success, count, msg = activate_check(code, user.id)
    
    if success:
        await message.answer(f"✅ {msg}\n💰 Текущий баланс: {get_gift_balance(user.id)}")
    else:
        await message.answer(f"❌ {msg}")

@dp.message(Command("send_gift"))
async def send_gift_cmd(message: types.Message):
    user = message.from_user
    balance = get_gift_balance(user.id)
    
    if balance <= 0:
        await message.answer("❌ У вас нет подарков в балансе!")
        return
    
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Используйте: `/send_gift @username`", parse_mode=ParseMode.MARKDOWN)
        return
    
    target = args[1].replace("@", "")
    
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET gift_balance = gift_balance - 1 WHERE user_id = ?', (user.id,))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Подарок отправлен пользователю {target}!")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ ДОСТУП ЗАПРЕЩЁН!")
        return
    
    await message.answer(
        "👑 **АДМИН ПАНЕЛЬ**\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query(F.data == "set_price_menu")
async def set_price_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"💰 **УСТАНОВКА ЦЕНЫ**\n\n"
        f"Текущая цена: {current_price} Stars\n\n"
        f"Введите новую цену командой:\n"
        f"`/set_price <число>`\n\n"
        f"Пример: `/set_price 20`",
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
        save_price(new_price)
        await message.answer(f"✅ Цена установлена: {new_price} Stars для всех подарков!")
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
        f"💰 **Текущая цена:** {current_price} Stars"
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
        await callback.answer(msg, show_alert=True)

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
        add_donation(user.id, amount, "")
        
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
                f"Вы пожертвовали {amount} Stars!\n"
                f"🌟 Ваша помощь помогает боту развиваться!",
                reply_markup=get_main_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"💝 Донат: @{user.username or user.first_name} | {amount} ⭐")
    
    elif payload.startswith("gift"):
        parts = payload.split("_")
        gift_key = parts[1]
        gift = GIFTS.get(gift_key)
        
        if gift:
            bot_info = await bot.get_me()
            
            if "no_comment" in payload:
                comment = f"Подарок от @{user.username or user.first_name}"
            else:
                comment = payload.split("_comment_")[1] if "_comment_" in payload else f"Подарок от @{bot_info.username}"
            
            success, response = await send_gift_via_api(user.id, gift["id"], comment, bot_info.username)
            
            if success:
                add_user(user.id, user.username or "", user.first_name or "")
                update_user_stats(user.id, stars_spent)
                add_purchase(user.id, stars_spent, gift["id"], gift["name"], comment)
                
                await message.answer(
                    f"✅ **ПОДАРОК ОТПРАВЛЕН!** 🎉\n\n"
                    f"{gift['emoji']} **{gift['name']}**\n"
                    f"💬 Комментарий: {comment}\n"
                    f"⭐ Потрачено: {stars_spent} Stars\n\n"
                    f"📱 Подарок уже в вашем профиле!",
                    reply_markup=get_main_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                
                for admin_id in ADMIN_IDS:
                    await bot.send_message(admin_id, f"💰 Покупка: @{user.username or user.first_name} | {gift['name']} | {stars_spent} ⭐")
            else:
                error = response.get('description', 'Unknown error')
                add_user(user.id, user.username or "", user.first_name or "")
                add_gift_balance(user.id, 1)
                
                await message.answer(
                    f"✅ **ПОДАРОК ДОБАВЛЕН В БАЛАНС!** 📦\n\n"
                    f"{gift['emoji']} {gift['name']}\n"
                    f"У бота временно нет Stars, но подарок сохранён.\n"
                    f"Используйте `/send_gift @username`\n\n"
                    f"⭐ Потрачено: {stars_spent} Stars",
                    reply_markup=get_main_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                
                for admin_id in ADMIN_IDS:
                    await bot.send_message(admin_id, f"⚠️ Ошибка: {error}\nПользователь: {user.id} | {stars_spent} ⭐")

async def main():
    balance = await get_bot_stars_balance()
    print("🚀 БОТ ЗАПУЩЕН!")
    print(f"💰 Баланс бота: {balance} Stars")
    print(f"🎁 Доступно подарков: 2 (Мишка и Сердце)")
    print(f"💰 Текущая цена: {current_price} Stars для всех подарков")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
