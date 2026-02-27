# config.py
import os
from pathlib import Path

# Путь к базе данных
DB_PATH = Path(r"G:\бд")

# Токены и API ключи
TELEGRAM_BOT_TOKEN = '7829623671:AAFZlD5khjq8JXqgNMx9jHR5oc10M5OROcY'
BOT_USERNAME = '@Doxing_foxing_fox_bot'

# ID администратора
ADMIN_ID = 6743518496

# API ключи
API_KEYS = {
    'vk_token': "0af157510af157510af15751aa0a89e69600af10af157516a0bc15996e74fe2b440998c",
    'vk_service_token': "0af157510af157510af15751aa0a89e69600af10af157516a0bc15996e74fe2b440998c",
    'shodan': "aytQRnUGbufbvrEoftFAGK5sglpFC6Mi",
    'virustotal': "dbbc251dda62fb51321132d79b070d00cad48acec4c660f7f0b313eb09056e9b",
    'abuseipdb': "58878ed65228db88eddfda4983bce5d19d425ddf81f427857b3f59f11aecc34f127862a1cc7d4581",
    'apilayer': "8ef518060216adc3e9f38b4b393830bd",
    'veriphone': "1A85D514E9B04073AC51FA394182728A",
    'htmlweb': "c335d87f4e99ce6a747f8628bea61368f7274ff83b39d019c4ed0731",
    'smsc_login': "alex",
    'smsc_password': "123",
    'infinity_check': "H97MbOpjQenpSQwnz98",
    'deepseek': "sk-dbe829e79aa5495ab28a690adb28bc44"
}

# Infinity Check API URLs
INFINITY_CHECK_URL_PHONE = "https://infinity-check.online/find?phone={phone}&token={token}"
INFINITY_CHECK_URL_EMAIL = "https://infinity-check.online/find?email={email}&token={token}"
INFINITY_CHECK_URL_FIO = "https://infinity-check.online/find?fio={fio}&token={token}"
INFINITY_CHECK_URL_FIO_WITH_DATE = "https://infinity-check.online/find?fio={fio}&bdate={bdate}&token={token}"

# Telegram API
TG_API_ID = 30207279
TG_API_HASH = "022064abaf06110a3722ceb63d2f0161"

# VK API версия
VK_API_VERSION = '5.131'

# Настройки бота
MAX_MESSAGE_LENGTH = 4000
REQUEST_TIMEOUT = 30
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1 ГБ
CONNECTION_RETRIES = 3

# Список исключаемых файлов
EXCLUDED_FILES = [
    'test-database-@resolink-part2.txt',
    'test-database-@resolink-part1.txt',
    'test-database.txt'
]

# Поддерживаемые расширения файлов
SUPPORTED_EXTENSIONS = ['.txt', '.csv', '.json', '.xlsx', '.xls', '.db', '.sqlite']

# Состояния для ConversationHandler
MAIN_MENU, SEARCH, TYPE_SELECTION = range(3)