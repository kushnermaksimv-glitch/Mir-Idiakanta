import os
import hashlib
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, jsonify

# Импортируем всё необходимое из нашего нового модуля базы данных
from database import init_db, load_posts, save_post, ROOMS, MEMORY_POSTS, get_db_connection, PSYCOPG2_AVAILABLE

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024

ADMIN_PASSWORD = "KING_MAX"

PINNED_MESSAGES = {
    "b": "Мир Идиаканта 2.0! Общайся, копи XP, зарабатывай Кото-Коинов и покупай скины! 💬",
    "games": "Обсуждаем моды, сервера, Brawl Stars, Prism Launcher и создание игр! 🎮",
    "code": "Пишем код на Python, HTML/JS, создаём PyOS и фиксим баги вместе! 💻",
    "cats": "Комната для любителей пушистых! Украшай своего кота в магазине 🐱",
    "memes": "Сюда кидаем самые свежие и угарные пикчи 🔥",
    "pm": "🔒 Абсолютно приватный ящик. Серверная защита: твои ЛС видишь только ты и твой собеседник."
}

STICKERS = [
    {"emoji": "🐱🕶️", "name": "Крутой кот"},
    {"emoji": "🐱💻", "name": "Кот-кодер"},
    {"emoji": "🐱🔥", "name": "Эпик кот"},
    {"emoji": "🐱🍕", "name": "Жрущий кот"},
    {"emoji": "👑🐱", "name": "Царь-кот"},
    {"emoji": "👾", "name": "Стикер Игры"},
    {"emoji": "💥", "name": "Бум!"},
    {"emoji": "💀", "name": "Мертвец"}
]

@app.route("/api/get_latest_ids")
def api_get_latest_ids():
    user_nick = request.args.get("user", "").strip()
    ids = {}
    for r_id in ROOMS:
        posts = load_posts(r_id, current_user=user_nick)
        ids[r_id] = posts[0]["id"] if posts else 0
    return jsonify(ids)

@app.route("/api/get_posts/<room_id>")
def api_get_posts(room_id):
    if room_id not in ROOMS: return jsonify([])
    user_nick = request.args.get("user", "").strip()
    return jsonify(load_posts(room_id, current_user=user_nick))

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
    user_nick = request.args.get("user", "").strip()
    posts = load_posts(room_id, current_user=user_nick)
        
    # Теперь используем render_template, который автоматически ищет файлы в папке templates/
    return render_template(
        "index.html", posts=posts, rooms=ROOMS, current_room=room_id, 
        room_title=ROOMS[room_id], current_room_name=ROOMS[room_id].split()[-1],
        pinned_msg=PINNED_MESSAGES.get(room_id, ""), admin_pwd=ADMIN_PASSWORD, stickers=STICKERS
    )

@app.route("/create/<room_id>", methods=["POST"])
def create_post(room_id):
    if room_id not in ROOMS: return redirect("/")
    text = request.form.get("text", "").strip()
    nickname = request.form.get("nickname", "").strip()
    image_data_uri = request.form.get("image_base64", "").strip() or None
    
    is_private = request.form.get("is_private") == "1" or room_id == "pm"
    recipient = request.form.get("recipient", "").strip()

    if text or image_data_uri:
        if not nickname:
            user_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or "127.0.0.1"
            user_id = hashlib.md5(user_ip.encode()).hexdigest()[:4].upper()
            author_name = f"Аноним ## {user_id}"
        else: author_name = nickname
        
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        target_room = "pm" if is_private else room_id
        
        save_post(target_room, author_name, text, image_data_uri, current_date, is_private, recipient)
        
    return redirect(f"/room/{room_id}?user={nickname}")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
