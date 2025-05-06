(function () {
    const script = document.currentScript;
    const iframeUrl = script.getAttribute("data-iframe-url") || "http://localhost:8000/chatbot-ui";
    const primaryColor = script.getAttribute("data-primary-color") || "#4CAF50";

    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = "http://localhost:8000/static/style.css";
    document.head.appendChild(style);

    const iframe = document.createElement("iframe");
    iframe.src = iframeUrl;
    iframe.style.position = "fixed";
    iframe.style.bottom = "80px";
    iframe.style.right = "20px";
    iframe.style.width = "min(90vw, 350px)";
    iframe.style.height = "min(80vh, 500px)";
    iframe.style.border = "none";
    iframe.style.zIndex = "9999";
    iframe.style.borderRadius = "10px";
    iframe.style.boxShadow = "0 0 10px rgba(0,0,0,0.2)";
    iframe.style.display = "none";

    const toggleBtn = document.createElement("div");
    toggleBtn.textContent = "💬";
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
    toggleBtn.style.fontSize = "24px";
    toggleBtn.style.cursor = "pointer";
    toggleBtn.style.zIndex = "9999";
    toggleBtn.style.boxShadow = "0 0 10px rgba(0,0,0,0.2)";

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
})();