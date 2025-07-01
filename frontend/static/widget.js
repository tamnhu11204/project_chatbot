(function () {
    console.log('Widget script loaded at', new Date().toLocaleString());

    const script = document.currentScript;
    const iframeUrl = script.getAttribute("data-iframe-url") || "https://project-chatbot-hgcl.onrender.com/chatbot-ui";
    const primaryColor = script.getAttribute("data-primary-color") || "#4CAF50";

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    function initChatbot() {
        const cookieIsAdmin = getCookie('isAdmin');
        const localStorageIsAdmin = localStorage.getItem('isAdmin');
        console.log('Checking admin role:', {
            cookieIsAdmin: cookieIsAdmin,
            localStorageIsAdmin: localStorageIsAdmin,
            cookies: document.cookie,
            localStorage: localStorage
        });

        const isAdmin = cookieIsAdmin === 'true' || localStorageIsAdmin === 'true';
        if (isAdmin) {
            console.log('Admin detected, chatbot will not be displayed.');
            return;
        }

        const iframe = document.createElement("iframe");
        iframe.src = iframeUrl + "?v=" + Date.now();
        iframe.style.position = "fixed";
        iframe.style.bottom = "80px";
        iframe.style.right = "20px";
        iframe.style.width = "350px";
        iframe.style.height = "500px";
        iframe.style.border = "none";
        iframe.style.zIndex = "9999";
        iframe.style.borderRadius = "10px";
        iframe.style.boxShadow = "0 0 10px rgba(0,0,0,0.2)";
        iframe.style.display = "none";
        iframe.setAttribute("sandbox", "allow-scripts allow-same-origin");

        const toggleBtn = document.createElement("div");
        toggleBtn.innerHTML = `<img src="https://project-chatbot-hgcl.onrender.com/static/asset/logo.png?v=${Date.now()}" alt="Chatbot Logo" class="toggle-logo" onerror="this.src='https://project-chatbot-hgcl.onrender.com/static/asset/fallback.png'; this.onerror=null;">`;
        toggleBtn.style.position = "fixed";
        toggleBtn.style.bottom = "20px";
        toggleBtn.style.right = "20px";
        toggleBtn.style.width = "50px";
        toggleBtn.style.height = "50px";
        toggleBtn.style.borderRadius = "50%";
        toggleBtn.style.background = primaryColor;
        toggleBtn.style.color = "white";
        toggleBtn.style.display = "flex";
        toggleBtn.style.alignItems = "center";
        toggleBtn.style.justifyContent = "center";
        toggleBtn.style.cursor = "pointer";
        toggleBtn.style.zIndex = "9999";
        toggleBtn.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.3)";
        toggleBtn.style.border = "2px solid rgba(255, 255, 255, 0.2)";

        const style = document.createElement("style");
        style.innerHTML = `
            .toggle-logo {
                max-width: 80%;
                max-height: 80%;
                object-fit: contain;
                object-position: center;
            }
            .toggle-btn:hover {
                box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4);
                background: ${primaryColor.replace('0.5', '0.7')};
            }
        `;
        document.head.appendChild(style);

        toggleBtn.className = "toggle-btn";

        toggleBtn.onclick = () => {
            iframe.style.display = iframe.style.display === "none" ? "block" : "none";
        };

        iframe.onerror = () => {
            const errorDiv = document.createElement("div");
            errorDiv.textContent = "Lỗi tải chatbot. Vui lòng thử lại sau.";
            errorDiv.style.color = "red";
            document.body.appendChild(errorDiv);
        };

        document.body.appendChild(toggleBtn);
        document.body.appendChild(iframe);
    }

    setTimeout(() => {
        initChatbot();
    }, 500);
})();