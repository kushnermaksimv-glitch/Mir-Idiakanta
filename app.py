import os
import hashlib
import base64
import json
import random
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, jsonify

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024

# Секретный пароль администратора для удаления постов
ADMIN_PASSWORD = "KING_MAX"

MEMORY_POSTS = {}
ROOMS = {
    "b": "💬 Бред (Основной)",
    "games": "🎮 Игровой уголок",
    "code": "💻 Программирование",
    "cats": "🐱 Ламповые коты",
    "memes": "🔥 Мемы и пикчи",
    "pm": "✉️ Личные сообщения"
}

PINNED_MESSAGES = {
    "b": "Мир Идиаканта 2.0! Общайся, копи XP, зарабатывай Кото-Коины и покупай скины! 💬",
    "games": "Обсуждаем моды, сервера, Brawl Stars, Prism Launcher и создание игр! 🎮",
    "code": "Пишем код на Python, HTML/JS, создаём PyOS и фиксим баги вместе! 💻",
    "cats": "Комната для любителей пушистых! Украшай своего кота в магазине 🐱",
    "memes": "Сюда кидаем самые свежие и угарные пикчи 🔥",
    "pm": "🔒 Твой приватный ящик. Здесь отображаются только диалоги с твоим участием."
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
                
    return MEMORY_POSTS.get(room_id, [])

def load_all_private_posts():
    """Загружает все ЛС для фильтрации на стороне сервера/клиента"""
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM posts WHERE is_private = TRUE ORDER BY id DESC")
                posts = cursor.fetchall()
                cursor.close()
                conn.close()
                for p in posts:
                    if isinstance(p['reactions'], str):
                        try: p['reactions'] = json.loads(p['reactions'])
                        except: p['reactions'] = {"❤️": 0, "🔥": 0, "😂": 0, "💀": 0}
                return posts
        except Exception as e:
            if conn: conn.close()
    
    # Для памяти: собираем из всех комнат то, что помечено как ЛС
    all_pms = []
    for r in MEMORY_POSTS:
        for p in MEMORY_POSTS[r]:
            if p.get("is_private"):
                all_pms.append(p)
    all_pms.sort(key=lambda x: x["id"], reverse=True)
    return all_pms

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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мир Идиаканта 2.0 — {{ room_title }}</title>
    <style>
        [data-theme="dark"] {
            --bg-main: #0f0f12; --bg-card: #16161f; --bg-header: #1a1a26; --bg-input: #111116;
            --text-main: #f0f0f5; --text-muted: #62627a; --border: #232334; --accent: #ff9800; --accent-light: #ffb74d;
            --bg-private: #211330; --border-private: #7b1fa2;
        }
        [data-theme="light"] {
            --bg-main: #f4f4f9; --bg-card: #ffffff; --bg-header: #ffffff; --bg-input: #edf0f5;
            --text-main: #1c1c24; --text-muted: #84849a; --border: #dcdce6; --accent: #e07b00; --accent-light: #ff9800;
            --bg-private: #f3e5f5; --border-private: #ba68c8;
        }

        * { box-sizing: border-box; transition: background 0.2s, color 0.2s; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background: var(--bg-main); color: var(--text-main); padding: 0; margin: 0; font-size: 15px;
        }
        .app-header {
            background: var(--bg-header); border-bottom: 2px solid var(--accent); padding: 12px 15px;
            display: flex; justify-content: space-between; align-items: center;
            position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        }
        .app-header h1 { margin: 0; font-size: 17px; color: var(--accent-light); }
        .header-btns { display: flex; gap: 8px; }
        .btn-toggle {
            background: var(--bg-input); border: 1px solid var(--border); color: var(--text-main);
            padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: bold;
        }
        .container { max-width: 600px; margin: 0 auto; padding: 12px; }
        
        .pinned-box {
            background: var(--bg-card); border-left: 4px solid var(--accent); padding: 10px;
            border-radius: 0 8px 8px 0; margin-bottom: 12px; font-size: 13px; border: 1px solid var(--border); border-left: 4px solid var(--accent);
        }

        .rooms-scroll { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 12px; }
        .room-chip {
            background: var(--bg-card); color: var(--text-muted); text-decoration: none; padding: 8px 14px;
            border-radius: 20px; font-size: 13px; white-space: nowrap; border: 1px solid var(--border);
        }
        .room-chip.active { color: #121212; background: linear-gradient(135deg, #ffb74d, #ff9800); border-color: #ff9800; font-weight: bold; }

        /* Игровой профиль */
        .profile-card {
            background: var(--bg-input); border: 1px solid var(--border); padding: 10px; border-radius: 8px; margin-bottom: 10px;
            display: flex; align-items: center; gap: 12px;
        }
        .stats-block { font-size: 12px; display: flex; flex-direction: column; gap: 2px; }
        .coin-count { color: #ffd54f; font-weight: bold; }
        .xp-count { color: #64b5f6; font-weight: bold; }

        /* Кот-Маркет */
        .market-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 8px; }
        .market-item {
            background: var(--bg-input); border: 1px solid var(--border); padding: 8px; border-radius: 6px; text-align: center; font-size: 12px;
        }
        .btn-buy { background: #4caf50; border: none; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; margin-top: 4px; }

        .post-form { background: var(--bg-card); padding: 14px; border-radius: 12px; margin-bottom: 15px; border: 1px solid var(--border); }
        .pm-selector {
            background: rgba(123, 31, 162, 0.15); border: 1px solid var(--border-private); padding: 8px; border-radius: 6px; margin-bottom: 8px;
            font-size: 13px; display: flex; align-items: center; justify-content: space-between; color: #ba68c8; font-weight: bold;
        }

        .nickname-input { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg-input); color: #81c784; font-weight: bold; margin-bottom: 8px; }
        textarea { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg-input); color: var(--text-main); font-size: 14px; resize: none; }
        
        .btn-submit { width: 100%; padding: 12px; background: linear-gradient(135deg, #ffb74d, #ff9800); border: none; color: #121212; font-weight: bold; border-radius: 6px; cursor: pointer; }
        
        /* Карточки постов */
        .post-card { background: var(--bg-card); padding: 14px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 10px; position: relative; }
        .post-card.private-messages { background: var(--bg-private) !important; border-color: var(--border-private) !important; }
        .post-card.gold-skin { background: linear-gradient(135deg, #2c2205, #141002) !important; border-color: #ffd54f !important; box-shadow: 0 0 10px rgba(255,213,79,0.2); }
        
        .post-header-layout { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
        .avatar-container { position: relative; width: 40px; height: 40px; }
        .avatar-img { width: 100%; height: 100%; border-radius: 50%; background: #2a2a2a; }
        .decor-item { position: absolute; top: -5px; right: -5px; font-size: 16px; }
        .decor-glasses { position: absolute; top: 12px; left: 6px; font-size: 16px; width: 28px; text-align: center; }

        .post-meta-info { flex-grow: 1; display: flex; flex-direction: column; font-size: 12px; }
        .author-badge { color: #81c784; font-weight: bold; }
        .level-badge { background: #333; color: #64b5f6; font-size: 10px; padding: 1px 4px; border-radius: 3px; margin-left: 4px; }
        .room-badge { background: var(--bg-input); color: var(--accent-light); padding: 1px 4px; border-radius: 4px; font-size: 10px; width: fit-content; }
        .post-id-date { color: var(--text-muted); font-size: 11px; text-align: right; }
        
        .post-text { font-size: 14.5px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
        .reply-link { color: var(--accent); text-decoration: none; font-weight: bold; }

        .post-footer-layout { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; border-top: 1px solid var(--border); padding-top: 6px; }
        .reactions-bar { display: flex; gap: 4px; }
        .btn-react { background: var(--bg-input); border: 1px solid var(--border); border-radius: 5px; padding: 3px 6px; font-size: 11px; cursor: pointer; color: var(--text-main); }
        .btn-reply, .btn-pm, .btn-admin-del { background: none; border: none; color: #26a69a; cursor: pointer; font-size: 12px; font-weight: bold; }
        .btn-pm { color: #ba68c8; }
        .btn-admin-del { color: #ff5252; margin-left: 10px; }
        
        .post-image-wrapper { margin-top: 8px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border); }
        .post-img { width: 100%; max-height: 300px; object-fit: contain; display: block; }
    </style>
</head>
<body>

    <div class="app-header">
        <h1>Мир Идиаканта 2.0</h1>
        <div class="header-btns">
            <button class="btn-toggle" onclick="toggleTheme()">🌗 Тема</button>
            <button class="btn-toggle" onclick="toggleSettings()">⚙️ Меню</button>
        </div>
    </div>
    
    <div class="container">
        
        {% if pinned_msg %}
        <div class="pinned-box">
            📌 <b>Закреплено:</b> {{ pinned_msg }}
        </div>
        {% endif %}

        <div id="settingsPanel" style="background: var(--bg-card); border: 1px solid var(--border); padding: 12px; border-radius: 10px; margin-bottom: 12px; display: none;">
            <h3 style="margin: 0 0 8px 0; font-size: 14px; color: var(--accent-light);">🎒 Твой Кото-Профиль:</h3>
            <div class="profile-card">
                <div class="stats-block">
                    <div>Уровень: <span id="profLvl" style="font-weight:bold; color:#64b5f6;">1</span></div>
                    <div>Опыт: <span id="profXp" class="xp-count">0</span> XP</div>
                    <div>Баланс: <span id="profCoins" class="coin-count">0</span> 💰 Кото-Коинов</div>
                </div>
            </div>

            <h3 style="margin: 8px 0 4px 0; font-size: 14px; color: #4caf50;">🛒 Кот-Маркет:</h3>
            <div class="market-grid">
                <div class="market-item">
                    <span>👓 Крутые Очки</span><br><strong class="coin-count">50 💰</strong><br>
                    <button class="btn-buy" onclick="buyItem('glasses', 50)">Купить</button>
                </div>
                <div class="market-item">
                    <span>🎩 Цилиндр</span><br><strong class="coin-count">100 💰</strong><br>
                    <button class="btn-buy" onclick="buyItem('hat', 100)">Купить</button>
                </div>
                <div class="market-item">
                    <span>🎭 Маска SCP-035</span><br><strong class="coin-count">200 💰</strong><br>
                    <button class="btn-buy" onclick="buyItem('mask', 200)">Купить</button>
                </div>
                <div class="market-item">
                    <span>✨ Золотая Карточка</span><br><strong class="coin-count">400 💰</strong><br>
                    <button class="btn-buy" onclick="buyItem('gold', 400)">Купить</button>
                </div>
            </div>

            <h3 style="margin: 12px 0 6px 0; font-size: 14px; color: var(--text-muted);">Размер шрифта:</h3>
            <select id="settingFontSize" onchange="applySettings()" style="width:100%; background:var(--bg-input); color:var(--text-main); border:1px solid var(--border); padding:6px; border-radius:4px;">
                <option value="14px">Мелкий</option>
                <option value="15px" selected>Обычный</option>
                <option value="17px">Крупный</option>
            </select>
        </div>

        <div class="rooms-scroll">
            {% for r_id, r_name in rooms.items() %}
                <a href="/room/{{ r_id }}" id="room-link-{{ r_id }}" class="room-chip {% if r_id == current_room %}active{% endif %}">
                    {{ r_name }}
                </a>
            {% endfor %}
        </div>
        
        <form class="post-form" id="chatForm" onsubmit="sendPostViaAjax(event)">
            <div id="pmIndicator" class="pm-selector" style="display: none;">
                <span>🔒 Личное сообщение для: <span id="pmTarget" style="color:#e040fb;">Ник</span></span>
                <button type="button" style="background:none; border:none; color:#ff5252; cursor:pointer; font-weight:bold;" onclick="disablePM()">❌ Отмена</button>
            </div>

            <input type="hidden" id="is_private" name="is_private" value="{% if current_room == 'pm' %}1{% else %}0{% endif %}">
            <input type="hidden" id="recipient" name="recipient" value="">

            <div style="margin-bottom: 8px;">
                <input type="text" id="nickname" name="nickname" class="nickname-input" placeholder="🕶️ Твой никнейм (или Аноним)" maxlength="20">
            </div>

            {% if current_room == 'pm' %}
            <div style="margin-bottom: 8px;" id="recipientFieldBox">
                <input type="text" id="direct_recipient" name="direct_recipient" class="nickname-input" style="color:#e040fb; border-color:var(--border-private);" placeholder="👤 Кому отправить ЛС? (Введите точный ник)" maxlength="20">
            </div>
            {% endif %}

            <div style="margin-bottom: 8px;">
                <textarea id="message_text" name="text" rows="3" placeholder="Напиши сообщение..." required></textarea>
            </div>
            <div style="margin-bottom: 8px;">
                <div class="file-input-wrapper">
                    <span class="btn-file" id="file-label">🖼️ Прикрепить фото</span>
                    <input type="file" id="image_file" accept="image/*" onchange="updateFileLabel()">
                </div>
            </div>
            <button type="submit" class="btn-submit">Отправить сообщение (+15XP, +5💰)</button>
        </form>

        <div class="posts-list" id="postsList">
            {% for post in posts %}
            <div class="post-card {% if post.is_private %}private-messages{% endif %}" data-post-id="{{ post.id }}" id="post-{{ post.id }}" data-author="{{ post.author }}">
                <div class="post-header-layout">
                    <div class="avatar-container">
                        <img class="avatar-img" src="https://api.dicebear.com/7.x/bottts-neutral/svg?seed={{ post.author | urlencode }}&backgroundColor=b6e3f4">
                    </div>
                    <div class="post-meta-info">
                        <div>
                            <span class="author-badge">{{ post.author }}</span>
                            <span class="level-badge">Lvl 1</span>
                        </div>
                        <span class="room-badge">
                            {% if post.is_private %}🔒 ЛС для: {{ post.recipient }}{% else %}{{ current_room_name }}{% endif %}
                        </span>
                    </div>
                    <div class="post-id-date">
                        <div>№{{ post.id }}</div>
                        <div>{{ post.date }}</div>
                    </div>
                </div>
                
                <div class="post-text">{{ post.text }}</div>
                
                {% if post.image_url %}
                    <div class="post-image-wrapper">
                        <a href="{{ post.image_url }}" target="_blank"><img class="post-img" src="{{ post.image_url }}"></a>
                    </div>
                {% endif %}
                
                <div class="post-footer-layout">
                    <div class="reactions-bar">
                        {% for emoji, count in post.reactions.items() %}
                        <button type="button" class="btn-react" onclick="addReaction('{{ post.id }}', '{{ emoji }}')">
                            <span>{{ emoji }}</span> <span id="react-count-{{ post.id }}-{{ emoji }}">{{ count }}</span>
                        </button>
                        {% endfor %}
                    </div>
                    <div>
                        <button type="button" class="btn-pm" onclick="enablePM('{{ post.author }}')">🔒 Ответить в ЛС</button>
                        <button type="button" class="btn-reply" onclick="replyTo('{{ post.id }}')">↩ Ответить</button>
                        <button type="button" class="btn-admin-del" id="del-btn-{{ post.id }}" style="display:none;" onclick="deletePost('{{ post.id }}')">🗑️ Удалить</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const currentRoom = "{{ current_room }}";
        let lastKnownPostId = {% if posts %}{{ posts[0].id }}{% else %}0{% endif %};
        
        let myProfile = JSON.parse(localStorage.getItem('koto_profile') || '{"xp":0,"coins":20,"lvl":1,"items":[]}');

        window.onload = function() {
            if (!localStorage.getItem('koto_profile')) { saveProfile(); }
            updateProfileUI();

            const savedNick = localStorage.getItem('user_nick');
            if (savedNick) { 
                document.getElementById('nickname').value = savedNick;
                checkAdminStatus(savedNick);
            }

            document.getElementById('nickname').oninput = function() {
                localStorage.setItem('user_nick', this.value);
                checkAdminStatus(this.value);
            };

            applySettings();
            formatRepliesInDOM();
            applyPurchasedSkins();
            setInterval(checkUpdates, 3000);
        }

        function checkAdminStatus(nick) {
            const isKing = (nick === "{{ admin_pwd }}");
            document.querySelectorAll(".btn-admin-del").forEach(b => b.style.display = isKing ? "inline-block" : "none");
        }

        function saveProfile() { localStorage.setItem('koto_profile', JSON.stringify(myProfile)); }
        
        function updateProfileUI() {
            document.getElementById('profLvl').innerText = myProfile.lvl;
            document.getElementById('profXp').innerText = myProfile.xp;
            document.getElementById('profCoins').innerText = myProfile.coins;
        }

        function buyItem(itemId, cost) {
            if (myProfile.coins < cost) { alert("Недостаточно Кото-Коинов!"); return; }
            if (myProfile.items.includes(itemId)) { alert("Этот предмет уже куплен!"); return; }
            myProfile.coins -= cost;
            myProfile.items.push(itemId);
            saveProfile(); updateProfileUI(); applyPurchasedSkins();
            alert("Куплено!");
        }

        function applyPurchasedSkins() {
            const myNick = localStorage.getItem('user_nick') || '';
            if(!myNick) return;
            document.querySelectorAll(".post-card").forEach(card => {
                if(card.getAttribute("data-author") === myNick) {
                    const avBox = card.querySelector(".avatar-container");
                    if (myProfile.items.includes('glasses') && !avBox.querySelector(".decor-glasses")) {
                        avBox.innerHTML += '<div class="decor-glasses">👓</div>';
                    }
                    if (myProfile.items.includes('hat') && !avBox.querySelector(".decor-hat")) {
                        avBox.innerHTML += '<div class="decor-item decor-hat">🎩</div>';
                    }
                    if (myProfile.items.includes('mask') && !avBox.querySelector(".decor-mask")) {
                        avBox.innerHTML += '<div class="decor-item decor-mask">🎭</div>';
                    }
                    if (myProfile.items.includes('gold')) { card.classList.add("gold-skin"); }
                    
                    card.querySelector(".level-badge").innerText = `Lvl ${myProfile.lvl}`;
                }
            });
        }

        function enablePM(targetNick) {
            if (currentRoom === 'pm') {
                document.getElementById("direct_recipient").value = targetNick;
            } else {
                document.getElementById("is_private").value = "1";
                document.getElementById("recipient").value = targetNick;
                document.getElementById("pmTarget").innerText = targetNick;
                document.getElementById("pmIndicator").style.display = "flex";
            }
            document.getElementById("message_text").placeholder = `Личное сообщение для ${targetNick}...`;
        }

        function disablePM() {
            document.getElementById("is_private").value = "0";
            document.getElementById("recipient").value = "";
            document.getElementById("pmIndicator").style.display = "none";
            document.getElementById("message_text").placeholder = "Напиши сообщение...";
        }

        function checkLvlUp() {
            let nextLvlXp = myProfile.lvl * 150;
            if (myProfile.xp >= nextLvlXp) {
                myProfile.xp -= nextLvlXp;
                myProfile.lvl += 1;
                alert(`🚀 Уровень повышен! Теперь ты Lvl ${myProfile.lvl}!`);
            }
        }

        function toggleTheme() {
            const curr = document.documentElement.getAttribute('data-theme');
            const next = curr === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
        }

        function toggleSettings() {
            const p = document.getElementById('settingsPanel');
            p.style.display = p.style.display === 'block' ? 'none' : 'block';
        }

        function applySettings() {
            const size = document.getElementById('settingFontSize').value;
            document.querySelectorAll('.post-text').forEach(el => el.style.fontSize = size);
        }

        function updateFileLabel() {
            const f = document.getElementById('image_file');
            const l = document.getElementById('file-label');
            if (f.files.length > 0) { l.innerText = "✅ Фото выбрано"; }
        }

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
            }
        }

        function replyTo(postId) {
            const textarea = document.getElementById('message_text');
            textarea.value = `>> №${postId} ` + textarea.value;
            textarea.focus();
        }

        async function deletePost(postId) {
            if(!confirm("Удалить пост?")) return;
            try {
                const res = await fetch(`/api/delete/${postId}`, { method: 'POST' });
                const d = await res.json();
                if(d.success) { document.getElementById(`post-${postId}`).remove(); }
            } catch(e){}
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
                        let w = img.width, h = img.height;
                        if (w > MAX_WIDTH) { h *= MAX_WIDTH / w; w = MAX_WIDTH; }
                        canvas.width = w; canvas.height = h;
                        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
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

            const formData = new FormData();
            formData.append('text', textEl.value);
            formData.append('nickname', nickEl.value);

            let isPrivate = document.getElementById("is_private").value;
            let rcpt = document.getElementById("recipient").value;

            // Если сидим в комнате PM, берем получателя из текстового поля
            if (currentRoom === 'pm') {
                isPrivate = "1";
                rcpt = document.getElementById("direct_recipient").value.strip || document.getElementById("direct_recipient").value;
                if(!rcpt) { alert("Укажите ник получателя личного сообщения!"); return; }
            }

            formData.append('is_private', isPrivate);
            formData.append('recipient', rcpt);

            if (fileEl.files.length > 0) {
                const comp = await processImage(fileEl.files[0]);
                formData.append('image_base64', comp);
            }

            textEl.value = ''; fileEl.value = ''; disablePM(); updateFileLabel();
            if(document.getElementById("direct_recipient")) document.getElementById("direct_recipient").value = '';

            try {
                await fetch(`/create/${currentRoom}`, { method: 'POST', body: formData });
                myProfile.xp += 15; myProfile.coins += 5;
                checkLvlUp(); saveProfile(); updateProfileUI();
                checkUpdates();
            } catch (e) { console.error(e); }
        }

        async function checkUpdates() {
            try {
                const response = await fetch('/api/get_latest_ids');
                const latestIds = await response.json();
                const latestInCurrent = latestIds[currentRoom] || 0;
                if (latestInCurrent > lastKnownPostId) { fetchNewPostsForCurrentRoom(); }
            } catch (e) {}
        }

        async function fetchNewPostsForCurrentRoom() {
            try {
                const response = await fetch(`/api/get_posts/${currentRoom}?user=${encodeURIComponent(localStorage.getItem('user_nick') || '')}`);
                const posts = await response.json();
                const postsList = document.getElementById('postsList');
                const newPosts = posts.filter(p => p.id > lastKnownPostId);
                const myNick = localStorage.getItem('user_nick') || '';
                
                if (newPosts.length > 0) {
                    newPosts.forEach(post => {
                        const card = document.createElement('div');
                        card.className = `post-card ${post.is_private ? 'private-messages' : ''}`;
                        card.id = `post-${post.id}`;
                        card.setAttribute('data-post-id', post.id);
                        card.setAttribute('data-author', post.author);
                        
                        let imgHtml = post.image_url ? `<div class="post-image-wrapper"><a href="${post.image_url}" target="_blank"><img class="post-img" src="${post.image_url}"></a></div>` : '';
                        let reactHtml = '';
                        for (const em in post.reactions) {
                            reactHtml += `<button type="button" class="btn-react" onclick="addReaction('${post.id}', '${em}')"><span>${em}</span> <span id="react-count-${post.id}-${em}">${post.reactions[em]}</span></button>`;
                        }

                        card.innerHTML = `
                            <div class="post-header-layout">
                                <div class="avatar-container"><img class="avatar-img" src="https://api.dicebear.com/7.x/bottts-neutral/svg?seed=${encodeURIComponent(post.author)}&backgroundColor=b6e3f4"></div>
                                <div class="post-meta-info">
                                    <div><span class="author-badge">${post.author}</span><span class="level-badge">Lvl 1</span></div>
                                    <span class="room-badge">${post.is_private ? '🔒 ЛС для: ' + post.recipient : 'Текущая комната'}</span>
                                </div>
                                <div class="post-id-date"><div>№${post.id}</div><div>${post.date}</div></div>
                            </div>
                            <div class="post-text">${post.text}</div>
                            ${imgHtml}
                            <div class="post-footer-layout">
                                <div class="reactions-bar">${reactHtml}</div>
                                <div>
                                    <button type="button" class="btn-pm" onclick="enablePM('${post.author}')">🔒 Ответить в ЛС</button>
                                    <button type="button" class="btn-reply" onclick="replyTo('${post.id}')">↩ Ответить</button>
                                    <button type="button" class="btn-admin-del" id="del-btn-${post.id}" style="display:none;" onclick="deletePost('${post.id}')">🗑️ Удалить</button>
                                </div>
                            </div>
                        `;
                        postsList.insertBefore(card, postsList.firstChild);
                    });

                    lastKnownPostId = posts[0].id;
                    formatRepliesInDOM(); applyPurchasedSkins(); checkAdminStatus(myNick);
                }
            } catch (e) {}
        }

        async function addReaction(postId, emoji) {
            try {
                const r = await fetch(`/api/react/${postId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ emoji: emoji })
                });
                const d = await r.json();
                if(d.success) { document.getElementById(`react-count-${postId}-${emoji}`).innerText = d.new_count; }
            } catch(e){}
        }
    </script>
</body>
</html>
"""

@app.route("/api/get_latest_ids")
def api_get_latest_ids():
    ids = {}
    for r_id in ROOMS:
        if r_id == "pm":
            posts = load_all_private_posts()
        else:
            posts = load_posts(r_id)
        ids[r_id] = posts[0]["id"] if posts else 0
    return jsonify(ids)

@app.route("/api/get_posts/<room_id>")
def api_get_posts(room_id):
    if room_id not in ROOMS: return jsonify([])
    user_nick = request.args.get("user", "").strip()
    
    if room_id == "pm":
        all_pms = load_all_private_posts()
        # Фильтруем приватные посты на сервере: только отправленные юзером или предназначенные ему
        filtered = [p for p in all_pms if p["author"] == user_nick or p["recipient"] == user_nick]
        return jsonify(filtered)
        
    return jsonify(load_posts(room_id))

@app.route("/api/delete/<int:post_id>", methods=["POST"])
def api_delete_post(post_id):
    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM posts WHERE id = %s", (post_id,))
                conn.commit()
                cursor.close()
                conn.close()
                return jsonify({"success": True})
        except Exception as e:
            if conn: conn.close()
    else:
        for r in MEMORY_POSTS:
            MEMORY_POSTS[r] = [p for p in MEMORY_POSTS[r] if p["id"] != post_id]
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/api/react/<int:post_id>", methods=["POST"])
def api_react(post_id):
    emoji = (request.json or {}).get("emoji")
    if emoji not in ["❤️", "🔥", "😂", "💀"]: return jsonify({"success": False})

    if PSYCOPG2_AVAILABLE:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT reactions FROM posts WHERE id = %s", (post_id,))
                row = cursor.fetchone()
                if row:
                    reactions = json.loads(row["reactions"])
                    reactions[emoji] = reactions.get(emoji, 0) + 1
                    cursor.execute("UPDATE posts SET reactions = %s WHERE id = %s", (json.dumps(reactions), post_id))
                    conn.commit()
                    return jsonify({"success": True, "new_count": reactions[emoji]})
        except Exception as e:
            if conn: conn.close()
    return jsonify({"success": False})

@app.route("/")
def index(): return redirect("/room/b")

@app.route("/room/<room_id>")
def view_room(room_id):
    if room_id not in ROOMS: return redirect("/")
    
    user_nick = request.args.get("user", "").strip() # Если передано в URL
    
    if room_id == "pm":
        all_pms = load_all_private_posts()
        # В шаблоне первоначальный рендеринг тоже фильтрует (хотя основной упор идет на JS-обновление)
        posts = all_pms # Фронтенд дополнительно отфильтрует по localStorage
    else:
        posts = load_posts(room_id)
        
    return render_template_string(
        HTML_TEMPLATE, posts=posts, rooms=ROOMS, current_room=room_id, 
        room_title=ROOMS[room_id], current_room_name=ROOMS[room_id].split()[-1],
        pinned_msg=PINNED_MESSAGES.get(room_id, ""), admin_pwd=ADMIN_PASSWORD
    )

@app.route("/create/<room_id>", methods=["POST"])
def create_post(room_id):
    if room_id not in ROOMS: return redirect("/")
    text = request.form.get("text", "").strip()
    nickname = request.form.get("nickname", "").strip()
    image_data_uri = request.form.get("image_base64", "").strip() or None
    
    is_private = request.form.get("is_private") == "1" or room_id == "pm"
    recipient = request.form.get("recipient", "").strip()

    if text:
        if not nickname:
            user_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or "127.0.0.1"
            user_id = hashlib.md5(user_ip.encode()).hexdigest()[:4].upper()
            author_name = f"Аноним ## {user_id}"
        else: author_name = nickname
        
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        # Если пишем прямо в комнате ЛС, перезаписываем целевую комнату на специальный тег pm
        target_room = "pm" if is_private else room_id
        save_post(target_room, author_name, text, image_data_uri, current_date, is_private, recipient)
        
    return redirect(f"/room/{room_id}")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
