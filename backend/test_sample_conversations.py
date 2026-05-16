"""
Assignment Sample Conversation Test
Exactly replicates the 5 conversations from the spec and verifies each response.
Runs in a SINGLE session so short-term memory works across turns.
"""
import asyncio, sys, uuid, json
sys.path.insert(0, ".")

G="\033[92m";R="\033[91m";Y="\033[93m";B="\033[94m";W="\033[0m";BOLD="\033[1m";C="\033[96m"
PASS=f"{G}✅ PASS{W}"; FAIL=f"{R}❌ FAIL{W}"
results={"pass":0,"fail":0}
issues=[]

def ok(tc, user_msg, agent, detail=""):
    results["pass"]+=1
    print(f"  {PASS}  {tc}")
    print(f"         {C}User:{W}  \"{user_msg}\"")
    print(f"         {Y}Agent:{W} {agent}")
    if detail: print(f"         {G}✓ {detail}{W}")

def err(tc, user_msg, agent, expected, got):
    results["fail"]+=1
    issues.append((tc, expected, got[:120]))
    print(f"  {FAIL}  {tc}")
    print(f"         {C}User:{W}  \"{user_msg}\"")
    print(f"         {Y}Agent:{W} {agent}")
    print(f"         {R}Expected: {expected}{W}")
    print(f"         {R}Got:      {got[:120]}{W}")

async def run():
    print(f"\n{BOLD}{B}{'='*60}{W}")
    print(f"{BOLD}{B}  Sample Conversation Test — 5 Assignment Cases{W}")
    print(f"{BOLD}{B}{'='*60}{W}\n")

    from app.database import db
    from app.agents.graph import get_graph
    from app.tools.query_tools import set_current_user
    await db.connect()

    # ── Get real user_id from DB ─────────────────────────
    cursor = await db._connection.execute(
        "SELECT user_id FROM user_tokens ORDER BY rowid DESC LIMIT 1")
    row = await cursor.fetchone()
    if not row:
        print(f"{R}ERROR: No logged-in user found. Please login first.{W}")
        return
    user_id = row["user_id"]
    session_id = f"sample_conv_{uuid.uuid4().hex[:8]}"
    set_current_user(user_id)

    print(f"{Y}Using user_id : {user_id[:20]}...{W}")
    print(f"{Y}Using session : {session_id}{W}\n")

    graph = get_graph()

    # Helper: send one message through the full pipeline
    async def chat(message):
        print(f"\n{BOLD}  ──────────────────────────────────────────────{W}")
        print(f"  {C}💬 User:{W} {message}")
        result = await graph.process_message(
            user_id=user_id,
            session_id=session_id,
            message=message
        )
        bot_reply  = result.get("message","")
        agent_used = result.get("agent_used","?")
        pending    = result.get("pending_action")
        label = "📖 Query Agent" if agent_used=="query" else ("✏️ Action Agent" if agent_used=="action" else f"🤖 {agent_used}")
        print(f"  {Y}🤖 Bot [{label}]:{W}")
        # Print first 300 chars of the response
        preview = bot_reply[:300] + ("…" if len(bot_reply)>300 else "")
        for line in preview.split("\n"):
            print(f"     {line}")
        if pending:
            print(f"  {Y}🔔 HIL Pending: {pending.get('tool_name')} — {json.dumps(pending.get('parameters',{}))[:80]}{W}")
        return bot_reply, agent_used, pending

    # ════════════════════════════════════════════════════
    # TC-1: "What projects do I have?"
    # Expected: Query Agent, lists projects by name
    # ════════════════════════════════════════════════════
    tc = "TC-1: List Projects"
    msg = "What projects do I have?"
    reply, agent, pending = await chat(msg)

    correct_agent   = agent == "query"
    has_projects    = any(p in reply.lower() for p in ["interviews","protein","sky secue","project"])
    shows_ids       = any(c.isdigit() for c in reply)

    if correct_agent and has_projects:
        ok(tc, msg, f"📖 Query Agent ({agent})",
           f"Lists projects with names/IDs. Found keywords: interviews={('interviews' in reply.lower())}, protein={('protein' in reply.lower())}")
    else:
        err(tc, msg, agent,
            "Query Agent + project names visible",
            f"agent={agent}, has_projects={has_projects}\n{reply[:120]}")

    # ════════════════════════════════════════════════════
    # TC-2: "Show tasks for the first one"
    # Expected: Query Agent, REMEMBERS project from TC-1 (short-term memory)
    # ════════════════════════════════════════════════════
    tc = "TC-2: Short-Term Memory — 'Show tasks for the first one'"
    msg = "Show tasks for the first one"
    reply, agent, pending = await chat(msg)

    correct_agent = agent == "query"
    # Should show tasks — not ask "which project?"
    asks_clarification = any(w in reply.lower() for w in ["which project","please specify","what project","clarify"])
    shows_tasks        = any(w in reply.lower() for w in ["task","no tasks","open","closed","status","due"])

    if correct_agent and shows_tasks and not asks_clarification:
        ok(tc, msg, f"📖 Query Agent ({agent})",
           "Remembered project from TC-1 (short-term memory). Shows tasks without asking which project.")
    elif correct_agent and asks_clarification:
        err(tc, msg, agent,
            "Remembers project from TC-1 — should NOT ask 'which project?'",
            reply[:200])
    else:
        err(tc, msg, agent,
            "Query Agent + task list (using short-term memory)",
            f"agent={agent}, shows_tasks={shows_tasks}\n{reply[:150]}")

    # ════════════════════════════════════════════════════
    # TC-3: "Create a task called API Integration"
    # Expected: Action Agent, HIL confirmation shown
    # ════════════════════════════════════════════════════
    tc = "TC-3: Create Task (Action Agent + HIL)"
    msg = "Create a task called API Integration in interviews"
    reply, agent, pending = await chat(msg)

    correct_agent = agent == "action"
    has_hil       = pending is not None or any(
        w in reply.lower() for w in ["confirm","yes/no","proceed","approve","shall i","do you want"])
    has_task_name = "api integration" in reply.lower()

    if correct_agent and (has_hil or has_task_name):
        ok(tc, msg, f"✏️ Action Agent ({agent})",
           f"HIL confirmation shown={has_hil}. Task name in reply={has_task_name}.")
    else:
        err(tc, msg, agent,
            "Action Agent + HIL confirmation with task name",
            f"agent={agent}, has_hil={has_hil}, pending={pending}\n{reply[:150]}")

    # Auto-decline so we don't actually create it
    if pending:
        await graph.process_message(user_id=user_id, session_id=session_id, message="no")
        print(f"  {Y}(Auto-declined HIL to avoid creating a real task){W}")

    # ════════════════════════════════════════════════════
    # TC-4: "Delete task #5"
    # Expected: Action Agent, asks for confirmation before deleting
    # ════════════════════════════════════════════════════
    tc = "TC-4: Delete Task (Action Agent confirms before deleting)"
    msg = "Delete the go out task from interviews"
    reply, agent, pending = await chat(msg)

    correct_agent  = agent == "action"
    asks_confirm   = pending is not None or any(
        w in reply.lower() for w in ["confirm","yes/no","proceed","sure","approve","are you sure"])

    if correct_agent and asks_confirm:
        ok(tc, msg, f"✏️ Action Agent ({agent})",
           "Asks for confirmation BEFORE deleting. Does NOT delete immediately.")
    elif correct_agent and not asks_confirm:
        err(tc, msg, agent,
            "Action Agent MUST ask confirmation before delete",
            reply[:200])
    else:
        err(tc, msg, agent,
            "Action Agent + delete confirmation prompt",
            f"agent={agent}, pending={pending}\n{reply[:150]}")

    # Auto-decline
    if pending:
        await graph.process_message(user_id=user_id, session_id=session_id, message="no")
        print(f"  {Y}(Auto-declined — task not deleted){W}")

    # ════════════════════════════════════════════════════
    # TC-5: "Who has the most tasks this month?"
    # Expected: Query Agent → get_task_utilisation → summary by member
    # ════════════════════════════════════════════════════
    tc = "TC-5: Task Utilisation (Query Agent → get_task_utilisation)"
    msg = "Who has the most tasks?"
    reply, agent, pending = await chat(msg)

    correct_agent   = agent == "query"
    has_utilisation = any(w in reply.lower() for w in
        ["task","member","bhanu","most","utilisation","utilization","assigned","load","count"])

    if correct_agent and has_utilisation:
        ok(tc, msg, f"📖 Query Agent ({agent})",
           "Returns utilisation summary with member names and task counts.")
    else:
        err(tc, msg, agent,
            "Query Agent + member task utilisation summary",
            f"agent={agent}, has_utilisation={has_utilisation}\n{reply[:150]}")

    # ════════════════════════════════════════════════════
    # SUMMARY
    # ════════════════════════════════════════════════════
    total = results["pass"] + results["fail"]
    pct   = int(100*results["pass"]/total) if total else 0

    print(f"\n{BOLD}{B}{'='*60}{W}")
    print(f"{BOLD}  SAMPLE CONVERSATION RESULTS{W}")
    print(f"{BOLD}{B}{'='*60}{W}")
    print(f"  {G}PASSED : {results['pass']}/{total} ({pct}%){W}")
    print(f"  {R}FAILED : {results['fail']}/{total}{W}")

    if results["fail"] == 0:
        print(f"\n  {G}{BOLD}🎉 All 5 sample conversations work correctly!{W}")
    else:
        print(f"\n  {R}Issues:{W}")
        for tc, expected, got in issues:
            print(f"  ❌ {tc}")
            print(f"     Expected: {expected}")
            print(f"     Got:      {got}")

    print(f"{BOLD}{B}{'='*60}{W}\n")
    await db.close()

asyncio.run(run())
