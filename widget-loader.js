(function () {
  const script = document.currentScript;
  if (!script) return;

  const siteId = script.dataset.siteId || "marketing-site";
  const widgetUrl = script.dataset.widgetUrl || "https://ai-chatbot-mvp-v2.netlify.app//widget.html";
  const backendHttp = script.dataset.backendHttp || "https://ai-chatbot-mvp-production.up.railway.app";
  const backendWs = script.dataset.backendWs || "wss://ai-chatbot-mvp-production.up.railway.app";
  const mode = script.dataset.mode || "popup";
  const inlineTarget = script.dataset.inlineTarget || "";
  const launcherLabel = script.dataset.launcherLabel || "Chat with us";

  function buildSrc(embedMode) {
    const src = new URL(widgetUrl, window.location.href);
    src.searchParams.set("site_id", siteId);
    src.searchParams.set("backend_http", backendHttp);
    src.searchParams.set("backend_ws", backendWs);
    src.searchParams.set("mode", embedMode);
    return src.toString();
  }

  function injectStyles() {
    if (document.getElementById("chatbot-loader-styles")) return;
    const style = document.createElement("style");
    style.id = "chatbot-loader-styles";
    style.textContent = `
      .chatbot-inline-frame {
        width: 100%;
        min-height: 620px;
        border: 0;
        border-radius: 24px;
        box-shadow: 0 22px 60px rgba(15, 23, 42, 0.16);
        background: #fff;
      }
      .chatbot-launcher {
        position: fixed;
        right: 20px;
        bottom: 20px;
        z-index: 9998;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        border: 0;
        border-radius: 999px;
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: #fff;
        padding: 14px 18px;
        font: 600 14px/1.1 'Segoe UI', sans-serif;
        box-shadow: 0 18px 45px rgba(37, 99, 235, 0.35);
        cursor: pointer;
      }
      .chatbot-launcher-icon {
        width: 22px;
        height: 22px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
      }
      .chatbot-panel {
        position: fixed;
        right: 20px;
        bottom: 88px;
        width: min(420px, calc(100vw - 24px));
        height: min(680px, calc(100dvh - 110px));
        border: 0;
        border-radius: 24px;
        background: #fff;
        box-shadow: 0 30px 80px rgba(15, 23, 42, 0.24);
        overflow: hidden;
        z-index: 9999;
        opacity: 0;
        pointer-events: none;
        transform: translateY(16px) scale(0.98);
        transition: opacity 0.2s ease, transform 0.2s ease;
      }
      .chatbot-panel.is-open {
        opacity: 1;
        pointer-events: auto;
        transform: translateY(0) scale(1);
      }
      @media (max-width: 640px) {
        .chatbot-inline-frame {
          min-height: 100dvh;
          border-radius: 0;
          box-shadow: none;
        }
        .chatbot-launcher {
          right: 14px;
          bottom: 14px;
          padding: 13px 16px;
        }
        .chatbot-panel {
          right: 0;
          bottom: 0;
          width: 100vw;
          height: 100dvh;
          border-radius: 0;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function renderInline(target) {
    const frame = document.createElement("iframe");
    frame.src = buildSrc("inline");
    frame.title = launcherLabel;
    frame.className = "chatbot-inline-frame";
    frame.loading = "lazy";
    target.appendChild(frame);
  }

  function renderPopup() {
    const launcher = document.createElement("button");
    launcher.type = "button";
    launcher.className = "chatbot-launcher";
    launcher.innerHTML = `<span class="chatbot-launcher-icon">?</span><span>${launcherLabel}</span>`;

    const panel = document.createElement("iframe");
    panel.src = buildSrc("panel");
    panel.title = launcherLabel;
    panel.className = "chatbot-panel";
    panel.loading = "lazy";

    const setOpen = (open) => {
      panel.classList.toggle("is-open", open);
      launcher.setAttribute("aria-expanded", open ? "true" : "false");
    };

    launcher.addEventListener("click", () => {
      setOpen(!panel.classList.contains("is-open"));
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setOpen(false);
    });

    window.addEventListener("message", (event) => {
      if (event.data && event.data.type === "chatbot:close") {
        setOpen(false);
      }
    });

    document.body.appendChild(panel);
    document.body.appendChild(launcher);
  }

  injectStyles();

  if (mode === "inline") {
    const target = inlineTarget ? document.querySelector(inlineTarget) : null;
    if (!target) return;
    renderInline(target);
    return;
  }

  renderPopup();
})();
