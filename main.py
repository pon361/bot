# main.py
import logging
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, Union
import sys
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)
from telegram.error import NetworkError, TimedOut

from config import TELEGRAM_BOT_TOKEN, BOT_USERNAME, ADMIN_ID, MAIN_MENU, SEARCH, TYPE_SELECTION
from database import DatabaseSearcher, UserDatabase
from api_searcher import APISearcher

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация
db_searcher = DatabaseSearcher()
api_searcher = APISearcher()
user_db = UserDatabase()

# Хранилище результатов
search_results = {}
temp_data = {}

def get_type_emoji(query_type: str) -> str:
    """Получить эмодзи для типа запроса"""
    emojis = {
        "phone": "📱",
        "vk": "👤",
        "telegram": "✈️",
        "ip": "🌐",
        "email": "📧",
        "full_name": "👥",
        "inn": "📑",
        "snils": "🔢",
        "passport": "🪪",
        "address": "🏠",
        "search": "🔍",
        "unknown": "❓"
    }
    return emojis.get(query_type, "🔍")

def get_main_keyboard():
    """Создать клавиатуру главного меню"""
    keyboard = [
        [KeyboardButton("🔍 Поиск информации")],
        [KeyboardButton("📚 История запросов")],
        [KeyboardButton("❓ Помощь")],
        [KeyboardButton("📊 Статистика")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def format_final_report(api_results: Dict[str, Any], db_categories: Dict[str, Any], query: str) -> str:
    """Форматирование единого отчета (только распределенные данные)"""
    output = []
    
    # Основная информация (оператор, регион, страна) из HTMLWeb
    if api_results.get('data', {}).get('phone_info', {}).get('htmlweb_info'):
        phone_info = api_results['data']['phone_info']['htmlweb_info']
        output.append("📡 ОСНОВНАЯ ИНФОРМАЦИЯ")
        for i, line in enumerate(phone_info):
            if i == len(phone_info) - 1:
                output.append(f"└ {line}")
            else:
                output.append(f"├ {line}")
        output.append("")
    
    # Данные из Infinity Check API (распределенные)
    infinity_parsed = None
    if api_results.get('data', {}).get('phone_info', {}).get('infinity_parsed'):
        infinity_parsed = api_results['data']['phone_info']['infinity_parsed']
    elif api_results.get('data', {}).get('email_info', {}).get('infinity_parsed'):
        infinity_parsed = api_results['data']['email_info']['infinity_parsed']
    elif api_results.get('data', {}).get('full_name_info', {}).get('infinity_parsed'):
        infinity_parsed = api_results['data']['full_name_info']['infinity_parsed']
    
    # Собираем все данные из БД и из Infinity в единые множества
    merged = {
        "fio": set(),
        "birth_date": set(),
        "address": set(),
        "phones": set(),
        "emails": set(),
        "passports": set(),
        "inn": set(),
        "snils": set(),
        "social": set(),
        "cars": set(),
    }
    
    # Из БД
    for cat in merged.keys():
        if cat in db_categories:
            for item in db_categories[cat]:
                merged[cat].add(item["value"])
    
    # Из Infinity
    if infinity_parsed:
        for cat in merged.keys():
            if cat in infinity_parsed:
                merged[cat].update(infinity_parsed[cat])
    
    # Формируем вывод по категориям (только если есть данные)
    
    # ЛИЧНЫЕ ДАННЫЕ (только ФИО и дата)
    personal_items = []
    if merged["fio"]:
        for fio in merged["fio"]:
            personal_items.append(f"ФИО: {fio}")
    if merged["birth_date"]:
        for bd in merged["birth_date"]:
            personal_items.append(f"Дата: {bd}")
    
    if personal_items:
        output.append("👤 ЛИЧНЫЕ ДАННЫЕ")
        for i, item in enumerate(personal_items):
            if i == len(personal_items) - 1:
                output.append(f"└ {item}")
            else:
                output.append(f"├ {item}")
        output.append("")
    
    # АДРЕСА
    if merged["address"]:
        output.append("🏠 АДРЕСА")
        addr_list = list(merged["address"])
        for i, addr in enumerate(addr_list[:5]):
            if i == len(addr_list[:5]) - 1:
                output.append(f"└ {addr}")
            else:
                output.append(f"├ {addr}")
        if len(addr_list) > 5:
            output.append(f"└ ... и еще {len(addr_list)-5}")
        output.append("")
    
    # ТЕЛЕФОНЫ
    if merged["phones"]:
        output.append("📱 ТЕЛЕФОНЫ")
        phone_list = list(merged["phones"])
        for i, phone in enumerate(phone_list[:5]):
            if i == len(phone_list[:5]) - 1:
                output.append(f"└ {phone}")
            else:
                output.append(f"├ {phone}")
        if len(phone_list) > 5:
            output.append(f"└ ... и еще {len(phone_list)-5}")
        output.append("")
    
    # EMAIL
    if merged["emails"]:
        output.append("📧 EMAIL")
        email_list = list(merged["emails"])
        for i, email in enumerate(email_list[:5]):
            if i == len(email_list[:5]) - 1:
                output.append(f"└ {email}")
            else:
                output.append(f"├ {email}")
        if len(email_list) > 5:
            output.append(f"└ ... и еще {len(email_list)-5}")
        output.append("")
    
    # СОЦ СЕТИ
    if merged["social"]:
        output.append("🌐 СОЦ СЕТИ")
        social_list = list(merged["social"])
        for i, link in enumerate(social_list[:5]):
            if i == len(social_list[:5]) - 1:
                output.append(f"└ {link}")
            else:
                output.append(f"├ {link}")
        if len(social_list) > 5:
            output.append(f"└ ... и еще {len(social_list)-5}")
        output.append("")
    
    # ПАСПОРТА
    if merged["passports"]:
        output.append("🪪 ПАСПОРТА")
        pass_list = list(merged["passports"])
        for i, p in enumerate(pass_list[:3]):
            if i == len(pass_list[:3]) - 1:
                output.append(f"└ {p}")
            else:
                output.append(f"├ {p}")
        if len(pass_list) > 3:
            output.append(f"└ ... и еще {len(pass_list)-3}")
        output.append("")
    
    # ИНН
    if merged["inn"]:
        output.append("📑 ИНН")
        inn_list = list(merged["inn"])
        for i, inn in enumerate(inn_list[:3]):
            if i == len(inn_list[:3]) - 1:
                output.append(f"└ {inn}")
            else:
                output.append(f"├ {inn}")
        if len(inn_list) > 3:
            output.append(f"└ ... и еще {len(inn_list)-3}")
        output.append("")
    
    # СНИЛС
    if merged["snils"]:
        output.append("🔢 СНИЛС")
        snils_list = list(merged["snils"])
        for i, s in enumerate(snils_list[:3]):
            if i == len(snils_list[:3]) - 1:
                output.append(f"└ {s}")
            else:
                output.append(f"├ {s}")
        if len(snils_list) > 3:
            output.append(f"└ ... и еще {len(snils_list)-3}")
        output.append("")
    
    # АВТОМОБИЛИ
    if merged["cars"]:
        output.append("🚗 АВТОМОБИЛИ")
        cars_list = list(merged["cars"])
        for i, car in enumerate(cars_list[:3]):
            if i == len(cars_list[:3]) - 1:
                output.append(f"└ {car}")
            else:
                output.append(f"├ {car}")
        if len(cars_list) > 3:
            output.append(f"└ ... и еще {len(cars_list)-3}")
        output.append("")
    
    # ИСПОЛЬЗОВАННЫЕ БАЗЫ
    if "used_files" in db_categories and db_categories["used_files"]:
        output.append("✉️ ИСПОЛЬЗОВАННЫЕ БАЗЫ")
        for i, item in enumerate(db_categories["used_files"]):
            if i == len(db_categories["used_files"]) - 1:
                output.append(f"└ {item['value']}")
            else:
                output.append(f"├ {item['value']}")
    
    return "\n".join(output)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    user_db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = f"""
👋 Добро пожаловать, {user.first_name}!

Я многофункциональный бот для поиска информации.

🆘 СПРАВКА ПО ИСПОЛЬЗОВАНИЮ

📱 Поиск по номеру:
├ +7 (777) 777-77-77
├ 87777777777
└ 7777777777

👤 Поиск по VK:
├ https://vk.com/id755057999
├ id755057999
└ 755057999

✈️ Поиск по Telegram:
├ @username
└ https://t.me/username

🌐 Анализ IP:
├ 8.8.8.8
└ 77.88.55.66

📧 Поиск по email:
├ name@mail.ru
└ user@gmail.com

👥 Поиск по ФИО:
├ Иванов Петр Сидорович
└ Бриткин Александр Александрович

📑 Поиск по документам:
├ /inn 1234567890
├ /passport 1234 567890
├ /snils 123-456-789 00
└ /adr Москва, ул. Ленина

📁 Команды:
/start - Главное меню
/help - Эта справка

💡 Просто отправьте любые данные - бот сам определит тип поиска!
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )
    
    return MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = f"""
🆘 СПРАВКА ПО ИСПОЛЬЗОВАНИЮ

📱 Поиск по номеру:
├ +7 (777) 777-77-77
├ 87777777777
└ 7777777777

👤 Поиск по VK:
├ https://vk.com/id755057999
├ id755057999
└ 755057999

✈️ Поиск по Telegram:
├ @username
└ https://t.me/username

🌐 Анализ IP:
├ 8.8.8.8
└ 77.88.55.66

📧 Поиск по email:
├ name@mail.ru
└ user@gmail.com

👥 Поиск по ФИО:
├ Иванов Петр Сидорович
└ Бриткин Александр Александрович

📑 Поиск по документам:
├ /inn 1234567890
├ /passport 1234 567890
├ /snils 123-456-789 00
└ /adr Москва, ул. Ленина

📁 Команды:
/start - Главное меню
/help - Эта справка
    """
    
    await update.message.reply_text(
        help_text,
        reply_markup=get_main_keyboard()
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика (только для админа)"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет доступа к этой команде")
        return
    
    stats = user_db.get_stats()
    
    stats_text = f"""
📊 СТАТИСТИКА БОТА

👥 Пользователей: {stats['total_users']}
📨 Запросов: {stats['total_requests']}
📚 Всего поисков: {stats['total_queries']}
⚙️ Версия: 13.0 (Финальная)
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    await update.message.reply_text(stats_text)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка главного меню"""
    text = update.message.text
    
    if text == "🔍 Поиск информации":
        await update.message.reply_text(
            "🔍 Отправьте данные для поиска:",
            reply_markup=get_main_keyboard()
        )
        return SEARCH
    
    elif text == "📚 История запросов":
        user_id = update.effective_user.id
        history = user_db.get_user_history(user_id)
        
        if history:
            history_text = "📚 ИСТОРИЯ ЗАПРОСОВ\n\n"
            for item in history[:10]:
                emoji = get_type_emoji(item['type'])
                history_text += f"{emoji} {item['query']}\n"
                history_text += f"   🕐 {item['time'][:19]}\n\n"
        else:
            history_text = "📚 История запросов пуста"
        
        await update.message.reply_text(history_text)
        return MAIN_MENU
    
    elif text == "❓ Помощь":
        await help_command(update, context)
        return MAIN_MENU
    
    elif text == "📊 Статистика":
        if update.effective_user.id == ADMIN_ID:
            await stats_command(update, context)
        else:
            await update.message.reply_text("📊 Статистика доступна только администратору")
        return MAIN_MENU
    
    else:
        return await handle_search_query(update, context, text)

async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Обработка поискового запроса"""
    user_id = update.effective_user.id
    
    temp_data[user_id] = {"query": query}
    
    possible_types = api_searcher.get_possible_types(query)
    
    if len(possible_types) == 1 or query.startswith('/'):
        await perform_search(update, context, user_id, query, is_message=True)
        return MAIN_MENU
    
    keyboard = []
    for type_key, type_name in possible_types:
        callback_data = f"type_{type_key}_{user_id}"
        keyboard.append([InlineKeyboardButton(type_name, callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "❓ Что вы ищете?",
        reply_markup=reply_markup
    )
    
    return TYPE_SELECTION

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсальный обработчик сообщений"""
    text = update.message.text.strip()
    
    if text in ["🔍 Поиск информации", "📚 История запросов", "❓ Помощь", "📊 Статистика"]:
        return await handle_main_menu(update, context)
    
    return await handle_search_query(update, context, text)

async def handle_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора типа поиска"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    parts = callback_data.split('_')
    
    if len(parts) >= 3 and parts[0] == "type":
        selected_type = parts[1]
        user_id = int(parts[2])
        
        if user_id in temp_data:
            user_query = temp_data[user_id]["query"]
            await perform_search(update, context, user_id, user_query, selected_type, is_message=False)
            del temp_data[user_id]
    
    return MAIN_MENU

async def perform_search(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                        user_id: int, query: str, forced_type: str = None, is_message: bool = False):
    """Выполнение поиска"""
    
    if is_message:
        message = update.message
    else:
        message = update.callback_query.message
    
    user_db.update_activity(user_id)
    
    if forced_type:
        query_type = forced_type
    else:
        query_type = api_searcher.detect_type(query)
    
    user_db.add_to_history(user_id, query, query_type)
    
    await message.chat.send_action(action="typing")
    wait_msg = await message.reply_text("🔍 Выполняю поиск...")
    
    try:
        api_results = api_searcher.search_all(query, forced_type)
        db_categories = db_searcher.search_in_files(query, user_id)
        
        await wait_msg.delete()
        
        # Отправляем сырой JSON от Infinity Check API как файл, если есть
        infinity_raw = None
        if api_results.get('data', {}).get('phone_info', {}).get('infinity_raw'):
            infinity_raw = api_results['data']['phone_info']['infinity_raw']
        elif api_results.get('data', {}).get('email_info', {}).get('infinity_raw'):
            infinity_raw = api_results['data']['email_info']['infinity_raw']
        elif api_results.get('data', {}).get('full_name_info', {}).get('infinity_raw'):
            infinity_raw = api_results['data']['full_name_info']['infinity_raw']
        
        if infinity_raw:
            # Формируем безопасное имя файла из запроса
            safe_query = re.sub(r'[\\/*?:"<>|]', "_", query)[:50]  # удаляем недопустимые символы
            filename = f"result:{safe_query}.json"
            file_data = BytesIO(infinity_raw.encode('utf-8'))
            await message.reply_document(document=file_data, filename=filename, caption="📦 ОТЧЕТ INFINITY CHECK API")
        
        # Формируем единый отчет с распределенными данными
        report = format_final_report(api_results, db_categories, query)
        
        # Кнопки
        keyboard = [
            [
                InlineKeyboardButton("◀️ Назад", callback_data="back"),
                InlineKeyboardButton("🔍 Новый поиск", callback_data="new_search"),
                InlineKeyboardButton("📋 Меню", callback_data="menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        search_results[user_id] = {
            "api": api_results,
            "db": db_categories,
            "query": query
        }
        
        await message.reply_text(report)
        await message.reply_text("Выберите действие:", reply_markup=reply_markup)
        
    except Exception as e:
        await wait_msg.delete()
        error_text = f"❌ Ошибка при поиске: {str(e)[:200]}"
        await message.reply_text(error_text)
        logger.error(f"Ошибка поиска: {e}", exc_info=True)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    action = query.data
    
    if action.startswith("type_"):
        return await handle_type_selection(update, context)
    
    try:
        if action == "back":
            # Возврат к предыдущему запросу
            if user_id in search_results:
                results = search_results[user_id]
                report = format_final_report(results["api"], results["db"], results["query"])
                await query.message.edit_text(report)
        
        elif action == "new_search":
            await query.message.reply_text(
                "🔍 Отправьте новый запрос для поиска:",
                reply_markup=get_main_keyboard()
            )
        
        elif action == "menu":
            await query.message.reply_text(
                "Главное меню:",
                reply_markup=get_main_keyboard()
            )
    
    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")
        logger.error(f"Ошибка в button_callback: {e}", exc_info=True)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    if isinstance(context.error, NetworkError):
        error_msg = "🌐 Ошибка сети. Проверьте подключение к интернету."
    elif isinstance(context.error, TimedOut):
        error_msg = "⏱️ Таймаут соединения. Повторите попытку."
    else:
        error_msg = f"❌ Произошла ошибка. Повторите попытку."
    
    try:
        if update and hasattr(update, 'effective_message') and update.effective_message:
            await update.effective_message.reply_text(error_msg)
    except:
        pass

async def shutdown(application: Application):
    """Корректное завершение работы"""
    logger.info("Завершение работы бота...")
    await application.shutdown()

def main():
    """Запуск бота"""
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ],
        states={
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
            SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
            TYPE_SELECTION: [
                CallbackQueryHandler(button_callback)
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_error_handler(error_handler)
    
    print(f"✅ Бот {BOT_USERNAME} запущен...")
    print(f"👤 Администратор: {ADMIN_ID}")
    print(f"📁 База данных: G:\\бд")
    print("🔄 Ожидание сообщений...")
    print("💡 Можно просто вставлять данные для поиска без выбора пункта меню!")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал прерывания. Завершение работы...")
        asyncio.run(shutdown(application))
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()