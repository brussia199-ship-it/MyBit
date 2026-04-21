import asyncio
import aiohttp
import random
import logging
import json
import os
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import string
from datetime import datetime, timedelta
from aiohttp_socks import ProxyConnector

API_TOKEN = '8325557607:AAE1CVGBGNgCMLCey9Xs2Ebu-9yOUjAcx3Y'
REQUIRED_CHANNEL = '@uralchikssnoser'
ADMIN_IDS = [7673683792]  # ЗАМЕНИТЕ НА СВОЙ ID

SUBSCRIPTIONS_FILE = 'subscriptions.json'
USERS_FILE = 'users.json'

def load_data(file_name, default_data):
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default_data

def save_data(file_name, data):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

subscriptions = load_data(SUBSCRIPTIONS_FILE, {})
users = load_data(USERS_FILE, {})

PROXY_LIST = [
    # 'socks5://логин:пароль@ip:порт',
]

COMPLAINT_TEMPLATES = [
    {
        'language': 'ru',
        'subject': 'Спам и мошенничество',
        'message': 'Данный аккаунт массово рассылает спам с мошенническими ссылками. Просьба заблокировать.'
    },
    {
        'language': 'ru',
        'subject': 'Оскорбления и угрозы',
        'message': 'Пользователь систематически оскорбляет и угрожает физической расправой.'
    },
    {
        'language': 'ru',
        'subject': 'Фейковый аккаунт',
        'message': 'Этот аккаунт выдает себя за другого человека и распространяет ложную информацию.'
    },
    {
        'language': 'ru',
        'subject': 'Распространение запрещенного контента',
        'message': 'Аккаунт распространяет запрещенные материалы и призывает к насилию.'
    },
    {
        'language': 'ru',
        'subject': 'Скам и фишинг',
        'message': 'Пользователь занимается скамом и пытается выманить личные данные.'
    }
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148'
]

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_sessions = {}

# Функция для безопасной отправки сообщений с Markdown
async def safe_send_message(chat_id, text, reply_markup=None):
    try:
        await bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=reply_markup)
    except:
        # Если ошибка с Markdown, отправляем без форматирования
        await bot.send_message(chat_id, text, reply_markup=reply_markup)

async def safe_edit_message(message, text, reply_markup=None):
    try:
        await message.edit_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    except:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
        except:
            pass

async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def has_active_subscription(user_id):
    if str(user_id) in subscriptions:
        expiry_date = datetime.strptime(subscriptions[str(user_id)]['expiry_date'], '%Y-%m-%d')
        return expiry_date > datetime.now()
    return False

def get_subscription_info(user_id):
    if str(user_id) in subscriptions:
        expiry_date = datetime.strptime(subscriptions[str(user_id)]['expiry_date'], '%Y-%m-%d')
        days_left = (expiry_date - datetime.now()).days
        return {
            'active': expiry_date > datetime.now(),
            'expiry_date': expiry_date,
            'days_left': days_left,
            'type': subscriptions[str(user_id)].get('type', 'unknown')
        }
    return {'active': False, 'days_left': 0}

def give_subscription(user_id, days, admin_id):
    user_id = str(user_id)
    
    if user_id in subscriptions:
        current_expiry = datetime.strptime(subscriptions[user_id]['expiry_date'], '%Y-%m-%d')
        if current_expiry > datetime.now():
            new_expiry = current_expiry + timedelta(days=days)
        else:
            new_expiry = datetime.now() + timedelta(days=days)
    else:
        new_expiry = datetime.now() + timedelta(days=days)
    
    subscriptions[user_id] = {
        'expiry_date': new_expiry.strftime('%Y-%m-%d'),
        'type': f'admin_granted_{days}d',
        'purchased_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'granted_by': admin_id
    }
    save_data(SUBSCRIPTIONS_FILE, subscriptions)
    return new_expiry

def remove_subscription(user_id):
    user_id = str(user_id)
    if user_id in subscriptions:
        del subscriptions[user_id]
        save_data(SUBSCRIPTIONS_FILE, subscriptions)
        return True
    return False

def escape_markdown(text):
    """Экранирует специальные символы Markdown"""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in special_chars else char for char in text)

def get_subscription_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"),
        InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")
    )
    return keyboard

def get_pricing_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="📅 1 день - 50⭐", callback_data="buy_1day"),
        InlineKeyboardButton(text="📅 7 дней - 300⭐", callback_data="buy_7days"),
        InlineKeyboardButton(text="📅 30 дней - 1000⭐", callback_data="buy_30days"),
        InlineKeyboardButton(text="📅 90 дней - 2500⭐", callback_data="buy_90days"),
        InlineKeyboardButton(text="🏆 Навсегда - 5000⭐", callback_data="buy_forever")
    )
    return keyboard

def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users"),
        InlineKeyboardButton(text="➕ Выдать подписку", callback_data="admin_give"),
        InlineKeyboardButton(text="➖ Забрать подписку", callback_data="admin_remove"),
        InlineKeyboardButton(text="🔍 Проверить подписку юзера", callback_data="admin_check_sub"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="💾 Бекап данных", callback_data="admin_backup")
    )
    return keyboard

class ReportManager:
    def __init__(self):
        self.proxy_pool = PROXY_LIST.copy()
        self.report_urls = [
            'https://telegram.org/contact',
            'https://t.me/abuse',
            'https://telegram.org/support'
        ]
    
    def get_random_proxy(self):
        return random.choice(self.proxy_pool) if self.proxy_pool else None
    
    def get_random_headers(self):
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def generate_fake_email(self):
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'mail.ru', 'yandex.ru']
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(8, 15)))
        return f"{username}@{random.choice(domains)}"
    
    async def send_report(self, target_username, proxy=None):
        template = random.choice(COMPLAINT_TEMPLATES)
        email = self.generate_fake_email()
        
        form_data = {
            'message': f"Жалоба на аккаунт @{target_username}\n\n{template['message']}",
            'email': email,
            'subject': template['subject'],
            'language': 'ru'
        }
        
        headers = self.get_random_headers()
        report_url = random.choice(self.report_urls)
        
        try:
            if proxy:
                connector = ProxyConnector.from_url(proxy)
            else:
                connector = None
            
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.post(report_url, data=form_data, timeout=15) as response:
                    if response.status in [200, 201, 202]:
                        return True, f"Жалоба отправлена"
                    else:
                        return False, f"Ошибка {response.status}"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    async def flood_reports(self, target_username, count=50):
        tasks = []
        
        for i in range(count):
            proxy = self.get_random_proxy()
            delay = random.uniform(0.5, 2.0)
            
            task = asyncio.create_task(self.send_report(target_username, proxy))
            tasks.append(task)
            
            if i < count - 1:
                await asyncio.sleep(delay)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for response in responses:
            if isinstance(response, tuple) and response[0]:
                success_count += 1
        
        return success_count, count - success_count

report_manager = ReportManager()

async def check_report_access(user_id, message):
    if str(user_id) not in users:
        users[str(user_id)] = {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        save_data(USERS_FILE, users)
    
    if user_id in ADMIN_IDS:
        return True, None
    
    if not await check_subscription(user_id):
        keyboard = get_subscription_keyboard()
        await safe_send_message(
            message.chat.id,
            f"❌ Доступ к /report запрещён!\n\nДля использования команды /report необходимо подписаться на канал {REQUIRED_CHANNEL}\n\nПосле подписки нажмите кнопку проверки.",
            reply_markup=keyboard
        )
        return False, None
    
    if not has_active_subscription(user_id):
        keyboard = get_pricing_keyboard()
        await safe_send_message(
            message.chat.id,
            f"⚠️ У вас нет активной подписки!\n\n💰 Тарифы:\n• 1 день - 50⭐\n• 7 дней - 300⭐\n• 30 дней - 1000⭐\n• 90 дней - 2500⭐\n• Навсегда - 5000⭐\n\n💎 Выберите тариф ниже, чтобы получить доступ к /report:",
            reply_markup=keyboard
        )
        return False, None
    
    return True, None

@dp.message_handler(commands=['start'])
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    if str(user_id) not in users:
        users[str(user_id)] = {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        save_data(USERS_FILE, users)
    
    if user_id in ADMIN_IDS:
        welcome_text = f"""
👑 Админ-панель активирована

Команды:
/report <username> - начать отправку жалоб (по подписке)
/status - проверить статус
/admin - открыть админ-панель
/profile - профиль и подписка

Пример: /report username123
        """
        await safe_send_message(message.chat.id, welcome_text)
        return
    
    if not await check_subscription(user_id):
        keyboard = get_subscription_keyboard()
        await safe_send_message(
            message.chat.id,
            f"🤖 Добро пожаловать!\n\nДля использования бота необходимо:\n1️⃣ Подписаться на канал {REQUIRED_CHANNEL}\n2️⃣ Приобрести подписку\n\n🔽 Нажмите кнопку ниже, чтобы подписаться:",
            reply_markup=keyboard
        )
        return
    
    if has_active_subscription(user_id):
        sub_info = get_subscription_info(user_id)
        welcome_text = f"""
✅ Доступ разрешён!

Ваша подписка:
📅 Действует до: {sub_info['expiry_date'].strftime('%d.%m.%Y')}
⏰ Осталось дней: {sub_info['days_left']}

Команды:
/report <username> - начать отправку жалоб
/status - проверить статус
/profile - информация о подписке

Пример: /report username123
        """
        await safe_send_message(message.chat.id, welcome_text)
    else:
        keyboard = get_pricing_keyboard()
        await safe_send_message(
            message.chat.id,
            f"⚠️ У вас нет активной подписки!\n\n💰 Выберите тариф ниже для доступа к /report:",
            reply_markup=keyboard
        )

@dp.message_handler(commands=['profile'])
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    
    sub_info = get_subscription_info(user_id)
    is_subscribed = await check_subscription(user_id)
    
    profile_text = f"""
👤 Ваш профиль

📝 Имя: {message.from_user.first_name}
🆔 ID: {user_id}
📢 Канал: {'✅ Подписан' if is_subscribed else '❌ Не подписан'}

💎 Подписка:
{'✅ Активна' if sub_info['active'] else '❌ Неактивна'}
{'📅 Действует до: ' + sub_info['expiry_date'].strftime('%d.%m.%Y') if sub_info['active'] else ''}
{'⏰ Осталось дней: ' + str(sub_info['days_left']) if sub_info['active'] else ''}

🔹 Доступ к /report: {'✅ Есть' if sub_info['active'] and is_subscribed else '❌ Нет'}
    """
    
    if not sub_info['active']:
        keyboard = get_pricing_keyboard()
        await safe_send_message(message.chat.id, profile_text, reply_markup=keyboard)
    else:
        await safe_send_message(message.chat.id, profile_text)

@dp.message_handler(commands=['report'])
async def cmd_report(message: Message):
    user_id = message.from_user.id
    
    has_access, _ = await check_report_access(user_id, message)
    if not has_access:
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await safe_send_message(message.chat.id, "❌ Укажи юзернейм.\n\nПример: /report username123")
        return
    
    target = args[1].strip().replace('@', '')
    
    status_msg = await message.reply(f"🚀 Запускаю атаку на @{target}\n📨 Отправляю 50 жалоб...")
    
    user_sessions[message.from_user.id] = {
        'target': target,
        'start_time': datetime.now(),
        'status': 'in_progress',
        'success': 0,
        'failed': 0
    }
    
    success, failed = await report_manager.flood_reports(target, count=50)
    
    if message.from_user.id in user_sessions:
        user_sessions[message.from_user.id]['status'] = 'completed'
        user_sessions[message.from_user.id]['success'] = success
        user_sessions[message.from_user.id]['failed'] = failed
    
    success_rate = (success/(success+failed))*100 if (success+failed) > 0 else 0
    
    result_text = f"""
📊 Результаты атаки на @{target}

✅ Успешно: {success}
❌ Неуспешно: {failed}
📈 Процент успеха: {success_rate:.1f}%

🏁 Атака завершена.
    """
    
    await safe_edit_message(status_msg, result_text)

@dp.message_handler(commands=['status'])
async def cmd_status(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        await safe_send_message(message.chat.id, "❌ Нет активных или завершённых сессий.\n\nИспользуйте /report <username> чтобы начать.")
        return
    
    session = user_sessions[user_id]
    
    time_elapsed = datetime.now() - session['start_time']
    minutes = time_elapsed.seconds // 60
    seconds = time_elapsed.seconds % 60
    
    success = session.get('success', 0)
    failed = session.get('failed', 0)
    total = success + failed
    success_rate = (success / total * 100) if total > 0 else 0
    
    filled = int(success_rate / 10)
    progress_bar = "▓" * filled + "░" * (10 - filled)
    
    if session['status'] == 'in_progress':
        status_icon = "🔄"
        status_text = "В процессе отправки..."
    else:
        status_icon = "✅"
        status_text = "Завершено"
    
    status_text_full = f"""
{status_icon} Статус отправки жалоб

Цель: @{session['target']}
Статус: {status_text}
Время работы: {minutes} мин {seconds} сек
Начато: {session['start_time'].strftime('%H:%M:%S %d.%m.%Y')}

📊 Результаты:
{progress_bar} {success_rate:.1f}%

├ ✅ Успешно: {success}
├ ❌ Неуспешно: {failed}
└ 📈 Всего: {total}
    """
    
    await safe_send_message(message.chat.id, status_text_full)

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await safe_send_message(message.chat.id, "❌ У вас нет доступа к админ-панели!")
        return
    
    keyboard = get_admin_keyboard()
    await safe_send_message(message.chat.id, "👑 Админ-панель\n\nВыберите действие:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'check_subscription')
async def check_subscription_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if await check_subscription(user_id):
        await callback.answer("✅ Подписка подтверждена!", show_alert=True)
        
        if has_active_subscription(user_id):
            sub_info = get_subscription_info(user_id)
            await safe_edit_message(
                callback.message,
                f"✅ Подписка подтверждена!\n\nВаша подписка активна до {sub_info['expiry_date'].strftime('%d.%m.%Y')}\n\nТеперь вы можете использовать /report"
            )
        else:
            keyboard = get_pricing_keyboard()
            await safe_edit_message(
                callback.message,
                f"✅ Подписка на канал подтверждена!\n\nТеперь приобретите подписку для доступа к /report:",
                reply_markup=keyboard
            )
    else:
        await callback.answer("❌ Вы не подписаны на канал!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def buy_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    plan = callback.data.replace('buy_', '')
    
    prices = {
        '1day': {'days': 1, 'price': 50},
        '7days': {'days': 7, 'price': 300},
        '30days': {'days': 30, 'price': 1000},
        '90days': {'days': 90, 'price': 2500},
        'forever': {'days': 3650, 'price': 5000}
    }
    
    plan_info = prices.get(plan, prices['1day'])
    
    invoice = types.LabeledPrice(label=f"Подписка на {plan_info['days']} дней", amount=plan_info['price'])
    
    await bot.send_invoice(
        chat_id=user_id,
        title=f"💎 Подписка на {plan_info['days']} дней",
        description=f"Доступ к команде /report на {plan_info['days']} дней",
        payload=f"sub_{plan}_{user_id}",
        provider_token="",
        currency="XTR",
        prices=[invoice],
        start_parameter="subscription"
    )

@dp.pre_checkout_query_handler(lambda query: True)
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    
    plan = payload.split('_')[1]
    
    prices = {
        '1day': 1,
        '7days': 7,
        '30days': 30,
        '90days': 90,
        'forever': 3650
    }
    
    days = prices.get(plan, 1)
    
    if str(user_id) in subscriptions:
        current_expiry = datetime.strptime(subscriptions[str(user_id)]['expiry_date'], '%Y-%m-%d')
        if current_expiry > datetime.now():
            new_expiry = current_expiry + timedelta(days=days)
        else:
            new_expiry = datetime.now() + timedelta(days=days)
    else:
        new_expiry = datetime.now() + timedelta(days=days)
    
    subscriptions[str(user_id)] = {
        'expiry_date': new_expiry.strftime('%Y-%m-%d'),
        'type': plan,
        'purchased_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    save_data(SUBSCRIPTIONS_FILE, subscriptions)
    
    await safe_send_message(
        message.chat.id,
        f"✅ Оплата прошла успешно!\n\nВаша подписка активирована до {new_expiry.strftime('%d.%m.%Y')}\n\nТеперь вы можете использовать /report"
    )

@dp.callback_query_handler(lambda c: c.data == 'admin_stats')
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    active_subs = sum(1 for uid, data in subscriptions.items() 
                     if datetime.strptime(data['expiry_date'], '%Y-%m-%d') > datetime.now())
    
    stats_text = f"""
📊 Статистика бота

👥 Всего пользователей: {len(users)}
💎 Активных подписок: {active_subs}
📅 Всего продаж: {len(subscriptions)}
👑 Администраторов: {len(ADMIN_IDS)}
    """
    
    await safe_edit_message(callback.message, stats_text)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == 'admin_users')
async def admin_users(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    users_list = "👥 Список пользователей:\n\n"
    for uid, data in list(users.items())[:20]:
        username = data.get('username', 'нет')
        users_list += f"🆔 {uid} | @{username}\n"
    
    if len(users) > 20:
        users_list += f"\n... и ещё {len(users) - 20} пользователей"
    
    await safe_edit_message(callback.message, users_list)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == 'admin_check_sub')
async def admin_check_sub_menu(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    await safe_edit_message(
        callback.message,
        "🔍 Проверка подписки пользователя\n\nОтправь сообщение в формате:\n/check user_id\n\nПример: /check 123456789"
    )
    await callback.answer()

@dp.message_handler(commands=['check'])
async def admin_check_subscription(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await safe_send_message(message.chat.id, "❌ Нет доступа!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await safe_send_message(message.chat.id, "❌ Формат: /check user_id\nПример: /check 123456789")
        return
    
    try:
        target_user_id = int(args[1])
        
        is_subscribed = await check_subscription(target_user_id)
        has_sub = has_active_subscription(target_user_id)
        sub_info = get_subscription_info(target_user_id)
        user_info = users.get(str(target_user_id), {})
        
        result_text = f"""
🔍 Результат проверки пользователя {target_user_id}

📢 Канал {REQUIRED_CHANNEL}: {'✅ Подписан' if is_subscribed else '❌ Не подписан'}

💎 Платная подписка: {'✅ Активна' if has_sub else '❌ Неактивна'}

{'📅 Действует до: ' + sub_info['expiry_date'].strftime('%d.%m.%Y') if has_sub else ''}
{'⏰ Осталось дней: ' + str(sub_info['days_left']) if has_sub else ''}

📝 Имя: {user_info.get('first_name', 'Неизвестно')}
📅 Зарегистрирован: {user_info.get('registered_at', 'Неизвестно')}
        """
        
        await safe_send_message(message.chat.id, result_text)
        
    except ValueError:
        await safe_send_message(message.chat.id, "❌ Ошибка: user_id должен быть числом!")

@dp.callback_query_handler(lambda c: c.data == 'admin_give')
async def admin_give_menu(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    await safe_edit_message(
        callback.message,
        "➕ Выдача подписки\n\nОтправь сообщение в формате:\n/give user_id количество_дней\n\nПример: /give 123456789 30"
    )
    await callback.answer()

@dp.message_handler(commands=['give'])
async def admin_give_subscription(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await safe_send_message(message.chat.id, "❌ Нет доступа!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await safe_send_message(message.chat.id, "❌ Формат: /give user_id количество_дней\nПример: /give 123456789 30")
        return
    
    try:
        target_user_id = int(args[1])
        days = int(args[2])
        
        if days <= 0 or days > 3650:
            await safe_send_message(message.chat.id, "❌ Количество дней должно быть от 1 до 3650")
            return
        
        new_expiry = give_subscription(target_user_id, days, user_id)
        
        await safe_send_message(
            message.chat.id,
            f"✅ Подписка выдана!\n\n👤 Пользователь: {target_user_id}\n📅 Дней: {days}\n📆 Действует до: {new_expiry.strftime('%d.%m.%Y')}"
        )
        
        try:
            await safe_send_message(
                target_user_id,
                f"🎉 Вам выдана подписка на {days} дней!\n\n📅 Действует до: {new_expiry.strftime('%d.%m.%Y')}\n\nТеперь вы можете использовать /report"
            )
        except:
            pass
            
    except ValueError:
        await safe_send_message(message.chat.id, "❌ Ошибка: user_id и количество дней должны быть числами!")

@dp.callback_query_handler(lambda c: c.data == 'admin_remove')
async def admin_remove_menu(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    await safe_edit_message(
        callback.message,
        "➖ Забрать подписку\n\nОтправь сообщение в формате:\n/remove user_id\n\nПример: /remove 123456789"
    )
    await callback.answer()

@dp.message_handler(commands=['remove'])
async def admin_remove_subscription(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await safe_send_message(message.chat.id, "❌ Нет доступа!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await safe_send_message(message.chat.id, "❌ Формат: /remove user_id\nПример: /remove 123456789")
        return
    
    try:
        target_user_id = int(args[1])
        
        if remove_subscription(target_user_id):
            await safe_send_message(
                message.chat.id,
                f"✅ Подписка удалена!\n\n👤 Пользователь: {target_user_id}"
            )
            
            try:
                await safe_send_message(
                    target_user_id,
                    f"⚠️ Ваша подписка была удалена администратором!\n\nДоступ к /report потерян."
                )
            except:
                pass
        else:
            await safe_send_message(message.chat.id, f"❌ У пользователя {target_user_id} нет активной подписки!")
            
    except ValueError:
        await safe_send_message(message.chat.id, "❌ Ошибка: user_id должен быть числом!")

@dp.callback_query_handler(lambda c: c.data == 'admin_backup')
async def admin_backup(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    if os.path.exists(SUBSCRIPTIONS_FILE):
        with open(SUBSCRIPTIONS_FILE, 'rb') as f:
            await bot.send_document(callback.from_user.id, f, caption="📦 Бекап подписок")
    
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'rb') as f:
            await bot.send_document(callback.from_user.id, f, caption="📦 Бекап пользователей")
    
    await callback.answer("✅ Бекап отправлен!")

admin_broadcast_targets = {}

@dp.callback_query_handler(lambda c: c.data == 'admin_broadcast')
async def admin_broadcast_menu(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    await safe_edit_message(
        callback.message,
        "📢 Рассылка\n\nОтправь сообщение для рассылки всем пользователям.\n\nПоддерживаются: текст, фото, видео, документы.\n\nДля отмены отправь /cancel_broadcast"
    )
    admin_broadcast_targets[callback.from_user.id] = True
    await callback.answer()

@dp.message_handler(commands=['cancel_broadcast'])
async def cancel_broadcast(message: Message):
    user_id = message.from_user.id
    if user_id in admin_broadcast_targets:
        admin_broadcast_targets[user_id] = False
        await safe_send_message(message.chat.id, "❌ Рассылка отменена!")
    else:
        await safe_send_message(message.chat.id, "Нет активной рассылки.")

@dp.message_handler(content_types=types.ContentType.ANY)
async def handle_broadcast(message: Message):
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS and admin_broadcast_targets.get(user_id, False):
        success_count = 0
        fail_count = 0
        
        status_msg = await message.reply("📢 Начинаю рассылку...")
        
        for uid in users.keys():
            try:
                if message.text:
                    await bot.send_message(int(uid), message.text)
                elif message.photo:
                    await bot.send_photo(int(uid), message.photo[-1].file_id, caption=message.caption)
                elif message.video:
                    await bot.send_video(int(uid), message.video.file_id, caption=message.caption)
                elif message.document:
                    await bot.send_document(int(uid), message.document.file_id, caption=message.caption)
                else:
                    continue
                success_count += 1
                await asyncio.sleep(0.05)
            except:
                fail_count += 1
        
        await safe_edit_message(
            status_msg,
            f"✅ Рассылка завершена!\n\n📨 Доставлено: {success_count}\n❌ Не доставлено: {fail_count}\n👥 Всего: {len(users)}"
        )
        
        admin_broadcast_targets[user_id] = False
        return
    
    if user_id not in ADMIN_IDS:
        await safe_send_message(message.chat.id, "❓ Неизвестная команда.\n\nИспользуй /start для начала работы")

async def main():
    print("🤖 Бот запущен")
    print(f"📢 Обязательный канал: {REQUIRED_CHANNEL}")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"🔒 /report доступна только при активной подписке")
    await dp.start_polling()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
