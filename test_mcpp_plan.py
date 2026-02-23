#!/usr/bin/env python3
"""
Integration tests for mcpp-plan via the MCP execute() entry point.

Runs against the real plan.db using ../mcpptest as workspace_dir.
All test tasks use a 'test-' prefix and are cleaned up after the run.

Usage:
    python test_mcpp_plan.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# ── Setup: import execute() from mcpp-plan ──
MODULE_DIR = Path(__file__).resolve().parent.parent / "mcpp-plan"
sys.path.insert(0, str(MODULE_DIR.parent))

# We need to import mcpptool directly to get execute()
import importlib.util
spec = importlib.util.spec_from_file_location("mcpptool", MODULE_DIR / "mcpptool.py")
mcpptool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcpptool)

execute = mcpptool.execute

WORKSPACE = str(Path(__file__).resolve().parent)
CONTEXT = {"workspace_dir": WORKSPACE}

# Unique suffix to avoid collisions
_ts = str(int(time.time()))[-6:]
TASK_A = f"test-alpha-{_ts}"
TASK_B = f"test-beta-{_ts}"

passed = 0
failed = 0
cleanup_tasks = []


def call(tool: str, args: dict | None = None) -> dict:
    """Call an MCP tool and return the result."""
    return execute(tool, args or {}, CONTEXT)


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")


def assert_ok(result: dict, label: str) -> dict:
    """Check result is successful, report and return it."""
    ok = result.get("success", False)
    if not ok:
        report(label, False, result.get("error", "unknown error"))
    else:
        report(label, True)
    return result


def cleanup():
    """Remove test tasks created during the run."""
    for name in cleanup_tasks:
        try:
            # Switch away first if needed
            call("plan_task_switch", {"name": TASK_B if name == TASK_A else TASK_A})
        except Exception:
            pass
    # We can't delete tasks, but we can complete them to keep things tidy
    for name in cleanup_tasks:
        try:
            call("plan_task_complete", {"name": name})
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════

def test_project():
    """Test project show/set."""
    print("\n== Project ==")
    r = call("plan_project_show")
    assert_ok(r, "project show")

    r = call("plan_project_set", {"name": "mcpptest", "description": "Integration test workspace"})
    assert_ok(r, "project set")
    report("project name", r.get("result", {}).get("project_name") == "mcpptest")


def test_user():
    """Test user show."""
    print("\n== User ==")
    r = call("plan_user_show")
    assert_ok(r, "user show")
    report("user has name", bool(r.get("result", {}).get("name")))


def test_config():
    """Test config show."""
    print("\n== Config ==")
    r = call("plan_config_show")
    assert_ok(r, "config show")
    cfg = r.get("result", {})
    report("has workflow section", "workflow" in cfg)
    report("has require_goal_and_plan", "require_goal_and_plan" in cfg.get("workflow", {}))
    report("has allow_reopen_completed", "allow_reopen_completed" in cfg.get("workflow", {}))


def test_create_task():
    """Test task creation with steps."""
    print("\n== Create tasks ==")

    r = call("plan_task_new", {
        "name": TASK_A,
        "title": "Alpha test task",
        "steps": ["Step A1", "Step A2", "Step A3"],
    })
    assert_ok(r, f"create {TASK_A}")
    cleanup_tasks.append(TASK_A)
    data = r.get("result", {})
    report("task name correct", data.get("context_name") == TASK_A)
    report("has 3 steps", len(data.get("tasks", [])) == 3)

    r = call("plan_task_new", {
        "name": TASK_B,
        "title": "Beta test task",
        "steps": ["Step B1", "Step B2"],
    })
    assert_ok(r, f"create {TASK_B}")
    cleanup_tasks.append(TASK_B)


def test_task_show_and_status():
    """Test task show and status."""
    print("\n== Task show/status ==")

    r = call("plan_task_show")
    assert_ok(r, "task show (active)")
    report("shows active task", r.get("result", {}).get("context_name") == TASK_B)

    r = call("plan_task_show", {"name": TASK_A})
    assert_ok(r, "task show (by name)")
    report("shows correct task", r.get("result", {}).get("context_name") == TASK_A)

    r = call("plan_task_status")
    assert_ok(r, "task status")


def test_task_switch():
    """Test task switching."""
    print("\n== Task switch ==")

    r = call("plan_task_switch", {"name": TASK_A})
    assert_ok(r, f"switch to {TASK_A}")
    report("switched correctly", r.get("result", {}).get("context_name") == TASK_A)


def test_task_list():
    """Test task listing."""
    print("\n== Task list ==")

    r = call("plan_task_list")
    assert_ok(r, "task list (active only)")
    tasks = r.get("result", {}).get("tasks", [])
    test_tasks = [t for t in tasks if t["name"].startswith("test-")]
    report("test tasks visible", len(test_tasks) >= 2)

    r = call("plan_task_list", {"show_all": True})
    assert_ok(r, "task list (all users)")


def test_notes_goal_plan():
    """Test adding goal and plan notes."""
    print("\n== Notes (goal/plan) ==")

    # Switch to task A for note tests
    call("plan_task_switch", {"name": TASK_A})

    r = call("plan_task_notes", {"text": "Test the full MCP tool layer", "kind": "goal"})
    assert_ok(r, "add goal note")
    notes = r.get("result", {}).get("notes", [])
    goal_notes = [n for n in notes if n.get("kind") == "goal"]
    report("goal note saved", len(goal_notes) >= 1)

    r = call("plan_task_notes", {"text": "Call execute() for each tool and verify", "kind": "plan"})
    assert_ok(r, "add plan note")
    notes = r.get("result", {}).get("notes", [])
    plan_notes = [n for n in notes if n.get("kind") == "plan"]
    report("plan note saved", len(plan_notes) >= 1)

    r = call("plan_task_notes", {"text": "This is a regular note"})
    assert_ok(r, "add regular note")

    # Read filtered
    r = call("plan_task_notes", {"kind": "goal"})
    assert_ok(r, "read goal notes")
    notes = r.get("result", {}).get("notes", [])
    report("filter returns only goals", all(n.get("kind") == "goal" for n in notes))

    # Verify task show includes goal/plan
    r = call("plan_task_show", {"name": TASK_A})
    data = r.get("result", {})
    report("task show has goal", data.get("goal") is not None)
    report("task show has plan", data.get("plan") is not None)


def test_step_operations():
    """Test step switch, show, done, new, delete, notes."""
    print("\n== Step operations ==")

    # We're on TASK_A with 3 steps
    r = call("plan_step_list")
    assert_ok(r, "step list")
    steps = r.get("result", {}).get("tasks", [])
    active_steps = [s for s in steps if not s.get("is_deleted")]
    report("3 steps listed", len(active_steps) == 3)

    r = call("plan_step_show")
    assert_ok(r, "step show (active)")

    r = call("plan_step_show", {"number": 2})
    assert_ok(r, "step show (by number)")
    report("step 2 title", "A2" in r.get("result", {}).get("title", ""))

    r = call("plan_step_switch", {"number": 1})
    assert_ok(r, "step switch to 1")

    r = call("plan_step_done", {"number": 1})
    assert_ok(r, "step done 1")
    report("step 1 complete", r.get("result", {}).get("status") == "complete")

    r = call("plan_step_switch", {"number": 2})
    assert_ok(r, "step switch to 2")

    r = call("plan_step_done", {"number": 2})
    assert_ok(r, "step done 2")

    # Add a new step
    r = call("plan_step_new", {"title": "Step A4 (added)"})
    assert_ok(r, "step new")
    report("new step created", "A4" in r.get("result", {}).get("title", ""))

    # Step notes
    r = call("plan_step_notes", {"text": "Step-level note", "number": 3})
    assert_ok(r, "step note add")

    r = call("plan_step_notes", {"number": 3})
    assert_ok(r, "step note read")
    notes = r.get("result", {}).get("notes", [])
    report("step note exists", len(notes) >= 1)

    # Delete a step
    r = call("plan_step_delete", {"number": 4})
    assert_ok(r, "step delete")


def test_step_reorder():
    """Test step reorder via MCP tool."""
    print("\n== Step reorder ==")

    # We're on TASK_A with 3 steps (A1[done], A2[done], A3) after test_step_operations
    r = call("plan_step_list")
    steps = r.get("result", {}).get("tasks", [])
    active_steps = [s for s in steps if not s.get("is_deleted")]
    report("3 steps before reorder", len(active_steps) == 3)

    # Reorder: move step 3 to position 1
    r = call("plan_step_reorder", {"order": [3, 1, 2]})
    assert_ok(r, "reorder [3,1,2]")
    steps = r.get("result", {}).get("tasks", [])
    active_steps = [s for s in steps if not s.get("is_deleted")]
    report("still 3 steps after reorder", len(active_steps) == 3)
    if len(active_steps) >= 3:
        report("step 1 is now A3", "A3" in active_steps[0].get("title", ""))
        report("step 2 is now A1", "A1" in active_steps[1].get("title", ""))
        report("step 3 is now A2", "A2" in active_steps[2].get("title", ""))

    # Verify mapping is returned
    mapping = r.get("result", {}).get("mapping", [])
    report("mapping returned", len(mapping) == 3)

    # Restore original order
    r = call("plan_step_reorder", {"order": [2, 3, 1]})
    assert_ok(r, "restore order")

    # Validation: partial list should fail
    r = call("plan_step_reorder", {"order": [1, 2]})
    report("partial list rejected", not r.get("success"))

    # Validation: unknown step should fail
    r = call("plan_step_reorder", {"order": [1, 2, 99]})
    report("unknown step rejected", not r.get("success"))


def test_task_complete_and_reopen():
    """Test completing a task and reopening via config."""
    print("\n== Task complete and reopen ==")

    # Switch to TASK_B so we can complete TASK_A
    call("plan_task_switch", {"name": TASK_B})

    r = call("plan_task_complete", {"name": TASK_A})
    assert_ok(r, f"complete {TASK_A}")

    # Verify it shows as completed
    r = call("plan_task_list", {"show_completed": True})
    tasks = r.get("result", {}).get("tasks", [])
    alpha = [t for t in tasks if t.get("name") == TASK_A]
    report("task shows as completed", alpha and alpha[0].get("status") == "completed")

    # Try to switch to completed task (should fail by default)
    r = call("plan_task_switch", {"name": TASK_A})
    if not r.get("success"):
        report("switch to completed denied", "allow_reopen_completed" in r.get("error", ""))
    else:
        report("switch to completed denied", False, "expected failure but succeeded")

    # Enable allow_reopen_completed
    r = call("plan_config_set", {"section": "workflow", "key": "allow_reopen_completed", "value": True})
    assert_ok(r, "enable allow_reopen_completed")

    # Now switch should succeed
    r = call("plan_task_switch", {"name": TASK_A})
    if r.get("success"):
        report("switch to completed allowed", True)
        report("task reopened", r.get("result", {}).get("context_name") == TASK_A)
    else:
        report("switch to completed allowed", False, r.get("error", ""))

    # Reset config
    call("plan_config_set", {"section": "workflow", "key": "allow_reopen_completed", "value": False})


def test_reports():
    """Test project and task report generation."""
    print("\n== Reports ==")

    # Project report
    r = call("plan_project_report")
    assert_ok(r, "project report")
    result = r.get("result", {})
    report("project report has file", bool(result.get("file")))
    report("project report has content", "# Project Report" in result.get("content", ""))

    # Verify file was written
    filepath = result.get("file", "")
    if filepath:
        from pathlib import Path
        report("project report file exists", Path(filepath).exists())
        # Clean up
        try:
            Path(filepath).unlink()
        except Exception:
            pass

    # Task report (active task)
    r = call("plan_task_report")
    assert_ok(r, "task report (active)")
    result = r.get("result", {})
    report("task report has file", bool(result.get("file")))
    report("task report has content", "# Task Report" in result.get("content", ""))

    filepath = result.get("file", "")
    if filepath:
        from pathlib import Path
        report("task report file exists", Path(filepath).exists())
        try:
            Path(filepath).unlink()
        except Exception:
            pass

    # Task report (by name)
    r = call("plan_task_report", {"name": TASK_A})
    assert_ok(r, f"task report ({TASK_A})")
    result = r.get("result", {})
    report("task report contains task name", TASK_A in result.get("content", ""))

    filepath = result.get("file", "")
    if filepath:
        from pathlib import Path
        try:
            Path(filepath).unlink()
        except Exception:
            pass


def test_config_set():
    """Test config set and show round-trip."""
    print("\n== Config set/show ==")

    r = call("plan_config_set", {"section": "workflow", "key": "allow_reopen_completed", "value": True})
    assert_ok(r, "config set")
    cfg = r.get("result", {})
    report("value updated", cfg.get("workflow", {}).get("allow_reopen_completed") is True)

    r = call("plan_config_show")
    assert_ok(r, "config show after set")
    cfg = r.get("result", {})
    report("value persisted", cfg.get("workflow", {}).get("allow_reopen_completed") is True)

    # Reset
    call("plan_config_set", {"section": "workflow", "key": "allow_reopen_completed", "value": False})


def test_notes_set_get_delete():
    """Test the new _set, _get, _delete note tools."""
    print("\n== Notes set/get/delete (task level) ==")

    # Ensure we're on TASK_A
    call("plan_task_switch", {"name": TASK_A})

    # Set goal via new tool (upsert — creates)
    r = call("plan_task_notes_set", {"text": "Goal via set tool", "kind": "goal"})
    assert_ok(r, "task notes set (goal create)")
    notes = r.get("result", {}).get("notes", [])
    goal_notes = [n for n in notes if n.get("kind") == "goal"]
    report("goal created", len(goal_notes) >= 1)

    # Set goal again (upsert — updates, should NOT create second)
    r = call("plan_task_notes_set", {"text": "Updated goal via set", "kind": "goal"})
    assert_ok(r, "task notes set (goal upsert)")
    notes = r.get("result", {}).get("notes", [])
    goal_notes = [n for n in notes if n.get("kind") == "goal"]
    report("still one goal", len(goal_notes) == 1, f"count={len(goal_notes)}")
    report("goal text updated", goal_notes[0].get("note") == "Updated goal via set")

    # Get notes
    r = call("plan_task_notes_get")
    assert_ok(r, "task notes get (all)")
    notes = r.get("result", {}).get("notes", [])
    report("notes returned", len(notes) >= 1)
    report("notes have ids", all("id" in n for n in notes))

    # Get filtered by kind
    r = call("plan_task_notes_get", {"kind": "goal"})
    assert_ok(r, "task notes get (goal only)")
    notes = r.get("result", {}).get("notes", [])
    report("only goals returned", all(n.get("kind") == "goal" for n in notes))

    # Set a regular note, then update by ID
    r = call("plan_task_notes_set", {"text": "Original note"})
    assert_ok(r, "task notes set (note create)")
    notes = r.get("result", {}).get("notes", [])
    regular = [n for n in notes if n.get("kind") == "note" and n.get("note") == "Original note"]
    report("regular note created", len(regular) >= 1)
    note_id = regular[0]["id"] if regular else None

    if note_id:
        r = call("plan_task_notes_set", {"text": "Edited note", "id": note_id})
        assert_ok(r, "task notes set (update by id)")
        notes = r.get("result", {}).get("notes", [])
        updated = [n for n in notes if n.get("id") == note_id]
        report("note updated in place", len(updated) == 1 and updated[0].get("note") == "Edited note")

        # Delete the note
        r = call("plan_task_notes_delete", {"id": note_id})
        assert_ok(r, "task notes delete")
        notes = r.get("result", {}).get("notes", [])
        remaining = [n for n in notes if n.get("id") == note_id]
        report("note deleted", len(remaining) == 0)


def test_step_notes_set_get_delete():
    """Test the new _set, _get, _delete step note tools."""
    print("\n== Notes set/get/delete (step level) ==")

    # Use step 3 on TASK_A
    r = call("plan_step_notes_set", {"text": "Step note via set", "number": 3})
    assert_ok(r, "step notes set (create)")
    notes = r.get("result", {}).get("notes", [])
    report("step note created", len(notes) >= 1)
    report("notes have ids", all("id" in n for n in notes))

    # Get step notes
    r = call("plan_step_notes_get", {"number": 3})
    assert_ok(r, "step notes get")
    notes = r.get("result", {}).get("notes", [])
    report("step notes returned", len(notes) >= 1)

    # Update by ID
    note_id = notes[0]["id"] if notes else None
    if note_id:
        r = call("plan_step_notes_set", {"text": "Edited step note", "id": note_id, "number": 3})
        assert_ok(r, "step notes set (update by id)")
        notes = r.get("result", {}).get("notes", [])
        updated = [n for n in notes if n.get("id") == note_id]
        report("step note updated", len(updated) == 1 and updated[0].get("note") == "Edited step note")

        # Delete
        r = call("plan_step_notes_delete", {"id": note_id, "number": 3})
        assert_ok(r, "step notes delete")
        notes = r.get("result", {}).get("notes", [])
        remaining = [n for n in notes if n.get("id") == note_id]
        report("step note deleted", len(remaining) == 0)


def test_show_switch_include_notes():
    """Test that show/switch responses include notes with IDs."""
    print("\n== Show/switch include notes ==")

    # Add a note so there's something to see
    call("plan_task_notes_set", {"text": "Visible in show", "kind": "goal"})

    # Task show should include notes
    r = call("plan_task_show", {"name": TASK_A})
    assert_ok(r, "task show")
    data = r.get("result", {})
    report("task show has notes", "notes" in data)
    if "notes" in data:
        report("notes have ids", all("id" in n for n in data["notes"]))

    # Step show should include notes
    call("plan_step_notes_set", {"text": "Visible in step show", "number": 3})
    r = call("plan_step_show", {"number": 3})
    assert_ok(r, "step show")
    data = r.get("result", {})
    report("step show has notes", "notes" in data)
    if "notes" in data:
        report("step notes have ids", all("id" in n for n in data["notes"]))


# ═══════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════

def main():
    global passed, failed

    print(f"mcpp-plan MCP integration tests")
    print(f"Module: {MODULE_DIR}")
    print(f"Workspace: {WORKSPACE}")

    try:
        test_project()
        test_user()
        test_config()
        test_create_task()
        test_task_show_and_status()
        test_task_switch()
        test_task_list()
        test_notes_goal_plan()
        test_step_operations()
        test_step_reorder()
        test_task_complete_and_reopen()
        test_reports()
        test_config_set()
        test_notes_set_get_delete()
        test_step_notes_set_get_delete()
        test_show_switch_include_notes()
    finally:
        print("\n== Cleanup ==")
        cleanup()
        print(f"  Completed test tasks: {cleanup_tasks}")

    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
