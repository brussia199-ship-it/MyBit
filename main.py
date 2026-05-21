import asyncio
import sqlite3
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.raw.types import LabeledPrice, PreCheckoutQuery
from pyrogram.enums import ParseMode

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8105002960:AAGF4uFOi8uTRHIhjwLn1ifhtTbZqp26DPk"        # Токен бота от @BotFather
ADMIN_IDS = [7673683792]                  # Ваш Telegram ID
GIFT_ID = "5025876399963955719"          # ID подарка (мишка)
DEFAULT_PRICE = 10                       # Цена по умолчанию в Stars

# ========== ИНИЦИАЛИЗАЦИЯ ==========
app = Client("gift_bot", bot_token=BOT_TOKEN)

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
            balance INTEGER DEFAULT 0,
            join_date TEXT DEFAULT CURRENT_TIMESTAMP
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
            gifts_received = gifts_received + 1,
            balance = balance + 1
        WHERE user_id = ?
    ''', (stars, user_id))
    conn.commit()
    conn.close()
    
    cursor.execute('''
        INSERT INTO purchases (user_id, stars, gift_id)
        VALUES (?, ?, ?)
    ''', (user_id, stars, GIFT_ID))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect('gift_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT stars_spent, gifts_received, balance, join_date FROM users WHERE user_id = ?', (user_id,))
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

# ========== КОМАНДЫ ПОЛЬЗОВАТЕЛЯ ==========
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    text = (
        "🎁 **Бот подарков Telegram Stars** 🎁\n\n"
        "Я отправляю **реальные подарки** в профиль!\n\n"
        f"🐻 **Подарок:** Мишка\n"
        f"📝 **Подпись:** Telegram моя жизнь\n"
        f"⭐ **Цена:** {current_price} Stars\n\n"
        "📌 **Команды:**\n"
        "/buy - Купить подарок\n"
        "/profile - Мой профиль\n"
        "/balance - Баланс подарков\n"
        "/ping - Проверить бота"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Купить подарок", callback_data="buy")],
        [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")]
    ])
    
    await message.reply(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("buy"))
async def buy_cmd(client: Client, message: Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "")
    
    prices = [LabeledPrice(label="Подарок Мишка", amount=current_price)]
    
    try:
        await client.send_invoice(
            chat_id=user.id,
            title="🐻 Подарок Мишка",
            description=f"Подарок за {current_price} Stars с подписью 'Telegram моя жизнь'",
            payload=f"gift_{GIFT_ID}",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="gift_purchase"
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@app.on_message(filters.command("profile"))
async def profile_cmd(client: Client, message: Message):
    user = message.from_user
    stats = get_user_stats(user.id)
    
    if stats:
        stars_spent, gifts_received, balance, join_date = stats
        text = (
            f"👤 **Профиль пользователя**\n\n"
            f"**Имя:** {user.first_name}\n"
            f"**Username:** @{user.username or 'Нет'}\n"
            f"**В боте с:** {join_date[:10]}\n\n"
            f"⭐ **Потрачено Stars:** {stars_spent}\n"
            f"🎁 **Получено подарков:** {gifts_received}\n"
            f"📦 **Доступно подарков:** {balance}\n"
        )
    else:
        text = "❌ Данные не найдены"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Купить ещё", callback_data="buy")]
    ])
    
    await message.reply(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("balance"))
async def balance_cmd(client: Client, message: Message):
    user = message.from_user
    stats = get_user_stats(user.id)
    
    if stats:
        balance = stats[2]
        await message.reply(f"📦 **Ваш баланс подарков:** {balance}\n\nИспользуйте /profile для деталей", parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply("❌ Данные не найдены")

@app.on_message(filters.command("ping"))
async def ping_cmd(client: Client, message: Message):
    await message.reply("🏓 **Pong!** Бот работает отлично!", parse_mode=ParseMode.MARKDOWN)

# ========== АДМИН КОМАНДЫ ==========
@app.on_message(filters.command("set_price") & filters.user(ADMIN_IDS))
async def set_price_cmd(client: Client, message: Message):
    global current_price
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply("❌ Используйте: /set_price <количество Stars>")
            return
        current_price = int(args[1])
        await message.reply(f"✅ Цена подарка установлена: {current_price} Stars")
    except ValueError:
        await message.reply("❌ Введите число")

@app.on_message(filters.command("stats") & filters.user(ADMIN_IDS))
async def stats_cmd(client: Client, message: Message):
    total_users, total_stars, total_gifts = get_total_stats()
    
    text = (
        f"📊 **Статистика бота**\n\n"
        f"👥 **Всего пользователей:** {total_users}\n"
        f"⭐ **Потрачено Stars:** {total_stars}\n"
        f"🎁 **Отправлено подарков:** {total_gifts}\n"
        f"💰 **Текущая цена:** {current_price} Stars\n"
    )
    
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_IDS))
async def broadcast_cmd(client: Client, message: Message):
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.reply("❌ Используйте: /broadcast <текст>")
        return
    
    users = get_all_users()
    success = 0
    fail = 0
    
    status_msg = await message.reply(f"📨 Начинаю рассылку для {len(users)} пользователей...")
    
    for user_id, username, first_name in users:
        try:
            await client.send_message(
                user_id,
                f"📢 **Рассылка от администратора**\n\n{broadcast_text}",
                parse_mode=ParseMode.MARKDOWN
            )
            success += 1
        except:
            fail += 1
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\nУспешно: {success}\nОшибок: {fail}")

@app.on_message(filters.command("user") & filters.user(ADMIN_IDS))
async def user_info_cmd(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply("❌ Используйте: /user <user_id>")
            return
        
        user_id = int(args[1])
        stats = get_user_stats(user_id)
        
        if stats:
            stars_spent, gifts_received, balance, join_date = stats
            text = (
                f"👤 **Информация о пользователе**\n\n"
                f"**ID:** `{user_id}`\n"
                f"**В боте с:** {join_date[:10]}\n"
                f"⭐ **Потрачено Stars:** {stars_spent}\n"
                f"🎁 **Получено подарков:** {gifts_received}\n"
                f"📦 **Баланс подарков:** {balance}\n"
            )
        else:
            text = "❌ Пользователь не найден"
        
        await message.reply(text, parse_mode=ParseMode.MARKDOWN)
    except:
        await message.reply("❌ Ошибка ввода")

# ========== ПЛАТЕЖИ ==========
@app.on_raw_update()
async def handle_pre_checkout(client, update, users, chats):
    # Обработка pre_checkout
    if hasattr(update, 'pre_checkout_query_id'):
        await client.answer_pre_checkout_query(update.pre_checkout_query_id, ok=True)

@app.on_message(filters.successful_payment)
async def successful_payment_handler(client: Client, message: Message):
    user = message.from_user
    stars_spent = message.successful_payment.total_amount
    
    # ОТПРАВЛЯЕМ РЕАЛЬНЫЙ ПОДАРОК ОТ БОТА!
    try:
        await client.send_gift(
            chat_id=user.id,
            gift_id=GIFT_ID,
            text="Telegram моя жизнь"
        )
        
        # Сохраняем в БД
        add_user(user.id, user.username or "", user.first_name or "")
        update_user_stats(user.id, stars_spent)
        
        await message.reply(
            f"✅ **Подарок отправлен!** 🎉\n\n"
            f"🐻 Мишка с подписью 'Telegram моя жизнь' уже в вашем профиле!\n"
            f"⭐ Потрачено: {stars_spent} Stars\n\n"
            f"Посмотреть подарок можно в разделе 'Подарки' в настройках Telegram.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Уведомление админу
        for admin_id in ADMIN_IDS:
            await client.send_message(
                admin_id,
                f"💰 **Новая покупка!**\n\n"
                f"👤 Пользователь: @{user.username or user.first_name} (ID: {user.id})\n"
                f"⭐ Потрачено Stars: {stars_spent}\n"
                f"🎁 Подарок: Мишка отправлен!"
            )
    except Exception as e:
        await message.reply(f"❌ Ошибка при отправке подарка: {e}\nОбратитесь к администратору.")
        
        for admin_id in ADMIN_IDS:
            await client.send_message(
                admin_id,
                f"⚠️ **Ошибка отправки подарка!**\n"
                f"Пользователь: {user.id}\n"
                f"Ошибка: {e}"
            )

# ========== КНОПКИ ==========
@app.on_callback_query()
async def callback_handler(client: Client, callback_query):
    if callback_query.data == "buy":
        await buy_cmd(client, callback_query.message)
        await callback_query.answer()
    elif callback_query.data == "profile":
        await profile_cmd(client, callback_query.message)
        await callback_query.answer()

# ========== ЗАПУСК ==========
print("🚀 Бот подарков запущен!")
print(f"🤖 Бот отправляет РЕАЛЬНЫЕ подарки!")
print(f"💰 Текущая цена: {DEFAULT_PRICE} Stars")
print(f"🐻 ID подарка: {GIFT_ID}")

app.run()
