# mcpptest

Integration test workspace for [mcpp-plan](../mcpp-plan), an MCP-based task and planning system.

## Contents

- `test_mcpp_plan.py` — Integration tests that exercise mcpp-plan's `execute()` entry point against a real database
- `hello.txt` — Sample fixture file used by tests

## Usage

```bash
python test_mcpp_plan.py
```

Tests use a `test-` prefix for all task names and clean up after themselves.
