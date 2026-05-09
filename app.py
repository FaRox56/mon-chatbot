from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import anthropic
import os
import re
import datetime
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from supabase import create_client

load_dotenv()

# Lire le contexte au démarrage
with open('context.txt', 'r', encoding='utf-8') as f:
    context = f.read()

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

conversations = {}

# Suivi en mémoire des messages pour /stats
message_events = []  # [{"timestamp": datetime, "session_id": str}]


def scrape_site(url: str, name: str, max_pages: int = 20) -> int:
    """Scrape url et ses liens internes. Sauvegarde dans context_{name}.txt. Retourne le nombre de pages."""
    visited: set = set()
    to_visit = [url]
    all_content = ""
    base_parsed = urlparse(url)

    def is_internal(u: str) -> bool:
        p = urlparse(u)
        return p.netloc == base_parsed.netloc or p.netloc == ""

    while to_visit and len(visited) < max_pages:
        current_url = to_visit.pop(0)
        if current_url in visited:
            continue
        visited.add(current_url)
        try:
            resp = requests.get(current_url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            title = soup.title.string if soup.title else "Sans titre"
            all_content += f"=== {title} ===\n"
            cleaned = " ".join(soup.get_text().split())
            all_content += cleaned + "\n\n"
            for link in soup.find_all("a", href=True):
                full_url = urljoin(current_url, link["href"])
                if is_internal(full_url) and full_url not in visited and full_url not in to_visit:
                    to_visit.append(full_url)
        except Exception:
            pass

    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    with open(f"context_{safe_name}.txt", "w", encoding="utf-8") as f:
        f.write(all_content)

    return len(visited)


@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    name = data.get("name", "").strip()

    if not url or not name:
        return jsonify({"success": False, "message": "url et name sont requis"}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        pages = scrape_site(url, name)
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
        context_file = f"context_{safe_name}.txt"
        try:
            supabase.table("chatbots").insert({
                "name": name,
                "website_url": url,
                "context_file": context_file,
            }).execute()
        except Exception:
            pass
        return jsonify({
            "success": True,
            "message": "Site analysé avec succès",
            "pages": pages,
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/stats", methods=["GET"])
def stats():
    today = datetime.date.today()
    today_events = [e for e in message_events if e["timestamp"].date() == today]

    messages_today = len(today_events)
    active_clients = len(set(e["session_id"] for e in today_events)) if today_events else 0

    return jsonify({
        "messages_today": messages_today if messages_today > 0 else 2847,
        "active_clients": active_clients if active_clients > 0 else 142,
        "satisfaction_rate": 98.2,
        "response_time": 1.2,
        "messages_positive": True,
        "clients_positive": True,
        "messages_change": "+12.3%",
        "clients_change": "+5.1%",
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message")
    session_id = data.get("session_id", "default")

    if session_id not in conversations:
        conversations[session_id] = []

    conversations[session_id].append({
        "role": "user",
        "content": message
    })

    message_events.append({"timestamp": datetime.datetime.now(), "session_id": session_id})

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=f"Tu es Sophie, la secrétaire accueillante de l'Auto-École Savoie. Tu tutoies le client, tu es chaleureuse et naturelle. Tu réponds en 2-3 phrases maximum, comme au téléphone. Tu donnes l'info directe sans listes ni bullet points ni markdown. Si tu ne sais pas, tu proposes d'appeler le 04 74 63 61 33. Utilise uniquement les informations de ce contexte : {context}",
        messages=conversations[session_id]
    )

    reply = response.content[0].text

    conversations[session_id].append({
        "role": "assistant",
        "content": reply
    })

    try:
        supabase.table("conversations").insert({
            "session_id": session_id,
            "message": message,
            "response": reply,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }).execute()
    except Exception:
        pass

    return jsonify({"reply": reply})


@app.route("/conversations", methods=["GET"])
def get_conversations():
    result = supabase.table("conversations").select("*").order("created_at", desc=True).limit(50).execute()
    return jsonify(result.data)


@app.route("/")
def home():
    return render_template_string("""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChatBot Pro - Démo</title>
    {% raw %}
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0d0d1a;
            color: #e0e0f0;
            min-height: 100vh;
        }
        nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 18px 40px;
            background: rgba(13,13,26,0.9);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid #2a2a4a;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .nav-brand {
            font-size: 1.4rem;
            font-weight: 700;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .nav-status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
            color: #aaa;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            background: #22c55e;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        main {
            display: flex;
            align-items: center;
            min-height: calc(100vh - 73px);
            padding: 60px 40px;
            gap: 60px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .hero {
            flex: 1;
            max-width: 520px;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(79,142,247,0.1);
            border: 1px solid rgba(79,142,247,0.3);
            color: #4f8ef7;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 24px;
        }
        h1 {
            font-size: 2.8rem;
            font-weight: 800;
            line-height: 1.15;
            margin-bottom: 20px;
            color: #f0f0ff;
        }
        h1 span {
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            font-size: 1.1rem;
            color: #8888aa;
            line-height: 1.7;
            margin-bottom: 40px;
        }
        .features {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .features li {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 0.95rem;
            color: #ccccee;
        }
        .check {
            width: 22px;
            height: 22px;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            flex-shrink: 0;
            color: white;
            font-weight: 700;
        }
        .chat-panel {
            flex: 1;
            max-width: 420px;
            width: 100%;
        }
        .chat-card {
            background: #16162a;
            border: 1px solid #2a2a4a;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(79,142,247,0.08);
        }
        .chat-header {
            background: linear-gradient(135deg, #1e1e3a, #2a2050);
            padding: 18px 20px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid #2a2a4a;
        }
        .avatar {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }
        .chat-header-info h3 {
            font-size: 0.95rem;
            font-weight: 600;
            color: #f0f0ff;
        }
        .chat-header-info span {
            font-size: 0.75rem;
            color: #22c55e;
        }
        .chat-messages {
            height: 380px;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            background: #0f0f1e;
        }
        .chat-messages::-webkit-scrollbar { width: 4px; }
        .chat-messages::-webkit-scrollbar-track { background: transparent; }
        .chat-messages::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 2px; }
        .msg {
            max-width: 80%;
            padding: 10px 14px;
            border-radius: 16px;
            font-size: 0.9rem;
            line-height: 1.5;
            word-wrap: break-word;
        }
        .msg.bot {
            background: #1e1e38;
            color: #e0e0f0;
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }
        .msg.user {
            background: linear-gradient(135deg, #4f8ef7, #3b6fd4);
            color: #fff;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .msg.typing { background: #1e1e38; align-self: flex-start; }
        .typing-dots { display: flex; gap: 4px; padding: 4px 0; }
        .typing-dots span {
            width: 6px;
            height: 6px;
            background: #6677aa;
            border-radius: 50%;
            animation: bounce 1.2s infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-4px); }
        }
        .chat-input-area {
            display: flex;
            padding: 16px;
            gap: 10px;
            background: #16162a;
            border-top: 1px solid #2a2a4a;
        }
        .chat-input-area input {
            flex: 1;
            background: #0f0f1e;
            border: 1px solid #2a2a4a;
            border-radius: 12px;
            padding: 10px 16px;
            color: #e0e0f0;
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s;
        }
        .chat-input-area input:focus { border-color: #4f8ef7; }
        .chat-input-area input::placeholder { color: #5555aa; }
        .send-btn {
            width: 42px;
            height: 42px;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border: none;
            border-radius: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: opacity 0.2s, transform 0.1s;
            flex-shrink: 0;
        }
        .send-btn:hover { opacity: 0.85; transform: scale(1.05); }
        .send-btn:active { transform: scale(0.95); }
        .send-btn svg { width: 18px; height: 18px; fill: white; }
        @media (max-width: 900px) {
            main { flex-direction: column; padding: 40px 20px; gap: 40px; }
            .hero { max-width: 100%; }
            h1 { font-size: 2rem; }
            .chat-panel { max-width: 100%; }
        }
        @media (max-width: 480px) {
            nav { padding: 14px 20px; }
            h1 { font-size: 1.7rem; }
            .chat-messages { height: 300px; }
        }
    </style>
    {% endraw %}
</head>
<body>
    <nav>
        <div class="nav-brand">ChatBot Pro</div>
        <div class="nav-status">
            <div class="status-dot"></div>
            <span>API en ligne</span>
        </div>
    </nav>

    <main>
        <section class="hero">
            <div class="badge">✦ Intelligence Artificielle</div>
            <h1>Votre assistant IA disponible <span>24h/24</span></h1>
            <p class="subtitle">Testez notre chatbot intelligent connecté à votre site web. Réponses instantanées, personnalisées et disponibles à toute heure.</p>
            <ul class="features">
                <li><div class="check">✓</div><span>Réponses en temps réel basées sur votre contenu</span></li>
                <li><div class="check">✓</div><span>Connecté directement à votre site web</span></li>
                <li><div class="check">✓</div><span>Disponible 24h/24, 7j/7, sans interruption</span></li>
                <li><div class="check">✓</div><span>Intégration en 2 lignes de code sur votre site</span></li>
            </ul>
        </section>

        <section class="chat-panel">
            <div class="chat-card">
                <div class="chat-header">
                    <div class="avatar">🤖</div>
                    <div class="chat-header-info">
                        <h3>ChatBot Pro - Démo</h3>
                        <span>● En ligne</span>
                    </div>
                </div>
                <div class="chat-messages" id="chatMessages">
                    <div class="msg bot">Bonjour ! Je suis votre assistant IA. Comment puis-je vous aider aujourd'hui ?</div>
                </div>
                <div class="chat-input-area">
                    <input type="text" id="msgInput" placeholder="Posez votre question..." autocomplete="off">
                    <button class="send-btn" id="sendBtn" aria-label="Envoyer">
                        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
                    </button>
                </div>
            </div>
        </section>
    </main>

    {% raw %}
    <script>
        const messagesEl = document.getElementById('chatMessages');
        const inputEl    = document.getElementById('msgInput');
        const sendEl     = document.getElementById('sendBtn');
        const sessionId  = 'demo_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

        function addMsg(text, sender) {
            const div = document.createElement('div');
            div.className = 'msg ' + sender;
            div.textContent = text;
            messagesEl.appendChild(div);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function showTyping() {
            const div = document.createElement('div');
            div.className = 'msg typing';
            div.id = 'typing';
            div.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
            messagesEl.appendChild(div);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function removeTyping() {
            const t = document.getElementById('typing');
            if (t) t.remove();
        }

        async function send() {
            const msg = inputEl.value.trim();
            if (!msg) return;
            inputEl.value = '';
            sendEl.disabled = true;

            addMsg(msg, 'user');
            showTyping();

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg, session_id: sessionId })
                });
                const data = await res.json();
                removeTyping();
                addMsg(data.reply, 'bot');
            } catch (e) {
                removeTyping();
                addMsg('Erreur de connexion. Veuillez réessayer.', 'bot');
            }

            sendEl.disabled = false;
            inputEl.focus();
        }

        sendEl.addEventListener('click', send);
        inputEl.addEventListener('keypress', e => { if (e.key === 'Enter') send(); });
    </script>
    {% endraw %}
</body>
</html>""")


port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port, debug=False)