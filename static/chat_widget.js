(function () {
  const bubble = document.getElementById("reconauto-chat-bubble");
  const panel = document.getElementById("reconauto-chat-panel");
  const messagesEl = document.getElementById("reconauto-chat-messages");
  const inputEl = document.getElementById("reconauto-chat-input");
  const sendBtn = document.getElementById("reconauto-chat-send");
  const escalateBox = document.getElementById("reconauto-chat-escalate");

  if (!bubble || !panel) return; // widget belum ditempel di halaman ini

  let history = [];
  let greeted = false;

  bubble.addEventListener("click", () => {
    panel.classList.toggle("open");
    if (panel.classList.contains("open") && !greeted) {
      addMessage(
        "bot",
        "Halo! Saya asisten ReconAuto.ID. Tanyakan apa saja seputar cara pakai atau dokumentasi sistem ini ya."
      );
      greeted = true;
    }
  });

  function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = "rc-msg " + (role === "user" ? "user" : "bot");
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showEscalation(cs) {
    if (!cs || (!cs.whatsapp && !cs.email)) return;
    let html = "Butuh bantuan lebih lanjut? ";
    if (cs.whatsapp) {
      html += `<a href="https://wa.me/${cs.whatsapp}" target="_blank" rel="noopener">Chat WhatsApp CS</a> `;
    }
    if (cs.email) {
      html += `${cs.whatsapp ? "atau " : ""}<a href="mailto:${cs.email}">email CS</a>`;
    }
    escalateBox.innerHTML = html;
    escalateBox.style.display = "block";
  }

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text) return;
    addMessage("user", text);
    inputEl.value = "";
    history.push({ role: "user", text });

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
      });
      const data = await res.json();
      addMessage("bot", data.reply);
      history.push({ role: "model", text: data.reply });
      if (data.need_escalation) showEscalation(data.cs_contact);
    } catch (err) {
      addMessage("bot", "Maaf, koneksi ke chat sedang bermasalah. Silakan coba lagi sebentar.");
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });
})();
