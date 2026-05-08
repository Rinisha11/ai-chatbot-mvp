# AI Chatbot MVP

Phase 1 multi-client AI chatbot/widget MVP for websites and apps.

## Local Run

1. Copy [backend/.env.example](C:/Users/hp1lk/Downloads/chatbot/ai-chatbot-mvp-v1/backend/.env.example:1) to `backend/.env`
2. Set `OPENAI_API_KEY` and `JWT_SECRET_KEY`
3. Start backend:

```powershell
cd C:\Users\hp1lk\Downloads\chatbot\ai-chatbot-mvp-v1\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5001
```

Use this exact path if PowerShell has issues with the relative one:

```powershell
C:\Users\hp1lk\Downloads\chatbot\ai-chatbot-mvp-v1\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5001
```

4. Start static frontend:

```powershell
cd C:\Users\hp1lk\Downloads\chatbot\ai-chatbot-mvp-v1
C:\Users\hp1lk\Downloads\chatbot\ai-chatbot-mvp-v1\.venv\Scripts\python.exe -m http.server 5500 --bind 127.0.0.1
```

5. Open:
- `http://127.0.0.1:5001/healthz`
- `http://127.0.0.1:5500/website_demo.html`

## Client Configuration

Client/site-specific settings live in [sites.json](C:/Users/hp1lk/Downloads/chatbot/ai-chatbot-mvp-v1/sites.json:1).

Each site can override:
- chatbot name
- welcome message
- allowed origins
- retrieval directory
- prompt suffix
- widget theme colors
- avatar text

## Production Prep

- Use [backend/.env.production.example](C:/Users/hp1lk/Downloads/chatbot/ai-chatbot-mvp-v1/backend/.env.production.example:1) as the server template
- Never commit real `.env` files
- Rotate any exposed OpenAI keys before deployment
- Rotate the JWT secret before deployment
