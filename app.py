import os
import hashlib
import base64
import json
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, jsonify

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

MEMORY_POSTS = {}
ROOMS = {
    "b": "💬 Бред (Основной)",
    "games": "🎮 Игровой уголок",
    "code": "💻 Программирование",
    "cats": "🐱 Ламповые коты",
    "memes": "🔥 Мемы и пикчи",
    "secret": "🔒 Секретная зона"
}

# Дефолтные закреплённые сообщения для комнат
PINNED_MESSAGES = {
    "b": "Добро пожаловать в основной зал Мира Идиаканта! Будьте как дома 💬",
    "games": "Здесь обсуждаем моды, сервера, Brawl Stars, Prism Launcher и создание игр! 🎮",
    "code": "Пишем код на Python, HTML/JS, делаем PyOS и фиксим баги вместе! 💻",
    "cats": "Комната для любителей пушистых! Выкладывайте котиков в очках и масках 🐱",
    "memes": "Сюда кидаем самые свежие и угарные пикчи 🔥",
    "secret": "Секретный бункер. Вход только для своих 🔒"
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
                # Создаём таблицу с поддержкой лайков (хранятся в JSON строке)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS posts (
                        id SERIAL PRIMARY KEY,
                        room TEXT NOT NULL DEFAULT 'b',
                        author TEXT NOT NULL,
                        text TEXT NOT NULL,
                        image_url TEXT,
                        date TEXT NOT NULL,
                        reactions TEXT DEFAULT '{}'
                    )
                """)
                conn.commit()
                cursor.close()
                conn.close()
                print("--- БАЗА ДАННЫХ SUPABASE УСПЕШНО ИНИЦИАЛИЗИРОВАНА ---")
        except Exception as e:
            print(f"Ошибка инициализации базы: {e}")
            if conn: conn.close()

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
                
                # Обработка реакций из базы данных
                for p in posts:
                    if not p.get('reactions'):
                        p['reactions'] = {"❤️": 0, "🔥": 0, "😂": 0, "💀": 0}
                    elif isinstance(p['reactions'], str):
                        try:
                            p['reactions'] = json.loads(p['reactions'])
                        except:
                            p['reactions'] = {"❤️": 0, "🔥": 0, "😂": 0, "💀": 0}
                return posts
        except Exception as e:
            print(f"Ошибка чтения базы: {e}")
            if conn: conn.close()
                
    return MEMORY_POSTS.get(room_id, [])

def save_post(room_id, author, text, image_data, date_str):
    default_reactions = json.dumps({"❤️": 0, "🔥": 0, "😂": 0, "💀": 0})
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO posts (room, author, text, image_url, date, reactions) VALUES (%s, %s, %s, %s, %s, %s)",
                    (room_id, author, text, image_data, date_str, default_reactions)
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
        "image_url": image_data, "date": date_str, "reactions": {"❤️": 0, "🔥": 0, "😂": 0, "💀": 0}
    }
    posts.insert(0, new_post)
    MEMORY_POSTS[room_id] = posts

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мир Идиаканта — {{ room_title }}</title>
    <style>
        /* Переменные для легкой смены тем оформления (Тёмная / Светлая) */
        [data-theme="dark"] {
            --bg-main: #121212; --bg-card: #1e1e1e; --bg-header: #1f1f1f; --bg-input: #151515;
            --text-main: #e5e5e5; --text-muted: #777; --border: #2d2d2d; --accent: #ff9800; --accent-light: #ffb74d;
        }
        [data-theme="light"] {
            --bg-main: #f5f5f7; --bg-card: #ffffff; --bg-header: #ffffff; --bg-input: #f0f0f2;
            --text-main: #1d1d1f; --text-muted: #86868b; --border: #e2e2e7; --accent: #e07b00; --accent-light: #ff9800;
        }

        * { box-sizing: border-box; transition: background 0.3s, color 0.3s, border-color 0.3s; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background: var(--bg-main); color: var(--text-main); padding: 0; margin: 0; font-size: 15px;
        }
        .app-header {
            background: var(--bg-header); border-bottom: 2px solid var(--accent); padding: 15px;
            display: flex; justify-content: space-between; align-items: center;
            position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
        .app-header h1 { margin: 0; font-size: 18px; color: var(--accent-light); }
        .header-btns { display: flex; gap: 8px; }
        .btn-toggle {
            background: var(--bg-input); border: 1px solid var(--border); color: var(--text-main);
            padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 14px;
        }
        .container { max-width: 600px; margin: 0 auto; padding: 15px; }
        
        /* Закреплённое сообщение (Анкор) */
        .pinned-box {
            background: var(--bg-card); border-left: 4px solid var(--accent); padding: 10px 14px;
            border-radius: 0 8px 8px 0; margin-bottom: 12px; font-size: 13px; border-top: 1px solid var(--border);
            border-right: 1px solid var(--border); border-bottom: 1px solid var(--border);
        }
        .pinned-title { font-weight: bold; color: var(--accent-light); margin-bottom: 3px; display: flex; justify-content: space-between; cursor: pointer; }

        .rooms-scroll { display: flex; gap: 10px; overflow-x: auto; padding: 5px 0 12px 0; margin-bottom: 15px; }
        .rooms-scroll::-webkit-scrollbar { height: 4px; }
        .rooms-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
        .room-chip {
            background: var(--bg-card); color: var(--text-muted); text-decoration: none; padding: 10px 16px;
            border-radius: 25px; font-size: 14px; white-space: nowrap; border: 1px solid var(--border); position: relative;
        }
        .room-chip.active { color: #121212; background: linear-gradient(135deg, #ffb74d, #ff9800); border-color: #ff9800; font-weight: bold; }
        
        @keyframes pulse-red {
            0% { box-shadow: 0 0 5px #ff5252; border-color: #ff5252; }
            50% { box-shadow: 0 0 15px #ff1744; border-color: #ff1744; background: rgba(255,23,68,0.1); }
            100% { box-shadow: 0 0 5px #ff5252; border-color: #ff5252; }
        }
        .room-chip.has-new { animation: pulse-red 1.5s infinite; font-weight: bold; color: #ff5252; }

        .settings-panel {
            background: var(--bg-card); border: 1px solid var(--accent); padding: 15px; 
            border-radius: 12px; margin-bottom: 15px; display: none;
        }
        .settings-panel h3 { margin-top: 0; color: var(--accent-light); font-size: 16px; }
        .setting-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .setting-row select { background: var(--bg-input); color: var(--text-main); border: 1px solid var(--border); padding: 6px; border-radius: 4px; }

        .post-form { background: var(--bg-card); padding: 16px; border-radius: 14px; margin-bottom: 20px; border: 1px solid var(--border); }
        .input-group { margin-bottom: 12px; }
        .nickname-input {
            width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border);
            background: var(--bg-input); color: #81c784; font-weight: bold; font-size: 15px;
        }
        textarea { 
            width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border); 
            background: var(--bg-input); color: var(--text-main); font-size: 15px; resize: none;
        }
        
        .file-input-wrapper { position: relative; overflow: hidden; display: inline-block; width: 100%; }
        .btn-file {
            border: 1px dashed var(--border); color: var(--text-muted); background-color: var(--bg-input);
            padding: 12px; border-radius: 8px; font-size: 14px; font-weight: bold; display: block; text-align: center; cursor: pointer;
        }
        .file-input-wrapper input[type=file] { font-size: 100px; position: absolute; left: 0; top: 0; opacity: 0; cursor: pointer; }
        .btn-submit { 
            width: 100%; padding: 14px; background: linear-gradient(135deg, #ffb74d, #ff9800); 
            border: none; color: #121212; font-weight: bold; font-size: 16px; border-radius: 8px; cursor: pointer; margin-top: 10px;
        }
        
        /* Карточки постов */
        .post-card { background: var(--bg-card); padding: 16px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 12px; position: relative; }
        .post-card.highlight-reply { animation: flash-orange 2s ease-out; }
        @keyframes flash-orange {
            0% { background: rgba(255,152,0,0.3); border-color: #ff9800; }
            100% { background: var(--bg-card); border-color: var(--border); }
        }

        .post-header-layout { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .avatar-img { width: 36px; height: 36px; border-radius: 50%; background: #2a2a2a; border: 1px solid var(--border); }
        .post-meta-info { flex-grow: 1; display: flex; flex-direction: column; font-size: 12px; }
        .author-badge { color: #81c784; font-weight: bold; font-size: 14px; }
        .room-badge { background: var(--bg-input); color: var(--accent-light); padding: 1px 5px; border-radius: 4px; font-size: 10px; width: fit-content; margin-top: 2px; }
        .post-id-date { color: var(--text-muted); font-size: 11px; text-align: right; }
        
        /* Ссылки на ответы */
        .reply-link { color: #ff9800; text-decoration: none; font-weight: bold; background: rgba(255,152,0,0.1); padding: 2px 5px; border-radius: 4px; }
        .reply-link:hover { text-decoration: underline; background: rgba(255,152,0,0.2); }
        .post-text { font-size: 15px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; color: var(--text-main); }
        
        /* Реакции и Футер */
        .post-footer-layout { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; border-top: 1px solid var(--border); padding-top: 8px; }
        .reactions-bar { display: flex; gap: 6px; }
        .btn-react {
            background: var(--bg-input); border: 1px solid var(--border); border-radius: 6px;
            padding: 4px 8px; font-size: 12px; cursor: pointer; color: var(--text-main); display: flex; align-items: center; gap: 4px;
        }
        .btn-react:hover { border-color: var(--accent); background: var(--bg-card); }
        .btn-reply { background: none; border: none; color: #26a69a; cursor: pointer; font-size: 13px; font-weight: bold; padding: 4px 8px; }
        
        .post-image-wrapper { margin-top: 12px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
        .post-img { width: 100%; max-height: 380px; object-fit: contain; display: block; }

        /* Всплывающие Push-уведомления внутри сайта */
        .notification-toast {
            position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #1f1f1f, #2d2d2d);
            border-left: 5px solid #ff1744; color: #fff; padding: 15px 20px; border-radius: 8px; z-index: 1000;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5); display: flex; flex-direction: column; gap: 4px;
            max-width: 320px; animation: slide-in 0.3s ease-out; cursor: pointer; border-top: 1px solid #444;
        }
        @keyframes slide-in { from { transform: translateY(100px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        .toast-title { font-weight: bold; color: #ff5252; font-size: 13px; }
        .toast-body { font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    </style>
</head>
<body>

    <div class="app-header">
        <h1>{{ room_title }}</h1>
        <div class="header-btns">
            <button class="btn-toggle" onclick="toggleTheme()">🌗 Тема</button>
            <button class="btn-toggle" onclick="toggleSettings()">⚙️ Меню</button>
        </div>
    </div>
    
    <div class="container">
        <!-- АНКОР: ЗАКРЕПЛЕННОЕ СООБЩЕНИЕ -->
        <div class="pinned-box">
            <div class="pinned-title" onclick="document.getElementById('pinnedText').style.display = document.getElementById('pinnedText').style.display === 'none' ? 'block' : 'none'">
                <span>📌 Закреплённое сообщение</span>
                <span style="font-size: 11px;">развернуть/свернуть</span>
            </div>
            <div id="pinnedText" style="margin-top: 5px; line-height: 1.4; color: var(--text-main);">
                {{ pinned_msg }}
            </div>
        </div>

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
                <textarea id="message_text" name="text" rows="3" placeholder="Напиши сообщение в этот чат... Используй @никнейм для упоминания" required></textarea>
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
            <div class="post-card" data-post-id="{{ post.id }}" id="post-{{ post.id }}">
                <div class="post-header-layout">
                    <!-- Робот-генератор кошачьих аватарок на базе Dicebear -->
                    <img class="avatar-img" src="https://api.dicebear.com/7.x/bottts-neutral/svg?seed={{ post.author | urlencode }}&backgroundColor=b6e3f4">
                    <div class="post-meta-info">
                        <span class="author-badge">{{ post.author }}</span>
                        <span class="room-badge">{{ current_room_name }}</span>
                    </div>
                    <div class="post-id-date">
                        <div>№{{ post.id }}</div>
                        <div style="margin-top:2px;">{{ post.date }}</div>
                    </div>
                </div>
                
                <div class="post-text">{{ post.text }}</div>
                
                {% if post.image_url %}
                    <div class="post-image-wrapper">
                        <a href="{{ post.image_url }}" target="_blank">
                            <img class="post-img" src="{{ post.image_url }}">
                        </a>
                    </div>
                {% endif %}
                
                <div class="post-footer-layout">
                    <!-- Панель реакций/лайков -->
                    <div class="reactions-bar">
                        {% for emoji, count in post.reactions.items() %}
                        <button type="button" class="btn-react" onclick="addReaction('{{ post.id }}', '{{ emoji }}')">
                            <span>{{ emoji }}</span> <span id="react-count-{{ post.id }}-{{ emoji }}">{{ count }}</span>
                        </button>
                        {% endfor %}
                    </div>
                    <button type="button" class="btn-reply" onclick="replyTo('{{ post.id }}', '{{ post.author }}')">↩ Ответить</button>
                </div>
            </div>
            {% else %}
            <p id="empty-state" style="text-align:center; color:var(--text-muted);">Тут пока пусто... Начни общение первым!</p>
            {% endfor %}
        </div>
    </div>

    <!-- Звуки -->
    <audio id="notifSound" src="https://assets.mixkit.co/active_storage/sfx/2357/2357-84.wav" preload="auto"></audio>
    <audio id="mentionSound" src="https://assets.mixkit.co/active_storage/sfx/911/911-84.wav" preload="auto"></audio>

    <div id="toastContainer"></div>

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
            const savedTheme = localStorage.getItem('cfg_theme') || 'dark';
            
            document.getElementById('settingFontSize').value = savedFontSize;
            document.getElementById('settingSound').value = savedSound;
            document.documentElement.setAttribute('data-theme', savedTheme);
            
            applySettings();
            formatRepliesInDOM();

            setInterval(checkUpdates, 3000);
        }

        function toggleTheme() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('cfg_theme', newTheme);
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

        function updateFileLabel() {
            const fileInput = document.getElementById('image_file');
            const label = document.getElementById('file-label');
            if (fileInput.files.length > 0) {
                let name = fileInput.files[0].name;
                label.innerText = `✅ Выбрано: ${name.length > 20 ? name.substring(0,20) + '...' : name}`;
                label.style.borderColor = '#ff9800'; label.style.color = '#ffb74d';
            } else {
                label.innerText = "🖼️ Прикрепить фото (до 5 МБ)";
                label.style.borderColor = 'var(--border)'; label.style.color = 'var(--text-muted)';
            }
        }

        // Превращает текстовые упоминания ">> №12" в кликабельные ссылки со скроллом
        function formatRepliesInDOM() {
            document.querySelectorAll('.post-text').forEach(el => {
                el.innerHTML = el.innerHTML.replace(/>&gt;\s*№\s*(\d+)/g, function(match, id) {
                    return `<a href="#post-${id}" class="reply-link" onclick="highlightTargetPost(event, '${id}')">${match}</a>`;
                });
            });
        }

        function highlightTargetPost(event, id) {
            const target = document.getElementById(`post-${id}`);
            if (target) {
                event.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                target.classList.remove('highlight-reply');
                void target.offsetWidth; // Триггер перезапуска анимации
                target.classList.add('highlight-reply');
            }
        }

        function replyTo(postId, author) {
            const textarea = document.getElementById('message_text');
            textarea.value = `>> №${postId} ` + textarea.value;
            textarea.focus();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        async function addReaction(postId, emoji) {
            try {
                const response = await fetch(`/api/react/${postId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ emoji: emoji })
                });
                const resData = await response.json();
                if (resData.success) {
                    document.getElementById(`react-count-${postId}-${emoji}`).innerText = resData.new_count;
                }
            } catch(e) { console.error(e); }
        }

        function showNotification(title, text, roomId) {
            if (localStorage.getItem('cfg_sound') !== 'off') {
                document.getElementById('mentionSound').play().catch(()=>{});
            }
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = 'notification-toast';
            toast.innerHTML = `<div class="toast-title">${title}</div><div class="toast-body">${text}</div>`;
            toast.onclick = () => { window.location.href = `/room/${roomId}`; };
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 5000);
        }

        function processImage(file) {
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = function (event) {
                    const img = new Image();
                    img.src = event.target.result;
                    img.onload = function () {
                        const canvas = document.createElement('canvas');
                        const MAX_WIDTH = 1000;
                        let width = img.width, height = img.height;
                        if (width > MAX_WIDTH) { height *= MAX_WIDTH / width; width = MAX_WIDTH; }
                        canvas.width = width; canvas.height = height;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, width, height);
                        resolve(canvas.toDataURL('image/jpeg', 0.7));
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

            if (fileEl.files.length > 0) {
                const compressedBase64 = await processImage(fileEl.files[0]);
                formData.append('image_base64', compressedBase64);
            }

            textEl.value = ''; fileEl.value = ''; updateFileLabel();

            try {
                await fetch(`/create/${currentRoom}`, { method: 'POST', body: formData });
                checkUpdates();
            } catch (e) { console.error(e); }
        }

        async function checkUpdates() {
            try {
                const response = await fetch('/api/get_latest_ids');
                const latestIds = await response.json();
                
                const latestInCurrent = latestIds[currentRoom] || 0;
                if (latestInCurrent > lastKnownPostId) { fetchNewPostsForCurrentRoom(); }

                const myNick = localStorage.getItem('user_nick') || '';

                for (const roomId in latestIds) {
                    if (roomId !== currentRoom) {
                        const lastSeen = roomLastSeen[roomId] || 0;
                        const chip = document.getElementById(`room-link-${roomId}`);
                        if (chip) {
                            if (latestIds[roomId] > lastSeen) { 
                                chip.classList.add('has-new'); 
                                // Проверяем на упоминания в других комнатах
                                checkMentionsInBackground(roomId, lastSeen, myNick);
                            } else { 
                                chip.classList.remove('has-new'); 
                            }
                        }
                    }
                }
            } catch (e) { console.error(e); }
        }

        async function checkMentionsInBackground(roomId, lastSeen, myNick) {
            try {
                const response = await fetch(`/api/get_posts/${roomId}`);
                const posts = await response.json();
                const newPosts = posts.filter(p => p.id > lastSeen);
                
                newPosts.forEach(post => {
                    // Уведомление если упомянули ник или ответили на пост
                    if (myNick && (post.text.includes(`@${myNick}`) || post.text.includes(`(${myNick})`))) {
                        showNotification(`🔔 Упоминание в комнате ${roomId}!`, `${post.author}: ${post.text}`, roomId);
                    }
                });
                
                // Обновляем, чтоб не спамить уведомлениями повторно
                if(newPosts.length > 0) {
                    roomLastSeen[roomId] = newPosts[0].id;
                    localStorage.setItem('room_last_seen', JSON.stringify(roomLastSeen));
                }
            } catch(e){}
        }

        async function fetchNewPostsForCurrentRoom() {
            try {
                const response = await fetch(`/api/get_posts/${currentRoom}`);
                const posts = await response.json();
                
                const postsList = document.getElementById('postsList');
                const emptyState = document.getElementById('empty-state');
                if (emptyState) emptyState.remove();

                const newPosts = posts.filter(p => p.id > lastKnownPostId);
                const myNick = localStorage.getItem('user_nick') || '';
                
                if (newPosts.length > 0) {
                    let hasAlerted = false;
                    const currentFontSize = localStorage.getItem('cfg_font_size') || '15px';

                    newPosts.forEach(post => {
                        // Если упомянули в текущей открытой комнате
                        if (myNick && (post.text.includes(`@${myNick}`) || post.text.includes(`(${myNick})`))) {
                            showNotification(`🔔 Вас упомянули!`, `${post.author}: ${post.text}`, currentRoom);
                            hasAlerted = true;
                        }

                        const postCard = document.createElement('div');
                        postCard.className = 'post-card';
                        postCard.id = `post-${post.id}`;
                        postCard.setAttribute('data-post-id', post.id);
                        
                        let imgHtml = '';
                        if (post.image_url) {
                            imgHtml = `<div class="post-image-wrapper"><a href="${post.image_url}" target="_blank"><img class="post-img" src="${post.image_url}"></a></div>`;
                        }

                        let reactionHtml = '';
                        for (const emoji in post.reactions) {
                            reactionHtml += `
                                <button type="button" class="btn-react" onclick="addReaction('${post.id}', '${emoji}')">
                                    <span>${emoji}</span> <span id="react-count-${post.id}-${emoji}">${post.reactions[emoji]}</span>
                                </button>`;
                        }

                        postCard.innerHTML = `
                            <div class="post-header-layout">
                                <img class="avatar-img" src="https://api.dicebear.com/7.x/bottts-neutral/svg?seed=${encodeURIComponent(post.author)}&backgroundColor=b6e3f4">
                                <div class="post-meta-info">
                                    <span class="author-badge">${post.author}</span>
                                    <span class="room-badge">${currentRoomName}</span>
                                </div>
                                <div class="post-id-date">
                                    <div>№${post.id}</div>
                                    <div style="margin-top:2px;">${post.date}</div>
                                </div>
                            </div>
                            <div class="post-text" style="font-size: ${currentFontSize}">${post.text}</div>
                            ${imgHtml}
                            <div class="post-footer-layout">
                                <div class="reactions-bar">${reactionHtml}</div>
                                <button type="button" class="btn-reply" onclick="replyTo('${post.id}', '${post.author}')">↩ Ответить</button>
                            </div>
                        `;
                        postsList.insertBefore(postCard, postsList.firstChild);
                    });

                    if (!hasAlerted && localStorage.getItem('cfg_sound') !== 'off') {
                        document.getElementById('notifSound').play().catch(()=>{});
                    }

                    lastKnownPostId = newPosts[0].id;
                    roomLastSeen[currentRoom] = lastKnownPostId;
                    localStorage.setItem('room_last_seen', JSON.stringify(roomLastSeen));
                    formatRepliesInDOM();
                }
            } catch (e) { console.error(e); }
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
    if room_id not in ROOMS: return jsonify([])
    return jsonify(load_posts(room_id))

@app.route("/api/react/<int:post_id>", methods=["POST"])
def api_react(post_id):
    data = request.json or {}
    emoji = data.get("emoji")
    if not emoji or emoji not in ["❤️", "🔥", "😂", "💀"]:
        return jsonify({"success": False})

    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT reactions FROM posts WHERE id = %s", (post_id,))
                row = cursor.fetchone()
                if row:
                    try: reactions = json.loads(row["reactions"])
                    except: reactions = {"❤️": 0, "🔥": 0, "😂": 0, "💀": 0}
                    
                    reactions[emoji] = reactions.get(emoji, 0) + 1
                    cursor.execute("UPDATE posts SET reactions = %s WHERE id = %s", (json.dumps(reactions), post_id))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    return jsonify({"success": True, "new_count": reactions[emoji]})
        except Exception as e:
            print(f"Ошибка реакций в БД: {e}")
            if conn: conn.close()
    else:
        for room in MEMORY_POSTS:
            for post in MEMORY_POSTS[room]:
                if post["id"] == post_id:
                    post["reactions"][emoji] += 1
                    return jsonify({"success": True, "new_count": post["reactions"][emoji]})
                    
    return jsonify({"success": False})

@app.route("/")
def index():
    return redirect("/room/b")

@app.route("/room/<room_id>")
def view_room(room_id):
    if room_id not in ROOMS: return redirect("/")
    posts = load_posts(room_id)
    return render_template_string(
        HTML_TEMPLATE, posts=posts, rooms=ROOMS, current_room=room_id, 
        room_title=ROOMS[room_id], current_room_name=ROOMS[room_id].split()[-1],
        pinned_msg=PINNED_MESSAGES.get(room_id, "")
    )

@app.route("/create/<room_id>", methods=["POST"])
def create_post(room_id):
    if room_id not in ROOMS: return redirect("/")
    
    text = request.form.get("text", "").strip()
    nickname = request.form.get("nickname", "").strip()
    image_data_uri = request.form.get("image_base64", "").strip()
    if not image_data_uri: image_data_uri = None

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
