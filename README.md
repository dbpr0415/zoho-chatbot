# ⚡ Zoho Project Assistant — Enterprise AI Chatbot

A production-grade AI agent system for Zoho Projects. Built with **FastAPI**, **LangGraph**, and **React**.
Designed to be robust, deterministic, and modular, featuring a multi-agent architecture with a strict Human-in-the-Loop (HIL) execution pipeline.

## 🎯 Architecture & AI Orchestration

The system enforces strict boundaries between **Natural Language Understanding (LLM)** and **Deterministic Execution (Backend Code)** to prevent hallucinations and unsafe actions.

```text
User Input
   │
[ Frontend (Vercel) ] ──(HTTP POST)──▶ [ FastAPI Routing (Railway) ]
                                              │
                                 [ LangGraph StateMachine ]
                                              │
         [ Supervisor LLM ] ──(Intent)──▶ "query" OR "action"
                                              │
                        ┌─────────────────────┴─────────────────────┐
                  [ QueryAgent ]                              [ ActionAgent ]
                   (Read Only)                                 (Write Only)
                        │                                           │
         [ LangChain Tool Bindings ]                 [ LangChain Tool Bindings ]
                        │                                           │
                  [ Query Tools ]                             [ HIL Service ]
                        │                                           │
                        ▼                                           ▼
         [ Zoho API Client (Execute) ]               [ EntityResolutionService ] (Fuzzy Match)
                                                                    │
                                                                    ▼
                                                     [ Pending Actions DB ] (Store for Approval)
```

### Agent Specialization

| Agent | Responsibility |
|---|---|
| **Supervisor** | Routes messages based on intent. Prevents monolithic agent instruction collisions. |
| **Query Agent** | Read-only operations (`list_projects`, `list_tasks`, `get_task_details`). |
| **Action Agent** | Write operations (`create_task`, `update_task`, `delete_task`). Strictly regulated by HIL. |

---

## 🛠 Project Structure

The repository is modular and structured for scalable PaaS deployment (Railway + Vercel):

```text
zoho-project-assistant/
├── backend/                 # Deploys to Railway (FastAPI)
│   ├── app/
│   │   ├── agents/          # Self-contained AI agents & Supervisor
│   │   ├── auth/            # Zoho OAuth logic
│   │   ├── executors/       # Command pattern execution logic
│   │   ├── formatters/      # Output hydration
│   │   ├── memory/          # Memory storage layer
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Orchestration (HIL, Memory, SafeExecutor)
│   │   ├── tools/           # LLM Tool bindings and schema interfaces
│   │   ├── utils/           # Fuzzy matcher & entity resolution
│   │   └── zoho/            # Raw HTTP clients
├── frontend/                # Deploys to Vercel (React / Vite SPA)
├── README.md                
└── .gitignore
```

---

## 🚀 Environment Setup (Local)

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- A [Groq API key](https://console.groq.com)
- Zoho API Credentials (from `api-console.zoho.in`)

### 2. Local Setup
Clone and configure:
```bash
git clone https://github.com/YOUR_USERNAME/zoho-project-assistant.git
cd zoho-project-assistant
```

**Backend:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill .env with your ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd ../frontend
npm install
npm run dev
```
Access the local application at `http://localhost:5173`.

---

## ☁️ Production Deployment

The project is optimized for modern PaaS platforms without the need for complex containerization overhead.

### Backend (Railway)
1. Create a new project on [Railway.app](https://railway.app).
2. Connect the GitHub repository and set the Root Directory to `/backend`.
3. Railway's Nixpacks will automatically detect FastAPI and install dependencies from `requirements.txt`.
4. Attach a **Railway Volume** mapped to `/data` to persist the SQLite database.
5. Add production environment variables (`ZOHO_CLIENT_ID`, `GROQ_API_KEY`, etc.).

### Frontend (Vercel)
1. Create a new project on [Vercel.com](https://vercel.com).
2. Connect the GitHub repository and set the Root Directory to `/frontend`.
3. Set the `VITE_API_URL` environment variable to point to your Railway backend URL.
4. Deploy the React SPA.

---

## 🔐 API Flow & Auth Configuration

1. Register an application at `api-console.zoho.in`.
2. Add Authorized Redirect URIs for both Local (`http://localhost:8000/auth/callback`) and Production (your Railway URL).
3. Update `.env`:
```env
ZOHO_CLIENT_ID=your_id
ZOHO_CLIENT_SECRET=your_secret
ZOHO_REDIRECT_URI=http://localhost:8000/auth/callback
ZOHO_PORTAL_NAME=your_portal
GROQ_API_KEY=gsk_your_key
FRONTEND_URL=http://localhost:5173
```

---
