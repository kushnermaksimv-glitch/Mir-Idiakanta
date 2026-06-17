import os
import hashlib
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)

# Папка для локального сохранения (если Supabase отключится)
LOCAL_STORAGE_DIR = "rooms_data"
if not os.path.exists(LOCAL_STORAGE_DIR):
    os.makedirs(LOCAL_STORAGE_DIR)

# Список доступных чатов (комнат)
ROOMS = {
    "b": "Бред (Основной)",
    "games": "Игровой уголок",
    "code": "Программирование",
    "cats": "Ламповые коты"
}

# Проверка: подключена ли облачная база данных
def is_supabase_available():
    return os.environ.get("DATABASE_URL") is not None

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

# Создание таблиц в Supabase
def init_db():
    if is_supabase_available():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    room TEXT NOT NULL DEFAULT 'b',
                    author TEXT NOT NULL,
                    text TEXT NOT NULL,
                    image_url TEXT,
                    date TEXT NOT NULL
                )
            """)
            conn.commit()
            cursor.close()
            conn.close()
            print("--- БАЗА ДАННЫХ SUPABASE УСПЕШНО ИНИЦИАЛИЗИРОВАНА ---")
        except Exception as e:
            print(f"Ошибка при работе с Supabase: {e}. Переходим на файлы.")

# Чтение сообщений (из базы или файлов)
def load_posts(room_id):
    if is_supabase_available():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM posts WHERE room = %s ORDER BY id DESC", (room_id,))
            posts = cursor.fetchall()
            cursor.close()
            conn.close()
            return posts
        except Exception as e:
            print(f"Ошибка чтения Supabase: {e}. Читаем из файлов.")
    
    # Резервный файловый метод (сохранение в файлы-папки)
    file_path = os.path.join(LOCAL_STORAGE_DIR, f"{room_id}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Запись сообщений (в базу или файлы)
def save_post(room_id, author, text, image_url, date_str):
    if is_supabase_available():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO posts (room, author, text, image_url, date) VALUES (%s, %s, %s, %s, %s)",
                (room_id, author, text, image_url, date_str)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return
        except Exception as e:
            print(f"Ошибка записи в Supabase: {e}. Пишем в файлы.")
            
    # Резервный файловый метод
    posts = load_posts(room_id)
    new_id = len(posts) + 1
    new_post = {
        "id": new_id,
        "room": room_id,
        "author": author,
        "text": text,
        "image_url": image_url,
        "date": date_str
    }
    posts.insert(0, new_post) # Добавляем в начало списка
    
    file_path = os.path.join(LOCAL_STORAGE_DIR, f"{room_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мир Идиаканта — {{ room_title }}</title>
    <style>
        body { 
            font-family: 'Courier New', monospace, sans-serif; 
            background: linear-gradient(rgba(29, 29, 29, 0.85), rgba(29, 29, 29, 0.85)), 
                        url('https://images.prodia.xyz/8f772418-4a6c-48be-88be-9b34a15a0c02.png') no-repeat center center fixed;
            background-size: cover;
            color: #e0e0e0; 
            padding: 10px; 
            margin: 0; 
        }
        .container { max-width: 650px; margin: 0 auto; }
        h1 { text-align: center; color: #ffca28; font-size: 26px; text-shadow: 2px 2px 4px #000; margin-bottom: 5px; }
        
        /* Стили меню выбора чатов */
        .rooms-menu {
            display: flex;
            justify-content: center;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            background: rgba(40, 40, 40, 0.9);
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #444;
        }
        .room-link {
            color: #aaa;
            text-decoration: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 13px;
            background: #222;
            border: 1px solid #555;
        }
        .room-link.active {
            color: #fff;
            background: #ff8f00;
            border-color: #ffca28;
            font-weight: bold;
        }
        
        form { 
            background: rgba(45, 45, 45, 0.85); 
            padding: 15px; 
            border-radius: 8px; 
            margin-bottom: 25px; 
            border: 1px solid #ffca28;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        .nickname-input {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            border-radius: 4px;
            border: 1px solid #555;
            background: #111;
            color: #81c784;
            font-weight: bold;
            box-sizing: border-box;
        }
        textarea { 
            width: 100%; 
            padding: 10px; 
            margin-bottom: 10px; 
            border-radius: 4px; 
            border: 1px solid #555; 
            background: #222; 
            color: #fff; 
            box-sizing: border-box; 
            resize: vertical;
        }
        .img-input-container { display: flex; gap: 5px; margin-bottom: 15px; }
        .img-input-container input { 
            flex: 1; 
            padding: 10px; 
            border-radius: 4px; 
            border: 1px solid #555; 
            background: #222; 
            color: #fff; 
            font-size: 13px;
        }
        .paste-btn { 
            padding: 0 15px; 
            background: #4db6ac; 
            border: none; 
            color: white; 
            border-radius: 4px; 
            cursor: pointer; 
            font-weight: bold;
        }
        .submit-btn { 
            width: 100%; 
            padding: 12px; 
            background: #ff8f00; 
            border: none; 
            color: white; 
            font-weight: bold; 
            font-size: 16px;
            border-radius: 4px; 
            cursor: pointer; 
        }
        
        .post { 
            background: rgba(40, 40, 40, 0.9); 
            padding: 15px; 
            border-radius: 6px; 
            margin-bottom: 15px; 
            border-left: 5px solid #ff8f00; 
        }
        .post-header { font-size: 12px; color: #ffb74d; margin-bottom: 10px; border-bottom: 1px dashed #444; padding-bottom: 5px; }
        .post-author { color: #81c784; font-weight: bold; }
        .post-text { font-size: 15px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; color: #f5f5f5; }
        .post-img { max-width: 100%; max-height: 350px; object-fit: contain; margin-top: 12px; border-radius: 4px; display: block; border: 1px solid #555; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Мир Идиаканта</h1>
        
        <div class="rooms-menu">
            {% for r_id, r_name in rooms.items() %}
                <a href="/room/{{ r_id }}" class="room-link {% if r_id == current_room %}active{% endif %}">
                    {{ r_name }}
                </a>
            {% endfor %}
        </div>
        
        <form method="POST" action="/create/{{ current_room }}">
            <input type="text" id="nickname" name="nickname" class="nickname-input" placeholder="Твой ник (оставь пустым для Анонима)..." maxlength="20">
            <textarea name="text" rows="4" placeholder="Напиши что-нибудь в этот чат..." required></textarea>
            
            <div class="img-input-container">
                <input type="url" id="image_url" name="image_url" placeholder="Ссылка на картинку (https://...)">
                <button type="button" class="paste-btn" onclick="pasteFromClipboard()">📋 Вставить</button>
            </div>
            
            <button type="submit" class="submit-btn" onclick="saveNick()">Отправить в {{ room_title }}</button>
        </form>

        <div class="posts">
            {% for post in posts %}
            <div class="post">
                <div class="post-header">
                    <span class="post-author">{{ post.author }}</span> • №{{ post.id }} • {{ post.date }}
                </div>
                <div class="post-text">{{ post.text }}</div>
                {% if post.image_url %}
                    <a href="{{ post.image_url }}" target="_blank">
                        <img class="post-img" src="{{ post.image_url }}" alt="Изображение">
                    </a>
                {% endif %}
            </div>
            {% else %}
            <p style="text-align:center; color:#aaa;">В этом чате ещё нет сообщений. Напиши первое!</p>
            {% endfor %}
        </div>
    </div>

    <script>
        window.onload = function() {
            if (localStorage.getItem('user_nick')) {
                document.getElementById('nickname').value = localStorage.getItem('user_nick');
            }
        }

        function saveNick() {
            const nick = document.getElementById('nickname').value;
            localStorage.setItem('user_nick', nick);
        }

        async function pasteFromClipboard() {
            try {
                const text = await navigator.clipboard.readText();
                if (text.startsWith('http://') || text.startsWith('https://')) {
                    document.getElementById('image_url').value = text;
                } else {
                    alert('В буфере обмена нет ссылки!');
                }
            } catch (err) {
                alert('Разреши доступ к буферу.');
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return redirect("/room/b")

@app.route("/room/<room_id>")
def view_room(room_id):
    if room_id not in ROOMS:
        return redirect("/")
    
    posts = load_posts(room_id)
    return render_template_string(
        HTML_TEMPLATE, 
        posts=posts, 
        rooms=ROOMS, 
        current_room=room_id, 
        room_title=ROOMS[room_id]
    )

@app.route("/create/<room_id>", methods=["POST"])
def create_post(room_id):
    if room_id not in ROOMS:
        return redirect("/")
        
    text = request.form.get("text", "").strip()
    image_url = request.form.get("image_url", "").strip()
    nickname = request.form.get("nickname", "").strip()
    
    if text:
        valid_url = image_url if image_url.startswith(("http://", "https://")) else None
        
        if not nickname:
            user_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or "127.0.0.1"
            user_id = hashlib.md5(user_ip.encode()).hexdigest()[:4].upper()
            author_name = f"Аноним ## {user_id}"
        else:
            author_name = nickname
            
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        save_post(room_id, author_name, text, valid_url, current_date)
        
    return redirect(f"/room/{room_id}")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
