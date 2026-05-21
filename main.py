 import telebot 
bot = telebot.TeleBot('8105002960:AAGF4uFOi8uTRHIhjwLn1ifhtTbZqp26DPk') 
 
@bot.message_handler(commands=['start'])  
def handle_start(message): 
 bot.send_gift(message.chat.id,5170233102089322756) 
bot.infinity_polling() 
