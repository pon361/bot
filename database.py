# database.py
import os
import csv
import json
import sqlite3
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import pandas as pd
from collections import defaultdict
from config import DB_PATH, SUPPORTED_EXTENSIONS, EXCLUDED_FILES, MAX_FILE_SIZE

class DataParser:
    """Класс для парсинга и категоризации данных с удалением дубликатов"""
    
    @classmethod
    def extract_fio(cls, text: str) -> Set[str]:
        """Извлечение ФИО из текста"""
        fio_set = set()
        
        fio_patterns = [
            r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)',
            r'([а-яё]+\s+[а-яё]+\s+[а-яё]+)',
        ]
        
        stop_words = ['области', 'района', 'города', 'гувд', 'овд', 'увд', 'мвд', 'говд']
        
        for pattern in fio_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                words = match.split()
                is_valid = True
                for word in words:
                    if word.lower() in stop_words:
                        is_valid = False
                        break
                    if len(word) > 15 or not re.match(r'^[А-Яа-яЁё]+$', word):
                        is_valid = False
                        break
                
                if is_valid and len(words) == 3:
                    formatted_fio = ' '.join([word.capitalize() for word in words])
                    fio_set.add(formatted_fio)
        
        return fio_set
    
    @classmethod
    def extract_addresses(cls, text: str) -> Set[str]:
        """Извлечение адресов"""
        addresses = set()
        
        address_keywords = [
            'г\.', 'город', 'ул\.', 'улица', 'д\.', 'дом', 'кв\.', 'квартира',
            'область', 'обл\.', 'район', 'р-н', 'мкр', 'микрорайон', 'пос\.', 'поселок',
            'проспект', 'пр-т', 'бульвар', 'набережная', 'переулок', 'пер\.',
            'шоссе', 'тупик', 'аллея', 'проезд'
        ]
        
        parts = re.split(r'[;,\n\r]+', text)
        
        for part in parts:
            part = part.strip()
            if any(re.search(keyword, part, re.IGNORECASE) for keyword in address_keywords):
                clean_part = re.sub(r'\s+', ' ', part).strip()
                if len(clean_part) > 15:
                    addresses.add(clean_part)
        
        return addresses
    
    @classmethod
    def extract_phones(cls, text: str) -> Set[str]:
        """Извлечение телефонов"""
        phones = set()
        
        phone_patterns = [
            (r'\+7\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}', 
             lambda x: re.sub(r'[^\d+]', '', x)),
            (r'8\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}', 
             lambda x: '+7' + re.sub(r'[^\d]', '', x)[1:]),
            (r'\b[78]\d{10}\b', 
             lambda x: '+7' + x[1:] if x.startswith('8') else '+' + x),
        ]
        
        for pattern, normalizer in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    normalized = normalizer(match)
                    if normalized and len(re.sub(r'[^\d]', '', normalized)) >= 11:
                        phones.add(normalized)
                except:
                    continue
        
        return phones
    
    @classmethod
    def extract_emails(cls, text: str) -> Set[str]:
        """Извлечение email"""
        emails = set()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(email_pattern, text, re.IGNORECASE)
        emails.update(matches)
        return emails
    
    @classmethod
    def extract_social_links(cls, text: str) -> Set[str]:
        """Извлечение ссылок на соцсети"""
        social_links = set()
        
        social_patterns = [
            r'https?://(?:www\.)?vk\.com/[a-zA-Z0-9_.]+',
            r'https?://(?:www\.)?t\.me/[a-zA-Z0-9_]+',
            r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+',
            r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9.]+',
            r'https?://(?:www\.)?twitter\.com/[a-zA-Z0-9_]+',
            r'https?://(?:www\.)?ok\.ru/[a-zA-Z0-9_.]+',
            r'https?://(?:www\.)?youtube\.com/@[a-zA-Z0-9_]+',
            r'https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.]+',
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            social_links.update(matches)
        
        return social_links
    
    @classmethod
    def extract_documents(cls, text: str) -> Dict[str, Set[str]]:
        """Извлечение документов"""
        docs = {
            "passports": set(),
            "inn": set(),
            "snils": set()
        }
        
        numbers = re.findall(r'\b\d{10}\b|\b\d{11}\b|\b\d{12}\b', text)
        
        for num in numbers:
            is_phone = False
            if len(num) == 11 and num.startswith(('7', '8')):
                is_phone = True
            elif len(num) == 10 and num.startswith(('7', '8')):
                is_phone = True
            
            if is_phone:
                continue
            
            if len(num) == 10 and not num.startswith(('7', '8')):
                docs["passports"].add(num)
                docs["inn"].add(num)
            elif len(num) == 11:
                formatted = f"{num[:3]}-{num[3:6]}-{num[6:9]} {num[9:]}"
                docs["snils"].add(formatted)
            elif len(num) == 12:
                docs["inn"].add(num)
        
        return docs
    
    @classmethod
    def extract_cars(cls, text: str) -> Set[str]:
        """Извлечение автомобильных номеров"""
        cars = set()
        
        car_patterns = [
            r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}',  # A123BC 777
            r'[A-Z]\d{3}[A-Z]{2}\d{2,3}',  # A123BC 777 (латиница)
            r'\b\d{4}[А-Я]{2}\d{2,3}\b',  # 1234AB 77
        ]
        
        for pattern in car_patterns:
            matches = re.findall(pattern, text)
            cars.update(matches)
        
        return cars
    
    @classmethod
    def extract_all_info(cls, text: str) -> Dict[str, Set[str]]:
        """Извлечение всей информации"""
        categories = {
            "full_record": {text.strip()},
            "fio": cls.extract_fio(text),
            "birth_date": set(),
            "address": cls.extract_addresses(text),
            "phones": cls.extract_phones(text),
            "emails": cls.extract_emails(text),
            "social": cls.extract_social_links(text),
            "cars": cls.extract_cars(text),
        }
        
        # Дата рождения
        dates = re.findall(r'\b(\d{2}\.\d{2}\.\d{4})\b', text)
        categories["birth_date"].update(dates)
        
        # Документы
        documents = cls.extract_documents(text)
        categories.update(documents)
        
        return categories


class DatabaseSearcher:
    """Класс для поиска по файлам"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.excluded_files = EXCLUDED_FILES
        self.current_results = {}
        self.parser = DataParser()
        
    def search_in_files(self, query: str, user_id: int = None) -> Dict[str, List[Dict[str, Any]]]:
        """Поиск запроса в файлах"""
        query_lower = query.lower().strip()
        
        if not self.db_path.exists():
            return {"error": f"Путь {self.db_path} не существует"}
        
        all_categories = defaultdict(lambda: defaultdict(set))
        used_files = set()
        
        for file_path in self.db_path.rglob('*'):
            if file_path.name in self.excluded_files:
                continue
                
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    if file_path.stat().st_size > MAX_FILE_SIZE:
                        continue
                    
                    file_matches = self._search_in_file(file_path, query_lower)
                    if file_matches:
                        used_files.add(file_path.name)
                        for match in file_matches:
                            categories = self.parser.extract_all_info(match["content"])
                            
                            for cat_name, values in categories.items():
                                for value in values:
                                    all_categories[cat_name][value].add(file_path.name)
                except Exception as e:
                    print(f"Ошибка при чтении {file_path}: {e}")
                    continue
        
        result = {}
        for cat_name, values_dict in all_categories.items():
            result[cat_name] = []
            for value, files in values_dict.items():
                result[cat_name].append({
                    "value": value,
                    "files": list(files)
                })
        
        # Добавляем информацию об использованных файлах
        result["used_files"] = [{"value": f, "files": [f]} for f in sorted(used_files)]
        
        # Сортируем
        for cat_name in result:
            if cat_name != "used_files":
                result[cat_name].sort(key=lambda x: len(x["files"]), reverse=True)
        
        if user_id:
            self.current_results[user_id] = {
                "query": query,
                "categories": result
            }
        
        return result
    
    def _search_in_file(self, file_path: Path, query: str) -> List[Dict[str, Any]]:
        """Поиск в файле"""
        matches = []
        ext = file_path.suffix.lower()
        
        try:
            if ext == '.txt':
                matches = self._search_txt(file_path, query)
            elif ext == '.csv':
                matches = self._search_csv(file_path, query)
            elif ext == '.json':
                matches = self._search_json(file_path, query)
            elif ext in ['.db', '.sqlite']:
                matches = self._search_sqlite(file_path, query)
            elif ext in ['.xlsx', '.xls']:
                matches = self._search_excel(file_path, query)
        except Exception as e:
            matches = [{"line": 0, "content": f"Ошибка чтения: {str(e)[:50]}...", "file": str(file_path)}]
        
        return matches
    
    def _search_txt(self, file_path: Path, query: str) -> List[Dict[str, Any]]:
        """Поиск в TXT"""
        matches = []
        try:
            encodings = ['utf-8', 'cp1251', 'latin-1', 'koi8-r']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                clean_line = line.strip().replace('\x00', '')
                                matches.append({
                                    "line": i,
                                    "content": clean_line,
                                    "file": str(file_path)
                                })
                    break
                except UnicodeDecodeError:
                    continue
        except:
            pass
        return matches
    
    def _search_csv(self, file_path: Path, query: str) -> List[Dict[str, Any]]:
        """Поиск в CSV"""
        matches = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader, 1):
                    row_str = ';'.join(str(cell) for cell in row)
                    if query.lower() in row_str.lower():
                        matches.append({
                            "line": i,
                            "content": row_str,
                            "file": str(file_path)
                        })
        except:
            pass
        return matches
    
    def _search_sqlite(self, file_path: Path, query: str) -> List[Dict[str, Any]]:
        """Поиск в SQLite"""
        matches = []
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5000")
                    rows = cursor.fetchall()
                    for row in rows:
                        row_str = ';'.join(str(cell) for cell in row)
                        if query.lower() in row_str.lower():
                            matches.append({
                                "line": 0,
                                "content": row_str,
                                "file": str(file_path)
                            })
                except:
                    continue
                    
            conn.close()
        except:
            pass
        return matches
    
    def _search_excel(self, file_path: Path, query: str) -> List[Dict[str, Any]]:
        """Поиск в Excel"""
        matches = []
        try:
            df = pd.read_excel(file_path)
            for idx, row in df.iterrows():
                row_str = ';'.join(str(cell) for cell in row.values)
                if query.lower() in row_str.lower():
                    matches.append({
                        "line": idx + 1,
                        "content": row_str,
                        "file": str(file_path)
                    })
        except:
            pass
        return matches
    
    def _search_json(self, file_path: Path, query: str) -> List[Dict[str, Any]]:
        """Поиск в JSON"""
        matches = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
                self._search_in_json_object(data, query, matches, path="root")
        except:
            pass
        return matches
    
    def _search_in_json_object(self, obj, query: str, matches: List, path: str = "", depth: int = 0):
        """Рекурсивный поиск в JSON"""
        if depth > 10:
            return
            
        if isinstance(obj, dict):
            for key, value in obj.items():
                str_value = json.dumps(value, ensure_ascii=False)
                if query.lower() in str(key).lower() or query.lower() in str_value.lower():
                    matches.append({
                        "line": 0,
                        "content": f"{path}.{key}: {str_value}",
                        "file": path
                    })
                self._search_in_json_object(value, query, matches, f"{path}.{key}", depth + 1)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._search_in_json_object(item, query, matches, f"{path}[{i}]", depth + 1)


class UserDatabase:
    """Класс для хранения информации о пользователях"""
    
    def __init__(self, db_file="users.db"):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self._create_tables()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                requests_count INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                query_type TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        self.conn.commit()
    
    def update_activity(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET last_activity = CURRENT_TIMESTAMP,
                requests_count = requests_count + 1
            WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()
    
    def add_to_history(self, user_id: int, query: str, query_type: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO history (user_id, query, query_type)
            VALUES (?, ?, ?)
        ''', (user_id, query, query_type))
        self.conn.commit()
    
    def get_user_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT query, query_type, timestamp 
            FROM history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "query": row[0],
                "type": row[1],
                "time": row[2]
            })
        return history
    
    def get_stats(self) -> Dict[str, int]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(requests_count) FROM users")
        total_requests = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM history")
        total_queries = cursor.fetchone()[0]
        
        return {
            "total_users": total_users,
            "total_requests": total_requests,
            "total_queries": total_queries
        }