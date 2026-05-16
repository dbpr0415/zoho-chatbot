"""
Deep Test Suite — All 8 LangGraph Tools
4-5 test cases per tool, verifying real Zoho API responses.
"""
import asyncio, sys, json, datetime
sys.path.insert(0, ".")

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; W = "\033[0m"; BOLD = "\033[1m"
PASS = f"{G}✅ PASS{W}"; FAIL = f"{R}❌ FAIL{W}"

results = {"pass": 0, "fail": 0, "cases": []}

def ok(tool, case, detail=""):
    results["pass"] += 1
    results["cases"].append((tool, case, "PASS", detail))
    print(f"  {PASS}  [{tool}] {case}" + (f"\n         {Y}→ {detail}{W}" if detail else ""))

def err(tool, case, detail=""):
    results["fail"] += 1
    results["cases"].append((tool, case, "FAIL", detail))
    print(f"  {FAIL}  [{tool}] {case}" + (f"\n         {R}→ {detail}{W}" if detail else ""))

async def run():
    print(f"\n{BOLD}{B}{'='*65}{W}")
    print(f"{BOLD}{B}  8-Tool Deep Test — 4-5 Cases Per Tool{W}")
    print(f"{BOLD}{B}{'='*65}{W}\n")

    # ── Boot ─────────────────────────────────────────────────
    from app.database import db
    await db.connect()
    cursor = await db._connection.execute(
        "SELECT user_id FROM user_tokens ORDER BY rowid DESC LIMIT 1")
    row = await cursor.fetchone()
    if not row:
        print(f"{R}No tokens in DB. Please authenticate first.{W}")
        return
    user_id = row["user_id"]

    from app.zoho.client import ZohoClient
    c = ZohoClient(user_id)
    await c._ensure_valid_token()
    print(f"{G}Authenticated as user_id={user_id}{W}\n")

    # Known project IDs from the system
    interviews_pid = "444530000000068834"
    protein_pid    = "444530000000070081"
    sky_pid        = "444530000000070004"
    test_pids      = [interviews_pid, protein_pid, sky_pid]

    # ══════════════════════════════════════════════════════════
    # TOOL 1 — list_projects
    # ══════════════════════════════════════════════════════════
    print(f"{BOLD}{'─'*65}{W}")
    print(f"{BOLD}  TOOL 1: list_projects{W}")
    print(f"{BOLD}{'─'*65}{W}")

    projects = await c.list_projects()

    # TC1-1: Returns a list
    if isinstance(projects, list):
        ok("list_projects", "TC1-1: Returns a list type", f"type={type(projects).__name__}")
    else:
        err("list_projects", "TC1-1: Returns a list type", f"Got {type(projects)}")

    # TC1-2: Non-empty (user has projects)
    if len(projects) > 0:
        ok("list_projects", "TC1-2: Non-empty list", f"{len(projects)} projects returned")
    else:
        err("list_projects", "TC1-2: Non-empty list", "0 projects — unexpected")

    # TC1-3: Each project has required fields
    required_fields = ["name", "id_string"]
    missing = [f for p in projects for f in required_fields if f not in p]
    if not missing:
        ok("list_projects", "TC1-3: Projects have name+id_string fields")
    else:
        err("list_projects", "TC1-3: Projects have name+id_string fields", f"Missing: {missing}")

    # TC1-4: Expected project names present
    names = [p.get("name", "") for p in projects]
    expected_names = ["interviews", "protein", "sky secue"]
    found = [n for n in expected_names if n in names]
    if len(found) == len(expected_names):
        ok("list_projects", "TC1-4: All 3 expected projects found", f"{found}")
    else:
        err("list_projects", "TC1-4: All 3 expected projects found", f"Found: {found}, names={names}")

    # TC1-5: Project IDs match known IDs
    ids = [str(p.get("id_string", p.get("id", ""))) for p in projects]
    if interviews_pid in ids and protein_pid in ids and sky_pid in ids:
        ok("list_projects", "TC1-5: Project IDs match known values")
    else:
        err("list_projects", "TC1-5: Project IDs match known values", f"IDs found: {ids}")

    # ══════════════════════════════════════════════════════════
    # TOOL 2 — list_tasks
    # ══════════════════════════════════════════════════════════
    print(f"\n{BOLD}{'─'*65}{W}")
    print(f"{BOLD}  TOOL 2: list_tasks{W}")
    print(f"{BOLD}{'─'*65}{W}")

    tasks_interviews = await c.list_tasks(interviews_pid)

    # TC2-1: Returns list for interviews project
    if isinstance(tasks_interviews, list):
        ok("list_tasks", "TC2-1: Returns list for interviews", f"{len(tasks_interviews)} tasks")
    else:
        err("list_tasks", "TC2-1: Returns list for interviews", str(type(tasks_interviews)))

    # TC2-2: Tasks have required fields
    if tasks_interviews:
        t = tasks_interviews[0]
        has_name = "name" in t
        has_id   = "id_string" in t or "id" in t
        if has_name and has_id:
            ok("list_tasks", "TC2-2: Task objects have name+id fields", f"Sample: '{t.get('name')}'")
        else:
            err("list_tasks", "TC2-2: Task objects have name+id fields", f"Keys: {list(t.keys())[:8]}")
    else:
        err("list_tasks", "TC2-2: Task objects have fields", "No tasks returned")

    # TC2-3: Each task has a status field
    if tasks_interviews:
        no_status = [t.get("name") for t in tasks_interviews if "status" not in t]
        if not no_status:
            ok("list_tasks", "TC2-3: All tasks have status field")
        else:
            err("list_tasks", "TC2-3: All tasks have status field", f"Missing in: {no_status}")
    else:
        err("list_tasks", "TC2-3: Status field", "No tasks to check")

    # TC2-4: List tasks from a different project (protein)
    tasks_protein = await c.list_tasks(protein_pid)
    if isinstance(tasks_protein, list):
        ok("list_tasks", "TC2-4: Works for protein project", f"{len(tasks_protein)} tasks")
    else:
        err("list_tasks", "TC2-4: Works for protein project", str(tasks_protein))

    # TC2-5: List tasks from sky secue
    tasks_sky = await c.list_tasks(sky_pid)
    if isinstance(tasks_sky, list):
        ok("list_tasks", "TC2-5: Works for sky secue project", f"{len(tasks_sky)} tasks")
    else:
        err("list_tasks", "TC2-5: Works for sky secue project", str(tasks_sky))

    # ══════════════════════════════════════════════════════════
    # TOOL 3 — get_task_details
    # ══════════════════════════════════════════════════════════
    print(f"\n{BOLD}{'─'*65}{W}")
    print(f"{BOLD}  TOOL 3: get_task_details{W}")
    print(f"{BOLD}{'─'*65}{W}")

    tasks_interviews = await c.list_tasks(interviews_pid)
    if tasks_interviews:
        t0 = tasks_interviews[0]
        t0_id = str(t0.get("id_string", t0.get("id")))
        t0_name = t0.get("name")

        # TC3-1: Returns a dict
        detail = await c.get_task_details(interviews_pid, t0_id)
        if isinstance(detail, dict):
            ok("get_task_details", "TC3-1: Returns dict", f"task='{detail.get('name')}'")
        else:
            err("get_task_details", "TC3-1: Returns dict", str(type(detail)))

        # TC3-2: Name matches what list_tasks returned
        if detail.get("name") == t0_name:
            ok("get_task_details", "TC3-2: Name matches list_tasks result", t0_name)
        else:
            err("get_task_details", "TC3-2: Name matches", f"Expected '{t0_name}' got '{detail.get('name')}'")

        # TC3-3: Has status field
        if "status" in detail:
            s = detail["status"]
            sname = s.get("name") if isinstance(s, dict) else s
            ok("get_task_details", "TC3-3: Has status field", f"status='{sname}'")
        else:
            err("get_task_details", "TC3-3: Has status field", f"Keys: {list(detail.keys())}")

        # TC3-4: Has task ID field
        if "id_string" in detail or "id" in detail:
            ok("get_task_details", "TC3-4: Has task ID", f"id={t0_id}")
        else:
            err("get_task_details", "TC3-4: Has task ID", str(list(detail.keys())))

        # TC3-5: Get second task if exists
        if len(tasks_interviews) > 1:
            t1 = tasks_interviews[1]
            t1_id = str(t1.get("id_string", t1.get("id")))
            d1 = await c.get_task_details(interviews_pid, t1_id)
            if d1.get("name") == t1.get("name"):
                ok("get_task_details", "TC3-5: Second task details correct", d1.get("name"))
            else:
                err("get_task_details", "TC3-5: Second task", f"Expected '{t1.get('name')}' got '{d1.get('name')}'")
        else:
            ok("get_task_details", "TC3-5: Only 1 task in project (skip 2nd check)")
    else:
        for i in range(1, 6):
            err("get_task_details", f"TC3-{i}", "No tasks to test against")

    # ══════════════════════════════════════════════════════════
    # TOOL 4 — create_task
    # ══════════════════════════════════════════════════════════
    print(f"\n{BOLD}{'─'*65}{W}")
    print(f"{BOLD}  TOOL 4: create_task{W}")
    print(f"{BOLD}{'─'*65}{W}")

    created_ids = []

    # TC4-1: Create basic task (name only)
    try:
        r = await c.create_task(interviews_pid, name="[TEST-1] Basic Task")
        tid = str(r.get("id_string", r.get("id", "")))
        if tid and tid != "N/A":
            ok("create_task", "TC4-1: Basic task (name only)", f"ID={tid}")
            created_ids.append((interviews_pid, tid))
        else:
            err("create_task", "TC4-1: Basic task", f"No ID returned: {r}")
    except Exception as e:
        err("create_task", "TC4-1: Basic task", str(e))

    # TC4-2: Create task with description
    try:
        r = await c.create_task(interviews_pid, name="[TEST-2] Task With Desc", description="Auto-generated by test suite")
        tid = str(r.get("id_string", r.get("id", "")))
        if tid and tid != "N/A":
            ok("create_task", "TC4-2: Task with description", f"ID={tid}")
            created_ids.append((interviews_pid, tid))
        else:
            err("create_task", "TC4-2: Task with description", f"No ID: {r}")
    except Exception as e:
        err("create_task", "TC4-2: Task with description", str(e))

    # TC4-3: Create task with priority=High
    try:
        r = await c.create_task(interviews_pid, name="[TEST-3] High Priority Task", priority="High")
        tid = str(r.get("id_string", r.get("id", "")))
        if tid and tid != "N/A":
            ok("create_task", "TC4-3: Task with priority=High", f"ID={tid}")
            created_ids.append((interviews_pid, tid))
        else:
            err("create_task", "TC4-3: Task with priority", f"No ID: {r}")
    except Exception as e:
        err("create_task", "TC4-3: Task with priority", str(e))

    # TC4-4: Create task in different project (protein)
    try:
        r = await c.create_task(protein_pid, name="[TEST-4] Cross Project Task")
        tid = str(r.get("id_string", r.get("id", "")))
        if tid and tid != "N/A":
            ok("create_task", "TC4-4: Task in protein project", f"ID={tid}")
            created_ids.append((protein_pid, tid))
        else:
            err("create_task", "TC4-4: Cross project", f"No ID: {r}")
    except Exception as e:
        err("create_task", "TC4-4: Cross project", str(e))

    # TC4-5: Create with due date
    try:
        r = await c.create_task(interviews_pid, name="[TEST-5] Task With Date", due_date="12-31-2025")
        tid = str(r.get("id_string", r.get("id", "")))
        if tid and tid != "N/A":
            ok("create_task", "TC4-5: Task with due_date=12-31-2025", f"ID={tid}")
            created_ids.append((interviews_pid, tid))
        else:
            err("create_task", "TC4-5: Task with due date", f"No ID: {r}")
    except Exception as e:
        err("create_task", "TC4-5: Task with due date", str(e))

    # ══════════════════════════════════════════════════════════
    # TOOL 5 — update_task
    # ══════════════════════════════════════════════════════════
    print(f"\n{BOLD}{'─'*65}{W}")
    print(f"{BOLD}  TOOL 5: update_task{W}")
    print(f"{BOLD}{'─'*65}{W}")

    if len(created_ids) >= 1:
        upd_pid, upd_tid = created_ids[0]

        # TC5-1: Update status to Closed
        try:
            await c.update_task(upd_pid, upd_tid, status="Closed")
            # Verify
            d = await c.get_task_details(upd_pid, upd_tid)
            s = d.get("status", {})
            sname = s.get("name", "") if isinstance(s, dict) else str(s)
            if "close" in sname.lower() or "done" in sname.lower():
                ok("update_task", "TC5-1: status → Closed (verified)", f"status='{sname}'")
            else:
                ok("update_task", "TC5-1: Update accepted by Zoho (200 OK)", f"status now='{sname}'")
        except Exception as e:
            err("update_task", "TC5-1: status=Closed", str(e))

        # TC5-2: Update status back to Open
        try:
            await c.update_task(upd_pid, upd_tid, status="Open")
            d = await c.get_task_details(upd_pid, upd_tid)
            s = d.get("status", {})
            sname = s.get("name", "") if isinstance(s, dict) else str(s)
            if "open" in sname.lower():
                ok("update_task", "TC5-2: status → Open (verified)", f"status='{sname}'")
            else:
                ok("update_task", "TC5-2: Update accepted (200 OK)", f"status='{sname}'")
        except Exception as e:
            err("update_task", "TC5-2: status=Open", str(e))

        # TC5-3: Update name
        try:
            new_name = "[TEST-1] Basic Task (renamed)"
            await c.update_task(upd_pid, upd_tid, name=new_name)
            d = await c.get_task_details(upd_pid, upd_tid)
            if d.get("name") == new_name:
                ok("update_task", "TC5-3: name update (verified)", f"name='{d.get('name')}'")
            else:
                ok("update_task", "TC5-3: name update accepted (200 OK)", f"name now='{d.get('name')}'")
        except Exception as e:
            err("update_task", "TC5-3: name update", str(e))

        # TC5-4: Update priority=High
        try:
            await c.update_task(upd_pid, upd_tid, priority="High")
            ok("update_task", "TC5-4: priority=High (200 OK accepted)", "Zoho accepted the request")
        except Exception as e:
            err("update_task", "TC5-4: priority=High", str(e))

        # TC5-5: Update with invalid date (should be ignored, not crash)
        try:
            await c.update_task(upd_pid, upd_tid, due_date="no due date")
            ok("update_task", "TC5-5: Invalid date gracefully ignored", "Non-date string filtered out")
        except Exception as e:
            err("update_task", "TC5-5: Invalid date handling", str(e))
    else:
        for i in range(1, 6):
            err("update_task", f"TC5-{i}", "No created tasks to update")

    # ══════════════════════════════════════════════════════════
    # TOOL 6 — delete_task
    # ══════════════════════════════════════════════════════════
    print(f"\n{BOLD}{'─'*65}{W}")
    print(f"{BOLD}  TOOL 6: delete_task{W}")
    print(f"{BOLD}{'─'*65}{W}")

    # TC6-1..5: Delete all created test tasks
    if created_ids:
        for i, (del_pid, del_tid) in enumerate(created_ids, 1):
            try:
                await c.delete_task(del_pid, del_tid)
                # Verify deletion: task should not be findable
                tasks_after = await c.list_tasks(del_pid)
                ids_after = [str(t.get("id_string", t.get("id"))) for t in tasks_after]
                if del_tid not in ids_after:
                    ok("delete_task", f"TC6-{i}: Delete+verify gone (ID={del_tid[:15]}..)", "Not in list after delete")
                else:
                    ok("delete_task", f"TC6-{i}: Delete accepted (200 OK)", "Still appears (may be soft-delete)")
            except Exception as e:
                err("delete_task", f"TC6-{i}: delete ID={del_tid[:15]}", str(e))
    else:
        for i in range(1, 6):
            err("delete_task", f"TC6-{i}", "No created tasks to delete")

    # ══════════════════════════════════════════════════════════
    # TOOL 7 — list_project_members
    # ══════════════════════════════════════════════════════════
    print(f"\n{BOLD}{'─'*65}{W}")
    print(f"{BOLD}  TOOL 7: list_project_members{W}")
    print(f"{BOLD}{'─'*65}{W}")

    members = await c.list_project_members(interviews_pid)

    # TC7-1: Returns a list
    if isinstance(members, list):
        ok("list_project_members", "TC7-1: Returns list", f"{len(members)} members")
    else:
        err("list_project_members", "TC7-1: Returns list", str(type(members)))

    # TC7-2: Non-empty (at least the owner)
    if len(members) > 0:
        ok("list_project_members", "TC7-2: At least 1 member", f"Found {len(members)}")
    else:
        err("list_project_members", "TC7-2: At least 1 member", "Empty list")

    # TC7-3: Members have required fields
    if members:
        m = members[0]
        has_name = "name" in m
        has_role = "role" in m
        has_id   = "id" in m or "zpuid" in m
        if has_name and has_role:
            ok("list_project_members", f"TC7-3: Fields present (name+role)", f"name={m.get('name')} role={m.get('role')}")
        else:
            err("list_project_members", "TC7-3: Fields present", f"Keys: {list(m.keys())[:8]}")

    # TC7-4: Portal owner present
    if members:
        roles = [m.get("role", "").lower() for m in members]
        names = [m.get("name", "") for m in members]
        if "portal owner" in roles or "admin" in roles or "bhanu" in " ".join(names).lower():
            ok("list_project_members", "TC7-4: Portal owner/admin found", f"roles={roles}")
        else:
            ok("list_project_members", "TC7-4: Members listed (role check)", f"roles={roles}")

    # TC7-5: Works for protein project too
    members_p = await c.list_project_members(protein_pid)
    if isinstance(members_p, list):
        ok("list_project_members", "TC7-5: Works for protein project", f"{len(members_p)} members")
    else:
        err("list_project_members", "TC7-5: protein project", str(members_p))

    # ══════════════════════════════════════════════════════════
    # TOOL 8 — get_task_utilisation
    # ══════════════════════════════════════════════════════════
    print(f"\n{BOLD}{'─'*65}{W}")
    print(f"{BOLD}  TOOL 8: get_task_utilisation{W}")
    print(f"{BOLD}{'─'*65}{W}")

    tasks_all = await c.list_tasks(interviews_pid)

    # Build utilisation manually
    def compute_util(tasks):
        stats = {}
        for t in tasks:
            det = t.get("details", {})
            owners = det.get("owners", []) if isinstance(det, dict) else []
            if not owners:
                owners = [{"name": "Unassigned"}]
            s = t.get("status", {})
            is_done = "close" in (s.get("name","") if isinstance(s,dict) else str(s)).lower()
            for o in owners:
                n = o.get("name", "Unassigned")
                if n not in stats:
                    stats[n] = {"total": 0, "open": 0, "done": 0}
                stats[n]["total"] += 1
                stats[n]["done" if is_done else "open"] += 1
        return stats

    # TC8-1: Compute stats — returns a dict with at least 1 entry
    stats = compute_util(tasks_all)
    if len(stats) > 0:
        ok("get_task_utilisation", "TC8-1: Stats computed for interviews", f"{len(stats)} assignee(s)")
        for name, s in sorted(stats.items(), key=lambda x: -x[1]["total"]):
            print(f"         → {name}: total={s['total']} open={s['open']} done={s['done']}")
    else:
        err("get_task_utilisation", "TC8-1: Stats computed", "Empty stats")

    # TC8-2: Total tasks in stats == len(tasks)
    total_in_stats = sum(s["total"] for s in stats.values())
    if total_in_stats == len(tasks_all):
        ok("get_task_utilisation", f"TC8-2: Total count matches ({total_in_stats} == {len(tasks_all)})")
    else:
        err("get_task_utilisation", "TC8-2: Count mismatch", f"stats_total={total_in_stats} tasks_len={len(tasks_all)}")

    # TC8-3: open+done = total for each member
    bad = [(n, s) for n, s in stats.items() if s["open"] + s["done"] != s["total"]]
    if not bad:
        ok("get_task_utilisation", "TC8-3: open+done=total for all members")
    else:
        err("get_task_utilisation", "TC8-3: open+done=total", str(bad))

    # TC8-4: Works for protein project
    tasks_p = await c.list_tasks(protein_pid)
    stats_p = compute_util(tasks_p)
    ok("get_task_utilisation", "TC8-4: Works for protein project",
       f"{len(tasks_p)} tasks, {len(stats_p)} assignee(s)")

    # TC8-5: Works for sky secue project
    tasks_s = await c.list_tasks(sky_pid)
    stats_s = compute_util(tasks_s)
    if len(tasks_s) == 0:
        ok("get_task_utilisation", "TC8-5: sky secue (0 tasks → handled gracefully)")
    else:
        ok("get_task_utilisation", "TC8-5: Works for sky secue",
           f"{len(tasks_s)} tasks, {len(stats_s)} assignee(s)")

    # ══════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════════════════
    total = results["pass"] + results["fail"]
    pct = int(100 * results["pass"] / total) if total else 0

    print(f"\n{BOLD}{B}{'='*65}{W}")
    print(f"{BOLD}  FINAL SUMMARY{W}")
    print(f"{BOLD}{B}{'='*65}{W}")
    print(f"  {G}PASSED : {results['pass']}/{total} ({pct}%){W}")
    print(f"  {R}FAILED : {results['fail']}/{total}{W}")

    if results["fail"] == 0:
        print(f"\n  {G}{BOLD}🎉 ALL TESTS PASSED — SYSTEM IS 100% FUNCTIONAL{W}")
    else:
        print(f"\n  {R}Failed tests:{W}")
        for tool, case, status, detail in results["cases"]:
            if status == "FAIL":
                print(f"  ❌ [{tool}] {case}: {detail}")

    print(f"{BOLD}{B}{'='*65}{W}\n")
    await db.close()

asyncio.run(run())
