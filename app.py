import os
import hashlib
import base64
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, jsonify

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

app = Flask(__name__)

# Максимальный размер запроса (с запасом для сжатых Base64 фото)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

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
                # Перестраховка: создаем таблицу, если её нет. Тип TEXT в Postgres вмещает до 1 ГБ текста.
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
            print(f"Ошибка инициализации базы: {e}.")
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
            print(f"Ошибка чтения базы: {e}")
            if conn:
                conn.close()
                
    return MEMORY_POSTS.get(room_id, [])

def save_post(room_id, author, text, image_data, date_str):
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO posts (room, author, text, image_url, date) VALUES (%s, %s, %s, %s, %s)",
                    (room_id, author, text, image_data, date_str)
                )
                conn.commit()
                cursor.close()
                conn.close()
                return
        except Exception as e:
            print(f"Ошибка записи в базу: {e}")
            if conn:
                conn.close()

    posts = MEMORY_POSTS.get(room_id, [])
    new_id = len(posts) + 1
    new_post = {
        "id": new_id,
        "room": room_id,
        "author": author,
        "text": text,
        "image_url": image_data,
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
        * { box-sizing: border-box; transition: background 0.2s, color 0.2s; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background: #121212; color: #e5e5e5; padding: 0; margin: 0; 
            font-size: 15px;
        }
        .app-header {
            background: #1f1f1f; border-bottom: 2px solid #ff9800; padding: 15px;
            display: flex; justify-content: space-between; align-items: center;
            position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 20px rgba(0,0,0,0.6);
        }
        .app-header h1 { margin: 0; font-size: 18px; color: #ffb74d; }
        .btn-settings-toggle {
            background: #333; border: 1px solid #444; color: #fff;
            padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 14px;
        }
        .container { max-width: 600px; margin: 0 auto; padding: 15px; }
        
        .rooms-scroll { display: flex; gap: 10px; overflow-x: auto; padding: 5px 0 12px 0; margin-bottom: 15px; }
        .rooms-scroll::-webkit-scrollbar { height: 4px; }
        .rooms-scroll::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
        .room-chip {
            background: #1e1e1e; color: #a0a0a0; text-decoration: none; padding: 10px 16px;
            border-radius: 25px; font-size: 14px; white-space: nowrap; border: 1px solid #2d2d2d;
            position: relative;
        }
        .room-chip.active { color: #121212; background: linear-gradient(135deg, #ffb74d, #ff9800); border-color: #ff9800; font-weight: bold; }
        
        @keyframes pulse-red {
            0% { box-shadow: 0 0 5px #ff5252; border-color: #ff5252; }
            50% { box-shadow: 0 0 15px #ff1744; border-color: #ff1744; background: #2c1313; color: #ff8a80; }
            100% { box-shadow: 0 0 5px #ff5252; border-color: #ff5252; }
        }
        .room-chip.has-new { animation: pulse-red 1.5s infinite; font-weight: bold; }

        .settings-panel {
            background: #1e1e1e; border: 1px solid #ff9800; padding: 15px; 
            border-radius: 12px; margin-bottom: 15px; display: none;
        }
        .settings-panel h3 { margin-top: 0; color: #ffb74d; font-size: 16px; }
        .setting-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .setting-row select { background: #333; color: #fff; border: 1px solid #555; padding: 6px; border-radius: 4px; }

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
        
        .file-input-wrapper { position: relative; overflow: hidden; display: inline-block; width: 100%; }
        .btn-file {
            border: 1px dashed #555; color: #b0b0b0; background-color: #151515;
            padding: 12px; border-radius: 8px; font-size: 14px; font-weight: bold;
            display: block; text-align: center; cursor: pointer;
        }
        .file-input-wrapper input[type=file] { font-size: 100px; position: absolute; left: 0; top: 0; opacity: 0; cursor: pointer; }

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
        <button class="btn-settings-toggle" onclick="toggleSettings()">⚙️ Настройки</button>
    </div>
    
    <div class="container">
        <div id="settingsPanel" class="settings-panel">
            <h3>⚙️ Персонализация чата</h3>
            <div class="setting-row">
                <label>Размер шрифта:</label>
                <select id="settingFontSize" onchange="applySettings()">
                    <option value="14px">Мелкий</option>
                    <option value="15px" selected>Обычный</option>
                    <option value="17px">Крупный</option>
                    <option value="19px">Гигантский</option>
                </select>
            </div>
            <div class="setting-row">
                <label>Звук уведомлений:</label>
                <select id="settingSound" onchange="applySettings()">
                    <option value="on">Включен 🔊</option>
                    <option value="off">Выключен 🔇</option>
                </select>
            </div>
        </div>

        <div class="rooms-scroll">
            {% for r_id, r_name in rooms.items() %}
                <a href="/room/{{ r_id }}" id="room-link-{{ r_id }}" class="room-chip {% if r_id == current_room %}active{% endif %}">
                    {{ r_name }}
                </a>
            {% endfor %}
        </div>
        
        <form class="post-form" id="chatForm" onsubmit="sendPostViaAjax(event)">
            <div class="input-group">
                <input type="text" id="nickname" name="nickname" class="nickname-input" placeholder="🕶️ Твой никнейм (или Аноним)" maxlength="20">
            </div>
            <div class="input-group">
                <textarea id="message_text" name="text" rows="3" placeholder="Напиши сообщение в этот чат..." required></textarea>
            </div>
            <div class="input-group">
                <div class="file-input-wrapper">
                    <span class="btn-file" id="file-label">🖼️ Прикрепить фото (до 5 МБ)</span>
                    <input type="file" id="image_file" accept="image/*" onchange="updateFileLabel()">
                </div>
            </div>
            <button type="submit" class="btn-submit">Отправить сообщение</button>
        </form>

        <div class="posts-list" id="postsList">
            {% for post in posts %}
            <div class="post-card" data-post-id="{{ post.id }}">
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
            <p id="empty-state" style="text-align:center; color:#666;">Тут пока пусто... Начни общение первым!</p>
            {% endfor %}
        </div>
    </div>

    <audio id="notifSound" src="https://assets.mixkit.co/active_storage/sfx/2357/2357-84.wav" preload="auto"></audio>

    <script>
        const currentRoom = "{{ current_room }}";
        const currentRoomName = "{{ current_room_name }}";
        let lastKnownPostId = {% if posts %}{{ posts[0].id }}{% else %}0{% endif %};
        
        let roomLastSeen = JSON.parse(localStorage.getItem('room_last_seen') || '{}');
        roomLastSeen[currentRoom] = lastKnownPostId;
        localStorage.setItem('room_last_seen', JSON.stringify(roomLastSeen));

        window.onload = function() {
            const savedNick = localStorage.getItem('user_nick');
            if (savedNick) { document.getElementById('nickname').value = savedNick; }
            
            const savedFontSize = localStorage.getItem('cfg_font_size') || '15px';
            const savedSound = localStorage.getItem('cfg_sound') || 'on';
            document.getElementById('settingFontSize').value = savedFontSize;
            document.getElementById('settingSound').value = savedSound;
            applySettings();

            setInterval(checkUpdates, 3000);
        }

        function updateFileLabel() {
            const fileInput = document.getElementById('image_file');
            const label = document.getElementById('file-label');
            if (fileInput.files.length > 0) {
                let name = fileInput.files[0].name;
                label.innerText = `✅ Выбрано: ${name.length > 20 ? name.substring(0,20) + '...' : name}`;
                label.style.borderColor = '#ff9800'; label.style.color = '#ffb74d';
            } else {
                label.innerText = "🖼️ Прикрепить фото (до 5 МБ)";
                label.style.borderColor = '#555'; label.style.color = '#b0b0b0';
            }
        }

        function toggleSettings() {
            const panel = document.getElementById('settingsPanel');
            panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
        }

        function applySettings() {
            const fontSize = document.getElementById('settingFontSize').value;
            localStorage.setItem('cfg_font_size', fontSize);
            localStorage.setItem('cfg_sound', document.getElementById('settingSound').value);
            document.querySelectorAll('.post-text').forEach(el => el.style.fontSize = fontSize);
        }

        function replyTo(postId, author) {
            const textarea = document.getElementById('message_text');
            textarea.value = `>> №${postId} (${author}): ` + textarea.value;
            textarea.focus();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        // УМНОЕ СЖАТИЕ КАРТИНКИ ПЕРЕД ОТПРАВКОЙ НА СЕРВЕР
        function processImage(file) {
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = function (event) {
                    const img = new Image();
                    img.src = event.target.result;
                    img.onload = function () {
                        const canvas = document.createElement('canvas');
                        const MAX_WIDTH = 1000; // Ограничиваем ширину картинки до 1000px
                        let width = img.width;
                        let height = img.height;

                        if (width > MAX_WIDTH) {
                            height *= MAX_WIDTH / width;
                            width = MAX_WIDTH;
                        }
                        canvas.width = width;
                        canvas.height = height;

                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, width, height);

                        // Сжимаем качество до 70% в формат JPEG (весит в 20 раз меньше оригинала!)
                        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
                        resolve(dataUrl);
                    };
                };
            });
        }

        async function sendPostViaAjax(event) {
            event.preventDefault();
            const textEl = document.getElementById('message_text');
            const fileEl = document.getElementById('image_file');
            const nickEl = document.getElementById('nickname');
            
            if(textEl.value.trim() === "") return;
            
            localStorage.setItem('user_nick', nickEl.value);

            const formData = new FormData();
            formData.append('text', textEl.value);
            formData.append('nickname', nickEl.value);

            // Если прикреплен файл, ждем его сжатия в Base64 текстовую строку
            if (fileEl.files.length > 0) {
                const compressedBase64 = await processImage(fileEl.files[0]);
                formData.append('image_base64', compressedBase64);
            }

            textEl.value = '';
            fileEl.value = '';
            updateFileLabel();

            try {
                await fetch(`/create/${currentRoom}`, { method: 'POST', body: formData });
                checkUpdates();
            } catch (e) { console.error("Ошибка отправки:", e); }
        }

        async function checkUpdates() {
            try {
                const response = await fetch('/api/get_latest_ids');
                const latestIds = await response.json();
                
                const latestInCurrent = latestIds[currentRoom] || 0;
                if (latestInCurrent > lastKnownPostId) { fetchNewPostsForCurrentRoom(); }

                for (const roomId in latestIds) {
                    if (roomId !== currentRoom) {
                        const lastSeen = roomLastSeen[roomId] || 0;
                        const chip = document.getElementById(`room-link-${roomId}`);
                        if (chip) {
                            if (latestIds[roomId] > lastSeen) { chip.classList.add('has-new'); } 
                            else { chip.classList.remove('has-new'); }
                        }
                    }
                }
            } catch (e) { console.error("Ошибка обновления", e); }
        }

        async function fetchNewPostsForCurrentRoom() {
            try {
                const response = await fetch(`/api/get_posts/${currentRoom}`);
                const posts = await response.json();
                
                const postsList = document.getElementById('postsList');
                const emptyState = document.getElementById('empty-state');
                if (emptyState) emptyState.remove();

                const newPosts = posts.filter(p => p.id > lastKnownPostId);
                
                if (newPosts.length > 0) {
                    if (localStorage.getItem('cfg_sound') !== 'off') {
                        document.getElementById('notifSound').play().catch(()=>{});
                    }

                    const currentFontSize = localStorage.getItem('cfg_font_size') || '15px';

                    newPosts.forEach(post => {
                        const postCard = document.createElement('div');
                        postCard.className = 'post-card';
                        postCard.setAttribute('data-post-id', post.id);
                        
                        let imgHtml = '';
                        if (post.image_url) {
                            imgHtml = `
                                <div class="post-image-wrapper">
                                    <a href="${post.image_url}" target="_blank">
                                        <img class="post-img" src="${post.image_url}">
                                    </a>
                                </div>`;
                        }

                        postCard.innerHTML = `
                            <div class="post-meta">
                                <div>
                                    <span class="author-badge">${post.author}</span>
                                    <span class="room-badge">${currentRoomName}</span>
                                </div>
                                <span>№${post.id} • ${post.date}</span>
                            </div>
                            <div class="post-text" style="font-size: ${currentFontSize}">${post.text}</div>
                            ${imgHtml}
                            <div class="post-footer">
                                <button type="button" class="btn-reply" onclick="replyTo('${post.id}', '${post.author}')">↩ Ответить</button>
                            </div>
                        `;
                        postsList.insertBefore(postCard, postsList.firstChild);
                    });

                    lastKnownPostId = newPosts[0].id;
                    roomLastSeen[currentRoom] = lastKnownPostId;
                    localStorage.setItem('room_last_seen', JSON.stringify(roomLastSeen));
                }
            } catch (e) { console.error("Ошибка загрузки новых постов:", e); }
        }
    </script>
</body>
</html>
"""

@app.route("/api/get_latest_ids")
def api_get_latest_ids():
    ids = {}
    for r_id in ROOMS:
        posts = load_posts(r_id)
        ids[r_id] = posts[0]["id"] if posts else 0
    return jsonify(ids)

@app.route("/api/get_posts/<room_id>")
def api_get_posts(room_id):
    if room_id not in ROOMS:
        return jsonify([])
    return jsonify(load_posts(room_id))

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
    nickname = request.form.get("nickname", "").strip()
    
    # Теперь мы принимаем уже готовую, сжатую на клиенте строку Base64
    image_data_uri = request.form.get("image_base64", "").strip()
    if not image_data_uri:
        image_data_uri = None

    if text:
        if not nickname:
            user_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or "127.0.0.1"
            user_id = hashlib.md5(user_ip.encode()).hexdigest()[:4].upper()
            author_name = f"Аноним ## {user_id}"
        else:
            author_name = nickname
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        save_post(room_id, author_name, text, image_data_uri, current_date)
        
    return redirect(f"/room/{room_id}")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
