# ⚡ Zoho Project Assistant — AI Chatbot

An AI-powered chatbot for Zoho Projects built with **LangGraph**, **FastAPI**, and **React**. 
Uses a multi-agent architecture with Human-in-the-Loop confirmation for all write operations.

## 🎯 Demo

> **Live Demo:** [https://your-vercel-url.vercel.app](https://your-vercel-url.vercel.app)  
> **Backend API:** [https://your-railway-url.railway.app](https://your-railway-url.railway.app)

---

## 🧠 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   React Frontend (Vercel)                 │
│   ChatWindow · Sidebar · CommandPalette · Toast          │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTPS + SameSite=None cookies
                        ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (Railway)                    │
│                                                           │
│  ┌──────────┐    ┌─────────────────────────────────┐    │
│  │  OAuth   │    │         LangGraph Graph           │    │
│  │  ZohoOAuth│    │                                  │    │
│  └──────────┘    │  ┌──────────┐                    │    │
│                  │  │Supervisor│ ← Routes messages   │    │
│  ┌──────────┐    │  └────┬─────┘                    │    │
│  │MemoryStore│   │       │                           │    │
│  │ Short-term│   │  ┌────┴──────┐ ┌──────────────┐  │    │
│  │ Long-term │   │  │QueryAgent │ │ ActionAgent  │  │    │
│  └──────────┘    │  │(read ops) │ │(write + HIL) │  │    │
│                  │  └─────┬─────┘ └──────┬───────┘  │    │
│  ┌──────────┐    │        └──────┬────────┘          │    │
│  │ZohoClient│◄───┤         8 Tools                   │    │
│  │ httpx    │    │  list·get·create·update·delete    │    │
│  └──────────┘    └─────────────────────────────────┘    │
│                                                           │
│  ┌──────────┐                                            │
│  │ SQLite DB│  (Railway Persistent Volume /data/)        │
│  │user_tokens│                                           │
│  │sessions  │                                            │
│  │memory    │                                            │
│  └──────────┘                                            │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
                  Zoho Projects API
```

### Agent Responsibilities

| Agent | Handles | Tools |
|---|---|---|
| **Supervisor** | Routes every message to the correct agent | LLM-based routing |
| **Query Agent** | All read operations | `list_projects`, `list_tasks`, `get_task_details`, `list_project_members`, `get_task_utilisation` |
| **Action Agent** | All write operations + HIL confirmation | `create_task`, `update_task`, `delete_task` |

---

## 🚀 Quick Start (Local)

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Zoho account with a project
- A free [Groq API key](https://console.groq.com)

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/zoho-project-assistant.git
cd zoho-project-assistant
```

### 2. Backend setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials (see OAuth Configuration below)
```

### 3. Frontend setup
```bash
cd ../frontend
npm install
# No .env needed for local dev — Vite proxy handles API calls
```

### 4. Run locally
```bash
# Terminal 1 — Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

---

## 🔐 OAuth Configuration Guide

### Step 1 — Create Zoho OAuth Client

1. Go to [api-console.zoho.in](https://api-console.zoho.in)
2. Click **Add Client** → choose **Server-based Applications**
3. Fill in:
   - **Client Name:** Zoho Project Assistant
   - **Homepage URL:** `http://localhost:5173` (local) or your Vercel URL (prod)
   - **Authorized Redirect URIs:**
     - Local: `http://localhost:8000/auth/callback`
     - Production: `https://YOUR-RAILWAY-URL.railway.app/auth/callback`
4. Copy the **Client ID** and **Client Secret**

### Step 2 — Find your Portal Name

1. Go to [projects.zoho.in](https://projects.zoho.in)
2. The URL shows: `https://projects.zoho.in/portal/YOUR_PORTAL_NAME/`
3. Copy `YOUR_PORTAL_NAME`

### Step 3 — Set environment variables

**Backend `.env`:**
```env
ZOHO_CLIENT_ID=1000.xxxxxxxxxxxxxxxxxxxx
ZOHO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ZOHO_REDIRECT_URI=http://localhost:8000/auth/callback
ZOHO_PORTAL_NAME=your-portal-name
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
FRONTEND_URL=http://localhost:5173
APP_SECRET_KEY=any-random-string-here
```

---

## ☁️ Production Deployment

### Backend → Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Select the `backend/` folder (or set Root Directory = `backend`)
3. Add environment variables in Railway dashboard:

```
ZOHO_CLIENT_ID          = (from Zoho Developer Console)
ZOHO_CLIENT_SECRET      = (from Zoho Developer Console)
ZOHO_REDIRECT_URI       = https://YOUR-RAILWAY-URL.railway.app/auth/callback
ZOHO_PORTAL_NAME        = your-portal-name
GROQ_API_KEY            = your-groq-key
FRONTEND_URL            = https://YOUR-VERCEL-URL.vercel.app
APP_SECRET_KEY          = (random 32+ char string)
DATABASE_PATH           = /data/zoho_assistant.db
IS_PRODUCTION           = true
```

4. Add a **Volume** in Railway:
   - Mount path: `/data`
   - This keeps the SQLite database alive across redeploys

5. Update the **Redirect URI** in your Zoho Developer Console to the Railway URL

### Frontend → Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project** → Import from GitHub
2. Set **Root Directory** = `frontend`
3. Add environment variable:
   ```
   VITE_API_URL = https://YOUR-RAILWAY-URL.railway.app
   ```
4. Deploy

### Update Zoho OAuth Redirect URI

In [api-console.zoho.in](https://api-console.zoho.in), add the production redirect URI:
```
https://YOUR-RAILWAY-URL.railway.app/auth/callback
```

---

## 💬 Sample Conversations

| User Says | Bot Does |
|---|---|
| `What projects do I have?` | Query Agent lists all projects |
| `Show tasks for the first one` | Remembers project (short-term memory), lists tasks |
| `Create a task called API Integration` | Action Agent asks for HIL confirmation |
| `Delete go out task` | Action Agent confirms before deleting |
| `Who has the most tasks?` | Query Agent returns task utilisation table |
| `What was I talking about?` | Recalls last session context (long-term memory) |

### Slash Commands
Type `/` in the chat to see all available commands:
- `/projects` — List all projects
- `/tasks` — Show tasks for a project
- `/create` — Create a new task
- `/update` — Update a task
- `/delete` — Delete a task
- `/members` — List project members
- `/utilisation` — Show task load per member
- `/memory` — Recall past context

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Vanilla CSS |
| **Backend** | FastAPI, Python 3.11+, Uvicorn |
| **AI/LLM** | LangGraph, LangChain, Groq (Llama 3.1) |
| **Memory** | SQLite (aiosqlite) — dual-layer (session + cross-session) |
| **Auth** | Zoho OAuth 2.0 Authorization Code Grant |
| **HTTP Client** | httpx (async) |
| **Deployment** | Vercel (frontend), Railway (backend) |

---

## 📁 Project Structure

```
zoho-project-assistant/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── graph.py          # LangGraph stateful graph
│   │   │   ├── supervisor.py     # LLM router
│   │   │   ├── query_agent.py    # Read operations
│   │   │   └── action_agent.py  # Write operations (HIL)
│   │   ├── auth/
│   │   │   ├── oauth.py          # Zoho OAuth flow
│   │   │   └── middleware.py     # Session cookie middleware
│   │   ├── memory/
│   │   │   └── store.py          # Dual-layer MemoryStore
│   │   ├── tools/
│   │   │   ├── query_tools.py    # 5 read tools
│   │   │   └── action_tools.py  # 3 write tools
│   │   ├── zoho/
│   │   │   └── client.py         # ZohoClient (async httpx)
│   │   ├── config.py             # Typed settings classes
│   │   ├── database.py           # SQLite (aiosqlite)
│   │   ├── models.py             # Pydantic models
│   │   └── main.py               # FastAPI app
│   ├── requirements.txt
│   ├── railway.toml              # Railway deployment config
│   └── Procfile
├── frontend/
│   ├── src/
│   │   ├── components/           # React components
│   │   ├── hooks/useChat.js      # State management
│   │   └── utils/api.js          # API client
│   ├── vercel.json               # Vercel SPA config
│   └── vite.config.js
└── README.md
```

---

## ⚠️ Known Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| **SQLite on Railway** | Data wiped if volume unmounts | Add Railway Persistent Volume at `/data` |
| **Zoho API rate limits** | Heavy use may hit limits | Groq LLM rate limits at ~30 req/min on free tier |
| **Single-portal support** | One Zoho portal per deployment | Change `ZOHO_PORTAL_NAME` env var |
| **Groq free tier** | 30 requests/minute LLM limit | Upgrade or use alternative LLM |
| **No real-time push** | Bot responses are pull-based (no WebSocket) | Acceptable for a chatbot UX |
| **Session cookies** | Requires same-origin or SameSite=None | Handled in production via `IS_PRODUCTION` flag |

---

## 🧪 Running Tests

```bash
cd backend && source venv/bin/activate

# Full system health check (45 tests)
python3 test_health.py

# All 8 Zoho tools (40 tests)
python3 test_8tools.py

# Memory system (14 tests)
python3 test_memory.py

# Sample conversations (5 end-to-end flows)
python3 test_sample_conversations.py

# Assignment requirements (28 checks)
python3 test_requirements.py
```

---

## 📝 License

MIT — free to use, modify, and distribute.
