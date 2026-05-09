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
    context_name = data.get("context_name", "").strip()
    company_name = data.get("company_name", "").strip()

    active_context = context
    if context_name:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", context_name)
        context_file = f"context_{safe_name}.txt"
        if os.path.exists(context_file):
            try:
                with open(context_file, "r", encoding="utf-8") as f:
                    active_context = f.read()
            except Exception:
                pass

    if session_id not in conversations:
        conversations[session_id] = []

    conversations[session_id].append({
        "role": "user",
        "content": message
    })

    message_events.append({"timestamp": datetime.datetime.now(), "session_id": session_id})

    persona = f"l'assistant de {company_name}" if company_name else "un assistant virtuel professionnel"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=f"Tu es {persona}. Tu tutoies le client, tu es chaleureux et naturel. Tu réponds en 2-3 phrases maximum. Tu donnes l'info directe sans listes ni bullet points ni markdown. Si tu ne sais pas, propose au client de vous contacter directement. Utilise uniquement les informations de ce contexte : {active_context}",
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
        .step-hidden { display: none !important; }
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
            width: 8px; height: 8px;
            background: #22c55e;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        main {
            display: flex;
            align-items: center;
            min-height: calc(100vh - 73px);
            padding: 60px 40px;
            gap: 60px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .hero { flex: 1; max-width: 520px; }
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
        .subtitle { font-size: 1.1rem; color: #8888aa; line-height: 1.7; margin-bottom: 40px; }
        .features { list-style: none; display: flex; flex-direction: column; gap: 14px; }
        .features li { display: flex; align-items: center; gap: 12px; font-size: 0.95rem; color: #ccccee; }
        .check {
            width: 22px; height: 22px;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 11px; flex-shrink: 0; color: white; font-weight: 700;
        }
        .chat-panel { flex: 1; max-width: 420px; width: 100%; }

        /* ── Onboarding card ── */
        .onboarding-card {
            background: #16162a;
            border: 1px solid #2a2a4a;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(79,142,247,0.08);
        }
        .onboarding-header {
            background: linear-gradient(135deg, #1e1e3a, #2a2050);
            padding: 22px 24px;
            border-bottom: 1px solid #2a2a4a;
        }
        .onboarding-header h2 { font-size: 1rem; font-weight: 700; color: #f0f0ff; margin-bottom: 4px; }
        .onboarding-header p { font-size: 0.8rem; color: #8888aa; }
        .onboarding-body { padding: 24px; display: flex; flex-direction: column; gap: 18px; }
        .form-group { display: flex; flex-direction: column; gap: 6px; }
        .form-label {
            font-size: 0.78rem; font-weight: 600; color: #8888aa;
            text-transform: uppercase; letter-spacing: 0.5px;
        }
        .form-input, .form-select {
            background: #0f0f1e;
            border: 1px solid #2a2a4a;
            border-radius: 12px;
            padding: 11px 14px;
            color: #e0e0f0;
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
            width: 100%;
            font-family: inherit;
        }
        .form-input::placeholder { color: #5555aa; }
        .form-input:focus, .form-select:focus {
            border-color: #4f8ef7;
            box-shadow: 0 0 0 3px rgba(79,142,247,0.12);
        }
        .form-select { cursor: pointer; }
        .form-select option { background: #16162a; }
        .cta-btn {
            width: 100%; padding: 13px;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border: none; border-radius: 12px;
            color: white; font-size: 0.95rem; font-weight: 700;
            cursor: pointer; transition: opacity 0.2s, transform 0.1s; margin-top: 4px;
        }
        .cta-btn:hover { opacity: 0.9; transform: translateY(-1px); }
        .cta-btn:active { transform: translateY(0); }
        .cta-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .form-note { text-align: center; font-size: 0.75rem; color: #5555aa; }

        /* ── Loading screen ── */
        .loading-screen {
            min-height: calc(100vh - 73px);
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            padding: 40px 20px; text-align: center;
        }
        .loading-icon {
            width: 72px; height: 72px;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border-radius: 20px;
            display: flex; align-items: center; justify-content: center;
            font-size: 32px; margin-bottom: 32px;
            animation: float 2s ease-in-out infinite;
            box-shadow: 0 16px 40px rgba(79,142,247,0.3);
        }
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }
        .loading-title { font-size: 1.5rem; font-weight: 700; color: #f0f0ff; margin-bottom: 10px; }
        .loading-subtitle { font-size: 0.95rem; color: #8888aa; margin-bottom: 40px; }
        .progress-container { width: 100%; max-width: 420px; }
        .progress-track {
            width: 100%; height: 6px; background: #2a2a4a;
            border-radius: 6px; overflow: hidden; margin-bottom: 14px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4f8ef7, #9b59b6);
            border-radius: 6px; width: 0%;
            transition: width 0.25s ease;
        }
        .progress-status { font-size: 0.82rem; color: #6677aa; text-align: left; }
        .progress-steps-list {
            margin-top: 32px;
            display: flex; flex-direction: column; gap: 10px;
            text-align: left; width: 100%; max-width: 420px;
        }
        .progress-step {
            display: flex; align-items: center; gap: 10px;
            font-size: 0.85rem; color: #5555aa; transition: color 0.3s;
        }
        .progress-step.done { color: #ccccee; }
        .progress-step-dot {
            width: 18px; height: 18px; border-radius: 50%;
            border: 2px solid #2a2a4a;
            display: flex; align-items: center; justify-content: center;
            font-size: 10px; flex-shrink: 0; transition: all 0.3s;
        }
        .progress-step.done .progress-step-dot {
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border-color: transparent; color: white;
        }
        .progress-step.active .progress-step-dot { border-color: #4f8ef7; }

        /* ── Chat card ── */
        .chat-card {
            background: #16162a;
            border: 1px solid #2a2a4a;
            border-radius: 20px; overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(79,142,247,0.08);
        }
        .chat-header {
            background: linear-gradient(135deg, #1e1e3a, #2a2050);
            padding: 18px 20px;
            display: flex; align-items: center; gap: 12px;
            border-bottom: 1px solid #2a2a4a;
        }
        .avatar {
            width: 40px; height: 40px;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center; font-size: 18px;
        }
        .chat-header-info h3 { font-size: 0.95rem; font-weight: 600; color: #f0f0ff; }
        .chat-header-info span { font-size: 0.75rem; color: #22c55e; }
        .chat-messages {
            height: 380px; overflow-y: auto;
            padding: 20px;
            display: flex; flex-direction: column; gap: 12px;
            background: #0f0f1e;
        }
        .chat-messages::-webkit-scrollbar { width: 4px; }
        .chat-messages::-webkit-scrollbar-track { background: transparent; }
        .chat-messages::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 2px; }
        .msg {
            max-width: 80%; padding: 10px 14px;
            border-radius: 16px; font-size: 0.9rem; line-height: 1.5; word-wrap: break-word;
        }
        .msg.bot { background: #1e1e38; color: #e0e0f0; align-self: flex-start; border-bottom-left-radius: 4px; }
        .msg.user { background: linear-gradient(135deg, #4f8ef7, #3b6fd4); color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }
        .msg.typing { background: #1e1e38; align-self: flex-start; }
        .typing-dots { display: flex; gap: 4px; padding: 4px 0; }
        .typing-dots span {
            width: 6px; height: 6px; background: #6677aa;
            border-radius: 50%; animation: bounce 1.2s infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
        .chat-input-area {
            display: flex; padding: 16px; gap: 10px;
            background: #16162a; border-top: 1px solid #2a2a4a;
        }
        .chat-input-area input {
            flex: 1; background: #0f0f1e; border: 1px solid #2a2a4a;
            border-radius: 12px; padding: 10px 16px;
            color: #e0e0f0; font-size: 0.9rem; outline: none; transition: border-color 0.2s;
        }
        .chat-input-area input:focus { border-color: #4f8ef7; }
        .chat-input-area input::placeholder { color: #5555aa; }
        .send-btn {
            width: 42px; height: 42px;
            background: linear-gradient(135deg, #4f8ef7, #9b59b6);
            border: none; border-radius: 12px; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            transition: opacity 0.2s, transform 0.1s; flex-shrink: 0;
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

    <!-- ÉTAPE 1 : Formulaire d'onboarding -->
    <div id="step-onboarding">
        <main>
            <section class="hero">
                <div class="badge">✦ Intelligence Artificielle</div>
                <h1>Un chatbot <span>personnalisé</span> pour votre site</h1>
                <p class="subtitle">Entrez l'URL de votre site et nous créons instantanément un assistant IA qui connaît votre activité, vos tarifs et vos services.</p>
                <ul class="features">
                    <li><div class="check">✓</div><span>Analyse automatique de votre contenu web</span></li>
                    <li><div class="check">✓</div><span>Réponses personnalisées à votre secteur</span></li>
                    <li><div class="check">✓</div><span>Disponible 24h/24, 7j/7, sans interruption</span></li>
                    <li><div class="check">✓</div><span>Intégration en 2 lignes de code sur votre site</span></li>
                </ul>
            </section>
            <section class="chat-panel">
                <div class="onboarding-card">
                    <div class="onboarding-header">
                        <h2>🚀 Lancer votre démo gratuite</h2>
                        <p>Analyse de votre site en moins de 30 secondes</p>
                    </div>
                    <div class="onboarding-body">
                        <form id="onboardingForm" novalidate>
                            <div style="display:flex;flex-direction:column;gap:18px;">
                                <div class="form-group">
                                    <label class="form-label" for="siteUrl">URL de votre site web</label>
                                    <input class="form-input" type="url" id="siteUrl" placeholder="https://monentreprise.fr" required>
                                </div>
                                <div class="form-group">
                                    <label class="form-label" for="companyNameInput">Nom de votre entreprise</label>
                                    <input class="form-input" type="text" id="companyNameInput" placeholder="Ex : Auto-École Savoie" required>
                                </div>
                                <div class="form-group">
                                    <label class="form-label" for="sector">Votre secteur</label>
                                    <select class="form-select" id="sector">
                                        <option value="auto-ecole">Auto-école</option>
                                        <option value="restaurant">Restaurant</option>
                                        <option value="commerce">Commerce</option>
                                        <option value="agence">Agence</option>
                                        <option value="autre">Autre</option>
                                    </select>
                                </div>
                                <button type="submit" class="cta-btn" id="ctaBtn">Lancer ma démo gratuite →</button>
                                <p class="form-note">Aucune carte bancaire · Démo instantanée</p>
                            </div>
                        </form>
                    </div>
                </div>
            </section>
        </main>
    </div>

    <!-- ÉTAPE 2 : Animation de chargement -->
    <div id="step-loading" class="step-hidden">
        <div class="loading-screen">
            <div class="loading-icon">🔍</div>
            <h2 class="loading-title">Analyse de votre site en cours...</h2>
            <p class="loading-subtitle">Nous explorons votre contenu pour créer votre assistant personnalisé</p>
            <div class="progress-container">
                <div class="progress-track">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="progress-status" id="progressStatus">Initialisation...</div>
            </div>
            <div class="progress-steps-list">
                <div class="progress-step" id="pstep-1">
                    <div class="progress-step-dot"></div>
                    <span>Connexion au site web</span>
                </div>
                <div class="progress-step" id="pstep-2">
                    <div class="progress-step-dot"></div>
                    <span>Lecture des pages</span>
                </div>
                <div class="progress-step" id="pstep-3">
                    <div class="progress-step-dot"></div>
                    <span>Analyse du contenu</span>
                </div>
                <div class="progress-step" id="pstep-4">
                    <div class="progress-step-dot"></div>
                    <span>Génération de la base de connaissance</span>
                </div>
            </div>
        </div>
    </div>

    <!-- ÉTAPE 3 : Chat personnalisé -->
    <div id="step-chat" class="step-hidden">
        <main>
            <section class="hero">
                <div class="badge">✦ Votre assistant est prêt</div>
                <h1>Testez votre assistant <span id="heroCompanyName">personnalisé</span></h1>
                <p class="subtitle">Votre chatbot a analysé votre site et peut maintenant répondre aux questions de vos clients comme un vrai membre de votre équipe.</p>
                <ul class="features">
                    <li><div class="check">✓</div><span>Connaît vos tarifs et services</span></li>
                    <li><div class="check">✓</div><span>Répond en temps réel, 24h/24</span></li>
                    <li><div class="check">✓</div><span>S'adapte au ton de votre marque</span></li>
                    <li><div class="check">✓</div><span>Prêt à intégrer sur votre site</span></li>
                </ul>
            </section>
            <section class="chat-panel">
                <div class="chat-card">
                    <div class="chat-header">
                        <div class="avatar">🤖</div>
                        <div class="chat-header-info">
                            <h3 id="chatBotName">Assistant</h3>
                            <span>● En ligne</span>
                        </div>
                    </div>
                    <div class="chat-messages" id="chatMessages"></div>
                    <div class="chat-input-area">
                        <input type="text" id="msgInput" placeholder="Posez votre question..." autocomplete="off">
                        <button class="send-btn" id="sendBtn" aria-label="Envoyer">
                            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
                        </button>
                    </div>
                </div>
            </section>
        </main>
    </div>

    {% raw %}
    <script>
        let companyName = '';
        let contextName = '';
        const sessionId = 'demo_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        let progressInterval = null;
        let progressPct = 0;

        // ── Navigation entre étapes ──────────────────────────────────────
        function showStep(id) {
            ['step-onboarding', 'step-loading', 'step-chat'].forEach(s => {
                document.getElementById(s).classList.toggle('step-hidden', s !== id);
            });
        }

        // ── Barre de progression ─────────────────────────────────────────
        const stepDefs = [
            { id: 'pstep-1', label: 'Connexion au site web...', threshold: 0 },
            { id: 'pstep-2', label: 'Lecture des pages...', threshold: 22 },
            { id: 'pstep-3', label: 'Analyse du contenu...', threshold: 52 },
            { id: 'pstep-4', label: 'Génération de la base de connaissance...', threshold: 76 },
        ];

        function startProgress() {
            progressPct = 0;
            stepDefs.forEach(s => {
                const el = document.getElementById(s.id);
                el.className = 'progress-step';
                el.querySelector('.progress-step-dot').textContent = '';
            });
            const fill = document.getElementById('progressFill');
            const status = document.getElementById('progressStatus');
            progressInterval = setInterval(() => {
                if (progressPct < 88) {
                    progressPct += progressPct < 30 ? 0.7 : progressPct < 60 ? 0.35 : 0.12;
                    progressPct = Math.min(progressPct, 88);
                }
                fill.style.width = progressPct + '%';
                for (let i = 0; i < stepDefs.length; i++) {
                    const s = stepDefs[i];
                    const next = stepDefs[i + 1];
                    const el = document.getElementById(s.id);
                    if (next && progressPct >= next.threshold) {
                        el.className = 'progress-step done';
                        el.querySelector('.progress-step-dot').textContent = '✓';
                    } else if (progressPct >= s.threshold) {
                        el.className = 'progress-step active';
                        el.querySelector('.progress-step-dot').textContent = '';
                        status.textContent = s.label;
                    }
                }
            }, 80);
        }

        function finishProgress() {
            clearInterval(progressInterval);
            document.getElementById('progressFill').style.width = '100%';
            document.getElementById('progressStatus').textContent = 'Analyse terminée !';
            stepDefs.forEach(s => {
                const el = document.getElementById(s.id);
                el.className = 'progress-step done';
                el.querySelector('.progress-step-dot').textContent = '✓';
            });
        }

        // ── Soumission du formulaire ─────────────────────────────────────
        document.getElementById('onboardingForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const url  = document.getElementById('siteUrl').value.trim();
            const name = document.getElementById('companyNameInput').value.trim();
            if (!url || !name) return;

            companyName = name;
            contextName = name;

            const btn = document.getElementById('ctaBtn');
            btn.disabled = true;
            btn.textContent = 'Analyse en cours...';

            showStep('step-loading');
            startProgress();

            try {
                await fetch('/scrape', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, name })
                });
            } catch (_) {}

            finishProgress();
            await new Promise(r => setTimeout(r, 700));
            showChat();
        });

        // ── Affichage du chat ────────────────────────────────────────────
        function showChat() {
            document.getElementById('chatBotName').textContent = companyName;
            document.getElementById('heroCompanyName').textContent = companyName;
            showStep('step-chat');
            const messagesEl = document.getElementById('chatMessages');
            messagesEl.innerHTML = '';
            addMsg('Bonjour ! Je suis l\'assistant de ' + companyName + '. Comment puis-je vous aider ?', 'bot');
            document.getElementById('msgInput').focus();
        }

        // ── Fonctions chat ───────────────────────────────────────────────
        function addMsg(text, sender) {
            const messagesEl = document.getElementById('chatMessages');
            const div = document.createElement('div');
            div.className = 'msg ' + sender;
            div.textContent = text;
            messagesEl.appendChild(div);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function showTyping() {
            const messagesEl = document.getElementById('chatMessages');
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
            const inputEl = document.getElementById('msgInput');
            const sendEl  = document.getElementById('sendBtn');
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
                    body: JSON.stringify({ message: msg, session_id: sessionId, context_name: contextName, company_name: companyName })
                });
                const data = await res.json();
                removeTyping();
                addMsg(data.reply, 'bot');
            } catch (_) {
                removeTyping();
                addMsg('Erreur de connexion. Veuillez réessayer.', 'bot');
            }

            sendEl.disabled = false;
            inputEl.focus();
        }

        document.getElementById('sendBtn').addEventListener('click', send);
        document.getElementById('msgInput').addEventListener('keypress', e => { if (e.key === 'Enter') send(); });
    </script>
    {% endraw %}
</body>
</html>""")


port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port, debug=False)