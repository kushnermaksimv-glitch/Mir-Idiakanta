import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)
DB_FILE = "posts.json"

# Загрузка и сохранение постов
def load_posts():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_posts(posts):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

# HTML-шаблон (адаптирован под мобильные экраны)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Анонимная Борда</title>
    <style>
        body { font-family: sans-serif; background: #1e1e1e; color: #e0e0e0; padding: 10px; margin: 0; }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { text-align: center; color: #ff5722; font-size: 24px; }
        form { background: #2d2d2d; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        input, textarea { width: 100%; padding: 10px; margin-bottom: 10px; border-radius: 4px; border: 1px solid #444; background: #333; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #ff5722; border: none; color: white; font-weight: bold; border-radius: 4px; cursor: pointer; }
        .post { background: #2d2d2d; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #ff5722; }
        .post-header { font-size: 12px; color: #888; margin-bottom: 8px; }
        .post-text { font-size: 16px; white-space: pre-wrap; word-break: break-word; }
        .post-img { max-width: 100%; height: auto; margin-top: 10px; border-radius: 4px; display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Anons Board</h1>
        
        <form method="POST" action="/create">
            <textarea name="text" rows="3" placeholder="Текст сообщения (обязательно)..." required></textarea>
            <input type="url" name="image_url" placeholder="Ссылка на картинку (https://... - необязательно)">
            <button type="submit">Отправить в бред</button>
        </form>

        <div class="posts">
            {% for post in posts %}
            <div class="post">
                <div class="post-header">Аноним №{{ post.id }} • {{ post.date }}</div>
                <div class="post-text">{{ post.text }}</div>
                {% if post.image_url %}
                    <img class="post-img" src="{{ post.image_url }}" alt="Изображение">
                {% endif %}
            </div>
            {% else %}
            <p style="text-align:center; color:#888;">Пока нет ни одного поста. Будь первым!</p>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    posts = load_posts()
    return render_template_string(HTML_TEMPLATE, posts=reversed(posts))

@app.route("/create", methods=["POST"])
def create():
    text = request.form.get("text", "").strip()
    image_url = request.form.get("image_url", "").strip()
    
    if text:
        posts = load_posts()
        new_post = {
            "id": len(posts) + 1,
            "text": text,
            "image_url": image_url if image_url.startswith(("http://", "https://")) else None,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        posts.append(new_post)
        save_posts(posts)
        
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
