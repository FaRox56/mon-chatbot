(function() {
    // Configuration
    const config = window.ChatbotConfig || {};
    const clientId = config.clientId || 'default';

    // Générer ou récupérer session_id
    let sessionId = localStorage.getItem('chatbot_session_id');
    if (!sessionId) {
        sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('chatbot_session_id', sessionId);
    }

    // Injecter le CSS
    const css = `
        .chatbot-bubble {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 60px;
            height: 60px;
            background-color: #007bff;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            transition: transform 0.2s;
            z-index: 10000;
        }
        .chatbot-bubble:hover {
            transform: scale(1.1);
        }
        .chatbot-bubble::after {
            content: "💬";
            font-size: 24px;
        }
        .chatbot-window {
            position: fixed;
            bottom: 90px;
            right: 20px;
            width: 350px;
            height: 500px;
            background-color: #1e1e1e;
            border-radius: 10px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.5);
            display: none;
            flex-direction: column;
            overflow: hidden;
            z-index: 10001;
        }
        .chatbot-header {
            background-color: #333;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            color: #fff;
        }
        .chatbot-messages {
            flex: 1;
            padding: 10px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        .chatbot-message {
            margin-bottom: 10px;
            padding: 8px 12px;
            border-radius: 18px;
            max-width: 70%;
            word-wrap: break-word;
        }
        .chatbot-message.bot {
            background-color: #333;
            color: #fff;
            align-self: flex-start;
        }
        .chatbot-message.user {
            background-color: #007bff;
            color: #fff;
            align-self: flex-end;
        }
        .chatbot-input {
            display: flex;
            padding: 10px;
            background-color: #333;
        }
        .chatbot-input input {
            flex: 1;
            padding: 8px;
            border: none;
            border-radius: 20px;
            background-color: #555;
            color: #fff;
            outline: none;
        }
        .chatbot-input button {
            margin-left: 10px;
            padding: 8px 16px;
            border: none;
            border-radius: 20px;
            background-color: #007bff;
            color: #fff;
            cursor: pointer;
        }
        .chatbot-input button:hover {
            background-color: #0056b3;
        }
    `;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    // Créer la bulle
    const bubble = document.createElement('div');
    bubble.className = 'chatbot-bubble';
    document.body.appendChild(bubble);

    // Créer la fenêtre
    const windowDiv = document.createElement('div');
    windowDiv.className = 'chatbot-window';
    windowDiv.innerHTML = `
        <div class="chatbot-header">Chatbot</div>
        <div class="chatbot-messages"></div>
        <div class="chatbot-input">
            <input type="text" placeholder="Tapez votre message...">
            <button>Envoyer</button>
        </div>
    `;
    document.body.appendChild(windowDiv);

    const messagesDiv = windowDiv.querySelector('.chatbot-messages');
    const input = windowDiv.querySelector('input');
    const button = windowDiv.querySelector('button');

    // Gestion du clic sur la bulle
    bubble.addEventListener('click', () => {
        windowDiv.style.display = windowDiv.style.display === 'flex' ? 'none' : 'flex';
    });

    // Fonction pour ajouter un message
    function addMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chatbot-message ' + sender;
        messageDiv.textContent = content;
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    // Fonction pour envoyer un message
    async function sendMessage() {
        const message = input.value.trim();
        if (!message) return;

        addMessage(message, 'user');
        input.value = '';

        try {
            const response = await fetch('http://127.0.0.1:5000/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    session_id: sessionId
                })
            });

            const data = await response.json();
            addMessage(data.reply, 'bot');
        } catch (error) {
            addMessage('Erreur de connexion au serveur.', 'bot');
        }
    }

    // Événements
    button.addEventListener('click', sendMessage);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
})();