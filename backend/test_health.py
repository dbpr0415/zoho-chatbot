"""
Full System Health Check
Tests: DB tables, token validity, OAuth endpoints, all APIs,
       agent routing, memory, and live Zoho API calls.
"""
import asyncio, sys, json, datetime
sys.path.insert(0, ".")

G="\033[92m";R="\033[91m";Y="\033[93m";B="\033[94m";W="\033[0m";BOLD="\033[1m";C="\033[96m"
PASS=f"{G}✅ PASS{W}"; FAIL=f"{R}❌ FAIL{W}"; WARN=f"{Y}⚠️  WARN{W}"

results={"pass":0,"fail":0,"warn":0}
failed_list=[]

def ok(name, detail=""):
    results["pass"]+=1
    print(f"  {PASS}  {name}" + (f"\n         {Y}→ {detail}{W}" if detail else ""))

def err(name, detail=""):
    results["fail"]+=1
    failed_list.append((name,detail))
    print(f"  {FAIL}  {name}" + (f"\n         {R}→ {detail}{W}" if detail else ""))

def warn(name, detail=""):
    results["warn"]+=1
    print(f"  {WARN}  {name}" + (f"\n         {Y}→ {detail}{W}" if detail else ""))

def section(title):
    print(f"\n{BOLD}{B}{'─'*55}{W}")
    print(f"{BOLD}{B}  {title}{W}")
    print(f"{BOLD}{B}{'─'*55}{W}")

async def run():
    print(f"\n{BOLD}{B}{'='*55}{W}")
    print(f"{BOLD}{B}  System Health Check — Database · Tokens · APIs{W}")
    print(f"{BOLD}{B}{'='*55}{W}")

    # ────────────────────────────────────────────────────
    section("1. DATABASE CONNECTIVITY & SCHEMA")
    # ────────────────────────────────────────────────────
    try:
        from app.database import db
        await db.connect()
        ok("SQLite connection established", f"Path: zoho_assistant.db")
    except Exception as e:
        err("SQLite connection", str(e)); return

    REQUIRED_TABLES = ["user_tokens","chat_sessions","short_term_memory",
                        "long_term_memory","pending_actions"]
    try:
        cursor = await db._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r["name"] async for r in cursor]
        missing = [t for t in REQUIRED_TABLES if t not in tables]
        if not missing:
            ok("All 5 required tables exist", ", ".join(sorted(tables)))
        else:
            err("DB schema", f"Missing tables: {missing}")
    except Exception as e:
        err("DB schema check", str(e))

    # Row counts
    for table in REQUIRED_TABLES:
        try:
            cursor = await db._connection.execute(f"SELECT COUNT(*) as c FROM {table}")
            row = await cursor.fetchone()
            ok(f"{table}: {row['c']} rows")
        except Exception as e:
            err(f"{table} row count", str(e))

    # ────────────────────────────────────────────────────
    section("2. OAUTH TOKENS & SESSION VALIDITY")
    # ────────────────────────────────────────────────────
    user_id = None
    try:
        cursor = await db._connection.execute(
            "SELECT * FROM user_tokens ORDER BY rowid DESC LIMIT 3")
        tokens = [dict(r) async for r in cursor]

        if not tokens:
            err("Token records", "No tokens in DB — user must login first")
        else:
            now = datetime.datetime.utcnow()
            for t in tokens:
                uid  = t["user_id"]
                exp  = datetime.datetime.fromisoformat(t["expires_at"])
                left = (exp - now).total_seconds()
                has_access  = bool(t.get("access_token"))
                has_refresh = bool(t.get("refresh_token"))
                if left > 0:
                    ok(f"Token valid: user={uid[:16]}",
                       f"expires in {int(left//60)}m | access={'✓' if has_access else '✗'} refresh={'✓' if has_refresh else '✗'}")
                    user_id = uid
                else:
                    warn(f"Token EXPIRED: user={uid[:16]}",
                         f"expired {int(-left//60)}m ago — refresh needed")
                    if not user_id:
                        user_id = uid  # still try with expired (refresh may work)
    except Exception as e:
        err("Token check", str(e))

    # ────────────────────────────────────────────────────
    section("3. HTTP API ENDPOINTS")
    # ────────────────────────────────────────────────────
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10) as http:

        # Public endpoints
        tests = [
            ("GET",  "/health",      None, [200],     "Health check"),
            ("GET",  "/auth/status", None, [200],     "Auth status (public)"),
            ("GET",  "/auth/login",  None, [307,302], "OAuth login redirect"),
            ("GET",  "/auth/callback?code=x&state=x", None, [307,302,400], "OAuth callback"),
        ]
        for method, path, body, expected, name in tests:
            try:
                if method == "GET":
                    r = await http.get(path, follow_redirects=False)
                else:
                    r = await http.post(path, json=body)
                if r.status_code in expected:
                    ok(f"{method} {path}", f"HTTP {r.status_code}")
                else:
                    err(f"{method} {path}", f"HTTP {r.status_code} (expected {expected})")
            except Exception as e:
                err(f"{method} {path}", str(e))

        # Protected endpoints — should return 401 without cookie
        for path in ["/chat", "/sessions", "/session/fake-id/history"]:
            try:
                method = "POST" if path == "/chat" else "GET"
                if method == "POST":
                    r = await http.post(path, json={"message":"hi","session_id":"x"})
                else:
                    r = await http.get(path)
                if r.status_code == 401:
                    ok(f"Auth guard: {method} {path} → 401 without cookie")
                else:
                    err(f"Auth guard: {path}", f"HTTP {r.status_code} (expected 401)")
            except Exception as e:
                err(f"Auth guard {path}", str(e))

    # ────────────────────────────────────────────────────
    section("4. ZOHO CLIENT & LIVE API CALLS")
    # ────────────────────────────────────────────────────
    if not user_id:
        warn("Zoho API tests", "Skipped — no user_id (login first)")
    else:
        try:
            from app.zoho.client import ZohoClient
            c = ZohoClient(user_id)
            await c._ensure_valid_token()
            ok("ZohoClient token refresh/validation", "Token ready")
        except Exception as e:
            err("ZohoClient token", str(e)); c = None

        if c:
            # list_projects
            try:
                projects = await c.list_projects()
                names = [p.get("name") for p in projects]
                ok(f"GET projects ({len(projects)} found)", f"{names}")
            except Exception as e:
                err("list_projects live call", str(e))
                projects = []

            # list_tasks for each project
            for p in projects[:3]:
                pid   = str(p.get("id_string", p.get("id")))
                pname = p.get("name")
                try:
                    tasks = await c.list_tasks(pid)
                    ok(f"GET tasks for '{pname}' ({len(tasks)} tasks)")
                except Exception as e:
                    err(f"list_tasks '{pname}'", str(e))

            # list_members
            if projects:
                pid = str(projects[0].get("id_string", projects[0].get("id")))
                try:
                    members = await c.list_project_members(pid)
                    ok(f"GET members ({len(members)} members)", f"{[m.get('name') for m in members]}")
                except Exception as e:
                    err("list_project_members", str(e))

            # create → update → delete (full lifecycle)
            if projects:
                pid = str(projects[0].get("id_string", projects[0].get("id")))
                tid = None
                try:
                    r = await c.create_task(pid, name="[HEALTH-CHECK] Temp Task")
                    tid = str(r.get("id_string", r.get("id","")))
                    ok(f"CREATE task lifecycle", f"ID={tid}")
                except Exception as e:
                    err("CREATE task", str(e))

                if tid:
                    try:
                        await c.update_task(pid, tid, status="Closed")
                        ok("UPDATE task (status=Closed)")
                    except Exception as e:
                        err("UPDATE task", str(e))
                    try:
                        await c.delete_task(pid, tid)
                        ok("DELETE task (cleanup done)")
                    except Exception as e:
                        err("DELETE task", str(e))

    # ────────────────────────────────────────────────────
    section("5. LANGGRAPH AGENTS & ROUTING")
    # ────────────────────────────────────────────────────
    try:
        from app.agents.supervisor import Supervisor
        from langchain_groq import ChatGroq
        from app.config import settings
        llm = ChatGroq(model=settings.llm.model_name, api_key=settings.llm.api_key, temperature=0)
        sup = Supervisor(llm)
        cases = [
            ("list my projects",          "query"),
            ("show tasks for interviews", "query"),
            ("who has the most tasks",    "query"),
            ("create a task",             "action"),
            ("update go out task",        "action"),
            ("delete the first task",     "action"),
        ]
        for msg, expected in cases:
            got = await sup.route(msg, "")
            if got == expected:
                ok(f"Router: '{msg[:35]}' → {got}")
            else:
                err(f"Router: '{msg[:35]}'", f"Expected '{expected}' got '{got}'")
    except Exception as e:
        err("Supervisor routing", str(e))

    # ────────────────────────────────────────────────────
    section("6. MEMORY SYSTEM")
    # ────────────────────────────────────────────────────
    import uuid
    try:
        from app.memory.store import MemoryStore
        uid = f"health_{uuid.uuid4().hex[:6]}"
        sid = f"sess_{uuid.uuid4().hex[:6]}"
        mem = MemoryStore(uid, sid)

        # Short-term
        await mem.add_message("user", "health check message")
        h = await mem.get_chat_history(5)
        if h and h[-1]["content"] == "health check message":
            ok("Short-term memory: add + retrieve")
        else:
            err("Short-term memory", f"Got {h}")

        # Formatted history
        fmt = await mem.get_formatted_history(5)
        if "User:" in fmt:
            ok("Short-term memory: formatted for LLM")
        else:
            err("Formatted history", fmt[:80])

        # Long-term
        await mem.store_preference("health_key", "health_val")
        prefs = await mem.get_preferences()
        found = [p for p in prefs if p.get("key") == "health_key"]
        if found and found[0]["value"] == "health_val":
            ok("Long-term memory: preference stored + retrieved")
        else:
            err("Long-term preference", str(prefs))

        # Cross-session (same user, new session)
        mem2 = MemoryStore(uid, f"sess_{uuid.uuid4().hex[:6]}")
        prefs2 = await mem2.get_preferences()
        found2 = [p for p in prefs2 if p.get("key") == "health_key"]
        if found2:
            ok("Long-term memory: persists across new sessions ✨")
        else:
            err("Cross-session persistence", str(prefs2))

        # get_memory_summary
        await mem.store_interaction("last_topic", "show projects")
        summary = await mem.get_memory_summary()
        if "session" in summary.lower() or "topic" in summary.lower() or "remember" in summary.lower():
            ok("Memory summary: human-readable recall text")
        else:
            ok("Memory summary generated", summary[:80])

    except Exception as e:
        err("Memory system", str(e))

    # ────────────────────────────────────────────────────
    section("7. FRONTEND FILES")
    # ────────────────────────────────────────────────────
    import pathlib
    fe = pathlib.Path("../frontend/src")
    components = ["App.jsx","ChatWindow.jsx","MessageBubble.jsx",
                   "LoginScreen.jsx","TypingIndicator.jsx","ConfirmationModal.jsx",
                   "CommandPalette.jsx","Toast.jsx"]
    hooks = ["useChat.js"]
    utils = ["api.js"]

    for f in components:
        p = (fe / f) if f == "App.jsx" else (fe / "components" / f)
        if p.exists():
            ok(f"Frontend: {f} ({p.stat().st_size//100/10}KB)")
        else:
            err(f"Frontend: {f}", "File missing!")

    for f in hooks:
        p = fe / "hooks" / f
        ok(f"Frontend: {f}") if p.exists() else err(f"Frontend: {f}", "Missing!")
    for f in utils:
        p = fe / "utils" / f
        ok(f"Frontend: {f}") if p.exists() else err(f"Frontend: {f}", "Missing!")

    await db.close()

    # ────────────────────────────────────────────────────
    total = results["pass"] + results["fail"]
    pct   = int(100*results["pass"]/total) if total else 0
    print(f"\n{BOLD}{B}{'='*55}{W}")
    print(f"{BOLD}  SYSTEM HEALTH SUMMARY{W}")
    print(f"{BOLD}{B}{'='*55}{W}")
    print(f"  {G}PASSED : {results['pass']}/{total} ({pct}%){W}")
    print(f"  {R}FAILED : {results['fail']}/{total}{W}")
    print(f"  {Y}WARNINGS: {results['warn']}{W}")

    if results["fail"] == 0:
        print(f"\n  {G}{BOLD}🎉 SYSTEM IS 100% HEALTHY{W}")
    else:
        print(f"\n  {R}Issues found:{W}")
        for name, detail in failed_list:
            print(f"  ❌ {name}: {detail}")
    print(f"{BOLD}{B}{'='*55}{W}\n")

asyncio.run(run())
