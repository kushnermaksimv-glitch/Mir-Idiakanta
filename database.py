import os
import json
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

MEMORY_POSTS = {}
BANNED_IPS = set()  # Для локальной памяти, если нет базы данных

ROOMS = {
    "b": "💬 Бред (Основной)",
    "games": "🎮 Игровой уголок",
    "code": "💻 Программирование",
    "cats": "🐱 Ламповые коты",
    "memes": "🔥 Мемы и пикчи",
    "pm": "✉️ Личные сообщения"
}

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def init_db():
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Таблица постов с поддержкой скинов автора
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS posts (
                        id SERIAL PRIMARY KEY,
                        room TEXT NOT NULL DEFAULT 'b',
                        author TEXT NOT NULL,
                        text TEXT NOT NULL,
                        image_url TEXT,
                        date TEXT NOT NULL,
                        reactions TEXT DEFAULT '{}',
                        is_private BOOLEAN DEFAULT FALSE,
                        recipient TEXT DEFAULT '',
                        author_skins TEXT DEFAULT '[]'
                    )
                """)
                # Новая таблица для забаненных IP
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bans (
                        ip TEXT PRIMARY KEY,
                        reason TEXT,
                        date TEXT
                    )
                """)
                conn.commit()
                cursor.close()
                conn.close()
                print("--- БАЗА ДАННЫХ ИДИАКАНТА 3.0 УСПЕШНО ИНИЦИАЛИЗИРОВАНА ---")
        except Exception as e:
            print(f"Ошибка инициализации базы 3.0: {e}")
            if conn: conn.close()

def is_ip_banned(ip):
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM bans WHERE ip = %s", (ip,))
                banned = cursor.fetchone() is not None
                cursor.close()
                conn.close()
                return banned
        except Exception as e:
            print(f"Ошибка проверки бана: {e}")
            if conn: conn.close()
    return ip in BANNED_IPS

def ban_user_ip(ip, reason="Нарушение правил"):
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO bans (ip, reason, date) VALUES (%s, %s, %s) ON CONFLICT (ip) DO NOTHING", 
                               (ip, reason, datetime.now().strftime("%d.%m.%Y %H:%M")))
                conn.commit()
                cursor.close()
                conn.close()
                return
        except Exception as e:
            if conn: conn.close()
    BANNED_IPS.add(ip)

def clear_room_db(room_id):
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM posts WHERE room = %s", (room_id,))
                conn.commit()
                cursor.close()
                conn.close()
                return
        except Exception as e:
            if conn: conn.close()
    if room_id in MEMORY_POSTS:
        MEMORY_POSTS[room_id] = []

def load_posts(room_id, current_user=""):
    current_user = current_user.strip() if current_user else ""
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                if room_id == "pm":
                    if not current_user:
                        cursor.close()
                        conn.close()
                        return []
                    cursor.execute("""
                        SELECT * FROM posts 
                        WHERE room = 'pm' AND (author = %s OR recipient = %s) 
                        ORDER BY id DESC
                    """, (current_user, current_user))
                else:
                    cursor.execute("SELECT * FROM posts WHERE room = %s ORDER BY id DESC", (room_id,))
                
                posts = cursor.fetchall()
                cursor.close()
                conn.close()
                
                for p in posts:
                    if not p.get('reactions'):
                        p['reactions'] = {"❤️": 0, "🔥": 0, "😂": 0, "💀": 0}
                    elif isinstance(p['reactions'], str):
                        try: p['reactions'] = json.loads(p['reactions'])
                        except: p['reactions'] = {"❤️": 0, "🔥": 0, "😂": 0, "💀": 0}
                    
                    if not p.get('author_skins'):
                        p['author_skins'] = []
                    elif isinstance(p['author_skins'], str):
                        try: p['author_skins'] = json.loads(p['author_skins'])
                        except: p['author_skins'] = []
                return posts
        except Exception as e:
            print(f"Ошибка чтения базы: {e}")
            if conn: conn.close()
                
    all_posts = MEMORY_POSTS.get(room_id, [])
    if room_id == "pm":
        if not current_user: return []
        return [p for p in all_posts if p.get("author") == current_user or p.get("recipient") == current_user]
    return all_posts

def save_post(room_id, author, text, image_data, date_str, is_private=False, recipient="", skins_list=None):
    default_reactions = json.dumps({"❤️": 0, "🔥": 0, "😂": 0, "💀": 0})
    skins_json = json.dumps(skins_list if skins_list else [])
    
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO posts (room, author, text, image_url, date, reactions, is_private, recipient, author_skins) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (room_id, author, text, image_data, date_str, default_reactions, is_private, recipient, skins_json))
                conn.commit()
                cursor.close()
                conn.close()
                return
        except Exception as e:
            print(f"Ошибка записи в базу: {e}")
            if conn: conn.close()

    if room_id not in MEMORY_POSTS: MEMORY_POSTS[room_id] = []
    posts = MEMORY_POSTS[room_id]
    new_id = len(posts) + 1
    new_post = {
        "id": new_id, "room": room_id, "author": author, "text": text,
        "image_url": image_data, "date": date_str, "reactions": {"❤️": 0, "🔥": 0, "😂": 0, "💀": 0},
        "is_private": is_private, "recipient": recipient, "author_skins": skins_list if skins_list else []
    }
    posts.insert(0, new_post)
    MEMORY_POSTS[room_id] = posts
