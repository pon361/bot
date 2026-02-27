# api_searcher.py
import re
import requests
import json
import socket
from typing import Dict, Any, Optional, List, Tuple, Set
from datetime import datetime
from urllib.parse import quote
from config import API_KEYS, INFINITY_CHECK_URL_PHONE, INFINITY_CHECK_URL_EMAIL, INFINITY_CHECK_URL_FIO, INFINITY_CHECK_URL_FIO_WITH_DATE, VK_API_VERSION, REQUEST_TIMEOUT

class APISearcher:
    """Класс для поиска информации через различные API"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.infinity_token = API_KEYS['infinity_check']
    
    def detect_type(self, query: str) -> str:
        """Определение типа запроса"""
        query = query.strip()
        
        # Команды
        if query.lower().startswith('/inn '):
            return "inn_command"
        elif query.lower().startswith('/passport '):
            return "passport_command"
        elif query.lower().startswith('/snils '):
            return "snils_command"
        elif query.lower().startswith('/adr '):
            return "address_command"
        
        # Проверка на номер телефона
        phone_clean = re.sub(r'[^\d]', '', query)
        if (query.startswith('+7') or query.startswith('8') or query.startswith('7')) and len(phone_clean) in [11, 12]:
            return "phone"
        
        # Проверка на email
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', query):
            return "email"
        
        # Проверка на IP
        if re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', query):
            return "ip"
        
        # Проверка на VK
        if 'vk.com/' in query or 'vkontakte.ru/' in query:
            return "vk"
        
        if query.isdigit() and len(query) > 5 and len(query) < 15:
            return "vk"
        
        # Проверка на Telegram
        if query.startswith('@') or 't.me/' in query:
            return "telegram"
        
        # Проверка на ФИО (русские буквы, минимум 2 слова)
        words = query.split()
        if len(words) >= 2 and all(re.match(r'^[А-Яа-яЁё]+$', word) for word in words):
            return "full_name"
        
        return "unknown"
    
    def get_possible_types(self, query: str) -> List[Tuple[str, str]]:
        """Получить возможные типы для неоднозначного запроса"""
        query = query.strip()
        possible_types = []
        
        digits_only = re.sub(r'[^\d]', '', query)
        
        if len(digits_only) == 10 and not (query.startswith('+7') or query.startswith('8') or query.startswith('7')):
            possible_types.append(("inn", "📑 ИНН (10 цифр)"))
            possible_types.append(("passport", "🪪 Паспорт (10 цифр)"))
        
        elif len(digits_only) == 11 and not (query.startswith('+7') or query.startswith('8') or query.startswith('7')):
            possible_types.append(("snils", "🔢 СНИЛС (11 цифр)"))
        
        elif len(digits_only) == 12:
            possible_types.append(("inn", "📑 ИНН (12 цифр)"))
        
        elif re.match(r'^[А-Яа-яЁё\s-]+$', query) and len(query.split()) >= 2:
            possible_types.append(("full_name", "👥 ФИО"))
        
        possible_types.append(("search", "🔍 Универсальный поиск"))
        
        return possible_types
    
    def _normalize_date(self, date_str: str) -> str:
        """Приведение даты к формату ДД.ММ.ГГГГ"""
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%d.%m.%Y")
            except:
                continue
        return date_str
    
    def _normalize_phone(self, phone_raw: str) -> str:
        """Нормализация телефона к формату +7XXXXXXXXXX"""
        digits = re.sub(r'[^\d]', '', str(phone_raw))
        if digits.startswith('8') and len(digits) == 11:
            return '+7' + digits[1:]
        elif digits.startswith('7') and len(digits) == 11:
            return '+' + digits
        elif len(digits) == 10:
            return '+7' + digits
        return phone_raw  # если не получилось, вернем как есть
    
    def _normalize_snils(self, snils_raw: str) -> str:
        """Форматирование СНИЛС в вид XXX-XXX-XXX XX"""
        digits = re.sub(r'[^\d]', '', snils_raw)
        if len(digits) == 11:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"
        return snils_raw
    
    def search_infinity_check(self, query: str, query_type: str, bdate: str = None) -> Tuple[Optional[Dict[str, Set[str]]], Optional[str]]:
        """
        Поиск через Infinity Check API
        Возвращает кортеж (распарсенные данные по категориям, сырой JSON)
        """
        token = self.infinity_token
        url = None
        
        if query_type == "phone":
            clean_phone = re.sub(r'[^\d]', '', query)
            url = INFINITY_CHECK_URL_PHONE.format(phone=clean_phone, token=token)
        elif query_type == "email":
            url = INFINITY_CHECK_URL_EMAIL.format(email=quote(query), token=token)
        elif query_type == "full_name":
            if bdate:
                url = INFINITY_CHECK_URL_FIO_WITH_DATE.format(fio=quote(query), bdate=bdate, token=token)
            else:
                url = INFINITY_CHECK_URL_FIO.format(fio=quote(query), token=token)
        else:
            return None, None
        
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                raw_json = json.dumps(data, ensure_ascii=False, indent=2)
                
                # Инициализируем множества для каждой категории
                parsed = {
                    "fio": set(),
                    "birth_date": set(),
                    "address": set(),
                    "phones": set(),
                    "emails": set(),
                    "passports": set(),
                    "inn": set(),
                    "snils": set(),
                    "cars": set(),
                }
                
                # Обрабатываем массив результатов
                if isinstance(data, dict) and "results" in data:
                    results = data["results"]
                    for item in results:
                        if not isinstance(item, dict):
                            continue
                        
                        # ФИО
                        for key in ["fio", "fullname", "name"]:
                            if key in item and item[key]:
                                val = str(item[key]).strip()
                                if val:
                                    parsed["fio"].add(val)
                        
                        # Дата рождения
                        for key in ["bdate", "bday", "date"]:
                            if key in item and item[key]:
                                val = self._normalize_date(str(item[key]))
                                if val:
                                    parsed["birth_date"].add(val)
                        
                        # Телефон
                        if "phone" in item and item["phone"]:
                            phone = self._normalize_phone(str(item["phone"]))
                            if phone:
                                parsed["phones"].add(phone)
                        
                        # Email
                        if "email" in item and item["email"]:
                            parsed["emails"].add(str(item["email"]).lower())
                        
                        # Паспорт
                        for key in ["passport", "pass_sn"]:
                            if key in item and item[key]:
                                parsed["passports"].add(str(item[key]))
                        
                        # ИНН
                        if "inn" in item and item["inn"]:
                            parsed["inn"].add(str(item["inn"]))
                        
                        # СНИЛС
                        if "snils" in item and item["snils"]:
                            snils = self._normalize_snils(str(item["snils"]))
                            parsed["snils"].add(snils)
                        
                        # Адрес
                        if "address" in item and item["address"]:
                            parsed["address"].add(str(item["address"]))
                        
                        # Автомобиль (госномер)
                        if "gosnumber" in item and item["gosnumber"]:
                            parsed["cars"].add(str(item["gosnumber"]))
                
                return parsed, raw_json
            return None, None
        except Exception as e:
            print(f"Infinity Check API error: {e}")
            return None, None
    
    def search_by_phone(self, phone: str) -> Dict[str, Any]:
        """Поиск по номеру телефона"""
        results = {}
        
        # HTMLWeb API
        clean_phone = re.sub(r'[^\d]', '', phone)
        if clean_phone.startswith('8'):
            clean_phone = '7' + clean_phone[1:]
        elif not clean_phone.startswith('7'):
            clean_phone = '7' + clean_phone
        
        try:
            url = f"https://htmlweb.ru/geo/api.php?json&telcod={clean_phone}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                htmlweb_info = []
                
                if isinstance(data, dict):
                    country = data.get('country', {})
                    if isinstance(country, dict):
                        htmlweb_info.append(f"Страна: {country.get('name', 'Не найдено')}")
                    
                    oper = data.get('oper', 'Не найдено')
                    htmlweb_info.append(f"Оператор: {oper}")
                    
                    region = data.get('region', {})
                    if isinstance(region, dict):
                        htmlweb_info.append(f"Регион: {region.get('name', 'Не найдено')}")
                    
                    results["htmlweb_info"] = htmlweb_info
        except Exception as e:
            results["htmlweb_error"] = str(e)
        
        # Infinity Check API
        parsed, raw_json = self.search_infinity_check(phone, "phone")
        if parsed:
            results["infinity_parsed"] = parsed
        if raw_json:
            results["infinity_raw"] = raw_json
        
        return results
    
    def search_by_email(self, email: str) -> Dict[str, Any]:
        """Поиск по email"""
        results = {}
        
        # Veriphone
        try:
            url = f"https://api.veriphone.io/v2/verify?email={email}&key={API_KEYS['veriphone']}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                email_info = []
                email_info.append(f"Email: {email}")
                email_info.append(f"Валидный: {data.get('email_valid', False)}")
                email_info.append(f"Домен: {data.get('domain', 'Неизвестно')}")
                email_info.append(f"Провайдер: {data.get('provider', 'Неизвестно')}")
                results["email_info"] = email_info
        except:
            pass
        
        # Infinity Check API
        parsed, raw_json = self.search_infinity_check(email, "email")
        if parsed:
            results["infinity_parsed"] = parsed
        if raw_json:
            results["infinity_raw"] = raw_json
        
        return results
    
    def search_by_full_name(self, full_name: str, bdate: str = None) -> Dict[str, Any]:
        """Поиск по ФИО"""
        results = {}
        
        # Infinity Check API
        parsed, raw_json = self.search_infinity_check(full_name, "full_name", bdate)
        if parsed:
            results["infinity_parsed"] = parsed
        if raw_json:
            results["infinity_raw"] = raw_json
        
        return results
    
    def search_by_vk(self, query: str) -> Dict[str, Any]:
        """Поиск по VK"""
        results = {}
        vk_identifier = self._extract_vk_identifier(query)
        
        try:
            token = API_KEYS['vk_token']
            
            if not vk_identifier.isdigit():
                resolve_url = "https://api.vk.com/method/utils.resolveScreenName"
                params = {
                    'screen_name': vk_identifier,
                    'access_token': token,
                    'v': VK_API_VERSION
                }
                
                response = self.session.get(resolve_url, params=params, timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    data = response.json()
                    if 'response' in data and data['response']:
                        vk_identifier = str(data['response']['object_id'])
            
            if vk_identifier.isdigit():
                users_url = "https://api.vk.com/method/users.get"
                params = {
                    'user_ids': vk_identifier,
                    'fields': 'sex,bdate,city,country,home_town,domain,status,last_seen,followers_count,photo_max_orig',
                    'access_token': token,
                    'v': VK_API_VERSION
                }
                
                response = self.session.get(users_url, params=params, timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    data = response.json()
                    if 'response' in data and len(data['response']) > 0:
                        user = data['response'][0]
                        vk_info = []
                        
                        vk_info.append(f"ID: {user.get('id', 'Не указано')}")
                        
                        first_name = user.get('first_name', '')
                        last_name = user.get('last_name', '')
                        vk_info.append(f"Имя: {first_name} {last_name}".strip())
                        
                        sex = user.get('sex')
                        if sex == 1:
                            vk_info.append("Пол: Женский")
                        elif sex == 2:
                            vk_info.append("Пол: Мужской")
                        
                        bdate = user.get('bdate', 'Не указана')
                        vk_info.append(f"Дата рождения: {bdate}")
                        
                        city = user.get('city', {})
                        if city:
                            vk_info.append(f"Город: {city.get('title', 'Не указан')}")
                        
                        country = user.get('country', {})
                        if country:
                            vk_info.append(f"Страна: {country.get('title', 'Не указана')}")
                        
                        last_seen = user.get('last_seen', {})
                        if last_seen:
                            last_seen_time = datetime.fromtimestamp(last_seen.get('time', 0)).strftime('%Y-%m-%d %H:%M:%S')
                            vk_info.append(f"Последний вход: {last_seen_time}")
                        
                        status = user.get('status', 'Не указан')
                        if status:
                            vk_info.append(f"Статус: {status}")
                        
                        online = user.get('online', 0)
                        vk_info.append(f"Онлайн: {'Да' if online else 'Нет'}")
                        
                        domain = user.get('domain', '')
                        if domain:
                            vk_info.append(f"Короткая ссылка: https://vk.com/{domain}")
                        
                        vk_info.append(f"Полная ссылка: https://vk.com/id{user.get('id', '')}")
                        
                        results["vk_info"] = vk_info
                    else:
                        results["vk_error"] = "Пользователь не найден"
        except Exception as e:
            results["vk_error"] = str(e)
        
        return results
    
    def _extract_vk_identifier(self, query: str) -> str:
        """Извлечение идентификатора VK"""
        query = query.strip()
        
        if 'vk.com/' in query:
            parts = query.split('vk.com/')[-1].split('/')[0].split('?')[0]
            if parts.startswith('id'):
                return parts[2:]
            return parts
        elif 'vkontakte.ru/' in query:
            parts = query.split('vkontakte.ru/')[-1].split('/')[0].split('?')[0]
            if parts.startswith('id'):
                return parts[2:]
            return parts
        
        if query.isdigit():
            return query
        
        return query
    
    def search_by_telegram(self, query: str) -> Dict[str, Any]:
        """Поиск по Telegram"""
        results = {}
        
        username = query.replace('@', '').replace('t.me/', '').split('/')[0]
        
        tg_info = [
            f"Username: @{username}",
            f"Ссылка: https://t.me/{username}"
        ]
        
        try:
            response = self.session.get(f"https://t.me/{username}", timeout=10)
            if response.status_code == 200:
                tg_info.append("Аккаунт: Существует")
            else:
                tg_info.append("Аккаунт: Не найден")
        except:
            tg_info.append("Аккаунт: Не удалось проверить")
        
        tg_info.append(f"Поиск: https://www.google.com/search?q=@{username}")
        
        results["telegram_info"] = tg_info
        
        return results
    
    def search_by_ip(self, ip: str) -> Dict[str, Any]:
        """Поиск по IP адресу"""
        results = {}
        ip_info = []
        
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            ip_info.append(f"Hostname: {hostname}")
        except:
            ip_info.append("Hostname: Не найден")
        
        try:
            response = self.session.get(f"http://ip-api.com/json/{ip}", timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    ip_info.append(f"Страна: {data.get('country', 'Не найдено')}")
                    ip_info.append(f"Регион: {data.get('regionName', 'Не найдено')}")
                    ip_info.append(f"Город: {data.get('city', 'Не найдено')}")
                    ip_info.append(f"Провайдер: {data.get('isp', 'Не найдено')}")
                    ip_info.append(f"Организация: {data.get('org', 'Не найдено')}")
                    ip_info.append(f"Координаты: {data.get('lat')}, {data.get('lon')}")
        except:
            pass
        
        results["ip_info"] = ip_info
        return results
    
    def search_all(self, query: str, forced_type: str = None, bdate: str = None) -> Dict[str, Any]:
        """Комплексный поиск"""
        if forced_type:
            query_type = forced_type
        else:
            query_type = self.detect_type(query)
        
        if query_type == "inn_command":
            inn = query.replace('/inn', '').strip()
            return {
                "query": inn,
                "type": "inn",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "data": {"inn_info": [f"ИНН: {inn}"]}
            }
        elif query_type == "passport_command":
            passport = query.replace('/passport', '').strip()
            return {
                "query": passport,
                "type": "passport",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "data": {"passport_info": [f"Паспорт: {passport}"]}
            }
        elif query_type == "snils_command":
            snils = query.replace('/snils', '').strip()
            return {
                "query": snils,
                "type": "snils",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "data": {"snils_info": [f"СНИЛС: {snils}"]}
            }
        elif query_type == "address_command":
            address = query.replace('/adr', '').strip()
            return {
                "query": address,
                "type": "address",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "data": {"address_info": [f"Адрес: {address}"]}
            }
        
        results = {
            "query": query,
            "type": query_type,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "data": {}
        }
        
        if query_type == "phone":
            results["data"]["phone_info"] = self.search_by_phone(query)
        elif query_type == "email":
            results["data"]["email_info"] = self.search_by_email(query)
        elif query_type == "full_name":
            results["data"]["full_name_info"] = self.search_by_full_name(query, bdate)
        elif query_type == "vk":
            results["data"]["vk_info"] = self.search_by_vk(query)
        elif query_type == "telegram":
            results["data"]["telegram_info"] = self.search_by_telegram(query)
        elif query_type == "ip":
            results["data"]["ip_info"] = self.search_by_ip(query)
        elif query_type == "unknown":
            results["data"]["unknown_info"] = [f"❓ Неизвестная команда: {query}", "Выполняю универсальный поиск..."]
        
        return results