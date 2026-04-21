import asyncio
import aiohttp
import random
import logging
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import string
from datetime import datetime, timedelta
from aiohttp_socks import ProxyConnector

API_TOKEN = '8325557607:AAE1CVGBGNgCMLCey9Xs2Ebu-9yOUjAcx3Y'
REQUIRED_CHANNEL = '@uralchikssnoser'  # Канал для обязательной подписки
ADMIN_IDS = [7673683792, 7534265394]  # Замените на реальные ID администраторов

# Файлы для хранения данных
SUBSCRIPTIONS_FILE = 'subscriptions.json'
USERS_FILE = 'users.json'

# Загрузка/сохранение данных
def load_data(file_name, default_data):
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default_data

def save_data(file_name, data):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Структура данных
subscriptions = load_data(SUBSCRIPTIONS_FILE, {})  # user_id: {'expiry_date': '2024-12-31', 'type': 'monthly'}
users = load_data(USERS_FILE, {})  # user_id: {'username': '...', 'registered_at': '...'}

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

# Проверка подписки на канал
async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# Проверка наличия активной подписки
def has_active_subscription(user_id):
    if str(user_id) in subscriptions:
        expiry_date = datetime.strptime(subscriptions[str(user_id)]['expiry_date'], '%Y-%m-%d')
        return expiry_date > datetime.now()
    return False

# Получение информации о подписке
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

# Проверка доступа к боту
async def check_access(user_id):
    if user_id in ADMIN_IDS:
        return True
    if not await check_subscription(user_id):
        return False
    return has_active_subscription(user_id)

# Клавиатура для проверки подписки
def get_subscription_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"),
        InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")
    )
    return keyboard

# Клавиатура для покупки подписки
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

# Админ-клавиатура
def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users"),
        InlineKeyboardButton(text="➕ Выдать подписку", callback_data="admin_give"),
        InlineKeyboardButton(text="➖ Забрать подписку", callback_data="admin_remove"),
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

# Декоратор проверки доступа
def require_access(handler):
    async def wrapper(message: Message):
        user_id = message.from_user.id
        
        # Сохраняем пользователя
        if str(user_id) not in users:
            users[str(user_id)] = {
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            save_data(USERS_FILE, users)
        
        # Проверка на админа
        if user_id in ADMIN_IDS:
            return await handler(message)
        
        # Проверка подписки на канал
        if not await check_subscription(user_id):
            keyboard = get_subscription_keyboard()
            await message.reply(
                f"❌ **Доступ запрещён!**\n\n"
                f"Для использования бота необходимо подписаться на канал {REQUIRED_CHANNEL}\n\n"
                f"После подписки нажмите кнопку проверки.",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            return
        
        # Проверка платной подписки
        if not has_active_subscription(user_id):
            sub_info = get_subscription_info(user_id)
            keyboard = get_pricing_keyboard()
            await message.reply(
                f"⚠️ **У вас нет активной подписки!**\n\n"
                f"💰 **Тарифы:**\n"
                f"• 1 день — 50 ⭐\n"
                f"• 7 дней — 300 ⭐\n"
                f"• 30 дней — 1000 ⭐\n"
                f"• 90 дней — 2500 ⭐\n"
                f"• Навсегда — 5000 ⭐\n\n"
                f"💎 Выберите тариф ниже:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            return
        
        return await handler(message)
    return wrapper

@dp.message_handler(commands=['start'])
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Сохраняем пользователя
    if str(user_id) not in users:
        users[str(user_id)] = {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        save_data(USERS_FILE, users)
    
    # Проверка на админа
    if user_id in ADMIN_IDS:
        welcome_text = f"""
👑 **Админ-панель активирована**

**Команды:**
/report <username> - начать отправку жалоб
/status - проверить статус
/admin - открыть админ-панель
/profile - профиль и подписка

**Пример:** `/report username123`
        """
        await message.reply(welcome_text, parse_mode='Markdown')
        return
    
    # Проверка подписки
    if not await check_subscription(user_id):
        keyboard = get_subscription_keyboard()
        await message.reply(
            f"🤖 **Добро пожаловать!**\n\n"
            f"Для использования бота необходимо:\n"
            f"1️⃣ Подписаться на канал {REQUIRED_CHANNEL}\n"
            f"2️⃣ Приобрести подписку\n\n"
            f"🔽 Нажмите кнопку ниже, чтобы подписаться:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return
    
    if has_active_subscription(user_id):
        sub_info = get_subscription_info(user_id)
        welcome_text = f"""
✅ **Доступ разрешён!**

**Ваша подписка:**
📅 Действует до: {sub_info['expiry_date'].strftime('%d.%m.%Y')}
⏰ Осталось дней: {sub_info['days_left']}

**Команды:**
/report <username> - начать отправку жалоб
/status - проверить статус
/profile - информация о подписке

**Пример:** `/report username123`
        """
        await message.reply(welcome_text, parse_mode='Markdown')
    else:
        keyboard = get_pricing_keyboard()
        await message.reply(
            f"⚠️ **У вас нет активной подписки!**\n\n"
            f"💰 Выберите тариф ниже:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

@dp.message_handler(commands=['profile'])
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    
    sub_info = get_subscription_info(user_id)
    is_subscribed = await check_subscription(user_id)
    
    profile_text = f"""
👤 **Ваш профиль**

📝 **Имя:** {message.from_user.first_name}
🆔 **ID:** {user_id}
📢 **Канал:** {'✅ Подписан' if is_subscribed else '❌ Не подписан'}

💎 **Подписка:**
{'✅ Активна' if sub_info['active'] else '❌ Неактивна'}
{'📅 Действует до: ' + sub_info['expiry_date'].strftime('%d.%m.%Y') if sub_info['active'] else ''}
{'⏰ Осталось дней: ' + str(sub_info['days_left']) if sub_info['active'] else ''}
    """
    
    if not sub_info['active']:
        keyboard = get_pricing_keyboard()
        await message.reply(profile_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.reply(profile_text, parse_mode='Markdown')

@dp.message_handler(commands=['report'])
@require_access
async def cmd_report(message: Message):
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply("❌ Укажи юзернейм.\n\nПример: `/report username123`", parse_mode='Markdown')
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
📊 **Результаты атаки на @{target}**

✅ Успешно: {success}
❌ Неуспешно: {failed}
📈 Процент успеха: {success_rate:.1f}%

🏁 Атака завершена.
    """
    
    await status_msg.edit_text(result_text, parse_mode='Markdown')

@dp.message_handler(commands=['status'])
@require_access
async def cmd_status(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        await message.reply("❌ Нет активных или завершённых сессий.\n\nИспользуйте `/report <username>` чтобы начать.", parse_mode='Markdown')
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
{status_icon} **Статус отправки жалоб**

**Цель:** @{session['target']}
**Статус:** {status_text}
**Время работы:** {minutes} мин {seconds} сек
**Начато:** {session['start_time'].strftime('%H:%M:%S %d.%m.%Y')}

📊 **Результаты:**
{progress_bar} {success_rate:.1f}%

├ ✅ Успешно: {success}
├ ❌ Неуспешно: {failed}
└ 📈 Всего: {total}
    """
    
    await message.reply(status_text_full, parse_mode='Markdown')

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.reply("❌ У вас нет доступа к админ-панели!")
        return
    
    keyboard = get_admin_keyboard()
    await message.reply("👑 **Админ-панель**\n\nВыберите действие:", reply_markup=keyboard, parse_mode='Markdown')

# Обработчики callback-запросов
@dp.callback_query_handler(lambda c: c.data == 'check_subscription')
async def check_subscription_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if await check_subscription(user_id):
        await callback.answer("✅ Подписка подтверждена!", show_alert=True)
        
        if has_active_subscription(user_id):
            sub_info = get_subscription_info(user_id)
            await callback.message.edit_text(
                f"✅ **Подписка подтверждена!**\n\n"
                f"Ваша подписка активна до {sub_info['expiry_date'].strftime('%d.%m.%Y')}\n\n"
                f"Используйте /report для начала работы.",
                parse_mode='Markdown'
            )
        else:
            keyboard = get_pricing_keyboard()
            await callback.message.edit_text(
                f"✅ **Подписка на канал подтверждена!**\n\n"
                f"Теперь приобретите подписку для использования бота:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    else:
        await callback.answer("❌ Вы не подписаны на канал!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def buy_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    plan = callback.data.replace('buy_', '')
    
    prices = {
        '1day': {'days': 1, 'price': 50, 'stars': 50},
        '7days': {'days': 7, 'price': 300, 'stars': 300},
        '30days': {'days': 30, 'price': 1000, 'stars': 1000},
        '90days': {'days': 90, 'price': 2500, 'stars': 2500},
        'forever': {'days': 3650, 'price': 5000, 'stars': 5000}
    }
    
    plan_info = prices.get(plan, prices['1day'])
    
    # Создаем инвойс для оплаты звездами Telegram
    invoice = types.LabeledPrice(label=f"Подписка на {plan_info['days']} дней", amount=plan_info['price'])
    
    await bot.send_invoice(
        chat_id=user_id,
        title=f"💎 Подписка на {plan_info['days']} дней",
        description=f"Доступ к боту на {plan_info['days']} дней",
        payload=f"sub_{plan}_{user_id}",
        provider_token="",  # Для звезд Telegram оставляем пустым
        currency="XTR",  # XTR = Telegram Stars
        prices=[invoice],
        start_parameter="subscription",
        need_name=False,
        need_email=False
    )

@dp.pre_checkout_query_handler(lambda query: True)
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    
    # Извлекаем тип подписки из payload
    plan = payload.split('_')[1]
    
    prices = {
        '1day': 1,
        '7days': 7,
        '30days': 30,
        '90days': 90,
        'forever': 3650
    }
    
    days = prices.get(plan, 1)
    
    # Обновляем подписку
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
    
    await message.reply(
        f"✅ **Оплата прошла успешно!**\n\n"
        f"Ваша подписка активирована до {new_expiry.strftime('%d.%m.%Y')}\n\n"
        f"Используйте /report для начала работы.",
        parse_mode='Markdown'
    )

# Админ-обработчики
@dp.callback_query_handler(lambda c: c.data == 'admin_stats')
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    active_subs = sum(1 for uid, data in subscriptions.items() 
                     if datetime.strptime(data['expiry_date'], '%Y-%m-%d') > datetime.now())
    
    stats_text = f"""
📊 **Статистика бота**

👥 Всего пользователей: {len(users)}
💎 Активных подписок: {active_subs}
📅 Всего продаж: {len(subscriptions)}
👑 Администраторов: {len(ADMIN_IDS)}
    """
    
    await callback.message.edit_text(stats_text, parse_mode='Markdown')
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == 'admin_users')
async def admin_users(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    users_list = "👥 **Список пользователей:**\n\n"
    for uid, data in list(users.items())[:20]:  # Показываем первых 20
        users_list += f"🆔 {uid} | @{data.get('username', 'нет')}\n"
    
    if len(users) > 20:
        users_list += f"\n... и ещё {len(users) - 20} пользователей"
    
    await callback.message.edit_text(users_list, parse_mode='Markdown')
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == 'admin_backup')
async def admin_backup(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    # Отправляем файлы с данными
    if os.path.exists(SUBSCRIPTIONS_FILE):
        with open(SUBSCRIPTIONS_FILE, 'rb') as f:
            await bot.send_document(callback.from_user.id, f, caption="📦 Бекап подписок")
    
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'rb') as f:
            await bot.send_document(callback.from_user.id, f, caption="📦 Бекап пользователей")
    
    await callback.answer("✅ Бекап отправлен!")

@dp.message_handler()
async def handle_message(message: Message):
    await message.reply("❓ Неизвестная команда.\n\nИспользуй /start для начала работы")

async def main():
    print("🤖 Бот запущен с системами подписок и админ-панелью")
    print(f"📢 Обязательный канал: {REQUIRED_CHANNEL}")
    print(f"👑 Админы: {ADMIN_IDS}")
    await dp.start_polling()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
