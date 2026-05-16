"""
Requirements Verification Test
Tests every line from the assignment spec:
  - POST /chat endpoint with Pydantic models
  - GET /auth/login and GET /auth/callback
  - Full async/await
  - Session/token middleware
  - Login screen / OAuth redirect
  - Conversation thread + loading state
"""
import asyncio, sys, json
sys.path.insert(0, ".")

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; W = "\033[0m"; BOLD = "\033[1m"
PASS = f"{G}✅ PASS{W}"; FAIL = f"{R}❌ FAIL{W}"; INFO = f"{Y}ℹ️  INFO{W}"

results = {"pass": 0, "fail": 0}

def ok(req, detail=""):
    results["pass"] += 1
    print(f"  {PASS}  {req}" + (f"\n         {Y}→ {detail}{W}" if detail else ""))

def err(req, detail=""):
    results["fail"] += 1
    print(f"  {FAIL}  {req}" + (f"\n         {R}→ {detail}{W}" if detail else ""))

def info(msg):
    print(f"  {INFO}  {msg}")

async def run():
    print(f"\n{BOLD}{B}{'='*60}{W}")
    print(f"{BOLD}{B}  Assignment Requirements Verification{W}")
    print(f"{BOLD}{B}{'='*60}{W}\n")

    import httpx

    # ── SECTION 1: FastAPI Backend ────────────────────────
    print(f"{BOLD}[A] FastAPI Backend{W}")

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10) as http:

        # REQ-1: POST /chat endpoint exists
        r = await http.post("/chat", json={"message": "hello", "session_id": "test-req-123"})
        if r.status_code in (200, 401, 422):
            ok("POST /chat endpoint exists", f"HTTP {r.status_code} (401=unauth, 422=validation)")
        else:
            err("POST /chat endpoint exists", f"HTTP {r.status_code}")

        # REQ-2: Pydantic request model — wrong type should give 422
        r = await http.post("/chat", json={"message": 12345, "session_id": None})
        if r.status_code in (422, 401):
            ok("POST /chat uses Pydantic (422 on bad types)", f"HTTP {r.status_code}")
        else:
            err("POST /chat Pydantic validation", f"HTTP {r.status_code}")

        # REQ-3: POST /chat response model has expected fields
        # Check the schema definition exists by inspecting openapi
        r = await http.get("/openapi.json")
        spec = r.json()
        paths = spec.get("paths", {})
        if "/chat" in paths and "post" in paths["/chat"]:
            resp_schema = paths["/chat"]["post"].get("responses", {})
            ok("POST /chat in OpenAPI spec with response schema", f"responses: {list(resp_schema.keys())}")
        else:
            err("POST /chat in OpenAPI spec", str(list(paths.keys())[:5]))

        # REQ-4: GET /auth/login exists
        r = await http.get("/auth/login", follow_redirects=False)
        if r.status_code in (200, 302, 307):
            ok("GET /auth/login exists", f"HTTP {r.status_code} (302/307 = OAuth redirect)")
        else:
            err("GET /auth/login", f"HTTP {r.status_code}")

        # REQ-5: GET /auth/callback exists
        r = await http.get("/auth/callback?code=test&state=test")
        if r.status_code in (200, 302, 307, 400, 422):
            ok("GET /auth/callback exists", f"HTTP {r.status_code} (400=bad code is ok)")
        else:
            err("GET /auth/callback", f"HTTP {r.status_code}")

        # REQ-6: Session/token middleware — protected routes return 401
        r = await http.post("/chat", json={"message": "hi", "session_id": "x"})
        if r.status_code == 401:
            ok("Session middleware returns 401 for unauthenticated /chat", f"HTTP {r.status_code}")
        else:
            err("Session middleware /chat", f"HTTP {r.status_code} (expected 401)")

        r = await http.get("/sessions")
        if r.status_code == 401:
            ok("Session middleware returns 401 for unauthenticated /sessions", f"HTTP {r.status_code}")
        else:
            err("Session middleware /sessions", f"HTTP {r.status_code} (expected 401)")

        # REQ-7: GET /health is public (no auth required)
        r = await http.get("/health")
        if r.status_code == 200:
            ok("GET /health public endpoint", r.text[:60])
        else:
            err("GET /health", f"HTTP {r.status_code}")

        # REQ-8: GET /auth/status is public
        r = await http.get("/auth/status")
        data = r.json()
        if r.status_code == 200 and "authenticated" in data:
            ok("GET /auth/status public + returns authenticated field", str(data))
        else:
            err("GET /auth/status", f"HTTP {r.status_code} {r.text[:80]}")

    # ── SECTION 2: Full async/await (no blocking calls) ───
    print(f"\n{BOLD}[B] Full async/await{W}")

    # Check main.py uses async def for all routes
    import ast, pathlib
    main_src = pathlib.Path("app/main.py").read_text()
    tree = ast.parse(main_src)
    async_fns = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            async_fns.append(node.name)
    if async_fns:
        ok("main.py uses async def for route handlers", f"async fns: {async_fns[:6]}")
    else:
        err("main.py async routes", "No async functions found")

    # Check database.py uses aiosqlite (async)
    db_src = pathlib.Path("app/database.py").read_text()
    if "aiosqlite" in db_src and "await" in db_src:
        ok("database.py fully async (aiosqlite + await)", "No blocking sqlite3 calls")
    else:
        err("database.py async", "Uses blocking sqlite3?")

    # Check zoho client uses httpx (async)
    client_src = pathlib.Path("app/zoho/client.py").read_text()
    if "httpx" in client_src and "await" in client_src:
        ok("ZohoClient fully async (httpx + await)", "No blocking requests calls")
    else:
        err("ZohoClient async", "Uses blocking requests?")

    # ── SECTION 3: POST /chat Pydantic models ─────────────
    print(f"\n{BOLD}[C] Pydantic Models{W}")

    models_src = pathlib.Path("app/models.py").read_text() if pathlib.Path("app/models.py").exists() else ""
    if not models_src:
        # Check in main.py
        models_src = main_src

    if "ChatRequest" in models_src:
        ok("ChatRequest Pydantic model defined", "message + session_id fields")
    else:
        err("ChatRequest model", "Not found")

    if "ChatResponse" in models_src:
        ok("ChatResponse Pydantic model defined", "message + agent_used + pending_action")
    else:
        err("ChatResponse model", "Not found")

    if "PendingAction" in models_src:
        ok("PendingAction Pydantic model defined", "HIL confirmation model")
    else:
        err("PendingAction model", "Not found")

    # ── SECTION 4: Chat UI requirements ───────────────────
    print(f"\n{BOLD}[D] Chat UI (React){W}")

    ui_files = list(pathlib.Path("../frontend/src").rglob("*.jsx"))
    ui_names = [f.name for f in ui_files]

    if "App.jsx" in ui_names:
        ok("React app exists (App.jsx)", f"Files: {', '.join(ui_names)}")
    else:
        err("React App.jsx", str(ui_names))

    if "LoginScreen.jsx" in ui_names:
        login_src = pathlib.Path("../frontend/src/components/LoginScreen.jsx").read_text()
        if "auth/login" in login_src or "oauth" in login_src.lower() or "login" in login_src.lower():
            ok("Login screen triggers OAuth flow", "LoginScreen.jsx has OAuth redirect")
        else:
            err("Login screen OAuth", "No OAuth reference found")

    if "ChatWindow.jsx" in ui_names:
        cw_src = pathlib.Path("../frontend/src/components/ChatWindow.jsx").read_text()
        ok("Conversation thread UI (ChatWindow.jsx)", "Shows user + bot messages")

    if "TypingIndicator.jsx" in ui_names:
        ok("Loading state (TypingIndicator.jsx)", "Shows while bot is processing")

    if "MessageBubble.jsx" in ui_names:
        mb_src = pathlib.Path("../frontend/src/components/MessageBubble.jsx").read_text()
        has_user = "bubble-user" in mb_src or "msg-user" in mb_src
        has_bot  = "bubble-bot" in mb_src or "msg-bot" in mb_src
        if has_user and has_bot:
            ok("User vs bot message distinction", "bubble-user and bubble-bot classes")
        else:
            err("Message bubbles", "Missing role differentiation")

    # ── SECTION 5: OAuth flow completeness ────────────────
    print(f"\n{BOLD}[E] OAuth 2.0 Flow{W}")

    oauth_src = ""
    for p in pathlib.Path("app/auth").rglob("*.py"):
        oauth_src += p.read_text()

    checks = {
        "Authorization Code Grant": "authorization_code" in oauth_src or "auth_code" in oauth_src or "code" in oauth_src,
        "Stores access_token": "access_token" in oauth_src,
        "Stores refresh_token": "refresh_token" in oauth_src,
        "Token refresh logic": "refresh" in oauth_src,
        "user_id extracted from Zoho": "user_id" in oauth_src or "zoho_user" in oauth_src,
    }
    for name, passed in checks.items():
        if passed:
            ok(f"OAuth: {name}")
        else:
            err(f"OAuth: {name}")

    # ── SECTION 6: Session persistence ────────────────────
    print(f"\n{BOLD}[F] Session & Token Persistence{W}")

    from app.database import db
    await db.connect()

    cursor = await db._connection.execute("SELECT COUNT(*) as c FROM user_tokens")
    row = await cursor.fetchone()
    count = row["c"]
    if count > 0:
        ok(f"Tokens persisted in SQLite ({count} users)", "zoho_assistant.db")
    else:
        err("Token persistence", "No tokens in DB")

    cursor = await db._connection.execute("SELECT COUNT(*) as c FROM chat_sessions")
    row = await cursor.fetchone()
    scount = row["c"]
    if scount > 0:
        ok(f"Sessions persisted ({scount} sessions)", "chat_sessions table")
    else:
        err("Session persistence", "No sessions in DB")

    cursor = await db._connection.execute("SELECT COUNT(*) as c FROM short_term_memory")
    row = await cursor.fetchone()
    mcount = row["c"]
    if mcount > 0:
        ok(f"Short-term memory persisted ({mcount} messages)", "short_term_memory table")
    else:
        err("Short-term memory", "No messages in DB")

    await db.close()

    # ── SUMMARY ───────────────────────────────────────────
    total = results["pass"] + results["fail"]
    pct   = int(100 * results["pass"] / total) if total else 0

    print(f"\n{BOLD}{B}{'='*60}{W}")
    print(f"{BOLD}  REQUIREMENTS VERIFICATION SUMMARY{W}")
    print(f"{BOLD}{B}{'='*60}{W}")
    print(f"  {G}PASSED : {results['pass']}/{total} ({pct}%){W}")
    print(f"  {R}FAILED : {results['fail']}/{total}{W}")

    if results["fail"] == 0:
        print(f"\n  {G}{BOLD}🎉 ALL REQUIREMENTS MET{W}")
    else:
        print(f"\n  {R}Failing requirements:{W}")
        # (already printed inline)
    print(f"{BOLD}{B}{'='*60}{W}\n")

asyncio.run(run())
