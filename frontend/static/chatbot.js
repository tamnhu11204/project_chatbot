const API_BASE_URL = "https://project-chatbot-hgcl.onrender.com";
const BE_API_URL = "http://localhost:3001";
let userId = getCookie('user_id') || localStorage.getItem('user_id') || `guest_${uuidv4()}`;
let accessToken = getCookie('access_token') || localStorage.getItem('access_token') || '';
let sessionId = uuidv4().slice(0, 8);
let isGuest = !accessToken;
let isAdminChat = false;
let isSupportRequested = false;
let displayedMessages = new Set();
let supportButtonLocked = false;

localStorage.setItem('user_id', userId);
localStorage.setItem('access_token', accessToken);
console.log('Initial userId:', userId, 'SessionId:', sessionId, 'Is guest:', isGuest);

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function formatTime(date) {
    return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

const socket = io(BE_API_URL, { withCredentials: true });
socket.on('supportRequest', (data) => {
    if (data.userId === userId && !isAdminChat) {
        const chatBox = document.getElementById('chat-box');
        const messageKey = `bot:Admin đang hỗ trợ bạn!:${data.timestamp}`;
        if (!displayedMessages.has(messageKey)) {
            chatBox.innerHTML += `<div class="bot-message">Admin đang hỗ trợ bạn!</div>`;
            displayedMessages.add(messageKey);
            isAdminChat = true;
            isSupportRequested = true;
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    }
});
socket.on('newMessage', (data) => {
    if (data.userId === userId) {
        const messageKey = `${data.sender}:${data.message}:${data.timestamp}`;
        if (!displayedMessages.has(messageKey)) {
            const chatBox = document.getElementById('chat-box');
            const div = document.createElement('div');
            div.className = data.sender === 'user' ? 'user-message' : 'bot-message';
            const timeSpan = document.createElement('span');
            timeSpan.className = 'message-time';
            timeSpan.textContent = formatTime(new Date(data.timestamp));
            const contentSpan = document.createElement('span');
            contentSpan.textContent = data.sender === 'admin' ? `Admin: ${data.message}` : `Bot: ${data.message}`;
            div.appendChild(contentSpan);
            div.appendChild(timeSpan);
            chatBox.appendChild(div);
            displayedMessages.add(messageKey);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    }
});

window.addEventListener('message', (event) => {
    if (event.data.type === 'USER_DATA') {
        const { user, token } = event.data.payload;
        if (user?._id) {
            userId = user._id;
            localStorage.setItem('user_id', userId);
            localStorage.setItem('access_token', token || '');
            isGuest = !token;
            console.log('Updated userId from postMessage:', userId, 'Token:', token);
            displayedMessages.clear();
            document.getElementById('chat-box').innerHTML = '';
            loadConversationHistory();
        }
    } else if (event.data.type === 'LOGOUT') {
        localStorage.removeItem('user_id');
        localStorage.removeItem('access_token');
        userId = `guest_${uuidv4()}`;
        isGuest = true;
        localStorage.setItem('user_id', userId);
        displayedMessages.clear();
        document.getElementById('chat-box').innerHTML = '';
        console.log('Logged out, reset userId:', userId);
        loadConversationHistory();
    }
});

async function sendFeedback(userMessage, botReply, feedbackType) {
    try {
        await fetch(`${API_BASE_URL}/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_input: userMessage,
                bot_response: botReply,
                feedback: feedbackType
            })
        });
        const chatBox = document.getElementById('chat-box');
        if (feedbackType === 'dislike' && !isSupportRequested) {
            await sendToAdmin(`Phản hồi sai cho: ${userMessage}`);
            chatBox.innerHTML += `<div class="bot-message">Đã gửi phản hồi đến admin để xử lý!</div>`;
            isSupportRequested = true;
        } else {
            chatBox.innerHTML += `<div class="bot-message">Cảm ơn bạn đã phản hồi!</div>`;
        }
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (error) {
        console.error("Lỗi gửi feedback:", error);
    }
}

async function sendToAdmin(message) {
    if (isSupportRequested || supportButtonLocked) return;
    supportButtonLocked = true;
    setTimeout(() => { supportButtonLocked = false; }, 2000);
    try {
        const headers = { "Content-Type": "application/json" };
        const token = localStorage.getItem('access_token');
        if (!isGuest && token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        console.log('Sending support request:', { userId, message });
        const response = await fetch(`${BE_API_URL}/api/chat/support`, {
            method: "POST",
            headers,
            body: JSON.stringify({
                userId,
                message: `Yêu cầu hỗ trợ: ${message}`
            })
        });
        if (!response.ok) throw new Error(`Support API failed: ${response.status}`);
        const chatBox = document.getElementById('chat-box');
        const messageKey = `bot:Đã gửi yêu cầu hỗ trợ đến admin!:${Date.now()}`;
        if (!displayedMessages.has(messageKey)) {
            chatBox.innerHTML += `<div class="bot-message">Đã gửi yêu cầu hỗ trợ đến admin!</div>`;
            displayedMessages.add(messageKey);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    } catch (error) {
        console.error("Lỗi gửi yêu cầu hỗ trợ:", error);
        const chatBox = document.getElementById('chat-box');
        chatBox.innerHTML += `<div class="bot-message">Lỗi khi gửi yêu cầu hỗ trợ. Vui lòng thử lại!</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

async function sendMessage() {
    console.log('sendMessage called');
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;

    const chatBox = document.getElementById('chat-box');
    const messageKey = `user:${message}:${Date.now()}`;
    if (!displayedMessages.has(messageKey)) {
        const userDiv = document.createElement("div");
        userDiv.className = "user-message";
        const contentSpan = document.createElement('span');
        contentSpan.textContent = message;
        const timeSpan = document.createElement('span');
        timeSpan.className = 'message-time';
        timeSpan.textContent = formatTime(new Date());
        userDiv.appendChild(contentSpan);
        userDiv.appendChild(timeSpan);
        chatBox.appendChild(userDiv);
        displayedMessages.add(messageKey);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    if (isAdminChat) {
        try {
            console.log('Sending to admin:', { userId, message });
            const headers = { "Content-Type": "application/json" };
            const token = localStorage.getItem('access_token');
            if (!isGuest && token) {
                headers["Authorization"] = `Bearer ${token}`;
            }
            await fetch(`${BE_API_URL}/api/chat/send`, {
                method: "POST",
                headers,
                body: JSON.stringify({ userId, message })
            });
            input.value = "";
            return;
        } catch (error) {
            console.error("Lỗi gửi tin nhắn admin:", error);
            chatBox.innerHTML += `<div class="bot-message">Lỗi khi gửi tin nhắn đến admin. Vui lòng thử lại!</div>`;
            chatBox.scrollTop = chatBox.scrollHeight;
            return;
        }
    }

    const loadingDiv = document.createElement("div");
    loadingDiv.className = "loading";
    loadingDiv.textContent = "Đang xử lý...";
    chatBox.appendChild(loadingDiv);

    try {
        console.log('Sending to bot:', { message, userId, sessionId });
        const res = await fetch(`${API_BASE_URL}/predict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, user_id: userId, session_id: sessionId })
        });

        if (chatBox.contains(loadingDiv)) {
            chatBox.removeChild(loadingDiv);
        }
        if (!res.ok) throw new Error(`Predict API failed: ${res.status}`);

        const data = await res.json();
        let botResponse = data.response;

        const botDiv = document.createElement("div");
        botDiv.className = "bot-message";
        const contentSpan = document.createElement('span');
        contentSpan.textContent = `Bot: ${botResponse}`;
        const timeSpan = document.createElement('span');
        timeSpan.className = 'message-time';
        timeSpan.textContent = formatTime(new Date());
        const feedbackDiv = document.createElement("div");
        feedbackDiv.className = "feedback-container";
        feedbackDiv.innerHTML = `
            <span class="feedback-icon like" onclick="sendFeedback('${message.replace(/'/g, "\\'")}', '${botResponse.replace(/'/g, "\\'")}', 'like')">👍</span>
            <span class="feedback-icon dislike" onclick="sendFeedback('${message.replace(/'/g, "\\'")}', '${botResponse.replace(/'/g, "\\'")}', 'dislike')">👎</span>
        `;
        botDiv.appendChild(contentSpan);
        botDiv.appendChild(timeSpan);
        botDiv.appendChild(feedbackDiv);

        if (data.books && data.books.length > 0) {
            const bookButtons = data.books.map(book => `<button onclick="sendMessage('chi tiết sách ${book.id}')">${book.name}</button>`).join("");
            botDiv.innerHTML += `<div class="book-buttons">${bookButtons}</div>`;
        }

        const botMessageKey = `bot:${botResponse}:${Date.now()}`;
        if (!displayedMessages.has(botMessageKey)) {
            chatBox.appendChild(botDiv);
            displayedMessages.add(botMessageKey);
            input.value = "";
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        if (data.intent === "support" || data.confidence < 0.5) {
            await sendToAdmin(message);
        }
    } catch (error) {
        if (chatBox.contains(loadingDiv)) {
            chatBox.removeChild(loadingDiv);
        }
        console.error("Lỗi gửi tin nhắn chatbot:", error);
        chatBox.innerHTML += `<div class="bot-message">Lỗi khi xử lý tin nhắn. Đã gửi yêu cầu hỗ trợ đến admin!</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
        await sendToAdmin(`Chatbot lỗi khi xử lý: ${message}`);
    }
}

async function loadConversationHistory() {
    try {
        const headers = { "Content-Type": "application/json" };
        const token = localStorage.getItem('access_token');
        if (!isGuest && token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        const res = await fetch(`${BE_API_URL}/api/chat/conversation/${userId}`, { headers });
        if (!res.ok) throw new Error(`API failed: ${res.status}`);
        const data = await res.json();
        const chatBox = document.getElementById('chat-box');
        (data.messages || []).forEach(msg => {
            const messageKey = `${msg.sender}:${msg.message}:${msg.timestamp}`;
            if (!displayedMessages.has(messageKey)) {
                const div = document.createElement('div');
                div.className = msg.sender === 'user' ? 'user-message' : 'bot-message';
                const contentSpan = document.createElement('span');
                contentSpan.textContent = msg.sender === 'admin' ? `Admin: ${msg.message}` : `Bot: ${msg.message}`;
                const timeSpan = document.createElement('span');
                timeSpan.className = 'message-time';
                timeSpan.textContent = formatTime(new Date(msg.timestamp));
                div.appendChild(contentSpan);
                div.appendChild(timeSpan);
                chatBox.appendChild(div);
                displayedMessages.add(messageKey);
            }
        });
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (error) {
        console.error('Lỗi tải lịch sử tin nhắn:', error);
    }
}

window.onload = () => {
    loadConversationHistory();
    document.getElementById("send-button").onclick = sendMessage;
    const userInput = document.getElementById("user-input");
    userInput.onkeypress = (e) => {
        console.log('Key pressed:', e.key);
        if (e.key === "Enter") sendMessage();
    };
    userInput.focus();
};

// CSS cho loading và nút sách
const style = document.createElement('style');
style.innerHTML = `
    .loading {
        display: flex;
        justify-content: center;
        align-items: center;
        color: #007bff;
        font-style: italic;
    }
    .loading::after {
        content: ".";
        animation: dots 1s infinite;
    }
    @keyframes dots {
        0% { content: "."; }
        33% { content: ".."; }
        66% { content: "..."; }
    }
    .book-buttons {
        margin-top: 10px;
    }
    .book-buttons button {
        margin: 5px;
        padding: 5px 10px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
    }
    .book-buttons button:hover {
        background-color: #0056b3;
    }
`;
document.head.appendChild(style);