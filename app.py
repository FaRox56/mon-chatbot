from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

# Lire le contexte au démarrage
with open('context.txt', 'r', encoding='utf-8') as f:
    context = f.read()

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

conversations = {}

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

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=f"Tu es Sophie, secrétaire d'accueil à l'auto-école Savoie. Tu tutoies le client, tu es chaleureuse et naturelle, comme une vraie secrétaire au téléphone. Réponds toujours en 2-3 phrases max, sans listes ni bullet points, de manière directe et conversationnelle. Utilise uniquement les informations de ce contexte : {context}. Si tu ne trouves pas la réponse, propose simplement d'appeler le 04 74 63 61 33.",
        messages=conversations[session_id]
    )

    reply = response.content[0].text

    conversations[session_id].append({
        "role": "assistant",
        "content": reply
    })

    return jsonify({"reply": reply})

@app.route("/")
def home():
    return "✅ Chatbot en ligne !"

if __name__ == "__main__":
    app.run(debug=True, port=5000)