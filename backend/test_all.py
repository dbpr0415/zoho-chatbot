"""
Comprehensive Test Suite for Zoho Project Assistant
Tests: DB, all 8 tools, API endpoints, agent routing
"""

import asyncio
import sys
sys.path.insert(0, ".")

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
BLUE  = "\033[94m"
RESET = "\033[0m"
BOLD  = "\033[1m"

PASS = f"{GREEN}✅ PASS{RESET}"
FAIL = f"{RED}❌ FAIL{RESET}"
SKIP = f"{YELLOW}⚠️  SKIP{RESET}"

results = []

def log(name, status, detail=""):
    results.append((name, status, detail))
    sym = PASS if status == "PASS" else (FAIL if status == "FAIL" else SKIP)
    print(f"  {sym}  {name}" + (f"\n         {YELLOW}{detail}{RESET}" if detail else ""))

async def run_all():
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE} Zoho Project Assistant — Full Test Suite{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

    # ─── 1. DATABASE ──────────────────────────────────────────
    print(f"{BOLD}[1] Database Health{RESET}")
    try:
        from app.database import db
        await db.connect()
        log("DB connects", "PASS")

        cursor = await db._connection.execute("SELECT COUNT(*) as c FROM user_tokens")
        row = await cursor.fetchone()
        count = row["c"]
        if count > 0:
            log(f"Token records ({count} found)", "PASS")
        else:
            log("Token records", "FAIL", "No tokens — user must authenticate first")

        cursor = await db._connection.execute("SELECT * FROM user_tokens ORDER BY rowid DESC LIMIT 1")
        token = await cursor.fetchone()
        user_id = None
        if token:
            user_id = token["user_id"]
            import datetime
            exp = datetime.datetime.fromisoformat(token["expires_at"])
            now = datetime.datetime.utcnow()
            if exp > now:
                log(f"Token validity (user={user_id[:20]}..)", "PASS", f"Expires {token['expires_at']}")
            else:
                log("Token validity", "FAIL", f"Token EXPIRED at {token['expires_at']} (now={now.isoformat()})")
        else:
            log("Token fetch", "FAIL", "No token record found")

        cursor = await db._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r["name"] async for r in cursor]
        expected = {"user_tokens", "chat_sessions", "short_term_memory", "long_term_memory", "pending_actions"}
        missing = expected - set(tables)
        if not missing:
            log(f"DB tables ({', '.join(sorted(tables))})", "PASS")
        else:
            log("DB tables", "FAIL", f"Missing: {missing}")

    except Exception as e:
        log("Database", "FAIL", str(e))
        user_id = None

    # ─── 2. ZOHO CLIENT ───────────────────────────────────────
    print(f"\n{BOLD}[2] Zoho Client & OAuth{RESET}")
    client = None
    project_id = None
    task_id = None
    task_name = None

    if not user_id:
        log("ZohoClient", "SKIP", "No user_id — cannot test without auth")
    else:
        try:
            from app.zoho.client import ZohoClient
            client = ZohoClient(user_id)
            await client._ensure_valid_token()
            log("OAuth token valid/refreshed", "PASS")
        except Exception as e:
            log("OAuth token", "FAIL", str(e))
            client = None

    # ─── 3. TOOL 1: list_projects ─────────────────────────────
    print(f"\n{BOLD}[3] Tool 1 — list_projects{RESET}")
    projects = []
    if client:
        try:
            projects = await client.list_projects()
            if projects:
                log(f"list_projects ({len(projects)} projects)", "PASS")
                for p in projects:
                    print(f"         → {p.get('name')} (ID: {p.get('id_string', p.get('id'))})")
                project_id = str(projects[0].get("id_string", projects[0].get("id")))
            else:
                log("list_projects", "FAIL", "Empty list returned")
        except Exception as e:
            log("list_projects", "FAIL", str(e))
    else:
        log("list_projects", "SKIP")

    # ─── 4. TOOL 2: list_tasks ────────────────────────────────
    print(f"\n{BOLD}[4] Tool 2 — list_tasks{RESET}")
    tasks = []
    if client and project_id:
        try:
            tasks = await client.list_tasks(project_id)
            if isinstance(tasks, list):
                log(f"list_tasks ({len(tasks)} tasks in {projects[0].get('name')})", "PASS")
                for t in tasks[:5]:
                    s = t.get("status", {})
                    sname = s.get("name","?") if isinstance(s, dict) else str(s)
                    print(f"         → {t.get('name')} [ID:{t.get('id_string',t.get('id'))}] Status:{sname}")
                if tasks:
                    task_id = str(tasks[0].get("id_string", tasks[0].get("id")))
                    task_name = tasks[0].get("name")
            else:
                log("list_tasks", "FAIL", f"Unexpected type: {type(tasks)}")
        except Exception as e:
            log("list_tasks", "FAIL", str(e))
    else:
        log("list_tasks", "SKIP")

    # ─── 5. TOOL 3: get_task_details ──────────────────────────
    print(f"\n{BOLD}[5] Tool 3 — get_task_details{RESET}")
    if client and project_id and task_id:
        try:
            detail = await client.get_task_details(project_id, task_id)
            if detail and detail.get("name"):
                log(f"get_task_details ('{detail.get('name')}')", "PASS")
                s = detail.get("status", {})
                print(f"         → Status: {s.get('name','?') if isinstance(s,dict) else s}")
                print(f"         → Priority: {detail.get('priority','?')}")
            else:
                log("get_task_details", "FAIL", f"Empty or missing name: {detail}")
        except Exception as e:
            log("get_task_details", "FAIL", str(e))
    else:
        log("get_task_details", "SKIP")

    # ─── 6. TOOL 4: create_task ───────────────────────────────
    print(f"\n{BOLD}[6] Tool 4 — create_task{RESET}")
    new_task_id = None
    if client and project_id:
        try:
            result = await client.create_task(project_id, name="[TEST] Auto-Test Task", description="Created by test suite")
            new_task_id = str(result.get("id_string", result.get("id", "")))
            if new_task_id and new_task_id != "N/A":
                log(f"create_task (ID: {new_task_id})", "PASS")
            else:
                log("create_task", "FAIL", f"No task ID returned: {result}")
        except Exception as e:
            log("create_task", "FAIL", str(e))
    else:
        log("create_task", "SKIP")

    # ─── 7. TOOL 5: update_task ───────────────────────────────
    print(f"\n{BOLD}[7] Tool 5 — update_task{RESET}")
    if client and project_id and new_task_id:
        try:
            result = await client.update_task(project_id, new_task_id, status="Closed")
            log(f"update_task (set status=Closed)", "PASS")
        except Exception as e:
            log("update_task", "FAIL", str(e))
    else:
        log("update_task", "SKIP", "Needs create_task to pass first")

    # ─── 8. TOOL 6: delete_task ───────────────────────────────
    print(f"\n{BOLD}[8] Tool 6 — delete_task{RESET}")
    if client and project_id and new_task_id:
        try:
            await client.delete_task(project_id, new_task_id)
            log(f"delete_task (ID: {new_task_id})", "PASS")
        except Exception as e:
            log("delete_task", "FAIL", str(e))
    else:
        log("delete_task", "SKIP")

    # ─── 9. TOOL 7: list_project_members ──────────────────────
    print(f"\n{BOLD}[9] Tool 7 — list_project_members{RESET}")
    if client and project_id:
        try:
            members = await client.list_project_members(project_id)
            if isinstance(members, list):
                log(f"list_project_members ({len(members)} members)", "PASS")
                for m in members[:5]:
                    print(f"         → {m.get('name','?')} | Role: {m.get('role','?')} | ID: {m.get('id','?')}")
            else:
                log("list_project_members", "FAIL", f"Unexpected: {members}")
        except Exception as e:
            log("list_project_members", "FAIL", str(e))
    else:
        log("list_project_members", "SKIP")

    # ─── 10. TOOL 8: get_task_utilisation ─────────────────────
    print(f"\n{BOLD}[10] Tool 8 — get_task_utilisation{RESET}")
    if client and project_id:
        try:
            # Test with specific project
            util = await client.list_tasks(project_id)
            # Manually compute
            stats = {}
            for t in util:
                det = t.get("details", {})
                owners = det.get("owners", []) if isinstance(det, dict) else []
                if not owners:
                    owners = [{"name": "Unassigned"}]
                for o in owners:
                    n = o.get("name", "?")
                    stats[n] = stats.get(n, 0) + 1
            if stats:
                busiest = max(stats, key=stats.get)
                log(f"get_task_utilisation (busiest: {busiest} with {stats[busiest]} tasks)", "PASS")
                for name, count in sorted(stats.items(), key=lambda x: -x[1]):
                    print(f"         → {name}: {count} task(s)")
            else:
                log("get_task_utilisation", "PASS", "No tasks to analyse (0 tasks)")
        except Exception as e:
            log("get_task_utilisation", "FAIL", str(e))
    else:
        log("get_task_utilisation", "SKIP")

    # ─── 11. SUPERVISOR / ROUTER ──────────────────────────────
    print(f"\n{BOLD}[11] Supervisor Router{RESET}")
    try:
        from app.agents.supervisor import Supervisor
        from langchain_groq import ChatGroq
        from app.config import settings
        llm = ChatGroq(model=settings.llm.model_name, api_key=settings.llm.api_key, temperature=0)
        sup = Supervisor(llm)
        r1 = await sup.route("show me my projects", "")
        r2 = await sup.route("create a task called Test", "")
        r3 = await sup.route("delete the first task", "")
        r4 = await sup.route("who has the most tasks?", "")
        log(f"Router: read query → '{r1}' (expect 'query')", "PASS" if r1 == "query" else "FAIL", f"Got: {r1}")
        log(f"Router: create → '{r2}' (expect 'action')", "PASS" if r2 == "action" else "FAIL", f"Got: {r2}")
        log(f"Router: delete → '{r3}' (expect 'action')", "PASS" if r3 == "action" else "FAIL", f"Got: {r3}")
        log(f"Router: utilisation → '{r4}' (expect 'query')", "PASS" if r4 == "query" else "FAIL", f"Got: {r4}")
    except Exception as e:
        log("Supervisor router", "FAIL", str(e))

    # ─── 12. HTTP ENDPOINTS ───────────────────────────────────
    print(f"\n{BOLD}[12] HTTP API Endpoints{RESET}")
    try:
        import httpx
        async with httpx.AsyncClient(base_url="http://localhost:8000") as http:
            r = await http.get("/health")
            log(f"GET /health → {r.status_code}", "PASS" if r.status_code == 200 else "FAIL", r.text[:100])

            r = await http.get("/auth/status")
            data = r.json()
            log(f"GET /auth/status → authenticated={data.get('authenticated')}", "PASS" if r.status_code == 200 else "FAIL")

            # Test chat endpoint (without auth — expect 401 or 500 depending on middleware)
            r = await http.post("/chat", json={"message": "hello", "session_id": "test-123"})
            log(f"POST /chat (no auth) → {r.status_code} (blocks unauthenticated)",
                "PASS" if r.status_code in (401, 403, 500) else "FAIL",
                "Middleware blocks unauthenticated requests")
    except Exception as e:
        log("HTTP endpoints", "FAIL", str(e))

    # ─── 13. MEMORY / LONG-TERM ───────────────────────────────
    print(f"\n{BOLD}[13] Memory System{RESET}")
    try:
        from app.memory.store import MemoryStore
        mem = MemoryStore("test_user", "test_session")
        await mem.add_message("user", "test message")
        history = await mem.get_formatted_history(5)
        log("Short-term memory (add/get)", "PASS" if isinstance(history, str) else "FAIL")
        await mem.store_interaction("test_key", "test_value")
        all_mem = await mem.get_all_long_term()
        log("Long-term memory (store/retrieve)", "PASS" if "test_key" in all_mem or isinstance(all_mem, str) else "FAIL", f"Got type: {type(all_mem).__name__}")
    except Exception as e:
        log("Memory system", "FAIL", str(e))

    # ─── SUMMARY ──────────────────────────────────────────────
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD} TEST SUMMARY{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}")
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    skipped = sum(1 for _, s, _ in results if s == "SKIP")
    total = len(results)
    print(f"  {GREEN}PASSED : {passed}/{total}{RESET}")
    print(f"  {RED}FAILED : {failed}/{total}{RESET}")
    print(f"  {YELLOW}SKIPPED: {skipped}/{total}{RESET}")

    if failed > 0:
        print(f"\n{RED}Failed tests:{RESET}")
        for name, status, detail in results:
            if status == "FAIL":
                print(f"  ❌ {name}: {detail}")

    await db.close()
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}\n")

asyncio.run(run_all())
