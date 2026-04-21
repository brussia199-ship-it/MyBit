import asyncio
import aiohttp
import random
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import string
from datetime import datetime
from aiohttp_socks import ProxyConnector

API_TOKEN = '8325557607:AAE1CVGBGNgCMLCey9Xs2Ebu-9yOUjAcx3Y'

PROXY_LIST = [
    'socks5://сюда проксач',
    'socks5://сюда проксач',
    'http://сюда проксач',
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
dp = Dispatcher(bot)  # В v2.x нужно передавать bot в Dispatcher

# Глобальный словарь для хранения сессий пользователей
user_sessions = {}

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
                        return True, f"Жалоба отправлена через {proxy if proxy else 'прямое соединение'}"
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

# Для v2.x используем message_handler вместо Command
@dp.message_handler(commands=['start'])
async def cmd_start(message: Message):
    welcome_text = """
⚡ БОТ НАХОДИТСЯ В РАЗРАБОТКЕ! 
⚡ НА ДАННЫЙ МОМЕНТ ОН НЕ РАБОТАЕТ (ЖАЛОБЫ НЕ ИДУТ) 
⚡ СЛЕДИТЕ ЗА РАЗРАБОТКОЙ В КАНАЛЕ: @uralchikssnoser

Команды:
/report <username> - начать отправку жалоб
/status - проверить статус
/info - информация о проекте

Пример для отправки жалоб: `/report @username`
    """
    await message.reply(welcome_text, parse_mode='Markdown')

@dp.message_handler(commands=['report'])
async def cmd_report(message: Message):
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply("❌ Укажи юзернейм.\n\nПример: `/report username123`", parse_mode='Markdown')
        return
    
    target = args[1].strip().replace('@', '')
    
    status_msg = await message.reply(f"🚀 Запускаю атаку на @{target}\n📨 Отправляю 50 жалоб...")
    
    # Сохраняем сессию пользователя
    user_sessions[message.from_user.id] = {
        'target': target,
        'start_time': datetime.now(),
        'status': 'in_progress',
        'success': 0,
        'failed': 0
    }
    
    success, failed = await report_manager.flood_reports(target, count=50)
    
    # Обновляем сессию после завершения
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
async def cmd_status(message: Message):
    user_id = message.from_user.id
    
    # Проверяем наличие сессии
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
    
    if session['status'] == 'completed':
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Новая атака", callback_data=f"new_{session['target']}")],
            [InlineKeyboardButton(text="🗑 Очистить историю", callback_data="clear")]
        ])
        await message.reply(status_text_full, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.reply(status_text_full, parse_mode='Markdown')

@dp.callback_query_handler(lambda c: c.data.startswith('new_'))
async def new_attack(callback: CallbackQuery):
    target = callback.data.replace('new_', '')
    await callback.answer("🔄 Запуск новой атаки...")
    await callback.message.answer(f"/report {target}")
    await callback.message.delete()

@dp.callback_query_handler(lambda c: c.data == 'clear')
async def clear_session(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    await callback.answer("✅ История очищена")
    await callback.message.edit_text("✅ История сессий очищена.\n\nИспользуйте `/report` для новой атаки.", parse_mode='Markdown')

@dp.message_handler()
async def handle_message(message: Message):
    await message.reply("❓ Неизвестная команда.\n\nИспользуй `/report <username>` или `/status`", parse_mode='Markdown')

async def main():
    print("🤖 Бот запущен. Нажми Ctrl + C для остановки.")
    await dp.start_polling()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
