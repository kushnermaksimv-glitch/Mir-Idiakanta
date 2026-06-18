import os
import hashlib
from datetime import datetime
from flask import Flask, render_template_string, request, redirect

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

app = Flask(__name__)

# Резервное хранилище прямо в оперативной памяти сервера (если база отключится)
MEMORY_POSTS = {
    "b": [], "games": [], "code": [], "cats": [], "memes": [], "secret": []
}

ROOMS = {
    "b": "💬 Бред (Основной)",
    "games": "🎮 Игровой уголок",
    "code": "💻 Программирование",
    "cats": "🐱 Ламповые коты",
    "memes": "🔥 Мемы и пикчи",
    "secret": "🔒 Секретная зона"
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
                        date TEXT NOT NULL
                    )
                """)
                conn.commit()
                cursor.close()
                conn.close()
                print("--- БАЗА ДАННЫХ SUPABASE УСПЕШНО ПОДКЛЮЧЕНА И ИНИЦИАЛИЗИРОВАНА ---")
        except Exception as e:
            print(f"Предупреждение при инициализации базы: {e}. Используем оперативную память.")
            if conn:
                conn.close()

def load_posts(room_id):
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM posts WHERE room = %s ORDER BY id DESC", (room_id,))
                posts = cursor.fetchall()
                cursor.close()
                conn.close()
                return posts
        except Exception as e:
            print(f"Ошибка чтения базы: {e}. Переключаемся на память сервера.")
            if conn:
                conn.close()
                
    return MEMORY_POSTS.get(room_id, [])

def save_post(room_id, author, text, image_url, date_str):
    # 1. Пробуем сохранить в вечную базу Supabase
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
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
            print(f"Ошибка записи в базу данных: {e}. Сохраняем в память.")
            if conn:
                conn.close()

    # 2. Резервный вариант, если база упала
    posts = MEMORY_POSTS.get(room_id, [])
    new_id = len(posts) + 1
    new_post = {
        "id": new_id,
        "room": room_id,
        "author": author,
        "text": text,
        "image_url": image_url,
        "date": date_str
    }
    posts.insert(0, new_post)
    MEMORY_POSTS[room_id] = posts

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мир Идиаканта — {{ room_title }}</title>
    <style>
        * { box-sizing: border-box; transition: all 0.2s ease; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background: #121212; color: #e5e5e5; padding: 0; margin: 0; 
        }
        .app-header {
            background: #1f1f1f; border-bottom: 2px solid #ff9800; padding: 15px;
            text-align: center; position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 20px rgba(0,0,0,0.6);
        }
        .app-header h1 { margin: 0; font-size: 20px; color: #ffb74d; }
        .container { max-width: 600px; margin: 0 auto; padding: 15px; }
        .rooms-scroll { display: flex; gap: 10px; overflow-x: auto; padding: 5px 0 12px 0; margin-bottom: 15px; }
        .rooms-scroll::-webkit-scrollbar { height: 4px; }
        .rooms-scroll::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
        .room-chip {
            background: #1e1e1e; color: #a0a0a0; text-decoration: none; padding: 10px 16px;
            border-radius: 25px; font-size: 14px; white-space: nowrap; border: 1px solid #2d2d2d;
        }
        .room-chip.active { color: #121212; background: linear-gradient(135deg, #ffb74d, #ff9800); border-color: #ff9800; font-weight: bold; }
        .post-form { background: #1e1e1e; padding: 16px; border-radius: 14px; margin-bottom: 20px; border: 1px solid #2d2d2d; }
        .input-group { margin-bottom: 12px; }
        .nickname-input {
            width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #333;
            background: #151515; color: #81c784; font-weight: bold; font-size: 15px;
        }
        textarea { 
            width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #333; 
            background: #151515; color: #fff; font-size: 15px; resize: none;
        }
        .url-box { display: flex; gap: 8px; }
        .url-box input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #333; background: #151515; color: #fff; }
        .btn-paste { padding: 0 15px; background: #26a69a; border: none; color: white; border-radius: 8px; cursor: pointer; }
        .btn-submit { 
            width: 100%; padding: 14px; background: linear-gradient(135deg, #ffb74d, #ff9800); 
            border: none; color: #121212; font-weight: bold; font-size: 16px; border-radius: 8px; cursor: pointer; margin-top: 10px;
        }
        .post-card { background: #1e1e1e; padding: 16px; border-radius: 12px; border: 1px solid #2d2d2d; margin-bottom: 12px; }
        .post-meta { 
            font-size: 12px; color: #777; margin-bottom: 8px; display: flex; justify-content: space-between;
            align-items: center; border-bottom: 1px solid #2d2d2d; padding-bottom: 6px;
        }
        .author-badge { color: #81c784; font-weight: bold; }
        .room-badge { background: #333; color: #ffb74d; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px; }
        .post-text { font-size: 15px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; color: #f5f5f5; }
        .post-footer { margin-top: 10px; display: flex; justify-content: flex-end; }
        .btn-reply { background: none; border: none; color: #26a69a; cursor: pointer; font-size: 13px; font-weight: bold; padding: 4px 8px; }
        .post-image-wrapper { margin-top: 12px; border-radius: 8px; overflow: hidden; border: 1px solid #2d2d2d; }
        .post-img { width: 100%; max-height: 380px; object-fit: contain; display: block; }
    </style>
</head>
<body>
    <div class="app-header">
        <h1>{{ room_title }}</h1>
    </div>
    <div class="container">
        <div class="rooms-scroll">
            {% for r_id, r_name in rooms.items() %}
                <a href="/room/{{ r_id }}" class="room-chip {% if r_id == current_room %}active{% endif %}">
                    {{ r_name }}
                </a>
            {% endfor %}
        </div>
        
        <form class="post-form" method="POST" action="/create/{{ current_room }}" onsubmit="saveNick()">
            <div class="input-group">
                <input type="text" id="nickname" name="nickname" class="nickname-input" placeholder="🕶️ Твой никнейм (или Аноним)" maxlength="20">
            </div>
            <div class="input-group">
                <textarea id="message_text" name="text" rows="3" placeholder="Напиши сообщение в этот чат..." required></textarea>
            </div>
            <div class="input-group url-box">
                <input type="url" id="image_url" name="image_url" placeholder="🔗 Ссылка на картинку">
                <button type="button" class="btn-paste" onclick="pasteFromClipboard()">📋</button>
            </div>
            <button type="submit" class="btn-submit">Отправить сообщение</button>
        </form>

        <div class="posts-list">
            {% for post in posts %}
            <div class="post-card">
                <div class="post-meta">
                    <div>
                        <span class="author-badge">{{ post.author }}</span>
                        <span class="room-badge">{{ current_room_name }}</span>
                    </div>
                    <span>№{{ post.id }} • {{ post.date }}</span>
                </div>
                <div class="post-text">{{ post.text }}</div>
                {% if post.image_url %}
                    <div class="post-image-wrapper">
                        <a href="{{ post.image_url }}" target="_blank">
                            <img class="post-img" src="{{ post.image_url }}">
                        </a>
                    </div>
                {% endif %}
                <div class="post-footer">
                    <button type="button" class="btn-reply" onclick="replyTo('{{ post.id }}', '{{ post.author }}')">↩ Ответить</button>
                </div>
            </div>
            {% else %}
            <p style="text-align:center; color:#666;">Тут пока пусто... Начни общение первым!</p>
            {% endfor %}
        </div>
    </div>

    <script>
        window.onload = function() {
            const savedNick = localStorage.getItem('user_nick');
            if (savedNick) { document.getElementById('nickname').value = savedNick; }
        }
        function saveNick() {
            const nick = document.getElementById('nickname').value;
            localStorage.setItem('user_nick', nick);
        }
        function replyTo(postId, author) {
            const textarea = document.getElementById('message_text');
            textarea.value = `>> №${postId} (${author}): ` + textarea.value;
            textarea.focus();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
        async function pasteFromClipboard() {
            try {
                const text = await navigator.clipboard.readText();
                if (text.startsWith('http://') || text.startsWith('https://')) {
                    document.getElementById('image_url').value = text;
                }
            } catch (err) {}
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
        HTML_TEMPLATE, posts=posts, rooms=ROOMS, current_room=room_id, 
        room_title=ROOMS[room_id], current_room_name=ROOMS[room_id].split()[-1]
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
