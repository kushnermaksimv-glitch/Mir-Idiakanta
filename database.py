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
                        recipient TEXT DEFAULT ''
                    )
                """)
                conn.commit()
                cursor.close()
                conn.close()
                print("--- БАЗА ДАННЫХ ИДИАКАНТА ОБНОВЛЕНА ---")
        except Exception as e:
            print(f"Ошибка инициализации базы: {e}")
            if conn: conn.close()

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
                return posts
        except Exception as e:
            print(f"Ошибка чтения базы: {e}")
            if conn: conn.close()
                
    all_posts = MEMORY_POSTS.get(room_id, [])
    if room_id == "pm":
        if not current_user: return []
        return [p for p in all_posts if p.get("author") == current_user or p.get("recipient") == current_user]
    return all_posts

def save_post(room_id, author, text, image_data, date_str, is_private=False, recipient=""):
    default_reactions = json.dumps({"❤️": 0, "🔥": 0, "😂": 0, "💀": 0})
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO posts (room, author, text, image_url, date, reactions, is_private, recipient) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (room_id, author, text, image_data, date_str, default_reactions, is_private, recipient)
                )
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
        "is_private": is_private, "recipient": recipient
    }
    posts.insert(0, new_post)
    MEMORY_POSTS[room_id] = posts
