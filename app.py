import os
from datetime import datetime
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)

# Храним посты прямо в памяти сервера
POSTS_STORAGE = [
    {
        "id": 1,
        "author": "Аноним #1",
        "text": "Добро пожаловать в Мир Идиаканта! Теперь у каждого автора есть своё имя с ID.",
        "image_url": "https://images.prodia.xyz/8f772418-4a6c-48be-88be-9b34a15a0c02.png",
        "date": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мир Идиаканта — Имиджборда</title>
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
        .subtitle { text-align: center; color: #81c784; font-size: 14px; margin-bottom: 20px; }
        
        form { 
            background: rgba(45, 45, 45, 0.85); 
            padding: 15px; 
            border-radius: 8px; 
            margin-bottom: 25px; 
            border: 1px solid #ffca28;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
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
        .submit-btn:hover { background: #ff6f00; }
        
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
        <div class="subtitle">※ Анонимный уголок тепла и ламповости ※</div>
        
        <form method="POST" action="/create">
            <textarea name="text" rows="4" placeholder="Напиши что-нибудь в бред..." required></textarea>
            
            <div class="img-input-container">
                <input type="url" id="image_url" name="image_url" placeholder="Ссылка на картинку (https://...)">
                <button type="button" class="paste-btn" onclick="pasteFromClipboard()">📋 Вставить</button>
            </div>
            
            <button type="submit" class="submit-btn">Отправить пост</button>
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
            {% endfor %}
        </div>
    </div>

    <script>
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
    return render_template_string(HTML_TEMPLATE, posts=reversed(POSTS_STORAGE))

@app.route("/create", methods=["POST"])
def create():
    text = request.form.get("text", "").strip()
    image_url = request.form.get("image_url", "").strip()
    
    if text:
        valid_url = image_url if image_url.startswith(("http://", "https://")) else None
        next_id = len(POSTS_STORAGE) + 1
        
        new_post = {
            "id": next_id,
            "author": f"Аноним #{next_id}",  # Формируем имя с ID поста
            "text": text,
            "image_url": valid_url,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        POSTS_STORAGE.append(new_post)
        
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
